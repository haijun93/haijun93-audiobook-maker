from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from scripts.configure_pam_godwin_scheduler import build_config
from webui.continuous_scheduler import (
    ContinuousTranslationScheduler,
    SchedulerConfigurationError,
    parse_timestamp,
    validate_config,
)
from webui.workflow_diagnostics import WorkflowDiagnostics


class FakeProcess:
    next_pid = 7000

    def __init__(self, command: list[str], **kwargs: Any) -> None:
        self.command = command
        self.kwargs = kwargs
        self.pid = FakeProcess.next_pid
        FakeProcess.next_pid += 1
        self.returncode: int | None = None

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9


def write_config(path: Path, *, accounts: list[dict[str, Any]], tasks: list[dict[str, Any]]) -> Path:
    payload = {
        "repo_dir": str(path.parent),
        "python": "/usr/bin/python3",
        "poll_seconds": 1,
        "accounts": accounts,
        "tasks": tasks,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def account(tmp_path: Path, account_id: str, provider: str) -> dict[str, Any]:
    return {
        "id": account_id,
        "label": account_id,
        "provider": provider,
        "profile_dir": str(tmp_path / "profiles" / account_id),
    }


def task(
    tmp_path: Path,
    task_id: str,
    *,
    providers: list[str],
    preferred_account: str,
) -> dict[str, Any]:
    return {
        "id": task_id,
        "title": task_id.title(),
        "providers": providers,
        "preferred_accounts": [preferred_account],
        "work_dir": str(tmp_path / task_id / "work"),
        "command": ["{python}", "worker.py", "--work-dir", "{work_dir}", "--provider", "{provider}"],
        "completion_paths": [str(tmp_path / task_id / "done.epub")],
    }


def test_config_validation_rejects_duplicate_work_dirs(tmp_path: Path) -> None:
    first = task(tmp_path, "first", providers=["gemini"], preferred_account="main")
    second = task(tmp_path, "second", providers=["gemini"], preferred_account="main")
    second["work_dir"] = first["work_dir"]

    with pytest.raises(SchedulerConfigurationError, match="work_dir is duplicated"):
        validate_config(
            {
                "accounts": [account(tmp_path, "main", "gemini")],
                "tasks": [first, second],
            }
        )


def test_three_accounts_claim_distinct_preferred_tasks(tmp_path: Path) -> None:
    accounts = [
        account(tmp_path, "main", "gemini"),
        account(tmp_path, "account2", "gemini"),
        account(tmp_path, "chatgpt", "chatgpt"),
    ]
    tasks = [
        task(tmp_path, "main-book", providers=["gemini", "chatgpt"], preferred_account="main"),
        task(tmp_path, "second-book", providers=["gemini", "chatgpt"], preferred_account="account2"),
        task(tmp_path, "chat-book", providers=["gemini", "chatgpt"], preferred_account="chatgpt"),
    ]
    created: list[FakeProcess] = []

    def factory(command: list[str], **kwargs: Any) -> FakeProcess:
        process = FakeProcess(command, **kwargs)
        created.append(process)
        return process

    scheduler = ContinuousTranslationScheduler(
        write_config(tmp_path / "config.json", accounts=accounts, tasks=tasks),
        state_dir=tmp_path / "state",
        process_reader=lambda: "",
        popen_factory=factory,
    )

    status = scheduler.tick()

    assert len(created) == 3
    assert {state["task_id"] for state in status["accounts"]} == {
        "main-book",
        "second-book",
        "chat-book",
    }
    assert status["summary"]["accounts_working"] == 3
    assert len({state["pid"] for state in status["accounts"]}) == 3
    environments = [process.kwargs["env"] for process in created]
    assert {environment["AUDIOBOOK_SCHEDULER_ACCOUNT"] for environment in environments} == {
        "main",
        "account2",
        "chatgpt",
    }


def test_standby_account_is_never_assigned_pending_work(tmp_path: Path) -> None:
    active_account = account(tmp_path, "account2", "gemini")
    standby_account = account(tmp_path, "account3", "gemini")
    standby_account["standby"] = True
    tasks = [
        task(tmp_path, "first-book", providers=["gemini"], preferred_account="account2"),
        task(tmp_path, "second-book", providers=["gemini"], preferred_account="account3"),
    ]
    launches: list[FakeProcess] = []

    def factory(command: list[str], **kwargs: Any) -> FakeProcess:
        process = FakeProcess(command, **kwargs)
        launches.append(process)
        return process

    scheduler = ContinuousTranslationScheduler(
        write_config(
            tmp_path / "config.json",
            accounts=[active_account, standby_account],
            tasks=tasks,
        ),
        state_dir=tmp_path / "state",
        process_reader=lambda: "",
        popen_factory=factory,
    )

    status = scheduler.tick()

    assert len(launches) == 1
    accounts_by_id = {state["id"]: state for state in status["accounts"]}
    assert accounts_by_id["account2"]["status"] == "running"
    assert accounts_by_id["account3"]["status"] == "standby"
    assert accounts_by_id["account3"]["task_id"] is None
    assert status["summary"]["accounts_working"] == 1

    # The standby account must stay parked on repeated ticks even though a
    # compatible task ("second-book") is still pending.
    status_again = scheduler.tick()
    assert status_again["accounts"][
        [state["id"] for state in status_again["accounts"]].index("account3")
    ]["status"] == "standby"


def test_profile_lock_adopts_external_work_without_duplicate_launch(tmp_path: Path) -> None:
    account_spec = account(tmp_path, "main", "gemini")
    task_spec = task(tmp_path, "external-book", providers=["gemini"], preferred_account="main")
    profile_lock = Path(account_spec["profile_dir"]) / "gemini" / ".audiobook_web_profile.lock"
    profile_lock.parent.mkdir(parents=True)
    profile_lock.write_text(f"pid={os.getpid()} provider=gemini\n", encoding="utf-8")
    command = (
        f"/usr/bin/python scripts/backfill_study_notes.py --work-dir {task_spec['work_dir']} "
        "--web-provider gemini"
    )
    process_output = f"{os.getpid():5d}     1       01:00 S    {command}\n"
    launches: list[FakeProcess] = []

    scheduler = ContinuousTranslationScheduler(
        write_config(tmp_path / "config.json", accounts=[account_spec], tasks=[task_spec]),
        state_dir=tmp_path / "state",
        process_reader=lambda: process_output,
        popen_factory=lambda command, **kwargs: launches.append(FakeProcess(command, **kwargs)),
    )

    status = scheduler.tick()

    assert not launches
    assert status["accounts"][0]["status"] == "external"
    assert status["accounts"][0]["task_id"] == "external-book"
    assert status["tasks"][0]["status"] == "external"


def test_batch_wrapper_keeps_account_occupied_during_child_retry_gap(tmp_path: Path) -> None:
    account_spec = account(tmp_path, "account2", "gemini")
    task_spec = task(tmp_path, "mad-mabel", providers=["gemini"], preferred_account="account2")
    task_spec["command"] = [
        "{python}",
        "scripts/run_soseol2_chatgpt_k_e_batch.py",
        "--only",
        "14. MAD MABEL by Sally Hepworth",
        "--web-provider",
        "{provider}",
    ]
    command = (
        "/usr/bin/python scripts/run_soseol2_chatgpt_k_e_batch.py "
        "--only 14. MAD MABEL by Sally Hepworth --web-provider gemini"
    )
    process_output = f"{777:5d}     1       01:00 S    {command}\n"
    launches: list[FakeProcess] = []
    scheduler = ContinuousTranslationScheduler(
        write_config(tmp_path / "config.json", accounts=[account_spec], tasks=[task_spec]),
        state_dir=tmp_path / "state",
        process_reader=lambda: process_output,
        popen_factory=lambda command, **kwargs: launches.append(FakeProcess(command, **kwargs)),
    )

    status = scheduler.tick()

    assert launches == []
    assert status["accounts"][0]["status"] == "external"
    assert status["accounts"][0]["task_id"] == "mad-mabel"
    assert status["tasks"][0]["status"] == "external"


def test_running_worker_claims_account_before_browser_profile_lock_exists(tmp_path: Path) -> None:
    account_spec = account(tmp_path, "main", "gemini")
    active_task = task(tmp_path, "active-book", providers=["gemini"], preferred_account="main")
    waiting_task = task(tmp_path, "waiting-book", providers=["gemini"], preferred_account="main")
    command = (
        "/usr/bin/python scripts/translate_epub_with_chatgpt_web_to_study_epub.py "
        f"--work-dir {active_task['work_dir']} --web-provider gemini"
    )
    process_output = f"{777:5d}     1       01:00 R    {command}\n"
    launches: list[FakeProcess] = []
    scheduler = ContinuousTranslationScheduler(
        write_config(
            tmp_path / "config.json",
            accounts=[account_spec],
            tasks=[active_task, waiting_task],
        ),
        state_dir=tmp_path / "state",
        process_reader=lambda: process_output,
        popen_factory=lambda command, **kwargs: launches.append(FakeProcess(command, **kwargs)),
    )

    status = scheduler.tick()

    assert launches == []
    assert status["accounts"][0]["status"] == "external"
    assert status["accounts"][0]["task_id"] == "active-book"
    assert status["tasks"][0]["status"] == "external"
    assert status["tasks"][1]["status"] == "pending"


def test_restart_resets_dead_running_task_while_adopting_live_worker(tmp_path: Path) -> None:
    account_spec = account(tmp_path, "main", "gemini")
    stale_task = task(tmp_path, "stale-book", providers=["gemini"], preferred_account="main")
    active_task = task(tmp_path, "active-book", providers=["gemini"], preferred_account="main")
    command = (
        "/usr/bin/python scripts/translate_epub_with_chatgpt_web_to_study_epub.py "
        f"--work-dir {active_task['work_dir']} --web-provider gemini"
    )
    process_output = f"{777:5d}     1       01:00 R    {command}\n"
    scheduler = ContinuousTranslationScheduler(
        write_config(
            tmp_path / "config.json",
            accounts=[account_spec],
            tasks=[stale_task, active_task],
        ),
        state_dir=tmp_path / "state",
        process_reader=lambda: process_output,
        popen_factory=FakeProcess,
    )
    scheduler._initialize_state()
    scheduler.state["tasks"]["stale-book"].update(
        {"status": "running", "account_id": "main", "pid": 99_999_999}
    )

    status = scheduler.tick()

    tasks = {item["id"]: item for item in status["tasks"]}
    assert tasks["stale-book"]["status"] == "pending"
    assert tasks["active-book"]["status"] == "external"
    assert status["accounts"][0]["task_id"] == "active-book"


def test_live_task_pid_prevents_duplicate_launch_when_process_scan_is_empty(tmp_path: Path) -> None:
    account_spec = account(tmp_path, "main", "gemini")
    active_task = task(tmp_path, "active-book", providers=["gemini"], preferred_account="main")
    waiting_task = task(tmp_path, "waiting-book", providers=["gemini"], preferred_account="main")
    launches: list[FakeProcess] = []
    scheduler = ContinuousTranslationScheduler(
        write_config(
            tmp_path / "config.json",
            accounts=[account_spec],
            tasks=[active_task, waiting_task],
        ),
        state_dir=tmp_path / "state",
        process_reader=lambda: "",
        popen_factory=lambda command, **kwargs: launches.append(FakeProcess(command, **kwargs)),
    )
    scheduler._initialize_state()
    scheduler.state["tasks"]["active-book"].update(
        {"status": "running", "account_id": "main", "pid": os.getpid()}
    )

    status = scheduler.tick()

    assert launches == []
    assert status["accounts"][0]["status"] == "external"
    assert status["accounts"][0]["task_id"] == "active-book"


def test_live_account_pid_without_task_metadata_prevents_duplicate_launch(tmp_path: Path) -> None:
    account_spec = account(tmp_path, "account2", "gemini")
    waiting_task = task(tmp_path, "waiting-book", providers=["gemini"], preferred_account="account2")
    launches: list[FakeProcess] = []
    scheduler = ContinuousTranslationScheduler(
        write_config(tmp_path / "config.json", accounts=[account_spec], tasks=[waiting_task]),
        state_dir=tmp_path / "state",
        process_reader=lambda: "",
        popen_factory=lambda command, **kwargs: launches.append(FakeProcess(command, **kwargs)),
    )
    scheduler._initialize_state()
    scheduler.state["accounts"]["account2"].update(
        {"status": "external", "task_id": None, "pid": os.getpid(), "message": "existing batch"}
    )

    status = scheduler.tick()

    assert launches == []
    assert status["accounts"][0]["status"] == "external"
    assert status["accounts"][0]["message"] == "existing batch"


def test_startup_adoption_grace_waits_before_launching_new_work(tmp_path: Path) -> None:
    now = [1000.0]
    account_spec = account(tmp_path, "main", "gemini")
    task_spec = task(tmp_path, "waiting-book", providers=["gemini"], preferred_account="main")
    config_path = write_config(
        tmp_path / "config.json",
        accounts=[account_spec],
        tasks=[task_spec],
    )
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["startup_adoption_grace_seconds"] = 8
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    launches: list[FakeProcess] = []

    def factory(command: list[str], **kwargs: Any) -> FakeProcess:
        process = FakeProcess(command, **kwargs)
        launches.append(process)
        return process

    scheduler = ContinuousTranslationScheduler(
        config_path,
        state_dir=tmp_path / "state",
        process_reader=lambda: "",
        wall_clock=lambda: now[0],
        popen_factory=factory,
    )

    first = scheduler.tick()
    now[0] += 9
    second = scheduler.tick()

    assert first["accounts"][0]["status"] == "reconnecting"
    assert first["accounts"][0]["message"] == "기존 작업 인계 확인 중"
    assert len(launches) == 1
    assert second["accounts"][0]["status"] == "running"


def test_browser_launch_stage_uses_short_watchdog_threshold(tmp_path: Path) -> None:
    now = [1000.0]
    account_spec = account(tmp_path, "chatgpt", "chatgpt")
    task_spec = task(tmp_path, "active-book", providers=["chatgpt"], preferred_account="chatgpt")
    config_path = write_config(
        tmp_path / "config.json",
        accounts=[account_spec],
        tasks=[task_spec],
    )
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["browser_launch_stale_seconds"] = 60
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    scheduler = ContinuousTranslationScheduler(
        config_path,
        state_dir=tmp_path / "state",
        process_reader=lambda: "",
        wall_clock=lambda: now[0],
        popen_factory=FakeProcess,
    )
    scheduler.tick()
    process = scheduler.children["chatgpt"]["process"]
    work_dir = Path(task_spec["work_dir"])
    (work_dir / "heartbeat.json").write_text(
        json.dumps(
            {
                "timestamp": 1000,
                "pid": process.pid,
                "stage": "translation_playwright_launch",
            }
        ),
        encoding="utf-8",
    )
    now[0] = 1061

    status = scheduler.tick()

    assert process.returncode == -15
    assert status["tasks"][0]["terminating_stale"] is True


def test_watchdog_ignores_heartbeat_from_previous_process(tmp_path: Path) -> None:
    now = [1000.0]
    account_spec = account(tmp_path, "main", "gemini")
    task_spec = task(tmp_path, "active-book", providers=["gemini"], preferred_account="main")
    scheduler = ContinuousTranslationScheduler(
        write_config(tmp_path / "config.json", accounts=[account_spec], tasks=[task_spec]),
        state_dir=tmp_path / "state",
        process_reader=lambda: "",
        wall_clock=lambda: now[0],
        popen_factory=FakeProcess,
    )
    scheduler.tick()
    process = scheduler.children["main"]["process"]
    work_dir = Path(task_spec["work_dir"])
    (work_dir / "heartbeat.json").write_text(
        json.dumps(
            {
                "timestamp": 1,
                "pid": process.pid + 1,
                "stage": "translation_browser_launch",
            }
        ),
        encoding="utf-8",
    )
    now[0] = 2000

    status = scheduler.tick()

    assert process.returncode is None
    assert status["tasks"][0]["terminating_stale"] is False


def test_rate_limit_cools_only_failed_account_and_keeps_checkpoint_for_retry(tmp_path: Path) -> None:
    now = [1000.0]
    account_spec = account(tmp_path, "chatgpt", "chatgpt")
    task_spec = task(tmp_path, "limited-book", providers=["chatgpt"], preferred_account="chatgpt")
    created: list[FakeProcess] = []

    def factory(command: list[str], **kwargs: Any) -> FakeProcess:
        process = FakeProcess(command, **kwargs)
        created.append(process)
        return process

    scheduler = ContinuousTranslationScheduler(
        write_config(tmp_path / "config.json", accounts=[account_spec], tasks=[task_spec]),
        state_dir=tmp_path / "state",
        process_reader=lambda: "",
        wall_clock=lambda: now[0],
        popen_factory=factory,
    )
    scheduler.tick()
    tracker = WorkflowDiagnostics(Path(task_spec["work_dir"]), "study_note_backfill")
    tracker.start(stage="request_notes", total_units=20)
    tracker.observe_condition(kind="rate_limit", stage="rate_limit_wait", retry_after_sec=120)
    created[0].returncode = 1
    now[0] = 1001

    status = scheduler.tick()

    assert status["accounts"][0]["status"] == "cooldown"
    assert status["accounts"][0]["failure_kind"] == "rate_limit"
    assert parse_timestamp(status["accounts"][0]["cooldown_until"]) == 2201
    assert status["tasks"][0]["status"] == "retry_wait"
    assert status["tasks"][0]["attempts"] == 1
    assert Path(task_spec["work_dir"]).is_dir()


def test_chatgpt_profile_cooldown_prevents_early_scheduler_launch(tmp_path: Path) -> None:
    account_spec = account(tmp_path, "chatgpt", "chatgpt")
    task_spec = task(tmp_path, "limited-book", providers=["chatgpt"], preferred_account="chatgpt")
    rate_state = Path(account_spec["profile_dir"]) / "chatgpt" / ".chatgpt_rate_limit_state.json"
    rate_state.parent.mkdir(parents=True)
    rate_state.write_text(
        json.dumps({"kind": "conversation_rate_limit", "blocked_until": 2500}),
        encoding="utf-8",
    )
    launches: list[FakeProcess] = []
    scheduler = ContinuousTranslationScheduler(
        write_config(tmp_path / "config.json", accounts=[account_spec], tasks=[task_spec]),
        state_dir=tmp_path / "state",
        process_reader=lambda: "",
        wall_clock=lambda: 1000,
        popen_factory=lambda command, **kwargs: launches.append(FakeProcess(command, **kwargs)),
    )

    status = scheduler.tick()

    assert launches == []
    assert status["accounts"][0]["status"] == "cooldown"
    assert status["accounts"][0]["failure_kind"] == "conversation_rate_limit"
    assert parse_timestamp(status["accounts"][0]["cooldown_until"]) == 2500


def test_successful_task_deploys_artifact_atomically(tmp_path: Path) -> None:
    account_spec = account(tmp_path, "main", "gemini")
    task_spec = task(tmp_path, "finished-book", providers=["gemini"], preferred_account="main")
    source = tmp_path / "finished-book" / "built.epub"
    task_spec["deploy"] = [{"source": str(source), "destination": task_spec["completion_paths"][0]}]
    created: list[FakeProcess] = []

    def factory(command: list[str], **kwargs: Any) -> FakeProcess:
        process = FakeProcess(command, **kwargs)
        created.append(process)
        return process

    scheduler = ContinuousTranslationScheduler(
        write_config(tmp_path / "config.json", accounts=[account_spec], tasks=[task_spec]),
        state_dir=tmp_path / "state",
        process_reader=lambda: "",
        popen_factory=factory,
    )
    scheduler.tick()
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"complete epub")
    created[0].returncode = 0

    status = scheduler.tick()

    destination = Path(task_spec["completion_paths"][0])
    assert destination.read_bytes() == b"complete epub"
    assert status["tasks"][0]["status"] == "completed"
    assert status["summary"]["tasks_completed"] == 1


def test_queue_has_three_vk_tasks_and_nine_general_translation_pam_tasks(tmp_path: Path) -> None:
    config = build_config(
        library_root=tmp_path / "library",
        scratch_root=tmp_path / "scratch",
        state_dir=tmp_path / "state",
    )

    assert len(config["accounts"]) == 3
    assert len(config["tasks"]) == 12
    vk_tasks = config["tasks"][:3]
    pam_tasks = config["tasks"][3:]
    assert all(task_spec["providers"] == ["gemini"] for task_spec in vk_tasks)
    assert all(task_spec["preferred_accounts"] == ["account2"] for task_spec in vk_tasks)
    assert all(task_spec["priority"] < 0 for task_spec in vk_tasks)
    assert all(task_spec["providers"] == ["gemini", "chatgpt"] for task_spec in pam_tasks)
    assert all(task_spec["id"].startswith("pam-general-") for task_spec in pam_tasks)
    assert all("scripts/translate_epub_with_chatgpt_web_to_study_epub.py" in task_spec["command"] for task_spec in pam_tasks)
    assert all("scripts/backfill_study_notes.py" not in task_spec["command"] for task_spec in pam_tasks)
    assert all(task_spec["command"][task_spec["command"].index("--chunks-per-conversation") + 1] == "10" for task_spec in pam_tasks)
    assert all(len(task_spec["completion_paths"]) == 4 for task_spec in pam_tasks)
    assert {task_spec["preferred_accounts"][0] for task_spec in pam_tasks} == {
        "main",
        "account2",
        "chatgpt",
    }


def test_operations_audit_runs_once_per_thirty_minute_window(tmp_path: Path) -> None:
    now = [1000.0]
    account_spec = account(tmp_path, "main", "gemini")
    task_spec = task(tmp_path, "audit-book", providers=["gemini"], preferred_account="main")
    scheduler = ContinuousTranslationScheduler(
        write_config(tmp_path / "config.json", accounts=[account_spec], tasks=[task_spec]),
        state_dir=tmp_path / "state",
        process_reader=lambda: "",
        wall_clock=lambda: now[0],
        popen_factory=FakeProcess,
    )

    first = scheduler.tick()
    now[0] += 1799
    before_due = scheduler.tick()
    now[0] += 2
    second = scheduler.tick()

    assert first["operations_audit"]["sequence"] == 1
    assert before_due["operations_audit"]["sequence"] == 1
    assert second["operations_audit"]["sequence"] == 2
    assert (tmp_path / "state" / "operations_audits.jsonl").read_text(encoding="utf-8").count("\n") == 2
    assert (tmp_path / "state" / "latest_operations_audit.json").is_file()


def test_operations_audit_applies_safer_runtime_settings_after_provider_burst(tmp_path: Path) -> None:
    now = 10_000.0
    account_spec = account(tmp_path, "main", "gemini")
    task_spec = task(tmp_path, "burst-book", providers=["gemini"], preferred_account="main")
    work_dir = Path(task_spec["work_dir"])
    work_dir.mkdir(parents=True)
    (work_dir / "workflow_diagnostics.json").write_text(
        json.dumps({"status": "running", "progress": {"completed": 1, "total": 20}}),
        encoding="utf-8",
    )
    (work_dir / "heartbeat.json").write_text(
        json.dumps({"timestamp": now - 5}),
        encoding="utf-8",
    )
    events = [
        json.dumps(
                {
                    "timestamp": now,
                    "kind": "temporary_service_error",
                "error": "Gemini error_kind=temporary_service_error",
            }
        )
        for index in range(8)
    ]
    (work_dir / "adaptive_error_events.jsonl").write_text("\n".join(events) + "\n", encoding="utf-8")
    scheduler = ContinuousTranslationScheduler(
        write_config(tmp_path / "config.json", accounts=[account_spec], tasks=[task_spec]),
        state_dir=tmp_path / "state",
        process_reader=lambda: "",
        wall_clock=lambda: now,
        popen_factory=FakeProcess,
    )

    status = scheduler.tick()

    overrides = scheduler.state["tasks"]["burst-book"]["runtime_overrides"]
    assert overrides["web_max_attempts"] == 3
    assert overrides["inter_request_delay_sec"] >= 8
    assert status["operations_audit"]["summary"]["new_errors"] == 8
    assert status["operations_audit"]["summary"]["actions_applied"] == 1


def test_backfill_launch_injects_shared_fallback_and_conservative_request_controls(tmp_path: Path) -> None:
    account_spec = account(tmp_path, "main", "gemini")
    task_spec = task(tmp_path, "backfill-book", providers=["gemini"], preferred_account="main")
    task_spec["command"] = [
        "{python}",
        "scripts/backfill_study_notes.py",
        "--work-dir",
        "{work_dir}",
        "--web-provider",
        "{provider}",
    ]
    created: list[FakeProcess] = []

    def factory(command: list[str], **kwargs: Any) -> FakeProcess:
        process = FakeProcess(command, **kwargs)
        created.append(process)
        return process

    scheduler = ContinuousTranslationScheduler(
        write_config(tmp_path / "config.json", accounts=[account_spec], tasks=[task_spec]),
        state_dir=tmp_path / "state",
        process_reader=lambda: "",
        popen_factory=factory,
    )

    scheduler.tick()

    command = created[0].command
    assert command[command.index("--web-max-attempts") + 1] == "3"
    assert command[command.index("--inter-request-delay-sec") + 1] == "8.0"
    expected_state = Path(account_spec["profile_dir"]) / "gemini"
    assert Path(command[command.index("--provider-fallback-state-dir") + 1]) == expected_state


def test_backfill_launch_discards_checkpoint_invalidating_adaptive_chunk_size(tmp_path: Path) -> None:
    account_spec = account(tmp_path, "main", "gemini")
    task_spec = task(tmp_path, "backfill-book", providers=["gemini"], preferred_account="main")
    task_spec["command"] = [
        "{python}",
        "scripts/backfill_study_notes.py",
        "--work-dir",
        "{work_dir}",
        "--web-provider",
        "{provider}",
    ]
    created: list[FakeProcess] = []

    def factory(command: list[str], **kwargs: Any) -> FakeProcess:
        process = FakeProcess(command, **kwargs)
        created.append(process)
        return process

    scheduler = ContinuousTranslationScheduler(
        write_config(tmp_path / "config.json", accounts=[account_spec], tasks=[task_spec]),
        state_dir=tmp_path / "state",
        process_reader=lambda: "",
        popen_factory=factory,
    )
    scheduler.config = scheduler._load_config()
    scheduler._initialize_state()
    scheduler.state["tasks"]["backfill-book"]["runtime_overrides"] = {
        "max_chars_per_chunk": 4200,
        "note_max_attempts": 2,
    }

    scheduler.tick()

    command = created[0].command
    assert "--max-chars-per-chunk" not in command
    assert command[command.index("--note-max-attempts") + 1] == "2"
    assert "max_chars_per_chunk" not in scheduler.state["tasks"]["backfill-book"]["runtime_overrides"]
