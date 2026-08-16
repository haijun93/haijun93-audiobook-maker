from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from scripts.atomic_io import atomic_output_path, atomic_write_json
from webui.operations_audit import analyze_task_window, summarize_provider_efficiency
from webui.runtime_monitor import command_option, parse_process_table, read_process_table
from webui.workflow_diagnostics import load_workflow_diagnostics

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback is validated by the work-dir lock.
    fcntl = None


STATE_VERSION = 1
PROFILE_LOCK_NAME = ".audiobook_web_profile.lock"
CHATGPT_RATE_LIMIT_STATE_NAME = ".chatgpt_rate_limit_state.json"
OPERATIONS_AUDIT_LOG_NAME = "operations_audits.jsonl"
OPERATIONS_AUDIT_LATEST_NAME = "latest_operations_audit.json"
DEFAULT_OPERATIONS_AUDIT_INTERVAL_SECONDS = 30 * 60
TERMINAL_TASK_STATES = {"completed", "blocked"}
ACCOUNT_FAILURE_KINDS = {
    "account_mismatch",
    "account_unavailable",
    "missing_credentials",
    "session_expired",
}
COOLDOWN_FAILURE_KINDS = {
    "conversation_rate_limit",
    "gemini_outage",
    "rate_limit",
    "service_unavailable",
}
NON_RETRYABLE_FAILURE_KINDS = {
    "invalid_input",
    "missing_dependency",
    "permission_denied",
}


class SchedulerConfigurationError(ValueError):
    pass


class SchedulerAlreadyRunning(RuntimeError):
    pass


def utc_now(timestamp: float | None = None) -> str:
    value = time.time() if timestamp is None else timestamp
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat(timespec="seconds")


def parse_timestamp(value: object) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except (TypeError, ValueError):
        return None


def expanded_path(value: object, *, base_dir: Path) -> Path:
    raw = os.path.expandvars(os.path.expanduser(str(value)))
    path = Path(raw)
    return path if path.is_absolute() else (base_dir / path).resolve()


def process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def profile_owner_pid(profile_base: Path, provider: str) -> int | None:
    lock_path = profile_base / provider / PROFILE_LOCK_NAME
    try:
        text = lock_path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"\bpid=(\d+)\b", text)
    if not match:
        return None
    pid = int(match.group(1))
    return pid if process_is_alive(pid) else None


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _string_list(value: object, *, field: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise SchedulerConfigurationError(f"{field} must be a non-empty list of strings")
    return list(value)


def validate_config(payload: Mapping[str, Any]) -> None:
    accounts = payload.get("accounts")
    tasks = payload.get("tasks")
    if not isinstance(accounts, list) or not accounts:
        raise SchedulerConfigurationError("accounts must be a non-empty list")
    if not isinstance(tasks, list):
        raise SchedulerConfigurationError("tasks must be a list")

    account_ids: set[str] = set()
    for index, account in enumerate(accounts):
        if not isinstance(account, dict):
            raise SchedulerConfigurationError(f"accounts[{index}] must be an object")
        account_id = str(account.get("id") or "")
        provider = str(account.get("provider") or "")
        if not account_id or account_id in account_ids:
            raise SchedulerConfigurationError(f"accounts[{index}].id is missing or duplicated")
        if not provider or not account.get("profile_dir"):
            raise SchedulerConfigurationError(f"accounts[{index}] requires provider and profile_dir")
        account_ids.add(account_id)

    task_ids: set[str] = set()
    work_dirs: set[str] = set()
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise SchedulerConfigurationError(f"tasks[{index}] must be an object")
        task_id = str(task.get("id") or "")
        if not task_id or task_id in task_ids:
            raise SchedulerConfigurationError(f"tasks[{index}].id is missing or duplicated")
        if not task.get("title") or not task.get("work_dir"):
            raise SchedulerConfigurationError(f"tasks[{index}] requires title and work_dir")
        _string_list(task.get("providers"), field=f"tasks[{index}].providers")
        _string_list(task.get("command"), field=f"tasks[{index}].command")
        _string_list(task.get("completion_paths"), field=f"tasks[{index}].completion_paths")
        work_dir = str(task["work_dir"])
        if work_dir in work_dirs:
            raise SchedulerConfigurationError(f"tasks[{index}].work_dir is duplicated")
        task_ids.add(task_id)
        work_dirs.add(work_dir)


class ContinuousTranslationScheduler:
    def __init__(
        self,
        config_path: Path,
        *,
        state_dir: Path | None = None,
        process_reader: Callable[[], str] = read_process_table,
        wall_clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
        popen_factory: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
    ) -> None:
        self.config_path = Path(config_path).expanduser().resolve()
        self.base_dir = self.config_path.parent
        self.config = self._load_config()
        configured_state = self.config.get("state_dir") or ".work/continuous_scheduler"
        self.state_dir = (
            Path(state_dir).expanduser().resolve()
            if state_dir is not None
            else expanded_path(configured_state, base_dir=self.base_dir)
        )
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.state_dir / "state.json"
        self.status_path = self.state_dir / "status.json"
        self.events_path = self.state_dir / "events.jsonl"
        self.operations_audit_path = self.state_dir / OPERATIONS_AUDIT_LOG_NAME
        self.latest_operations_audit_path = self.state_dir / OPERATIONS_AUDIT_LATEST_NAME
        self.logs_dir = self.state_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.process_reader = process_reader
        self.wall_clock = wall_clock
        self.sleeper = sleeper
        self.popen_factory = popen_factory
        self.state = self._load_state()
        self.children: dict[str, dict[str, Any]] = {}
        self._stop_event = threading.Event()
        self._lock_handle: TextIO | None = None
        self._started_at = utc_now(self.wall_clock())
        self._launch_not_before = self.wall_clock() + max(
            0.0,
            float(self.config.get("startup_adoption_grace_seconds", 0)),
        )

    def _load_config(self) -> dict[str, Any]:
        payload = load_json_object(self.config_path)
        if not payload:
            raise SchedulerConfigurationError(f"Cannot read scheduler config: {self.config_path}")
        validate_config(payload)
        return payload

    def _load_state(self) -> dict[str, Any]:
        payload = load_json_object(self.state_path)
        if payload.get("version") != STATE_VERSION:
            payload = {}
        accounts_raw = payload.get("accounts")
        accounts_dict = (
            {a["id"]: a for a in accounts_raw if isinstance(a, dict) and "id" in a}
            if isinstance(accounts_raw, list)
            else (accounts_raw if isinstance(accounts_raw, dict) else {})
        )
        tasks_raw = payload.get("tasks")
        tasks_dict = (
            {t["id"]: t for t in tasks_raw if isinstance(t, dict) and "id" in t}
            if isinstance(tasks_raw, list)
            else (tasks_raw if isinstance(tasks_raw, dict) else {})
        )
        return {
            "version": STATE_VERSION,
            "created_at": payload.get("created_at") or utc_now(self.wall_clock()),
            "updated_at": payload.get("updated_at"),
            "scheduler": payload.get("scheduler") if isinstance(payload.get("scheduler"), dict) else {},
            "operations_audit": (
                payload.get("operations_audit")
                if isinstance(payload.get("operations_audit"), dict)
                else {}
            ),
            "accounts": accounts_dict,
            "tasks": tasks_dict,
        }

    def _account_specs(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.config["accounts"]]

    def _task_specs(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.config["tasks"]]

    def _task_by_id(self, task_id: str) -> dict[str, Any] | None:
        return next((task for task in self._task_specs() if str(task["id"]) == task_id), None)

    def _account_by_id(self, account_id: str) -> dict[str, Any] | None:
        return next((account for account in self._account_specs() if str(account["id"]) == account_id), None)

    def _task_work_dir(self, task: Mapping[str, Any]) -> Path:
        return expanded_path(task["work_dir"], base_dir=self.base_dir)

    def _task_completion_paths(self, task: Mapping[str, Any]) -> list[Path]:
        values = task.get("completion_paths")
        if not isinstance(values, list):
            return []
        return [expanded_path(value, base_dir=self.base_dir) for value in values]

    def _is_complete(self, task: Mapping[str, Any]) -> bool:
        paths = self._task_completion_paths(task)
        return bool(paths) and all(path.is_file() and path.stat().st_size > 0 for path in paths)

    def _initialize_state(self) -> None:
        now = self.wall_clock()
        account_states = self.state["accounts"]
        for account in self._account_specs():
            account_id = str(account["id"])
            current = account_states.setdefault(account_id, {})
            current.setdefault("provider", str(account["provider"]))
            current.setdefault("status", "starting")
            current.setdefault("cooldown_until", None)
            current.setdefault("failure_count", 0)

        task_states = self.state["tasks"]
        configured_ids = set()
        for order, task in enumerate(self._task_specs()):
            task_id = str(task["id"])
            configured_ids.add(task_id)
            current = task_states.setdefault(task_id, {})
            current.setdefault("status", "pending")
            current.setdefault("attempts", 0)
            current.setdefault("stall_restarts", 0)
            current.setdefault("priority", int(task.get("priority", 100)))
            current.setdefault("order", order)
            current.setdefault("primary_complete", False)
            if self._is_complete(task):
                current.update(
                    {
                        "status": "completed",
                        "completed_at": current.get("completed_at") or utc_now(now),
                        "pid": None,
                        "account_id": None,
                        "primary_complete": True,
                    }
                )
        for task_id, current in task_states.items():
            if task_id not in configured_ids and current.get("status") not in TERMINAL_TASK_STATES:
                current["status"] = "removed"

    def acquire_lock(self) -> None:
        lock_path = self.state_dir / "scheduler.lock"
        handle = lock_path.open("a+", encoding="utf-8")
        if fcntl is not None:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                handle.close()
                raise SchedulerAlreadyRunning(f"Scheduler lock is already held: {lock_path}") from exc
        handle.seek(0)
        handle.truncate()
        handle.write(f"pid={os.getpid()} started={self._started_at}\n")
        handle.flush()
        self._lock_handle = handle

    def release_lock(self) -> None:
        if self._lock_handle is None:
            return
        if fcntl is not None:
            try:
                fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        self._lock_handle.close()
        self._lock_handle = None

    def request_stop(self, *_args: object) -> None:
        self._stop_event.set()

    def _event(self, event: str, **payload: Any) -> None:
        record = {"timestamp": utc_now(self.wall_clock()), "event": event, **payload}
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()

    def _save_state(self) -> None:
        self.state["updated_at"] = utc_now(self.wall_clock())
        atomic_write_json(self.state_path, self.state, trailing_newline=True)

    def _format_tokens(self, value: str, *, account: Mapping[str, Any], task: Mapping[str, Any]) -> str:
        tokens = {
            "account_id": str(account["id"]),
            "provider": str(account["provider"]),
            "profile_dir": str(expanded_path(account["profile_dir"], base_dir=self.base_dir)),
            "repo": str(Path(__file__).resolve().parents[1]),
            "work_dir": str(self._task_work_dir(task)),
            "python": str(self.config.get("python") or os.sys.executable),
        }
        result = value
        for key, replacement in tokens.items():
            result = result.replace("{" + key + "}", replacement)
        return os.path.expandvars(os.path.expanduser(result))

    @staticmethod
    def _set_command_option(command: list[str], option: str, value: object) -> None:
        rendered = str(value)
        if option in command:
            index = command.index(option)
            if index + 1 < len(command):
                command[index + 1] = rendered
                return
        command.extend([option, rendered])

    def _command(self, values: Sequence[str], *, account: Mapping[str, Any], task: Mapping[str, Any]) -> list[str]:
        command = [self._format_tokens(value, account=account, task=task) for value in values]
        task_state = self.state["tasks"].get(str(task["id"]), {})
        overrides = task_state.get("runtime_overrides")
        script_text = " ".join(command)
        supported = {
            "web_max_attempts": "--web-max-attempts",
            "inter_request_delay_sec": "--inter-request-delay-sec",
        }
        if "backfill_study_notes.py" in script_text:
            supported["note_max_attempts"] = "--note-max-attempts"
            profile_state_dir = (
                expanded_path(account["profile_dir"], base_dir=self.base_dir)
                / str(account["provider"])
            )
            self._set_command_option(
                command,
                "--provider-fallback-state-dir",
                profile_state_dir,
            )
            self._set_command_option(
                command,
                "--web-max-attempts",
                max(1, int(self.config.get("backfill_web_max_attempts", 3))),
            )
            self._set_command_option(
                command,
                "--inter-request-delay-sec",
                max(0.0, float(self.config.get("backfill_inter_request_delay_seconds", 8.0))),
            )
        is_web_script = any(name in script_text for name in ("translate_epub", "run_soseol2", "run_k_e", "backfill_study_notes"))
        if is_web_script and isinstance(overrides, dict):
            # Rechunking changes the meaning of chunk_XXXX.json and invalidates resume caches.
            # Remove the legacy adaptive override while preserving explicit task command options.
            if "max_chars_per_chunk" in overrides:
                overrides = dict(overrides)
                overrides.pop("max_chars_per_chunk", None)
                task_state["runtime_overrides"] = overrides
            for key, option in supported.items():
                if key in overrides:
                    self._set_command_option(command, option, overrides[key])
        return command

    def _environment(self, account: Mapping[str, Any], task: Mapping[str, Any]) -> dict[str, str]:
        environment = dict(os.environ)
        environment.update(
            {
                "PYTHONUNBUFFERED": "1",
                "AUDIOBOOK_WEB_PROFILE_DIR": str(
                    expanded_path(account["profile_dir"], base_dir=self.base_dir)
                ),
                "AUDIOBOOK_SCHEDULER_ACCOUNT": str(account["id"]),
                "AUDIOBOOK_SCHEDULER_TASK": str(task["id"]),
            }
        )
        for source in (self.config.get("env"), account.get("env"), task.get("env")):
            if not isinstance(source, dict):
                continue
            for key, value in source.items():
                environment[str(key)] = self._format_tokens(str(value), account=account, task=task)
        return environment

    def _launch(self, account: Mapping[str, Any], task: Mapping[str, Any]) -> None:
        account_id = str(account["id"])
        task_id = str(task["id"])
        task_state = self.state["tasks"][task_id]
        work_dir = self._task_work_dir(task)
        work_dir.mkdir(parents=True, exist_ok=True)
        command = self._command(_string_list(task["command"], field=f"task {task_id} command"), account=account, task=task)
        log_path = self.logs_dir / f"{account_id}.log"
        log_handle = log_path.open("a", encoding="utf-8")
        log_handle.write(
            f"\n[{utc_now(self.wall_clock())}] START task={task_id} title={task['title']} command={command!r}\n"
        )
        log_handle.flush()
        try:
            process = self.popen_factory(
                command,
                cwd=str(expanded_path(self.config.get("repo_dir") or Path(__file__).resolve().parents[1], base_dir=self.base_dir)),
                env=self._environment(account, task),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
        except BaseException:
            log_handle.close()
            raise

        now = self.wall_clock()
        task_state.update(
            {
                "status": "running",
                "account_id": account_id,
                "pid": process.pid,
                "attempts": int(task_state.get("attempts") or 0) + 1,
                "started_at": utc_now(now),
                "last_seen_at": utc_now(now),
                "next_attempt_at": None,
                "error": None,
                "terminating_stale": False,
            }
        )
        self.state["accounts"][account_id].update(
            {
                "status": "running",
                "task_id": task_id,
                "pid": process.pid,
                "source": "scheduler",
                "message": str(task["title"]),
            }
        )
        self.children[account_id] = {
            "process": process,
            "task_id": task_id,
            "log_handle": log_handle,
        }
        self._event("task_started", task_id=task_id, account_id=account_id, pid=process.pid)

    def _diagnosis(self, task: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        diagnostics = load_workflow_diagnostics(self._task_work_dir(task))
        diagnosis = diagnostics.get("diagnosis") if isinstance(diagnostics.get("diagnosis"), dict) else {}
        recovery = diagnostics.get("recovery") if isinstance(diagnostics.get("recovery"), dict) else {}
        return str(diagnosis.get("kind") or "child_process_failed"), recovery

    def _schedule_retry(
        self,
        *,
        account_id: str,
        task: Mapping[str, Any],
        returncode: int,
        reason: str | None = None,
    ) -> None:
        now = self.wall_clock()
        task_id = str(task["id"])
        task_state = self.state["tasks"][task_id]
        kind, recovery = self._diagnosis(task)
        if reason == "heartbeat_stale":
            kind = "heartbeat_stale"
        elif reason and reason.startswith("operational_audit:"):
            kind = reason.split(":", 1)[1] or "unknown_error"
        max_attempts = max(1, int(task.get("max_attempts", 12)))
        attempts = int(task_state.get("attempts") or 0)
        retryable = kind not in NON_RETRYABLE_FAILURE_KINDS and attempts < max_attempts
        if recovery.get("safe_to_resume") is False:
            retryable = False
        if reason == "heartbeat_stale" and int(task_state.get("stall_restarts") or 0) > int(
            task.get("max_stall_restarts", 1)
        ):
            retryable = False

        if kind in ACCOUNT_FAILURE_KINDS:
            delay = int(task.get("account_retry_seconds", 15 * 60))
        else:
            requested_delay = int(recovery.get("retry_after_sec") or 0)
            exponential = min(30 * 60, 30 * (2 ** min(6, max(0, attempts - 1))))
            delay = max(requested_delay, exponential)
        account = self._account_by_id(account_id)
        if kind == "rate_limit" and account is not None and account.get("provider") == "chatgpt":
            delay = max(delay, int(task.get("chatgpt_rate_limit_retry_seconds", 20 * 60)))
        if kind in COOLDOWN_FAILURE_KINDS or kind in ACCOUNT_FAILURE_KINDS:
            account_state = self.state["accounts"][account_id]
            account_state.update(
                {
                    "status": "cooldown" if kind not in ACCOUNT_FAILURE_KINDS else "attention",
                    "cooldown_until": utc_now(now + delay),
                    "failure_kind": kind,
                    "failure_count": int(account_state.get("failure_count") or 0) + 1,
                    "message": recovery.get("action") or kind,
                    "task_id": None,
                    "pid": None,
                }
            )

        if retryable:
            task_state.update(
                {
                    "status": "retry_wait",
                    "next_attempt_at": utc_now(now + delay),
                    "last_exit_code": returncode,
                    "failure_kind": kind,
                    "error": reason or kind,
                    "pid": None,
                    "account_id": None,
                }
            )
            self._event(
                "task_retry_scheduled",
                task_id=task_id,
                account_id=account_id,
                failure_kind=kind,
                retry_after_seconds=delay,
            )
        else:
            task_state.update(
                {
                    "status": "blocked",
                    "blocked_at": utc_now(now),
                    "last_exit_code": returncode,
                    "failure_kind": kind,
                    "error": reason or kind,
                    "pid": None,
                    "account_id": None,
                }
            )
            self._event("task_blocked", task_id=task_id, account_id=account_id, failure_kind=kind)

    def _run_post_command(self, command: list[str], *, task: Mapping[str, Any], log_handle: TextIO) -> None:
        result = subprocess.run(
            command,
            cwd=str(expanded_path(self.config.get("repo_dir") or Path(__file__).resolve().parents[1], base_dir=self.base_dir)),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=max(30, int(task.get("post_timeout_seconds", 15 * 60))),
            check=False,
        )
        if result.returncode:
            raise RuntimeError(f"post command exited with {result.returncode}: {command!r}")

    def _deploy_artifacts(self, task: Mapping[str, Any]) -> None:
        deployments = task.get("deploy")
        if not isinstance(deployments, list):
            return
        for item in deployments:
            if not isinstance(item, dict) or not item.get("source") or not item.get("destination"):
                raise SchedulerConfigurationError(f"Invalid deployment in task {task['id']}")
            source = expanded_path(item["source"], base_dir=self.base_dir)
            destination = expanded_path(item["destination"], base_dir=self.base_dir)
            if not source.is_file() or source.stat().st_size == 0:
                raise FileNotFoundError(f"Deployment source is missing: {source}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with atomic_output_path(destination) as temporary:
                shutil.copy2(source, temporary)

    def _finalize(self, task: Mapping[str, Any], *, account: Mapping[str, Any]) -> bool:
        task_id = str(task["id"])
        task_state = self.state["tasks"][task_id]
        log_path = self.logs_dir / f"post-{task_id}.log"
        try:
            with log_path.open("a", encoding="utf-8") as log_handle:
                log_handle.write(f"\n[{utc_now(self.wall_clock())}] FINALIZE {task_id}\n")
                post_commands = task.get("post_commands")
                if isinstance(post_commands, list):
                    for values in post_commands:
                        command = self._command(
                            _string_list(values, field=f"task {task_id} post command"),
                            account=account,
                            task=task,
                        )
                        self._run_post_command(command, task=task, log_handle=log_handle)
                self._deploy_artifacts(task)
            if not self._is_complete(task):
                raise RuntimeError("final completion artifacts were not created")
        except (OSError, RuntimeError, SchedulerConfigurationError, subprocess.SubprocessError) as exc:
            attempts = int(task_state.get("finalize_attempts") or 0) + 1
            delay = min(15 * 60, 30 * (2 ** min(5, attempts - 1)))
            task_state.update(
                {
                    "status": "finalize_wait" if attempts < 5 else "blocked",
                    "finalize_attempts": attempts,
                    "next_attempt_at": utc_now(self.wall_clock() + delay),
                    "error": f"finalize_failed: {exc}",
                    "pid": None,
                    "account_id": None,
                }
            )
            self._event("task_finalize_failed", task_id=task_id, attempt=attempts, error=str(exc))
            return False

        task_state.update(
            {
                "status": "completed",
                "completed_at": utc_now(self.wall_clock()),
                "primary_complete": True,
                "pid": None,
                "account_id": None,
                "next_attempt_at": None,
                "error": None,
            }
        )
        self._event("task_completed", task_id=task_id)
        return True

    def _poll_children(self) -> None:
        for account_id, child in list(self.children.items()):
            process = child["process"]
            returncode = process.poll()
            if returncode is None:
                task_state = self.state["tasks"].get(child["task_id"], {})
                task_state["last_seen_at"] = utc_now(self.wall_clock())
                task = self._task_by_id(str(child["task_id"]))
                account_state = self.state["accounts"].get(account_id, {})
                diagnostics = load_workflow_diagnostics(self._task_work_dir(task)) if task is not None else {}
                diagnosis = diagnostics.get("diagnosis") if isinstance(diagnostics.get("diagnosis"), dict) else {}
                recovery = diagnostics.get("recovery") if isinstance(diagnostics.get("recovery"), dict) else {}
                kind = str(diagnosis.get("kind") or "")
                if kind in COOLDOWN_FAILURE_KINDS:
                    account_state.update(
                        {
                            "status": "cooldown",
                            "failure_kind": kind,
                            "message": recovery.get("action") or diagnosis.get("root_cause") or kind,
                        }
                    )
                elif account_state.get("source") == "scheduler":
                    account_state.update({"status": "running", "failure_kind": None})
                continue
            log_handle = child["log_handle"]
            log_handle.write(f"[{utc_now(self.wall_clock())}] EXIT returncode={returncode}\n")
            log_handle.close()
            self.children.pop(account_id, None)
            task = self._task_by_id(str(child["task_id"]))
            account = self._account_by_id(account_id)
            if task is None or account is None:
                continue
            task_state = self.state["tasks"][str(task["id"])]
            account_state = self.state["accounts"][account_id]
            account_state.update({"status": "ready", "task_id": None, "pid": None, "source": None})
            if returncode == 0:
                task_state["primary_complete"] = True
                self._finalize(task, account=account)
            else:
                self._schedule_retry(
                    account_id=account_id,
                    task=task,
                    returncode=returncode,
                    reason=child.get("termination_reason"),
                )

    def _heartbeat_snapshot(self, task: Mapping[str, Any]) -> dict[str, Any]:
        heartbeat = self._task_work_dir(task) / "heartbeat.json"
        payload = load_json_object(heartbeat)
        try:
            timestamp = float(payload.get("timestamp") or heartbeat.stat().st_mtime)
        except OSError:
            return {}
        except (TypeError, ValueError):
            return {}
        return {
            **payload,
            "age_seconds": max(0.0, self.wall_clock() - timestamp),
            "timestamp": timestamp,
        }

    def _watchdog(self) -> None:
        stale_after = max(60, int(self.config.get("heartbeat_stale_seconds", 30 * 60)))
        browser_launch_stale_after = max(
            60,
            int(self.config.get("browser_launch_stale_seconds", 3 * 60)),
        )
        for account_id, child in list(self.children.items()):
            task = self._task_by_id(str(child["task_id"]))
            if task is None:
                continue
            task_state = self.state["tasks"][str(task["id"])]
            heartbeat = self._heartbeat_snapshot(task)
            age = heartbeat.get("age_seconds")
            heartbeat_pid = int(heartbeat.get("pid") or 0)
            process = child["process"]
            if heartbeat_pid and heartbeat_pid != process.pid:
                continue
            heartbeat_timestamp = float(heartbeat.get("timestamp") or 0)
            task_started = parse_timestamp(task_state.get("started_at")) or 0
            if heartbeat_timestamp and task_started and heartbeat_timestamp + 1 < task_started:
                continue
            stage = str(heartbeat.get("stage") or "")
            effective_stale_after = (
                browser_launch_stale_after
                if stage in {"translation_playwright_launch", "translation_browser_launch"}
                else stale_after
            )
            if task_state.get("terminating_stale"):
                termination_at = parse_timestamp(task_state.get("termination_requested_at"))
                if termination_at is not None and self.wall_clock() - termination_at >= 30:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except (OSError, ProcessLookupError):
                        process.kill()
                continue
            if age is None or float(age) < effective_stale_after:
                continue
            task_state["stall_restarts"] = int(task_state.get("stall_restarts") or 0) + 1
            task_state["terminating_stale"] = True
            task_state["termination_requested_at"] = utc_now(self.wall_clock())
            child["termination_reason"] = "heartbeat_stale"
            process = child["process"]
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except (OSError, ProcessLookupError):
                process.terminate()
            self._event(
                "heartbeat_stale",
                task_id=str(task["id"]),
                account_id=account_id,
                age_seconds=round(age),
                stage=stage,
                threshold_seconds=effective_stale_after,
            )

    def _operations_audit_interval(self) -> int:
        return max(
            60,
            int(
                self.config.get(
                    "operations_audit_interval_seconds",
                    DEFAULT_OPERATIONS_AUDIT_INTERVAL_SECONDS,
                )
            ),
        )

    def _operations_audit_due(self) -> bool:
        audit_state = self.state.setdefault("operations_audit", {})
        last_run = parse_timestamp(audit_state.get("last_run_at"))
        return last_run is None or self.wall_clock() - last_run >= self._operations_audit_interval()

    def _append_operations_audit(self, report: Mapping[str, Any]) -> None:
        with self.operations_audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(report), ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        atomic_write_json(self.latest_operations_audit_path, dict(report), trailing_newline=True)

    def _update_runtime_overrides(self, task_id: str, finding: Mapping[str, Any]) -> dict[str, Any]:
        task_state = self.state["tasks"][task_id]
        current = dict(task_state.get("runtime_overrides") or {})
        action = str(finding.get("action") or "")
        changes: dict[str, Any] = {}
        if action in {
            "cooldown_and_restart",
            "increase_request_pacing",
            "monitor_and_tune",
            "restart_from_checkpoint",
        }:
            previous_delay = float(current.get("inter_request_delay_sec") or 4.0)
            changes["inter_request_delay_sec"] = min(30.0, max(8.0, previous_delay * 1.5))
            changes["web_max_attempts"] = min(3, int(current.get("web_max_attempts") or 3))
        preserve_chunk_plan = action in {"reduce_chunk_and_retries", "split_format_retries"}
        if preserve_chunk_plan:
            removed_legacy_override = current.pop("max_chars_per_chunk", None) is not None
            changes["note_max_attempts"] = 2
            changes["web_max_attempts"] = min(3, int(current.get("web_max_attempts") or 3))
            changes["inter_request_delay_sec"] = max(
                8.0,
                float(current.get("inter_request_delay_sec") or 4.0),
            )
        else:
            removed_legacy_override = False
        if changes or removed_legacy_override:
            current.update(changes)
            task_state["runtime_overrides"] = current
            task_state["runtime_overrides_updated_at"] = utc_now(self.wall_clock())
        if preserve_chunk_plan:
            changes["chunk_plan_preserved"] = True
        return changes

    def _audit_restart(
        self,
        *,
        task: Mapping[str, Any],
        account_id: str,
        finding: Mapping[str, Any],
    ) -> bool:
        account_state = self.state["accounts"].get(account_id)
        task_state = self.state["tasks"][str(task["id"])]
        if not isinstance(account_state, dict):
            return False
        pid = int(task_state.get("pid") or account_state.get("pid") or 0)
        if pid <= 0 or not process_is_alive(pid):
            return False

        provider = str(finding.get("provider") or "")
        finding_kind = str(finding.get("kind") or "operational_audit")
        failure_kind = (
            "gemini_outage"
            if finding_kind == "provider_error_burst" and provider == "gemini"
            else finding_kind
        )
        cooldown = max(60, int(finding.get("cooldown_seconds") or 60))
        now = self.wall_clock()
        account_state.update(
            {
                "status": "cooldown",
                "cooldown_until": utc_now(now + cooldown),
                "failure_kind": failure_kind,
                "failure_count": int(account_state.get("failure_count") or 0) + 1,
                "message": "30분 운영 감사에서 원인을 확인하여 안전 재시작 중",
            }
        )
        child = self.children.get(account_id)
        if child is not None and child["process"].pid == pid:
            child["termination_reason"] = f"operational_audit:{failure_kind}"
        else:
            task_state.update(
                {
                    "status": "retry_wait",
                    "next_attempt_at": utc_now(now + cooldown),
                    "failure_kind": failure_kind,
                    "error": f"operational_audit:{failure_kind}",
                    "pid": None,
                    "account_id": None,
                }
            )
        try:
            os.killpg(pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            try:
                os.kill(pid, signal.SIGTERM)
            except (OSError, ProcessLookupError):
                return False
        self._event(
            "operations_audit_restart_requested",
            task_id=str(task["id"]),
            account_id=account_id,
            pid=pid,
            failure_kind=failure_kind,
            cooldown_seconds=cooldown,
        )
        return True

    def _run_operations_audit(self) -> dict[str, Any] | None:
        if not self._operations_audit_due():
            return None
        now = self.wall_clock()
        interval = self._operations_audit_interval()
        audit_state = self.state.setdefault("operations_audit", {})
        previous_run = parse_timestamp(audit_state.get("last_run_at"))
        period_start = max(now - interval, previous_run or now - interval)
        baselines = audit_state.get("task_baselines")
        if not isinstance(baselines, dict):
            baselines = {}

        findings: list[dict[str, Any]] = []
        next_baselines: dict[str, Any] = {}
        action_count = 0
        for task in self._task_specs():
            task_id = str(task["id"])
            task_state = self.state["tasks"][task_id]
            account_id = str(task_state.get("account_id") or "") or None
            account = self._account_by_id(account_id) if account_id else None
            provider = str(account.get("provider")) if account is not None else None
            finding = analyze_task_window(
                task_id=task_id,
                title=str(task["title"]),
                work_dir=self._task_work_dir(task),
                task_state=task_state,
                account_id=account_id,
                provider=provider,
                now=now,
                period_start=period_start,
                baseline=baselines.get(task_id) if isinstance(baselines.get(task_id), dict) else None,
                interval_seconds=interval,
                heartbeat_stale_seconds=max(
                    60,
                    int(self.config.get("heartbeat_stale_seconds", 30 * 60)),
                ),
                provider_error_threshold=max(
                    2,
                    int(self.config.get("operations_audit_provider_error_threshold", 6)),
                ),
                format_error_threshold=max(
                    2,
                    int(self.config.get("operations_audit_format_error_threshold", 3)),
                ),
            )
            next_baselines[task_id] = finding.pop("baseline")
            changes = self._update_runtime_overrides(task_id, finding)
            restarted = False
            if bool(finding.get("restart_required")) and account_id:
                restarted = self._audit_restart(
                    task=task,
                    account_id=account_id,
                    finding=finding,
                )
            finding["improvement"] = {
                "applied": bool(changes or restarted),
                "runtime_overrides": changes,
                "restart_requested": restarted,
            }
            if changes or restarted:
                action_count += 1
            if finding.get("kind") != "healthy" or task_state.get("status") in {
                "running",
                "external",
                "reconnecting",
            }:
                findings.append(finding)

        sequence = int(audit_state.get("sequence") or 0) + 1
        issue_count = sum(1 for finding in findings if finding.get("kind") != "healthy")
        critical_count = sum(1 for finding in findings if finding.get("severity") == "error")
        provider_efficiency = summarize_provider_efficiency(findings)
        report = {
            "version": 1,
            "sequence": sequence,
            "started_at": utc_now(now),
            "period_start": utc_now(period_start),
            "interval_seconds": interval,
            "next_run_at": utc_now(now + interval),
            "status": (
                "attention"
                if critical_count
                else ("improved" if action_count else ("observing" if issue_count else "healthy"))
            ),
            "summary": {
                "tasks_checked": len(self._task_specs()),
                "findings": issue_count,
                "critical": critical_count,
                "new_errors": sum(
                    int(finding.get("evidence", {}).get("new_error_count") or 0)
                    for finding in findings
                    if isinstance(finding.get("evidence"), dict)
                ),
                "actions_applied": action_count,
            },
            "provider_efficiency": provider_efficiency,
            "findings": findings,
        }
        audit_state.update(
            {
                "sequence": sequence,
                "last_run_at": utc_now(now),
                "next_run_at": utc_now(now + interval),
                "task_baselines": next_baselines,
                "latest": report,
            }
        )
        self._append_operations_audit(report)
        self._event(
            "operations_audit_completed",
            sequence=sequence,
            findings=issue_count,
            critical=critical_count,
            actions_applied=action_count,
        )
        return report

    def _scan_occupancy(self, process_output: str) -> dict[str, dict[str, Any]]:
        records = parse_process_table(process_output)
        record_by_pid = {record.pid: record for record in records}
        task_by_work_dir = {str(self._task_work_dir(task)): task for task in self._task_specs()}
        task_by_batch_only: dict[str, dict[str, Any]] = {}
        for task in self._task_specs():
            command = task.get("command")
            if not isinstance(command, list) or "--only" not in command:
                continue
            option_index = command.index("--only")
            if option_index + 1 < len(command):
                task_by_batch_only[str(command[option_index + 1])] = task
        occupancy: dict[str, dict[str, Any]] = {}
        child_pids = {child["process"].pid for child in self.children.values()}
        assigned_pids: set[int] = set(child_pids)
        active_wrapper_task_ids: set[str] = set()
        now = self.wall_clock()

        # A restarted scheduler does not own an already-running batch wrapper. The wrapper can
        # temporarily have no translation child while it applies retry backoff, so the profile
        # lock alone is not enough to prove the account is occupied during that gap.
        for record in records:
            if record.script_name != "run_soseol2_chatgpt_k_e_batch.py":
                continue
            only_value = command_option(record.command, "only")
            task = task_by_batch_only.get(str(only_value or ""))
            if task is None:
                continue
            task_id = str(task["id"])
            task_state = self.state["tasks"][task_id]
            preferred_accounts = task.get("preferred_accounts")
            preferred_account = (
                str(preferred_accounts[0])
                if isinstance(preferred_accounts, list) and preferred_accounts
                else ""
            )
            account_id = str(preferred_account or task_state.get("account_id") or "")
            if not account_id or self._account_by_id(account_id) is None:
                continue
            active_wrapper_task_ids.add(task_id)
            assigned_pids.add(record.pid)
            occupancy.setdefault(
                account_id,
                {
                    "status": "external",
                    "pid": record.pid,
                    "task_id": task_id,
                    "message": str(task["title"]),
                },
            )
            task_state.update(
                {
                    "status": "external",
                    "account_id": account_id,
                    "pid": record.pid,
                    "last_seen_at": utc_now(now),
                    "missing_since": None,
                }
            )

        # A translation worker can spend meaningful time extracting and normalizing the EPUB
        # before Chrome creates the provider-profile lock. Adopt the worker from its configured
        # work directory during that startup window so a restarted scheduler cannot launch a
        # second book on the same account.
        for record in sorted(records, key=lambda item: item.pid):
            if record.pid in child_pids:
                continue
            work_dir = command_option(record.command, "work-dir")
            if not work_dir:
                continue
            task = task_by_work_dir.get(str(Path(work_dir).expanduser().resolve()))
            if task is None:
                continue
            task_id = str(task["id"])
            task_state = self.state["tasks"][task_id]
            preferred_accounts = task.get("preferred_accounts")
            preferred_account = (
                str(preferred_accounts[0])
                if isinstance(preferred_accounts, list) and preferred_accounts
                else ""
            )
            account_id = str(preferred_account or task_state.get("account_id") or "")
            if not account_id or self._account_by_id(account_id) is None:
                continue
            current = occupancy.get(account_id)
            if current is not None and current.get("task_id") != task_id:
                continue
            assigned_pids.add(record.pid)
            occupancy[account_id] = {
                "status": "external",
                "pid": record.pid,
                "task_id": task_id,
                "message": str(task["title"]),
            }
            task_state.update(
                {
                    "status": "external",
                    "account_id": account_id,
                    "pid": record.pid,
                    "last_seen_at": utc_now(now),
                    "missing_since": None,
                }
            )

        # Process-table reads can transiently fail during launchd hand-off. A live PID already
        # recorded in durable state is still authoritative enough to prevent a duplicate launch;
        # the next successful scan will replace it with command-derived task metadata.
        for task in self._task_specs():
            task_id = str(task["id"])
            task_state = self.state["tasks"][task_id]
            preferred_accounts = task.get("preferred_accounts")
            preferred_account = (
                str(preferred_accounts[0])
                if isinstance(preferred_accounts, list) and preferred_accounts
                else ""
            )
            account_id = str(preferred_account or task_state.get("account_id") or "")
            pid = int(task_state.get("pid") or 0)
            if (
                task_state.get("status") not in {"running", "external", "reconnecting"}
                or not account_id
                or account_id in self.children
                or account_id in occupancy
                or self._account_by_id(account_id) is None
                or not process_is_alive(pid)
                or (pid > 0 and pid in assigned_pids)
            ):
                continue
            if pid > 0:
                assigned_pids.add(pid)
            occupancy[account_id] = {
                "status": "external",
                "pid": pid,
                "task_id": task_id,
                "message": str(task["title"]),
            }

        for account in self._account_specs():
            account_id = str(account["id"])
            account_state = self.state["accounts"][account_id]
            pid = int(account_state.get("pid") or 0)
            if (
                account_id in self.children
                or account_id in occupancy
                or account_state.get("status") not in {"running", "external", "reconnecting"}
                or not process_is_alive(pid)
                or (pid > 0 and pid in assigned_pids)
            ):
                continue
            if pid > 0:
                assigned_pids.add(pid)
            task_id = str(account_state.get("task_id") or "") or None
            task = self._task_by_id(task_id) if task_id else None
            occupancy[account_id] = {
                "status": "external",
                "pid": pid,
                "task_id": task_id,
                "message": str(task["title"]) if task else str(account_state.get("message") or "외부 번역 작업"),
            }

        for account in self._account_specs():
            account_id = str(account["id"])
            if account_id in self.children or account_id in occupancy:
                continue
            profile_dir = expanded_path(account["profile_dir"], base_dir=self.base_dir)
            owner_pid = profile_owner_pid(profile_dir, str(account["provider"]))
            if owner_pid is not None and owner_pid not in assigned_pids:
                assigned_pids.add(owner_pid)
                record = record_by_pid.get(owner_pid)
                work_dir = command_option(record.command, "work-dir") if record else None
                task = task_by_work_dir.get(str(Path(work_dir).expanduser().resolve())) if work_dir else None
                occupancy[account_id] = {
                    "status": "external",
                    "pid": owner_pid,
                    "task_id": str(task["id"]) if task else None,
                    "message": str(task["title"]) if task else "외부 번역 작업",
                }
                if task is not None and owner_pid not in child_pids:
                    task_state = self.state["tasks"][str(task["id"])]
                    task_state.update(
                        {
                            "status": "external",
                            "account_id": account_id,
                            "pid": owner_pid,
                            "last_seen_at": utc_now(now),
                            "missing_since": None,
                        }
                    )
                continue

            patterns = account.get("external_process_patterns")
            if isinstance(patterns, list) and any(str(pattern) in process_output for pattern in patterns):
                occupancy[account_id] = {
                    "status": "external",
                    "pid": None,
                    "task_id": None,
                    "message": "기존 배치 인계 대기",
                }

        active_work_dirs = {
            str(Path(value).expanduser().resolve())
            for record in records
            if (value := command_option(record.command, "work-dir"))
        }
        owned_task_ids = {str(child["task_id"]) for child in self.children.values()}
        for task in self._task_specs():
            task_id = str(task["id"])
            task_state = self.state["tasks"][task_id]
            if task_state.get("status") != "running" or task_id in owned_task_ids:
                continue
            if task_id in active_wrapper_task_ids or str(self._task_work_dir(task)) in active_work_dirs:
                continue
            stale_pid = int(task_state.get("pid") or 0)
            if stale_pid > 0 and process_is_alive(stale_pid):
                continue
            task_state.update(
                {
                    "status": "pending",
                    "pid": None,
                    "account_id": None,
                    "missing_since": None,
                    "terminating_stale": False,
                }
            )
        for task in self._task_specs():
            task_id = str(task["id"])
            task_state = self.state["tasks"][task_id]
            if task_state.get("status") != "external":
                continue
            if task_id in active_wrapper_task_ids:
                continue
            if str(self._task_work_dir(task)) in active_work_dirs:
                continue
            if self._is_complete(task):
                task_state.update({"status": "completed", "completed_at": utc_now(now), "pid": None})
                continue
            missing_since = parse_timestamp(task_state.get("missing_since"))
            if missing_since is None:
                task_state["missing_since"] = utc_now(now)
                missing_since = now
            grace = max(0, int(self.config.get("external_missing_grace_seconds", 15)))
            if now - missing_since >= grace:
                task_state.update(
                    {
                        "status": "pending",
                        "pid": None,
                        "account_id": None,
                        "missing_since": None,
                    }
                )
            else:
                previous_account = str(task_state.get("account_id") or "")
                if previous_account and previous_account not in occupancy:
                    occupancy[previous_account] = {
                        "status": "reconnecting",
                        "pid": None,
                        "task_id": task_id,
                        "message": str(task["title"]),
                    }
        return occupancy

    def _retry_due(self, task_state: Mapping[str, Any]) -> bool:
        next_attempt = parse_timestamp(task_state.get("next_attempt_at"))
        return next_attempt is None or next_attempt <= self.wall_clock()

    def _finalize_due_tasks(self) -> None:
        accounts = self._account_specs()
        if not accounts:
            return
        for task in self._task_specs():
            state = self.state["tasks"][str(task["id"])]
            if state.get("status") != "finalize_wait" or not self._retry_due(state):
                continue
            compatible = next(
                (account for account in accounts if str(account["provider"]) in task["providers"]),
                accounts[0],
            )
            self._finalize(task, account=compatible)

    def _available_tasks(self, account: Mapping[str, Any]) -> list[dict[str, Any]]:
        provider = str(account["provider"])
        candidates: list[dict[str, Any]] = []
        for task in self._task_specs():
            state = self.state["tasks"][str(task["id"])]
            if provider not in task["providers"]:
                continue
            if state.get("status") not in {"pending", "retry_wait"}:
                continue
            if state.get("status") == "retry_wait" and not self._retry_due(state):
                continue
            candidates.append(task)
        candidates.sort(
            key=lambda task: (
                0
                if str(account["id"]) in task.get("preferred_accounts", [])
                else 1,
                int(task.get("priority", 100)),
                int(self.state["tasks"][str(task["id"])].get("order") or 0),
            )
        )
        return candidates

    def _account_in_cooldown(self, account_id: str) -> bool:
        state = self.state["accounts"][account_id]
        account = self._account_by_id(account_id)
        provider = str(account.get("provider")) if account is not None else ""
        if account is not None and provider == "chatgpt":
            profile_base = expanded_path(account["profile_dir"], base_dir=self.base_dir)
            rate_state = load_json_object(
                profile_base / "chatgpt" / CHATGPT_RATE_LIMIT_STATE_NAME
            )
            try:
                persisted_deadline = float(rate_state.get("blocked_until") or 0)
            except (TypeError, ValueError):
                persisted_deadline = 0
            configured_deadline = parse_timestamp(state.get("cooldown_until")) or 0
            if persisted_deadline > max(self.wall_clock(), configured_deadline):
                state.update(
                    {
                        "status": "cooldown",
                        "cooldown_until": utc_now(persisted_deadline),
                        "failure_kind": str(rate_state.get("kind") or "rate_limit"),
                        "message": "ChatGPT 프로필 요청 제한 해제 대기",
                    }
                )
        elif account is not None and provider == "gemini":
            profile_base = expanded_path(account["profile_dir"], base_dir=self.base_dir)
            fallback_state = load_json_object(
                profile_base / "gemini" / "provider_fallback_state.json"
            )
            persisted_deadline = parse_timestamp(fallback_state.get("gemini_down_until")) or 0
            configured_deadline = parse_timestamp(state.get("cooldown_until")) or 0
            if persisted_deadline > max(self.wall_clock(), configured_deadline):
                state.update(
                    {
                        "status": "cooldown",
                        "cooldown_until": utc_now(persisted_deadline),
                        "failure_kind": "gemini_outage",
                        "message": "Gemini 일시 오류 냉각 후 자동 재개",
                    }
                )
        cooldown_until = parse_timestamp(state.get("cooldown_until"))
        if cooldown_until is None or cooldown_until <= self.wall_clock():
            if cooldown_until is not None:
                state.update(
                    {
                        "cooldown_until": None,
                        "failure_kind": None,
                        "status": "ready",
                        "message": "재시도 준비",
                    }
                )
            return False
        return True

    def _update_accounts_and_launch(self, occupancy: Mapping[str, dict[str, Any]]) -> None:
        for account in self._account_specs():
            account_id = str(account["id"])
            account_state = self.state["accounts"][account_id]
            if account_id in self.children:
                continue
            if account_id in occupancy:
                account_state.update({**occupancy[account_id], "source": "external"})
                continue
            if bool(account.get("standby")):
                account_state.update(
                    {
                        "status": "standby",
                        "task_id": None,
                        "pid": None,
                        "source": None,
                        "message": "신규 계정 대기 - 수동 활성화 전까지 작업 미배정",
                    }
                )
                continue
            if self.wall_clock() < self._launch_not_before:
                account_state.update(
                    {
                        "status": "reconnecting",
                        "task_id": None,
                        "pid": None,
                        "source": None,
                        "message": "기존 작업 인계 확인 중",
                    }
                )
                continue
            if self._account_in_cooldown(account_id):
                account_state.update({"task_id": None, "pid": None, "source": None})
                continue
            candidates = self._available_tasks(account)
            if not candidates:
                pending_compatible = any(
                    str(account["provider"]) in task["providers"]
                    and self.state["tasks"][str(task["id"])].get("status") not in TERMINAL_TASK_STATES
                    for task in self._task_specs()
                )
                account_state.update(
                    {
                        "status": "waiting" if pending_compatible else "idle_no_work",
                        "task_id": None,
                        "pid": None,
                        "source": None,
                        "message": "재시도 시각 대기" if pending_compatible else "실행 가능한 대기 작업 없음",
                    }
                )
                continue
            try:
                self._launch(account, candidates[0])
            except (OSError, SchedulerConfigurationError) as exc:
                task = candidates[0]
                self.state["tasks"][str(task["id"])].update(
                    {
                        "status": "retry_wait",
                        "next_attempt_at": utc_now(self.wall_clock() + 30),
                        "error": f"launch_failed: {exc}",
                    }
                )
                account_state.update({"status": "degraded", "message": str(exc), "task_id": None, "pid": None})
                self._event("task_launch_failed", task_id=str(task["id"]), account_id=account_id, error=str(exc))

    def _status_payload(self) -> dict[str, Any]:
        configured_tasks = {str(task["id"]): task for task in self._task_specs()}
        tasks = []
        for task_id, task in configured_tasks.items():
            state = dict(self.state["tasks"][task_id])
            tasks.append(
                {
                    "id": task_id,
                    "title": str(task["title"]),
                    "providers": list(task["providers"]),
                    "work_dir": str(self._task_work_dir(task)),
                    **state,
                }
            )
        status_counts: dict[str, int] = {}
        for task in tasks:
            status = str(task.get("status") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        accounts = []
        for spec in self._account_specs():
            account_id = str(spec["id"])
            accounts.append(
                {
                    "id": account_id,
                    "label": str(spec.get("label") or account_id),
                    "provider": str(spec["provider"]),
                    **dict(self.state["accounts"][account_id]),
                }
            )
        return {
            "version": STATE_VERSION,
            "updated_at": utc_now(self.wall_clock()),
            "scheduler": {
                "pid": os.getpid(),
                "status": "stopping" if self._stop_event.is_set() else "running",
                "started_at": self._started_at,
                "config_path": str(self.config_path),
                "state_dir": str(self.state_dir),
            },
            "summary": {
                "accounts_total": len(accounts),
                "accounts_working": sum(
                    1 for account in accounts if account.get("status") in {"running", "external", "reconnecting"}
                ),
                "tasks_total": len(tasks),
                "tasks_completed": status_counts.get("completed", 0),
                "tasks_blocked": status_counts.get("blocked", 0),
                "task_statuses": status_counts,
            },
            "operations_audit": dict(
                self.state.get("operations_audit", {}).get("latest") or {}
            ),
            "accounts": accounts,
            "tasks": tasks,
        }

    def _write_status(self) -> dict[str, Any]:
        payload = self._status_payload()
        atomic_write_json(self.status_path, payload, trailing_newline=True)
        return payload

    def tick(self) -> dict[str, Any]:
        self.config = self._load_config()
        self._initialize_state()
        self._poll_children()
        self._finalize_due_tasks()
        self._watchdog()
        process_output = self.process_reader()
        occupancy = self._scan_occupancy(process_output)
        self._update_accounts_and_launch(occupancy)
        self._run_operations_audit()
        self.state["scheduler"] = {
            "pid": os.getpid(),
            "status": "running",
            "heartbeat_at": utc_now(self.wall_clock()),
            "started_at": self._started_at,
        }
        self._save_state()
        return self._write_status()

    def run(self) -> None:
        self.acquire_lock()
        previous_handlers: dict[int, Any] = {}
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.signal(signum, self.request_stop)
        self._event("scheduler_started", pid=os.getpid(), config_path=str(self.config_path))
        try:
            while not self._stop_event.is_set():
                try:
                    self.tick()
                except BaseException as exc:
                    self.state["scheduler"] = {
                        "pid": os.getpid(),
                        "status": "degraded",
                        "heartbeat_at": utc_now(self.wall_clock()),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                    self._save_state()
                    self._write_status()
                    self._event("scheduler_tick_failed", error=f"{type(exc).__name__}: {exc}")
                self.sleeper(max(1.0, float(self.config.get("poll_seconds", 3))))
        finally:
            self.state["scheduler"].update({"status": "stopped", "heartbeat_at": utc_now(self.wall_clock())})
            self._save_state()
            self._write_status()
            self._event("scheduler_stopped", pid=os.getpid())
            for signum, handler in previous_handlers.items():
                signal.signal(signum, handler)
            self.release_lock()


def read_scheduler_status(path: Path, *, stale_seconds: int = 30) -> dict[str, Any]:
    payload = load_json_object(path)
    updated_at = parse_timestamp(payload.get("updated_at"))
    if updated_at is None:
        return {}
    payload["stale"] = time.time() - updated_at > stale_seconds
    return payload
