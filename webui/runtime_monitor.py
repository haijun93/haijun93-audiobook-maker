from __future__ import annotations

import hashlib
import json
import re
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from webui.workflow_diagnostics import diagnose_failure, load_workflow_diagnostics


MONITORED_SCRIPTS = {
    "audiobook_maker.py": "audiobook_generation",
    "backfill_study_notes.py": "study_note_backfill",
    "run_soseol2_chatgpt_k_e_batch.py": "epub_translation_batch",
    "translate_epub_with_chatgpt_web_to_study_epub.py": "epub_translation",
    "workflow_runner.py": "workflow_runner",
    "make_korean_only_epubs.py": "korean_only_epub_generation",
    "make_english_study_epubs.py": "english_study_epub_generation",
    "final_epub_quality_audit.py": "final_quality_audit",
    "final_epub_dialogue_consistency_review.py": "dialogue_consistency_review",
    "final_epub_tone_review.py": "tone_review",
}
ACTIVE_RUNTIME_STATES = {"running", "recovering", "paused", "stalled", "reconnecting"}
PROCESS_MISSING_GRACE_SECONDS = 15
KNOWN_WORKFLOW_RETENTION_SECONDS = 60 * 60
RUNTIME_STALE_SECONDS = 15 * 60
SNAPSHOT_CACHE_SECONDS = 0.75
DEFAULT_SCHEDULER_STATUS_PATH = Path(__file__).resolve().parents[1] / ".work" / "continuous_scheduler" / "status.json"
SCHEDULER_STALE_SECONDS = 15


@dataclass(frozen=True)
class ProcessRecord:
    pid: int
    ppid: int
    elapsed: str
    state: str
    command: str
    script_name: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_process_table(output: str) -> list[ProcessRecord]:
    records: list[ProcessRecord] = []
    for raw_line in output.splitlines():
        parts = raw_line.strip().split(maxsplit=4)
        if len(parts) != 5:
            continue
        pid_text, ppid_text, elapsed, state, command = parts
        try:
            pid = int(pid_text)
            ppid = int(ppid_text)
        except ValueError:
            continue
        script_name = next(
            (
                script
                for script in MONITORED_SCRIPTS
                if re.search(rf"(?:^|\s)(?:[^\s]*/)?{re.escape(script)}(?:\s|$)", command)
            ),
            "",
        )
        if script_name:
            records.append(ProcessRecord(pid, ppid, elapsed, state, command, script_name))
    return records


def command_option(command: str, name: str) -> str | None:
    match = re.search(
        rf"(?:^|\s)--{re.escape(name)}(?:=|\s+)(.*?)(?=\s+--[A-Za-z0-9][A-Za-z0-9-]*(?:=|\s)|$)",
        command,
    )
    return match.group(1).strip() if match else None


def read_process_table() -> str:
    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,etime=,state=,command="],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout if result.returncode == 0 else ""


def read_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_timestamp(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except ValueError:
        return None


def progress_from_label(label: str) -> tuple[int | None, int | None]:
    match = re.search(r"(?<!\d)(\d{1,7})\s*/\s*(\d{1,7})(?!\d)", label)
    return (int(match.group(1)), int(match.group(2))) if match else (None, None)


def workflow_identity(work_dir: Path) -> str:
    digest = hashlib.sha1(str(work_dir).encode("utf-8"), usedforsecurity=False).hexdigest()[:14]
    return f"runtime-{digest}"


def display_title(diagnostics: dict[str, Any], command: str, work_dir: Path) -> str:
    runtime_paths = diagnostics.get("runtime", {}).get("paths", {})
    if isinstance(runtime_paths, dict):
        for key in ("input_epub", "input", "source", "input_file"):
            entry = runtime_paths.get(key)
            if isinstance(entry, dict) and entry.get("path"):
                title = Path(str(entry["path"])).stem
                return re.sub(r"^\[[^]]+\]\s*", "", title).lstrip("#")
    for option in ("input-epub", "input-file", "source-dir"):
        value = command_option(command, option)
        if value:
            return re.sub(r"^\[[^]]+\]\s*", "", Path(value).stem).lstrip("#")
    return work_dir.parent.name or work_dir.name


def progress_velocity(events_path: Path, *, completed: int | None, total: int | None) -> dict[str, Any]:
    if completed is None or total is None or completed >= total:
        return {}
    try:
        with events_path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - 256 * 1024))
            raw = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return {}

    samples: list[tuple[float, int]] = []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(event, dict) or event.get("event") != "progress":
            continue
        event_completed = event.get("completed")
        timestamp = parse_timestamp(event.get("timestamp"))
        if timestamp is None or not isinstance(event_completed, int):
            continue
        if samples and event_completed <= samples[-1][1]:
            continue
        samples.append((timestamp, event_completed))
    if len(samples) < 2:
        return {}
    latest_time, latest_completed = samples[-1]
    recent = [sample for sample in samples if sample[0] >= latest_time - 6 * 60 * 60]
    first_time, first_completed = recent[0]
    elapsed_seconds = latest_time - first_time
    completed_delta = latest_completed - first_completed
    if elapsed_seconds < 5 or completed_delta <= 0:
        return {}
    units_per_hour = completed_delta * 3600 / elapsed_seconds
    eta_seconds = int(max(0, total - completed) * 3600 / units_per_hour)
    return {"units_per_hour": round(units_per_hour, 1), "eta_seconds": eta_seconds}


class RuntimeMonitor:
    def __init__(
        self,
        *,
        ignored_roots: list[Path] | None = None,
        process_reader: Callable[[], str] | None = None,
        scheduler_status_path: Path | None = None,
        wall_clock: Callable[[], float] = time.time,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ignored_roots = [Path(path).expanduser().resolve() for path in (ignored_roots or [])]
        self.process_reader = process_reader or read_process_table
        self.scheduler_status_path = Path(scheduler_status_path or DEFAULT_SCHEDULER_STATUS_PATH)
        self.wall_clock = wall_clock
        self.monotonic_clock = monotonic_clock
        self._lock = threading.Lock()
        self._known: dict[str, dict[str, Any]] = {}
        self._cached_snapshot: dict[str, Any] | None = None
        self._cached_at = 0.0

    def _is_ignored(self, work_dir: Path) -> bool:
        resolved = work_dir.resolve()
        for root in self.ignored_roots:
            try:
                resolved.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def _work_dir(self, process: ProcessRecord) -> Path | None:
        value = command_option(process.command, "work-dir")
        if not value:
            return None
        path = Path(value).expanduser()
        try:
            return path.resolve()
        except OSError:
            return path

    def _workflow_payload(self, process: ProcessRecord, work_dir: Path, now: float) -> dict[str, Any]:
        diagnostics = load_workflow_diagnostics(work_dir)
        heartbeat = read_json_file(work_dir / "heartbeat.json")
        progress_data = diagnostics.get("progress") if isinstance(diagnostics.get("progress"), dict) else {}
        heartbeat_current, heartbeat_total = progress_from_label(str(heartbeat.get("label") or ""))
        completed = progress_data.get("completed")
        total = progress_data.get("total") or heartbeat_total
        if not isinstance(completed, int):
            completed = max(0, heartbeat_current - 1) if heartbeat_current is not None else None
        if not isinstance(total, int):
            total = None
        percent = round(completed * 100 / total) if completed is not None and total else 0

        heartbeat_at = parse_timestamp(heartbeat.get("timestamp"))
        if heartbeat_at is None:
            try:
                heartbeat_at = (work_dir / "heartbeat.json").stat().st_mtime
            except OSError:
                heartbeat_at = parse_timestamp(diagnostics.get("updated_at"))
        heartbeat_age = max(0.0, now - heartbeat_at) if heartbeat_at is not None else None
        diagnosis = diagnostics.get("diagnosis") if isinstance(diagnostics.get("diagnosis"), dict) else None
        recovery = diagnostics.get("recovery") if isinstance(diagnostics.get("recovery"), dict) else None
        diagnostic_status = str(diagnostics.get("status") or "running")
        if heartbeat_age is not None and heartbeat_age >= RUNTIME_STALE_SECONDS:
            status = "stalled"
            health_state = "stalled"
            if diagnosis is None:
                stale = diagnose_failure("stale heartbeat", explicit_kind="heartbeat_stale")
                diagnosis = stale.to_dict()
                recovery = {
                    "automatic_retry": False,
                    "safe_to_resume": stale.safe_to_resume,
                    "retry_after_sec": 0,
                    "action": stale.action,
                    "circuit_open": False,
                }
        elif diagnosis and isinstance(recovery, dict) and recovery.get("automatic_retry"):
            status = "recovering"
            health_state = "degraded"
        elif diagnostic_status in {"paused", "failed"}:
            status = diagnostic_status
            health_state = diagnostic_status
        elif diagnostic_status == "complete":
            status = "completed"
            health_state = "healthy"
        else:
            status = "running"
            health = diagnostics.get("health") if isinstance(diagnostics.get("health"), dict) else {}
            health_state = str(health.get("state") or "healthy")

        metadata = diagnostics.get("metadata") if isinstance(diagnostics.get("metadata"), dict) else {}
        provider = str(
            metadata.get("provider")
            or command_option(process.command, "web-provider")
            or command_option(process.command, "provider")
            or command_option(process.command, "translation-provider")
            or command_option(process.command, "audio-provider")
            or ""
        )
        workflow = str(diagnostics.get("workflow") or MONITORED_SCRIPTS[process.script_name])
        velocity = progress_velocity(
            work_dir / "workflow_events.jsonl",
            completed=completed,
            total=total,
        )
        profile_dir = str(
            metadata.get("web_profile_dir")
            or command_option(process.command, "web-profile-dir")
            or ""
        )
        account_id = None
        cmd_str = " ".join(process.command) if isinstance(process.command, (list, tuple)) else str(process.command)
        if "account2" in profile_dir or "account2" in cmd_str:
            account_id = "account2"
        elif "account3" in profile_dir or "account3" in cmd_str:
            account_id = "account3"
        elif "chatgpt" in profile_dir or "chatgpt" in cmd_str or "chatgpt" in provider.lower():
            account_id = "chatgpt"
        elif "AudiobookStudio" in profile_dir or "main" in cmd_str or "gemini" in provider.lower():
            account_id = "main"

        stage = str(heartbeat.get("stage") or diagnostics.get("current_stage") or "starting")
        POST_PROCESSING_STAGES = {
            "validate_cache",
            "build_epub",
            "build_study_epub",
            "final_tone_review",
            "final_dialogue_review_pass2",
            "final_terminology_review",
            "final_presentation_review",
            "final_quality_audit",
            "finalize",
            "post_commands",
            "finalize_wait",
            "organize_library",
            "deploy",
            "korean_only_epub_generation",
            "english_study_epub_generation",
            "final_quality_audit",
            "dialogue_consistency_review",
            "tone_review",
        }
        is_postproc = (
            stage in POST_PROCESSING_STAGES
            or workflow in ("korean_only_epub_generation", "english_study_epub_generation", "final_quality_audit", "dialogue_consistency_review", "tone_review")
            or (completed is not None and total is not None and completed >= total and total > 0 and stage not in ("complete", "done"))
        )

        return {
            "id": workflow_identity(work_dir),
            "account_id": account_id,
            "profile_dir": profile_dir,
            "source": "external",
            "pid": process.pid,
            "ppid": process.ppid,
            "process_alive": True,
            "process_state": process.state,
            "elapsed": process.elapsed,
            "workflow": workflow,
            "phase": "post_processing" if is_postproc else "translation",
            "title": display_title(diagnostics, process.command, work_dir),
            "provider": provider,
            "status": status,
            "health": health_state,
            "stage": stage,
            "stage_label": str(heartbeat.get("label") or progress_data.get("current") or ""),
            "detail": str(heartbeat.get("detail") or progress_data.get("detail") or "")[:500],
            "progress": {
                "completed": completed,
                "total": total,
                "current": heartbeat_current or progress_data.get("current"),
                "percent": min(100, max(0, percent)),
                **velocity,
            },
            "heartbeat": {
                "timestamp": heartbeat_at,
                "age_seconds": round(heartbeat_age, 1) if heartbeat_age is not None else None,
                "fresh": heartbeat_age is not None and heartbeat_age < 30,
            },
            "diagnosis": diagnosis,
            "recovery": recovery,
            "updated_at": diagnostics.get("updated_at") or utc_now(),
        }

    def _scan(self) -> dict[str, Any]:
        now = self.wall_clock()
        scheduler = read_json_file(self.scheduler_status_path)
        scheduler_has_task_inventory = isinstance(scheduler.get("tasks"), list)
        scheduler_tasks = scheduler.get("tasks") if scheduler_has_task_inventory else []
        configured_workflow_ids = {
            workflow_identity(Path(str(task["work_dir"])).expanduser().resolve())
            for task in scheduler_tasks
            if isinstance(task, dict) and task.get("work_dir")
        }
        task_account_map: dict[str, str] = {}
        for task in scheduler_tasks:
            if isinstance(task, dict) and task.get("work_dir") and task.get("account_id"):
                try:
                    wd_key = workflow_identity(Path(str(task["work_dir"])).expanduser().resolve())
                    task_account_map[wd_key] = str(task["account_id"])
                    task_account_map[str(task["work_dir"])] = str(task["account_id"])
                except Exception:
                    pass

        active_ids: set[str] = set()
        workflows: list[dict[str, Any]] = []
        for process in parse_process_table(self.process_reader()):
            work_dir = self._work_dir(process)
            if work_dir is None or self._is_ignored(work_dir):
                continue
            payload = self._workflow_payload(process, work_dir, now)
            workflow_id = str(payload["id"])
            if workflow_id in task_account_map:
                payload["account_id"] = task_account_map[workflow_id]
            elif str(work_dir) in task_account_map:
                payload["account_id"] = task_account_map[str(work_dir)]
            active_ids.add(workflow_id)
            previous = self._known.get(workflow_id, {})
            self._known[workflow_id] = {
                "work_dir": work_dir,
                "last_seen": now,
                "payload": payload,
                "scheduler_managed": bool(
                    previous.get("scheduler_managed")
                    or workflow_id in configured_workflow_ids
                ),
            }
            workflows.append(payload)

        for workflow_id, known in list(self._known.items()):
            if workflow_id in active_ids:
                continue
            if (
                scheduler_has_task_inventory
                and known.get("scheduler_managed")
                and workflow_id not in configured_workflow_ids
            ):
                self._known.pop(workflow_id, None)
                continue
            missing_for = now - float(known["last_seen"])
            if missing_for > KNOWN_WORKFLOW_RETENTION_SECONDS:
                self._known.pop(workflow_id, None)
                continue
            payload = dict(known["payload"])
            if workflow_id in task_account_map:
                payload["account_id"] = task_account_map[workflow_id]
            diagnostics = load_workflow_diagnostics(Path(known["work_dir"]))
            if str(diagnostics.get("status") or "") == "complete":
                payload.update({"status": "completed", "health": "healthy", "process_alive": False})
            elif missing_for <= PROCESS_MISSING_GRACE_SECONDS:
                payload.update({"status": "reconnecting", "health": "degraded", "process_alive": False})
            else:
                failure = diagnose_failure("monitored process disappeared", explicit_kind="child_process_failed")
                payload.update(
                    {
                        "status": "interrupted",
                        "health": "failed",
                        "process_alive": False,
                        "diagnosis": failure.to_dict(),
                        "recovery": {
                            "automatic_retry": False,
                            "safe_to_resume": failure.safe_to_resume,
                            "retry_after_sec": 0,
                            "action": failure.action,
                            "circuit_open": True,
                        },
                    }
                )
            workflows.append(payload)

        managed_inactive_ids = {
            workflow_identity(Path(str(task["work_dir"])).expanduser().resolve())
            for task in scheduler_tasks
            if isinstance(task, dict)
            and task.get("work_dir")
            and task.get("status") in {"pending", "retry_wait", "completed"}
        }
        workflows = [
            workflow
            for workflow in workflows
            if workflow.get("process_alive") or workflow.get("id") not in managed_inactive_ids
        ]
        def account_sort_weight(item: dict[str, Any]) -> int:
            acc = str(item.get("account_id") or "").lower()
            if acc == "main" or "account1" in acc or "gemini1" in acc:
                return 1
            if acc == "account2" or "gemini2" in acc:
                return 2
            if acc == "account3" or "gemini3" in acc:
                return 3
            if acc == "chatgpt":
                return 4
            raw = (
                str(item.get("title") or "")
                + " "
                + str(item.get("id") or "")
                + " "
                + str(item.get("provider") or "")
            ).lower()
            if "beneath the burn" in raw or "account2" in raw:
                return 2
            if "heart of frost" in raw or "account3" in raw:
                return 3
            if "how to stop time" in raw or "@my_fiction" in raw or "chatgpt" in raw:
                return 4
            if "dead of eve" in raw or "main" in raw:
                return 1
            return 5

        status_order = {"stalled": 0, "failed": 1, "interrupted": 1, "recovering": 2, "running": 3}
        workflows.sort(key=lambda item: (account_sort_weight(item), status_order.get(str(item.get("status")), 4), str(item.get("title"))))
        scheduler_updated_at = parse_timestamp(scheduler.get("updated_at"))
        scheduler_stale = scheduler_updated_at is not None and now - scheduler_updated_at > SCHEDULER_STALE_SECONDS
        scheduler_accounts = scheduler.get("accounts") if isinstance(scheduler.get("accounts"), list) else []
        operations_audit = (
            scheduler.get("operations_audit")
            if isinstance(scheduler.get("operations_audit"), dict)
            else {}
        )
        accounts: list[dict[str, Any]] = []
        for raw_account in scheduler_accounts:
            if not isinstance(raw_account, dict):
                continue
            account = dict(raw_account)
            if scheduler_stale:
                account.update(
                    {
                        "status": "stalled",
                        "message": "스케줄러 상태 신호가 중단되었습니다",
                    }
                )
            matching_workflow = next(
                (workflow for workflow in workflows if workflow.get("pid") == account.get("pid")),
                None,
            )
            if matching_workflow is not None and matching_workflow.get("status") == "recovering":
                diagnosis = matching_workflow.get("diagnosis")
                kind = str(diagnosis.get("kind") or "") if isinstance(diagnosis, dict) else ""
                if kind in {"conversation_rate_limit", "rate_limit", "usage_limit"}:
                    account.update(
                        {
                            "status": "cooldown",
                            "failure_kind": kind,
                            "message": "요청 제한 해제 후 체크포인트에서 자동 재개",
                        }
                    )
            if (
                matching_workflow is not None
                and matching_workflow.get("stage") == "chatgpt_request_pacing"
            ):
                account.update(
                    {
                        "status": "pacing",
                        "message": str(matching_workflow.get("detail") or "안전 요청 간격 조절 중"),
                    }
                )
            accounts.append(account)
        return {
            "snapshot_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(timespec="seconds"),
            "refresh_after_ms": 1000,
            "summary": {
                "active": sum(1 for item in workflows if item["status"] in ACTIVE_RUNTIME_STATES),
                "healthy": sum(1 for item in workflows if item["health"] == "healthy"),
                "recovering": sum(1 for item in workflows if item["status"] == "recovering"),
                "attention": sum(1 for item in workflows if item["health"] in {"stalled", "failed", "paused"}),
            },
            "scheduler": {
                "status": scheduler.get("scheduler", {}).get("status")
                if isinstance(scheduler.get("scheduler"), dict)
                else None,
                "updated_at": scheduler.get("updated_at"),
                "stale": scheduler_stale,
            },
            "operations_audit": operations_audit,
            "accounts": accounts,
            "workflows": workflows,
        }

    def snapshot(self, *, force: bool = False) -> dict[str, Any]:
        with self._lock:
            now = self.monotonic_clock()
            if not force and self._cached_snapshot is not None and now - self._cached_at < SNAPSHOT_CACHE_SECONDS:
                return self._cached_snapshot
            self._cached_snapshot = self._scan()
            self._cached_at = now
            return self._cached_snapshot
