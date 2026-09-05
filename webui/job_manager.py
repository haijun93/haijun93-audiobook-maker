from __future__ import annotations

import json
import os
import queue
import re
import signal
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO

from webui.book_organizer import organize_from_output_dir, get_existing_korean_books
from webui.storage import atomic_write_json
from webui.workflow_diagnostics import diagnose_failure, load_workflow_diagnostics


AUDIO_EXTENSIONS = {".txt", ".epub", ".docx", ".pdf"}
TRANSLATION_EXTENSIONS = {".epub", ".pdf", ".mobi"}
PROVIDERS = {"chatgpt_web", "gemini_web", "gemini_api_tts", "edge_tts"}
MODES = {"plain", "material_only", "study"}
WORKFLOW_TYPES = {"translation", "batch_translation", "batch_audio"}
TERMINAL_STATES = {"completed", "failed", "cancelled"}
ACTIVE_STATES = {"queued", "running", "recovering", "cancelling"}
HEARTBEAT_STALE_SECONDS = 30 * 60
MODEL_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")
PROGRESS_RE = re.compile(r"(?<!\d)(\d{1,6})\s*/\s*(\d{1,6})(?!\d)")


class JobValidationError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def job_process_is_alive(pid: int, job_dir: Path) -> bool:
    if not process_is_alive(pid):
        return False
    if os.name == "nt":
        return True
    try:
        result = subprocess.run(
            ["ps", "-ww", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return True
    if result.returncode != 0:
        return False
    return str(job_dir) in result.stdout


def safe_file_stem(name: str) -> str:
    stem = unicodedata.normalize("NFKC", Path(name).stem).strip()
    stem = re.sub(r"[^\w\- ]+", "", stem, flags=re.UNICODE)
    stem = re.sub(r"[\s_-]+", "_", stem).strip("_")
    return stem[:80] or "audiobook"


def safe_book_stem(name: str) -> str:
    stem = unicodedata.normalize("NFKC", Path(name).stem).strip()
    stem = re.sub(r"^\[(?:e|s|k|k-e)\]\s*", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"[^\w\- ]+", "", stem, flags=re.UNICODE)
    stem = re.sub(r"[\s_-]+", "_", stem).strip("_")
    return stem[:80] or "book"


def validate_settings(settings: dict[str, Any]) -> dict[str, Any]:
    provider = str(settings.get("provider") or "").strip()
    mode = str(settings.get("mode") or "").strip()
    if provider not in PROVIDERS:
        raise JobValidationError("Unsupported provider")
    if mode not in MODES:
        raise JobValidationError("Unsupported audiobook mode")

    voice = str(settings.get("voice") or "").strip()
    if not voice or len(voice) > 80 or not re.fullmatch(r"[A-Za-z0-9._-]+", voice):
        raise JobValidationError("Invalid voice")

    try:
        max_chars = int(settings.get("max_chars") or 0)
        bitrate = int(settings.get("bitrate") or 96)
        max_attempts = int(settings.get("max_attempts") or 3)
    except (TypeError, ValueError) as exc:
        raise JobValidationError("Numeric settings are invalid") from exc
    if max_chars and not 200 <= max_chars <= 20_000:
        raise JobValidationError("Chunk size must be between 200 and 20000")
    if not 32 <= bitrate <= 320:
        raise JobValidationError("Bitrate must be between 32 and 320")
    if not 1 <= max_attempts <= 20:
        raise JobValidationError("Retry count must be between 1 and 20")

    model = str(settings.get("model") or "gemini-2.5-flash-preview-tts").strip()
    if not MODEL_RE.fullmatch(model):
        raise JobValidationError("Invalid model name")

    return {
        "provider": provider,
        "mode": mode,
        "voice": voice,
        "max_chars": max_chars,
        "bitrate": bitrate,
        "max_attempts": max_attempts,
        "model": model,
        "visible": bool(settings.get("visible")),
    }


def validate_translation_settings(settings: dict[str, Any]) -> dict[str, Any]:
    provider = str(settings.get("translation_provider") or "gemini").strip()
    output = str(settings.get("translation_output") or "both").strip()
    if provider not in {"gemini", "chatgpt"}:
        raise JobValidationError("Unsupported translation provider")
    if output not in {"both", "korean", "bilingual"}:
        raise JobValidationError("Unsupported translation output")
    try:
        max_chars = int(settings.get("max_chars") or 6000)
        max_attempts = int(settings.get("max_attempts") or 5)
        chunks_per_conversation = int(settings.get("chunks_per_conversation") or 10)
        request_timeout = int(settings.get("request_timeout") or 1200)
        inter_request_delay = float(settings.get("inter_request_delay") or 4.0)
    except (TypeError, ValueError) as exc:
        raise JobValidationError("Translation settings are invalid") from exc
    if not 2000 <= max_chars <= 20_000:
        raise JobValidationError("Translation chunk size must be between 2000 and 20000")
    if not 1 <= max_attempts <= 20:
        raise JobValidationError("Retry count must be between 1 and 20")
    if not 1 <= chunks_per_conversation <= 50:
        raise JobValidationError("Chunks per conversation must be between 1 and 50")
    if not 60 <= request_timeout <= 7200:
        raise JobValidationError("Request timeout must be between 60 and 7200 seconds")
    if not 0 <= inter_request_delay <= 120:
        raise JobValidationError("Request delay must be between 0 and 120 seconds")
    return {
        "translation_provider": provider,
        "translation_output": output,
        "max_chars": max_chars,
        "max_attempts": max_attempts,
        "chunks_per_conversation": chunks_per_conversation,
        "request_timeout": request_timeout,
        "inter_request_delay": inter_request_delay,
        "visible": bool(settings.get("visible")),
        "overwrite": bool(settings.get("overwrite")),
        "recursive": bool(settings.get("recursive")),
        "priority_substrings": str(settings.get("priority_substrings") or "").strip(),
        "disable_web_fallback": bool(settings.get("disable_web_fallback")),
        "reverse": bool(settings.get("reverse")),
    }


def scan_folder_sources(source_dir: str | Path, *, operation: str, recursive: bool = False) -> dict[str, Any]:
    if not str(source_dir).strip():
        raise JobValidationError("Enter a source folder path")
    source = Path(source_dir).expanduser().resolve()
    if not source.is_dir():
        raise JobValidationError("Source folder does not exist")
    if operation not in {"batch_translation", "batch_audio"}:
        raise JobValidationError("Unsupported folder operation")
    extensions = TRANSLATION_EXTENSIONS if operation == "batch_translation" else AUDIO_EXTENSIONS | {".mobi"}
    iterator = source.rglob("*") if recursive else source.iterdir()
    files = [
        path
        for path in iterator
        if path.is_file()
        and path.suffix.lower() in extensions
        and not path.name.lower().startswith(("[k]", "[k-e]"))
    ]
    files.sort(key=lambda path: path.name.casefold())
    counts: dict[str, int] = {}
    for path in files:
        suffix = path.suffix.lower().lstrip(".")
        counts[suffix] = counts.get(suffix, 0) + 1
    return {
        "folder_name": source.name or str(source),
        "total": len(files),
        "counts": counts,
        "sample": [path.name for path in files[:8]],
        "truncated": len(files) > 1000,
    }


class JobManager:
    def __init__(
        self,
        data_root: Path,
        *,
        runner_script: Path | None = None,
        workflow_runner_script: Path | None = None,
        python_executable: str | None = None,
        start_worker: bool = True,
        korean_root: Path | None = None,
        bilingual_root: Path | None = None,
        finished_root: Path | None = None,
        english_root: Path | None = None,
        study_root: Path | None = None,
        english_study_root: Path | None = None,
    ) -> None:
        self.data_root = Path(data_root).expanduser().resolve()
        self.jobs_root = self.data_root / "jobs"
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self.runner_script = (runner_script or Path(__file__).resolve().parents[1] / "audiobook_maker.py").resolve()
        self.workflow_runner_script = (
            workflow_runner_script or Path(__file__).resolve().parent / "workflow_runner.py"
        ).resolve()
        self.python_executable = python_executable or sys.executable
        # 실제 서재 위치. 테스트에서는 반드시 tmp_path 하위 값으로 주입해서 실사용자의
        # ~/Desktop/소설2 를 건드리지 않도록 한다.
        self.korean_root = Path(korean_root or "~/Desktop/소설2/[k]").expanduser().resolve()
        self.bilingual_root = Path(bilingual_root or "~/Desktop/소설2/[k-e]").expanduser().resolve()
        self.finished_root = Path(finished_root or "~/Desktop/소설2/finished").expanduser().resolve()
        self.english_root = Path(english_root or "~/Desktop/소설2/[e]").expanduser().resolve()
        self.study_root = Path(study_root or "~/Desktop/소설2/[study]").expanduser().resolve()
        self.english_study_root = Path(english_study_root or "~/Desktop/소설2/[e-s]").expanduser().resolve()
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.RLock()
        self._processes: dict[str, subprocess.Popen[bytes]] = {}
        self._recovered_processes: dict[str, tuple[int, bool]] = {}
        self._recovery_monitors: dict[str, threading.Thread] = {}
        self._shutdown_event = threading.Event()
        self._watchdog: threading.Thread | None = None
        self._closed = False
        self._recover_jobs()
        self._worker: threading.Thread | None = None
        if start_worker:
            self._worker = threading.Thread(target=self._worker_loop, name="audiobook-job-worker", daemon=True)
            self._worker.start()
            self._start_recovery_monitors()
            self._watchdog = threading.Thread(
                target=self._watchdog_loop,
                name="audiobook-job-watchdog",
                daemon=True,
            )
            self._watchdog.start()

    def _job_dir(self, job_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", job_id):
            raise KeyError(job_id)
        return self.jobs_root / job_id

    def _metadata_path(self, job_id: str) -> Path:
        return self._job_dir(job_id) / "job.json"

    def _read_job(self, job_id: str) -> dict[str, Any]:
        path = self._metadata_path(job_id)
        if not path.is_file():
            raise KeyError(job_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_job(self, job: dict[str, Any]) -> None:
        job["updated_at"] = utc_now()
        atomic_write_json(self._metadata_path(str(job["id"])), job)

    def _recover_jobs(self) -> None:
        for metadata_path in sorted(self.jobs_root.glob("*/job.json")):
            try:
                job = json.loads(metadata_path.read_text(encoding="utf-8"))
                status = str(job.get("status") or "")
                if status not in ACTIVE_STATES:
                    continue
                job_id = str(job["id"])
                pid = int(job.get("pid") or 0)
                process_alive = status != "queued" and job_process_is_alive(pid, metadata_path.parent)
                if process_alive:
                    resume_cancellation = status == "cancelling"
                    job["status"] = "cancelling" if resume_cancellation else "recovering"
                    job["message"] = (
                        "Resuming cancellation after web server restart"
                        if resume_cancellation
                        else "Monitoring job after web server restart"
                    )
                    self._recovered_processes[job_id] = (pid, resume_cancellation)
                else:
                    job["status"] = "queued"
                    job["pid"] = None
                    job["message"] = "Resuming from checkpoints after web server restart"
                    if status != "queued":
                        job["restart_recovery_attempts"] = int(job.get("restart_recovery_attempts") or 0) + 1
                    self._queue.put(job_id)
                self._write_job(job)
            except (OSError, ValueError, KeyError, TypeError):
                continue

    def _start_recovery_monitors(self) -> None:
        for job_id, (pid, resume_cancellation) in list(self._recovered_processes.items()):
            monitor = threading.Thread(
                target=self._monitor_recovered_process,
                args=(job_id, pid, resume_cancellation),
                name=f"audiobook-recovery-{job_id[:8]}",
                daemon=True,
            )
            self._recovery_monitors[job_id] = monitor
            monitor.start()

    def create_job(
        self,
        *,
        source_name: str,
        source_stream: BinaryIO,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            if self._closed:
                raise JobValidationError("The job manager is shutting down")
        normalized = validate_settings(settings)
        original_name = Path(source_name).name
        suffix = Path(original_name).suffix.lower()
        if suffix not in AUDIO_EXTENSIONS:
            raise JobValidationError("Only TXT, EPUB, DOCX, and PDF files are supported")

        job_id = uuid.uuid4().hex
        job_dir = self._job_dir(job_id)
        input_dir = job_dir / "input"
        output_dir = job_dir / "output"
        work_dir = job_dir / "work"
        try:
            for directory in (input_dir, output_dir, work_dir):
                directory.mkdir(parents=True, exist_ok=False)

            safe_name = safe_file_stem(original_name) + suffix
            input_path = input_dir / safe_name
            with input_path.open("xb") as handle:
                while chunk := source_stream.read(1024 * 1024):
                    handle.write(chunk)
            if input_path.stat().st_size <= 0:
                raise JobValidationError("Input file is empty")
        except Exception:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise

        output_name = safe_file_stem(original_name) + "_audiobook.m4a"
        job: dict[str, Any] = {
            "id": job_id,
            "job_type": "audio",
            "status": "queued",
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "started_at": None,
            "finished_at": None,
            "pid": None,
            "return_code": None,
            "message": "Waiting to start",
            "input_name": original_name[:240],
            "input_relpath": str(input_path.relative_to(job_dir)),
            "output_name": output_name,
            "output_relpath": str((output_dir / output_name).relative_to(job_dir)),
            "work_relpath": str(work_dir.relative_to(job_dir)),
            "heartbeat_relpath": "heartbeat.json",
            "artifact_manifest_relpath": "artifacts.json",
            "artifact_root": str(output_dir.resolve()),
            "log_relpath": "job.log",
            "settings": normalized,
        }
        with self._lock:
            if self._closed:
                shutil.rmtree(job_dir, ignore_errors=True)
                raise JobValidationError("The job manager is shutting down")
            self._write_job(job)
            self._queue.put(job_id)
        return self.public_job(job_id)

    def create_translation_job(
        self,
        *,
        source_name: str,
        source_stream: BinaryIO,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = validate_translation_settings(settings)
        original_name = Path(source_name).name
        suffix = Path(original_name).suffix.lower()
        if suffix not in TRANSLATION_EXTENSIONS:
            raise JobValidationError("Only EPUB, PDF, and MOBI files can be translated")

        job_id = uuid.uuid4().hex
        job_dir = self._job_dir(job_id)
        input_dir = job_dir / "input"
        output_dir = job_dir / "output"
        work_dir = job_dir / "work"
        try:
            for directory in (input_dir, output_dir, work_dir):
                directory.mkdir(parents=True, exist_ok=False)
            book_stem = safe_book_stem(original_name)
            input_path = input_dir / (book_stem + suffix)
            with input_path.open("xb") as handle:
                while chunk := source_stream.read(1024 * 1024):
                    handle.write(chunk)
            if input_path.stat().st_size <= 0:
                raise JobValidationError("Input file is empty")
        except Exception:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise

        job: dict[str, Any] = {
            "id": job_id,
            "job_type": "translation",
            "status": "queued",
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "started_at": None,
            "finished_at": None,
            "pid": None,
            "return_code": None,
            "message": "Waiting to translate",
            "input_name": original_name[:240],
            "input_relpath": str(input_path.relative_to(job_dir)),
            "output_name": f"[k-e] {book_stem.replace('_', ' ')}.epub",
            "work_relpath": str(work_dir.relative_to(job_dir)),
            "heartbeat_relpath": "heartbeat.json",
            "artifact_manifest_relpath": "artifacts.json",
            "artifact_root": str(output_dir.resolve()),
            "log_relpath": "job.log",
            "settings": normalized,
        }
        with self._lock:
            if self._closed:
                shutil.rmtree(job_dir, ignore_errors=True)
                raise JobValidationError("The job manager is shutting down")
            self._write_job(job)
            self._queue.put(job_id)
        return self.public_job(job_id)

    def create_folder_job(
        self,
        *,
        operation: str,
        source_dir: str,
        output_dir: str | None,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        if operation not in {"batch_translation", "batch_audio"}:
            raise JobValidationError("Unsupported folder operation")
        if not str(source_dir).strip():
            raise JobValidationError("Enter a source folder path")
        source = Path(source_dir).expanduser().resolve()
        if not source.is_dir():
            raise JobValidationError("Source folder does not exist")
        if operation == "batch_translation":
            normalized = validate_translation_settings(settings)
            default_output = source
        else:
            normalized = validate_settings(settings)
            normalized.update(
                {
                    "recursive": bool(settings.get("recursive")),
                    "overwrite": bool(settings.get("overwrite")),
                }
            )
            default_output = source / "audiobooks"
        summary = scan_folder_sources(source, operation=operation, recursive=bool(normalized.get("recursive")))

        # 배치 번역 작업일 때 이미 번역된 파일들을 제외
        if operation == "batch_translation":
            korean_root = Path("/Users/hyeokjunkong/Desktop/소설2/[k]").expanduser().resolve()
            existing_books = get_existing_korean_books(korean_root)

            # 이미 번역된 파일들을 샘플에서 제외
            if existing_books and summary["sample"]:
                summary["sample"] = [f for f in summary["sample"] if f not in existing_books]

        if summary["total"] <= 0:
            raise JobValidationError("No supported source files were found in the selected folder")
        output = Path(output_dir).expanduser().resolve() if str(output_dir or "").strip() else default_output
        try:
            output.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise JobValidationError(f"Output folder cannot be created: {exc}") from exc

        job_id = uuid.uuid4().hex
        job_dir = self._job_dir(job_id)
        work_dir = job_dir / "work"
        work_dir.mkdir(parents=True, exist_ok=False)
        job: dict[str, Any] = {
            "id": job_id,
            "job_type": operation,
            "status": "queued",
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "started_at": None,
            "finished_at": None,
            "pid": None,
            "return_code": None,
            "message": "Waiting for folder batch",
            "input_name": source.name[:240] or str(source),
            "source_dir": str(source),
            "output_name": output.name,
            "work_relpath": str(work_dir.relative_to(job_dir)),
            "heartbeat_relpath": "heartbeat.json",
            "batch_status_relpath": "batch_status.json",
            "artifact_manifest_relpath": "artifacts.json",
            "artifact_root": str(output),
            "log_relpath": "job.log",
            "settings": normalized,
        }
        with self._lock:
            if self._closed:
                shutil.rmtree(job_dir, ignore_errors=True)
                raise JobValidationError("The job manager is shutting down")
            self._write_job(job)
            self._queue.put(job_id)
        return self.public_job(job_id)

    def build_command(self, job: dict[str, Any]) -> list[str]:
        job_type = str(job.get("job_type") or "audio")
        if job_type in WORKFLOW_TYPES:
            return self._build_workflow_command(job)
        job_dir = self._job_dir(str(job["id"]))
        settings = validate_settings(dict(job["settings"]))
        command = [
            self.python_executable,
            str(self.runner_script),
            "--input-file",
            str(job_dir / str(job["input_relpath"])),
            "--output-file",
            str(job_dir / str(job["output_relpath"])),
            "--work-dir",
            str(job_dir / str(job["work_relpath"])),
            "--heartbeat-file",
            str(job_dir / str(job["heartbeat_relpath"])),
            "--provider",
            settings["provider"],
            "--audiobook-mode",
            settings["mode"],
            "--voice",
            settings["voice"],
            "--audio-bitrate-kbps",
            str(settings["bitrate"]),
        ]
        if settings["max_chars"]:
            command.extend(["--max-chars-per-chunk", str(settings["max_chars"])])
        if settings["provider"] == "chatgpt_web":
            command.extend(["--chatgpt-web-max-attempts", str(settings["max_attempts"])])
            if settings["visible"]:
                command.append("--chatgpt-web-visible")
        elif settings["provider"] == "gemini_web":
            command.extend(["--gemini-web-max-attempts", str(settings["max_attempts"])])
            if settings["visible"]:
                command.append("--gemini-web-visible")
        elif settings["provider"] == "edge_tts":
            command.extend(["--edge-tts-max-attempts", str(settings["max_attempts"])])
        else:
            command.extend(
                [
                    "--gemini-api-tts-max-attempts",
                    str(settings["max_attempts"]),
                    "--gemini-api-tts-model",
                    settings["model"],
                ]
            )
        return command

    def _build_workflow_command(self, job: dict[str, Any]) -> list[str]:
        job_dir = self._job_dir(str(job["id"]))
        job_type = str(job.get("job_type") or "")
        settings = dict(job.get("settings") or {})
        command = [
            self.python_executable,
            str(self.workflow_runner_script),
            "--task",
            job_type,
            "--output-dir",
            str(job["artifact_root"]),
            "--work-dir",
            str(job_dir / str(job["work_relpath"])),
            "--heartbeat-file",
            str(job_dir / str(job["heartbeat_relpath"])),
            "--artifact-manifest-file",
            str(job_dir / str(job["artifact_manifest_relpath"])),
            "--max-chars",
            str(settings.get("max_chars") or 6000),
            "--max-attempts",
            str(settings.get("max_attempts") or 5),
        ]
        if job.get("batch_status_relpath"):
            command.extend(["--batch-status-file", str(job_dir / str(job["batch_status_relpath"]))])
        if job_type == "translation":
            command.extend(["--input-file", str(job_dir / str(job["input_relpath"]))])
        else:
            command.extend(["--source-dir", str(job["source_dir"])])
        if job_type in {"translation", "batch_translation"}:
            command.extend(
                [
                    "--translation-provider",
                    str(settings["translation_provider"]),
                    "--translation-output",
                    str(settings["translation_output"]),
                    "--chunks-per-conversation",
                    str(settings["chunks_per_conversation"]),
                    "--inter-request-delay",
                    str(settings["inter_request_delay"]),
                    "--request-timeout",
                    str(settings["request_timeout"]),
                ]
            )
        else:
            command.extend(
                [
                    "--audio-provider",
                    str(settings["provider"]),
                    "--audio-mode",
                    str(settings["mode"]),
                    "--voice",
                    str(settings["voice"]),
                    "--model",
                    str(settings["model"]),
                    "--bitrate",
                    str(settings["bitrate"]),
                ]
            )
        if settings.get("visible"):
            command.append("--visible")
        if settings.get("recursive"):
            command.append("--recursive")
        if settings.get("overwrite"):
            command.append("--overwrite")
        if settings.get("priority_substrings"):
            command.extend(["--priority-substrings", str(settings["priority_substrings"])])
        if settings.get("disable_web_fallback"):
            command.append("--disable-overnight-web-fallback")
        if settings.get("reverse"):
            command.append("--reverse")
        return command

    def _worker_loop(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                if job_id is None:
                    return
                with self._lock:
                    if self._closed:
                        continue
                try:
                    self._run_job(job_id)
                except Exception as exc:
                    self._mark_unhandled_failure(job_id, exc)
            finally:
                self._queue.task_done()

    def _watchdog_loop(self) -> None:
        while not self._shutdown_event.wait(5):
            try:
                self._watchdog_once()
            except Exception as error:
                print(f"Warning: job watchdog check failed: {error}", file=sys.stderr)

    def _watchdog_once(self) -> None:
        stale_processes: list[subprocess.Popen[bytes]] = []
        with self._lock:
            if self._closed:
                return
            for job_id, process in list(self._processes.items()):
                if process.poll() is not None:
                    continue
                try:
                    job = self._read_job(job_id)
                except KeyError:
                    continue
                if job.get("status") != "running":
                    continue
                heartbeat = self._heartbeat(job)
                age = self._heartbeat_age_seconds(job, heartbeat)
                if age is None or age < HEARTBEAT_STALE_SECONDS:
                    continue

                restarts = int(job.get("watchdog_restarts") or 0)
                should_restart = restarts < 1
                diagnosis = diagnose_failure("stale heartbeat", explicit_kind="heartbeat_stale")
                job["status"] = "cancelling"
                job["watchdog_action"] = "restart" if should_restart else "fail"
                job["watchdog_restarts"] = restarts + 1 if should_restart else restarts
                job["message"] = (
                    "No progress heartbeat; restarting once from checkpoints"
                    if should_restart
                    else "No progress heartbeat after automatic recovery"
                )
                job["diagnosis"] = diagnosis.to_dict()
                job["recovery"] = {
                    "automatic_retry": should_restart,
                    "attempt": restarts + 1,
                    "attempt_limit": 1,
                    "retry_after_sec": 0,
                    "safe_to_resume": diagnosis.safe_to_resume,
                    "action": (
                        "Terminate the unresponsive process and resume once from checkpoints."
                        if should_restart
                        else diagnosis.action
                    ),
                    "circuit_open": not should_restart,
                }
                self._write_job(job)
                self._append_log_note(
                    job_id,
                    f"WATCHDOG_STALE heartbeat_age_sec={age:.1f} action={job['watchdog_action']}",
                )
                stale_processes.append(process)
        for process in stale_processes:
            self._terminate_process(process, grace_seconds=2)

    def _mark_unhandled_failure(self, job_id: str, error: Exception) -> None:
        with self._lock:
            try:
                job = self._read_job(job_id)
            except KeyError:
                return
            job["status"] = "failed"
            job["pid"] = None
            job["return_code"] = -1
            job["finished_at"] = utc_now()
            job["message"] = f"Internal job error: {error}"
            self._write_job(job)

    @staticmethod
    def _completion_message(job_type: str) -> str:
        return {
            "audio": "Audiobook ready",
            "translation": "Korean and bilingual EPUBs ready",
            "batch_translation": "Folder translation complete",
            "batch_audio": "Folder audiobooks complete",
        }.get(job_type, "Job complete")

    def _recovered_completion_detected(self, job: dict[str, Any]) -> bool:
        if not self._artifact_entries(job):
            return False
        heartbeat_stage = str(self._heartbeat(job).get("stage") or "")
        if heartbeat_stage in {"done", "complete"}:
            return True
        diagnostics_status = str(self._workflow_diagnostics(job).get("status") or "")
        if diagnostics_status == "complete":
            return True
        batch_status = self._batch_status(job) or {}
        return str(batch_status.get("status") or "") == "complete"

    def _monitor_recovered_process(self, job_id: str, pid: int, resume_cancellation: bool) -> None:
        try:
            if resume_cancellation:
                self._terminate_pid_group(pid, grace_seconds=8)
            while job_process_is_alive(pid, self._job_dir(job_id)):
                with self._lock:
                    if self._closed:
                        return
                time.sleep(0.5)

            requeue = False
            should_organize = False
            with self._lock:
                if self._closed:
                    return
                try:
                    job = self._read_job(job_id)
                except KeyError:
                    return
                if int(job.get("pid") or 0) != pid or job.get("status") not in ACTIVE_STATES:
                    return
                job_type = str(job.get("job_type") or "audio")
                job["pid"] = None
                job["finished_at"] = utc_now()
                job["recovered_process"] = True
                if job.get("status") == "cancelling":
                    job["status"] = "cancelled"
                    job["message"] = "Job cancelled"
                elif self._recovered_completion_detected(job):
                    job["status"] = "completed"
                    job["message"] = self._completion_message(job_type)
                    should_organize = job_type in {"translation", "batch_translation"}
                elif int(job.get("restart_recovery_attempts") or 0) < 1:
                    job["status"] = "queued"
                    job["finished_at"] = None
                    job["restart_recovery_attempts"] = 1
                    job["message"] = "Recovered process ended without completion; resuming from checkpoints"
                    requeue = True
                else:
                    diagnosis = diagnose_failure(
                        "Recovered process exited without a completion marker",
                        explicit_kind="child_process_failed",
                    )
                    job["status"] = "failed"
                    job["message"] = "Recovered process exited before completion"
                    job["diagnosis"] = diagnosis.to_dict()
                    job["recovery"] = {
                        "automatic_retry": False,
                        "attempt": int(job.get("restart_recovery_attempts") or 1),
                        "attempt_limit": 1,
                        "retry_after_sec": 0,
                        "safe_to_resume": diagnosis.safe_to_resume,
                        "action": diagnosis.action,
                        "circuit_open": True,
                    }
                    job["error_detail"] = self._log_error_detail(job) or diagnosis.root_cause
                self._write_job(job)
            if requeue:
                self._queue.put(job_id)
            elif should_organize:
                self._organize_translation_outputs(job_id)
        finally:
            with self._lock:
                self._recovered_processes.pop(job_id, None)
                self._recovery_monitors.pop(job_id, None)

    def _run_job(self, job_id: str) -> None:
        with self._lock:
            try:
                job = self._read_job(job_id)
            except KeyError:
                return
            if job.get("status") != "queued":
                return
            job["status"] = "running"
            job["started_at"] = utc_now()
            job["message"] = "Starting job engine"
            self._write_job(job)

        job_dir = self._job_dir(job_id)
        log_path = job_dir / str(job["log_relpath"])
        command = self.build_command(job)
        environment = os.environ.copy()
        environment["PYTHONUNBUFFERED"] = "1"
        popen_kwargs: dict[str, Any] = {}
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True

        try:
            with log_path.open("ab", buffering=0) as log_handle:
                with self._lock:
                    job = self._read_job(job_id)
                    if job.get("status") != "running":
                        return
                    process = subprocess.Popen(
                        command,
                        cwd=self.runner_script.parent,
                        stdin=subprocess.DEVNULL,
                        stdout=log_handle,
                        stderr=subprocess.STDOUT,
                        env=environment,
                        **popen_kwargs,
                    )
                    self._processes[job_id] = process
                    job["pid"] = process.pid
                    job["message"] = "Job in progress"
                    self._write_job(job)
                return_code = process.wait()
        except Exception as exc:
            return_code = -1
            with self._lock:
                job = self._read_job(job_id)
                job["message"] = f"Could not start job: {exc}"
        finally:
            with self._lock:
                self._processes.pop(job_id, None)

        requeue = False
        with self._lock:
            job = self._read_job(job_id)
            job["return_code"] = return_code
            job["pid"] = None
            job["finished_at"] = utc_now()
            artifacts = self._artifact_entries(job)
            job_type = str(job.get("job_type") or "audio")
            watchdog_action = str(job.pop("watchdog_action", "") or "")
            if job.get("status") in {"cancelling", "cancelled"}:
                if watchdog_action == "restart":
                    job["status"] = "queued"
                    job["return_code"] = None
                    job["finished_at"] = None
                    job["last_diagnosis"] = job.pop("diagnosis", None)
                    job["last_recovery"] = job.pop("recovery", None)
                    job["message"] = "Resuming from checkpoints after watchdog recovery"
                    requeue = True
                elif watchdog_action == "fail":
                    job["status"] = "failed"
                    job["message"] = "Job stopped: heartbeat_stale"
                    job["error_detail"] = self._log_error_detail(job)
                else:
                    job["status"] = "cancelled"
                    job["message"] = "Job cancelled"
            elif return_code == 0 and artifacts:
                job["status"] = "completed"
                job["message"] = self._completion_message(job_type)
            else:
                job["status"] = "failed"
                workflow_diagnostics = self._workflow_diagnostics(job)
                diagnosis = workflow_diagnostics.get("diagnosis")
                recovery = workflow_diagnostics.get("recovery")
                if isinstance(diagnosis, dict):
                    kind = str(diagnosis.get("kind") or "unknown_error")
                    job["message"] = f"Job stopped: {kind}"
                    job["diagnosis"] = diagnosis
                    job["recovery"] = recovery if isinstance(recovery, dict) else None
                    root_cause = str(diagnosis.get("root_cause") or "").strip()
                    recovery_data = recovery if isinstance(recovery, dict) else {}
                    action = str(recovery_data.get("action") or diagnosis.get("action") or "").strip()
                    diagnostic_detail = "\n".join(part for part in (root_cause, action) if part)
                    log_detail = self._log_error_detail(job)
                    job["error_detail"] = "\n".join(
                        part for part in (diagnostic_detail, log_detail) if part
                    )[:1200]
                else:
                    job["message"] = "Job engine exited with an error"
                    job["error_detail"] = self._log_error_detail(job)

            self._write_job(job)
        if requeue:
            self._queue.put(job_id)
        elif job_type in {"translation", "batch_translation"}:
            self._organize_translation_outputs(job_id)

    def _organize_translation_outputs(self, job_id: str) -> None:
        try:
            with self._lock:
                job = self._read_job(job_id)
            job_type = str(job.get("job_type") or "")
            if job_type == "translation" and job.get("status") == "completed":
                job_dir = self._job_dir(job_id)
                input_relpath = str(job.get("input_relpath") or "")
                if input_relpath:
                    input_path = (job_dir / input_relpath).resolve()
                    if input_path.is_file():
                        self.finished_root.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(input_path), str(self.finished_root / input_path.name))

            artifact_root = str(job.get("artifact_root") or "")
            if artifact_root:
                organize_from_output_dir(
                    Path(artifact_root).expanduser().resolve(),
                    self.korean_root,
                    self.bilingual_root,
                    english_root=self.english_root,
                    study_root=self.study_root,
                    english_study_root=self.english_study_root,
                    mode="copy",
                )
        except Exception as error:
            # 결과 정리 실패가 생성 작업 자체의 완료 상태를 훼손하지 않게 로그로만 남긴다.
            print(f"Warning: Failed to process translation job: {error}", file=sys.stderr)

    def _terminate_process(self, process: subprocess.Popen[bytes], grace_seconds: float = 8.0) -> None:
        if process.poll() is not None:
            return
        try:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=grace_seconds)
            return
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()

    def _terminate_pid_group(self, pid: int, grace_seconds: float = 8.0) -> None:
        if not process_is_alive(pid):
            return
        try:
            if os.name == "nt":
                os.kill(pid, signal.SIGTERM)
            else:
                os.killpg(pid, signal.SIGTERM)
        except OSError:
            return
        deadline = time.monotonic() + grace_seconds
        while process_is_alive(pid) and time.monotonic() < deadline:
            time.sleep(0.1)
        if not process_is_alive(pid):
            return
        try:
            if os.name == "nt":
                os.kill(pid, signal.SIGKILL)
            else:
                os.killpg(pid, signal.SIGKILL)
        except OSError:
            pass

    def stop_job(self, job_id: str, *, reason: str = "unknown caller") -> dict[str, Any]:
        # 원인 불명의 배치 중단(외부 SIGTERM)을 나중에 추적할 수 있도록, 중지 요청이
        # 어디서(reason) 들어왔는지 job.log에 남겨 둔다.
        self._append_log_note(job_id, f"STOP_REQUESTED reason={reason}")
        with self._lock:
            job = self._read_job(job_id)
            if job.get("status") in TERMINAL_STATES:
                return self.public_job(job_id)
            process = self._processes.get(job_id)
            if process is None:
                pid = int(job.get("pid") or 0)
                if not job_process_is_alive(pid, self._job_dir(job_id)):
                    job["status"] = "cancelled"
                    job["pid"] = None
                    job["finished_at"] = utc_now()
                    job["message"] = "Job cancelled before start"
                    self._write_job(job)
                    return self.public_job(job_id)
                job["status"] = "cancelling"
                job["message"] = "Stopping recovered job engine"
                self._write_job(job)
                recovered_pid = pid
            else:
                recovered_pid = None
                job["status"] = "cancelling"
                job["message"] = "Stopping audiobook engine"
                self._write_job(job)
        if process is not None:
            self._terminate_process(process)
        elif recovered_pid is not None:
            self._terminate_pid_group(recovered_pid)
            with self._lock:
                job = self._read_job(job_id)
                if job.get("status") == "cancelling":
                    job["status"] = "cancelled"
                    job["pid"] = None
                    job["finished_at"] = utc_now()
                    job["message"] = "Job cancelled"
                    self._write_job(job)
        return self.public_job(job_id)

    def _append_log_note(self, job_id: str, note: str) -> None:
        try:
            job = self._read_job(job_id)
            log_path = self._job_dir(job_id) / str(job.get("log_relpath") or "job.log")
            with log_path.open("ab", buffering=0) as handle:
                handle.write(f"[{utc_now()}] {note}\n".encode("utf-8"))
        except Exception:
            pass

    def delete_job(self, job_id: str) -> None:
        with self._lock:
            job = self._read_job(job_id)
            if job.get("status") not in TERMINAL_STATES:
                raise JobValidationError("Stop the job before deleting it")
            shutil.rmtree(self._job_dir(job_id))

    def _heartbeat(self, job: dict[str, Any]) -> dict[str, Any]:
        path = self._job_dir(str(job["id"])) / str(job["heartbeat_relpath"])
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _heartbeat_age_seconds(self, job: dict[str, Any], heartbeat: dict[str, Any]) -> float | None:
        timestamp = heartbeat.get("timestamp")
        try:
            observed_at = float(timestamp) if timestamp is not None else None
        except (TypeError, ValueError):
            observed_at = None
        if observed_at is None:
            path = self._job_dir(str(job["id"])) / str(job["heartbeat_relpath"])
            try:
                observed_at = path.stat().st_mtime
            except OSError:
                pass
        started_at = str(job.get("started_at") or "")
        try:
            process_started_at = datetime.fromisoformat(started_at).timestamp()
        except ValueError:
            process_started_at = None
        if process_started_at is not None:
            observed_at = max(observed_at or process_started_at, process_started_at)
        if observed_at is None:
            return None
        return max(0.0, time.time() - observed_at)

    def _workflow_diagnostics(self, job: dict[str, Any]) -> dict[str, Any]:
        job_dir = self._job_dir(str(job["id"]))
        work_dir = job_dir / str(job.get("work_relpath") or "work")
        candidates = [work_dir / "workflow_diagnostics.json"]
        try:
            candidates.extend(work_dir.rglob("workflow_diagnostics.json"))
        except OSError:
            pass
        diagnosed: list[tuple[str, dict[str, Any]]] = []
        completed: list[tuple[str, dict[str, Any]]] = []
        seen: set[Path] = set()
        for path in candidates:
            if path in seen:
                continue
            seen.add(path)
            payload = load_workflow_diagnostics(path)
            if not payload:
                continue
            entry = (str(payload.get("updated_at") or ""), payload)
            if isinstance(payload.get("diagnosis"), dict):
                diagnosed.append(entry)
            else:
                completed.append(entry)
        pool = diagnosed or completed
        return max(pool, key=lambda item: item[0])[1] if pool else {}

    def _log_error_detail(self, job: dict[str, Any], max_bytes: int = 4000) -> str:
        job_dir = self._job_dir(str(job["id"]))
        log_path = job_dir / str(job.get("log_relpath") or "job.log")
        try:
            with log_path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                handle.seek(max(0, size - max_bytes))
                tail = handle.read().decode("utf-8", errors="replace")
        except OSError:
            return ""
        lines = [line.strip() for line in tail.splitlines() if line.strip()]
        if not lines:
            return ""
        error_lines = [line for line in lines if re.search(r"error|failed|traceback|실패|오류", line, re.IGNORECASE)]
        candidates = error_lines[-3:] if error_lines else lines[-3:]
        return "\n".join(candidates)[:800]

    def _batch_status(self, job: dict[str, Any]) -> dict[str, Any] | None:
        relpath = job.get("batch_status_relpath")
        if not relpath:
            return None
        path = self._job_dir(str(job["id"])) / str(relpath)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else None
        except (OSError, ValueError, TypeError):
            return None

    def _artifact_entries(self, job: dict[str, Any]) -> list[dict[str, Any]]:
        job_id = str(job["id"])
        job_dir = self._job_dir(job_id)
        job_type = str(job.get("job_type") or "audio")
        if job_type == "audio" and job.get("output_relpath"):
            path = (job_dir / str(job["output_relpath"])).resolve()
            if path.is_file() and path.stat().st_size > 0:
                return [{"index": 0, "name": path.name, "kind": "audio", "size": path.stat().st_size, "path": path}]
            return []

        root_value = str(job.get("artifact_root") or "").strip()
        manifest_relpath = str(job.get("artifact_manifest_relpath") or "artifacts.json")
        if not root_value:
            return []
        root = Path(root_value).expanduser().resolve()
        manifest_path = job_dir / manifest_relpath
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return []
        try:
            manifest_root = Path(str(payload.get("root") or "")).expanduser().resolve()
        except (OSError, RuntimeError):
            return []
        if manifest_root != root:
            return []
        items = payload.get("artifacts")
        if not isinstance(items, list):
            return []
        allowed_suffixes = {
            "audio": {".m4a", ".mp3", ".wav", ".aiff", ".aif"},
            "bilingual_epub": {".epub"},
            "korean_epub": {".epub"},
        }
        artifacts: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            relative = Path(str(item.get("path") or ""))
            kind = str(item.get("kind") or "")
            if not relative.parts or relative.is_absolute() or ".." in relative.parts:
                continue
            path = (root / relative).resolve()
            try:
                path.relative_to(root)
            except ValueError:
                continue
            if kind not in allowed_suffixes or path.suffix.lower() not in allowed_suffixes[kind]:
                continue
            if not path.is_file() or path.stat().st_size <= 0:
                continue
            artifacts.append(
                {
                    "index": len(artifacts),
                    "name": path.name,
                    "kind": kind,
                    "size": path.stat().st_size,
                    "path": path,
                }
            )
        return artifacts

    def public_job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._read_job(job_id)
        heartbeat = self._heartbeat(job)
        status = str(job.get("status") or "failed")
        progress = 100 if status == "completed" else 0
        progress_text = ""
        searchable = " ".join(str(heartbeat.get(key) or "") for key in ("label", "section_prefix", "detail"))
        match = PROGRESS_RE.search(searchable)
        if match and status != "completed":
            current, total = int(match.group(1)), int(match.group(2))
            if total > 0:
                progress = min(99, max(0, round(current * 100 / total)))
                progress_text = f"{current}/{total}"
        artifacts = self._artifact_entries(job)
        if str(job.get("job_type") or "audio") == "audio" and status != "completed":
            artifacts = []
        batch_status = self._batch_status(job)
        workflow_diagnostics = self._workflow_diagnostics(job)
        heartbeat_age = self._heartbeat_age_seconds(job, heartbeat)
        heartbeat_stale = (
            status in {"running", "recovering", "cancelling"}
            and heartbeat_age is not None
            and heartbeat_age >= HEARTBEAT_STALE_SECONDS
        )
        diagnosis = (
            job.get("diagnosis")
            if isinstance(job.get("diagnosis"), dict)
            else workflow_diagnostics.get("diagnosis")
        )
        recovery = (
            job.get("recovery")
            if isinstance(job.get("recovery"), dict)
            else workflow_diagnostics.get("recovery")
        )
        if heartbeat_stale and not isinstance(diagnosis, dict):
            stale_diagnosis = diagnose_failure("stale heartbeat", explicit_kind="heartbeat_stale")
            diagnosis = stale_diagnosis.to_dict()
            recovery = {
                "automatic_retry": False,
                "retry_after_sec": 0,
                "safe_to_resume": stale_diagnosis.safe_to_resume,
                "action": stale_diagnosis.action,
                "circuit_open": False,
            }
        batch = None
        if batch_status is not None:
            completed = batch_status.get("completed") if isinstance(batch_status.get("completed"), list) else []
            batch = {
                "status": str(batch_status.get("status") or "running"),
                "total": int(batch_status.get("total") or 0),
                "targets": [str(name) for name in (batch_status.get("targets") or [])],
                "current": batch_status.get("current"),
                "current_index": batch_status.get("current_index"),
                "completed": [
                    {
                        "name": str(item.get("name") or ""),
                        "status": str(item.get("status") or "done"),
                        "error": str(item.get("error") or "") or None,
                    }
                    for item in completed
                    if isinstance(item, dict)
                ],
                "diagnosis": batch_status.get("diagnosis")
                if isinstance(batch_status.get("diagnosis"), dict)
                else None,
            }
        return {
            "id": job_id,
            "job_type": str(job.get("job_type") or "audio"),
            "status": status,
            "created_at": job.get("created_at"),
            "updated_at": job.get("updated_at"),
            "started_at": job.get("started_at"),
            "finished_at": job.get("finished_at"),
            "input_name": job.get("input_name"),
            "output_name": job.get("output_name"),
            "message": job.get("message"),
            "error_detail": job.get("error_detail"),
            "diagnosis": diagnosis,
            "recovery": recovery,
            "health": workflow_diagnostics.get("health")
            if isinstance(workflow_diagnostics.get("health"), dict)
            else {},
            "return_code": job.get("return_code"),
            "settings": job.get("settings") if isinstance(job.get("settings"), dict) else {},
            "batch": batch,
            "heartbeat": {
                key: heartbeat.get(key)
                for key in ("iso_time", "stage", "label", "section_prefix", "attempt", "detail")
                if heartbeat.get(key) is not None
            },
            "progress": progress,
            "progress_text": progress_text,
            "heartbeat_age_seconds": round(heartbeat_age, 1) if heartbeat_age is not None else None,
            "heartbeat_stale": heartbeat_stale,
            "download_ready": bool(artifacts),
            "artifacts": [
                {
                    "index": item["index"],
                    "name": item["name"],
                    "kind": item["kind"],
                    "size": item["size"],
                }
                for item in artifacts
            ],
        }

    def list_jobs(self) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        for path in self.jobs_root.glob("*/job.json"):
            try:
                jobs.append(self.public_job(path.parent.name))
            except (KeyError, OSError, ValueError):
                continue
        return sorted(jobs, key=lambda item: str(item.get("created_at") or ""), reverse=True)

    def output_path(self, job_id: str) -> Path:
        job = self._read_job(job_id)
        if str(job.get("job_type") or "audio") == "audio" and job.get("status") != "completed":
            raise FileNotFoundError(job_id)
        artifacts = self._artifact_entries(job)
        if not artifacts:
            raise FileNotFoundError(job_id)
        return Path(artifacts[0]["path"])

    def artifact_path(self, job_id: str, index: int) -> Path:
        job = self._read_job(job_id)
        if str(job.get("job_type") or "audio") == "audio" and job.get("status") != "completed":
            raise FileNotFoundError(f"{job_id}:{index}")
        artifacts = self._artifact_entries(job)
        if index < 0 or index >= len(artifacts):
            raise FileNotFoundError(f"{job_id}:{index}")
        return Path(artifacts[index]["path"])

    def read_log(self, job_id: str, offset: int = 0, max_bytes: int = 128 * 1024) -> dict[str, Any]:
        job = self._read_job(job_id)
        path = self._job_dir(job_id) / str(job["log_relpath"])
        if not path.is_file():
            return {"text": "", "next_offset": 0, "truncated": False}
        size = path.stat().st_size
        requested = max(0, min(offset, size))
        start = max(requested, size - max_bytes) if requested == 0 else requested
        with path.open("rb") as handle:
            handle.seek(start)
            data = handle.read(max_bytes)
        return {
            "text": data.decode("utf-8", "replace"),
            "next_offset": start + len(data),
            "truncated": start > requested,
        }

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._shutdown_event.set()
            processes = list(self._processes.values())
            recovered_pids = [
                self._recovered_processes[job_id][0]
                for job_id in self._recovery_monitors
                if job_id in self._recovered_processes
            ]
            recovery_monitors = list(self._recovery_monitors.values())
        for process in processes:
            self._terminate_process(process, grace_seconds=1)
        for pid in recovered_pids:
            self._terminate_pid_group(pid, grace_seconds=1)
        if self._worker is not None:
            self._queue.put(None)
            self._worker.join(timeout=2)
        if self._watchdog is not None:
            self._watchdog.join(timeout=2)
        for monitor in recovery_monitors:
            monitor.join(timeout=2)
