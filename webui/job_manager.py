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
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO

from webui.storage import atomic_write_json


ALLOWED_EXTENSIONS = {".txt", ".epub", ".docx", ".pdf"}
PROVIDERS = {"chatgpt_web", "gemini_web", "gemini_api_tts"}
MODES = {"plain", "material_only", "study"}
TERMINAL_STATES = {"completed", "failed", "cancelled"}
ACTIVE_STATES = {"queued", "running", "cancelling"}
MODEL_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")
PROGRESS_RE = re.compile(r"(?<!\d)(\d{1,6})\s*/\s*(\d{1,6})(?!\d)")


class JobValidationError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_file_stem(name: str) -> str:
    stem = unicodedata.normalize("NFKC", Path(name).stem).strip()
    stem = re.sub(r"[^\w\- ]+", "", stem, flags=re.UNICODE)
    stem = re.sub(r"[\s_-]+", "_", stem).strip("_")
    return stem[:80] or "audiobook"


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


class JobManager:
    def __init__(
        self,
        data_root: Path,
        *,
        runner_script: Path | None = None,
        python_executable: str | None = None,
        start_worker: bool = True,
    ) -> None:
        self.data_root = Path(data_root).expanduser().resolve()
        self.jobs_root = self.data_root / "jobs"
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self.runner_script = (runner_script or Path(__file__).resolve().parents[1] / "audiobook_maker.py").resolve()
        self.python_executable = python_executable or sys.executable
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.RLock()
        self._processes: dict[str, subprocess.Popen[bytes]] = {}
        self._closed = False
        self._recover_jobs()
        self._worker: threading.Thread | None = None
        if start_worker:
            self._worker = threading.Thread(target=self._worker_loop, name="audiobook-job-worker", daemon=True)
            self._worker.start()

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
                if job.get("status") in ACTIVE_STATES:
                    job["status"] = "queued"
                    job["pid"] = None
                    job["message"] = "Resumed after web server restart"
                    self._write_job(job)
                    self._queue.put(str(job["id"]))
            except (OSError, ValueError, KeyError, TypeError):
                continue

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
        if suffix not in ALLOWED_EXTENSIONS:
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
            job["message"] = "Starting audiobook engine"
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
                        stdout=log_handle,
                        stderr=subprocess.STDOUT,
                        env=environment,
                        **popen_kwargs,
                    )
                    self._processes[job_id] = process
                    job["pid"] = process.pid
                    job["message"] = "Audiobook generation in progress"
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

        with self._lock:
            job = self._read_job(job_id)
            job["return_code"] = return_code
            job["pid"] = None
            job["finished_at"] = utc_now()
            output_path = job_dir / str(job["output_relpath"])
            if job.get("status") in {"cancelling", "cancelled"}:
                job["status"] = "cancelled"
                job["message"] = "Job cancelled"
            elif return_code == 0 and output_path.is_file() and output_path.stat().st_size > 0:
                job["status"] = "completed"
                job["message"] = "Audiobook ready"
            else:
                job["status"] = "failed"
                job["message"] = "Audiobook engine exited with an error"
            self._write_job(job)

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

    def stop_job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._read_job(job_id)
            if job.get("status") in TERMINAL_STATES:
                return self.public_job(job_id)
            process = self._processes.get(job_id)
            if process is None:
                job["status"] = "cancelled"
                job["finished_at"] = utc_now()
                job["message"] = "Job cancelled before start"
                self._write_job(job)
                return self.public_job(job_id)
            job["status"] = "cancelling"
            job["message"] = "Stopping audiobook engine"
            self._write_job(job)
        self._terminate_process(process)
        return self.public_job(job_id)

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
        job_dir = self._job_dir(job_id)
        output_path = job_dir / str(job["output_relpath"])
        return {
            "id": job_id,
            "status": status,
            "created_at": job.get("created_at"),
            "updated_at": job.get("updated_at"),
            "started_at": job.get("started_at"),
            "finished_at": job.get("finished_at"),
            "input_name": job.get("input_name"),
            "output_name": job.get("output_name"),
            "message": job.get("message"),
            "return_code": job.get("return_code"),
            "settings": job.get("settings") if isinstance(job.get("settings"), dict) else {},
            "heartbeat": {
                key: heartbeat.get(key)
                for key in ("iso_time", "stage", "label", "section_prefix", "attempt", "detail")
                if heartbeat.get(key) is not None
            },
            "progress": progress,
            "progress_text": progress_text,
            "download_ready": status == "completed" and output_path.is_file(),
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
        path = self._job_dir(job_id) / str(job["output_relpath"])
        if job.get("status") != "completed" or not path.is_file():
            raise FileNotFoundError(job_id)
        return path

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
            processes = list(self._processes.values())
        for process in processes:
            self._terminate_process(process, grace_seconds=1)
        if self._worker is not None:
            self._queue.put(None)
            self._worker.join(timeout=2)
