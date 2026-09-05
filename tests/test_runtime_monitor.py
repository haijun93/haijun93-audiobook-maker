from __future__ import annotations

import json
from pathlib import Path

from webui.runtime_monitor import RuntimeMonitor, command_option, parse_process_table, progress_velocity
from webui.workflow_diagnostics import WorkflowDiagnostics


def process_line(pid: int, command: str) -> str:
    return f"{pid:5d}     1       12:34 S    {command}\n"


def test_process_parser_ignores_shell_commands_that_only_mention_script_name() -> None:
    output = process_line(
        101,
        "/usr/bin/python scripts/backfill_study_notes.py --work-dir /tmp/book/work --web-provider chatgpt",
    ) + process_line(
        102,
        '/bin/zsh -lc "rg backfill_study_notes.py|web_app.py; sleep 10"',
    )

    records = parse_process_table(output)

    assert [record.pid for record in records] == [101]
    assert records[0].script_name == "backfill_study_notes.py"


def test_command_option_preserves_paths_with_spaces() -> None:
    command = (
        "/usr/bin/python scripts/backfill_study_notes.py "
        "--work-dir /private/tmp/notes/Dark Notes Pam Godwin (3.92)/work "
        "--web-provider chatgpt"
    )

    assert command_option(command, "work-dir") == "/private/tmp/notes/Dark Notes Pam Godwin (3.92)/work"


def test_runtime_snapshot_combines_process_heartbeat_and_diagnostics(tmp_path: Path) -> None:
    input_epub = tmp_path / "[e] Dark Notes.epub"
    input_epub.write_bytes(b"epub")
    work_dir = tmp_path / "Dark Notes Pam Godwin (3.92)" / "work"
    tracker = WorkflowDiagnostics(work_dir, "study_note_backfill")
    tracker.start(
        stage="request_notes",
        total_units=213,
        metadata={"provider": "chatgpt"},
        evidence_paths={"input_epub": input_epub},
    )
    tracker.progress(stage="request_notes", completed=35, total=213, current=35, success=True)
    tracker.observe_condition(kind="conversation_rate_limit", stage="conversation_rate_limit_wait", retry_after_sec=120)
    (work_dir / "heartbeat.json").write_text(
        json.dumps(
            {
                "timestamp": 990,
                "stage": "conversation_rate_limit_wait",
                "label": "학습노트 36/213",
                "detail": "remaining=120s",
            }
        ),
        encoding="utf-8",
    )
    command = (
        "/usr/bin/python scripts/backfill_study_notes.py "
        f"--input-epub {input_epub} --work-dir {work_dir} --web-provider chatgpt"
    )
    monitor = RuntimeMonitor(
        process_reader=lambda: process_line(95764, command),
        wall_clock=lambda: 1000,
        monotonic_clock=lambda: 1,
    )

    snapshot = monitor.snapshot(force=True)
    workflow = snapshot["workflows"][0]

    assert snapshot["summary"] == {"active": 1, "healthy": 0, "recovering": 1, "attention": 0}
    assert workflow["title"] == "Dark Notes"
    assert workflow["provider"] == "chatgpt"
    assert workflow["status"] == "recovering"
    assert workflow["progress"]["completed"] == 35
    assert workflow["progress"]["total"] == 213
    assert workflow["progress"]["current"] == 36
    assert workflow["heartbeat"]["age_seconds"] == 10
    assert workflow["diagnosis"]["kind"] == "conversation_rate_limit"


def test_stale_runtime_heartbeat_is_reported_as_stalled(tmp_path: Path) -> None:
    work_dir = tmp_path / "book" / "work"
    tracker = WorkflowDiagnostics(work_dir, "epub_translation")
    tracker.start(stage="translate", total_units=10)
    tracker.progress(stage="translate", completed=2, total=10, current=3, success=True)
    (work_dir / "heartbeat.json").write_text(
        json.dumps({"timestamp": 1, "stage": "wait_for_response", "label": "3/10"}),
        encoding="utf-8",
    )
    command = f"/usr/bin/python scripts/translate_epub_with_chatgpt_web_to_study_epub.py --work-dir {work_dir}"
    monitor = RuntimeMonitor(
        process_reader=lambda: process_line(555, command),
        wall_clock=lambda: 2000,
        monotonic_clock=lambda: 1,
    )

    workflow = monitor.snapshot(force=True)["workflows"][0]

    assert workflow["status"] == "stalled"
    assert workflow["health"] == "stalled"
    assert workflow["diagnosis"]["kind"] == "heartbeat_stale"


def test_missing_process_transitions_from_reconnecting_to_interrupted(tmp_path: Path) -> None:
    work_dir = tmp_path / "book" / "work"
    tracker = WorkflowDiagnostics(work_dir, "study_note_backfill")
    tracker.start(stage="request_notes", total_units=10)
    tracker.progress(stage="request_notes", completed=4, total=10, current=5, success=True)
    (work_dir / "heartbeat.json").write_text(
        json.dumps({"timestamp": 995, "stage": "wait_for_response", "label": "5/10"}),
        encoding="utf-8",
    )
    command = f"/usr/bin/python scripts/backfill_study_notes.py --work-dir {work_dir}"
    process_output = [process_line(777, command)]
    now = [1000.0]
    monotonic = [1.0]
    monitor = RuntimeMonitor(
        process_reader=lambda: process_output[0],
        wall_clock=lambda: now[0],
        monotonic_clock=lambda: monotonic[0],
    )
    assert monitor.snapshot(force=True)["workflows"][0]["status"] == "running"

    process_output[0] = ""
    now[0] = 1005
    monotonic[0] = 2
    reconnecting = monitor.snapshot(force=True)["workflows"][0]
    assert reconnecting["status"] == "reconnecting"

    now[0] = 1020
    monotonic[0] = 3
    interrupted = monitor.snapshot(force=True)["workflows"][0]
    assert interrupted["status"] == "interrupted"
    assert interrupted["diagnosis"]["kind"] == "child_process_failed"


def test_managed_retry_wait_is_removed_from_live_workflow_cards(tmp_path: Path) -> None:
    work_dir = tmp_path / "book" / "work"
    tracker = WorkflowDiagnostics(work_dir, "study_note_backfill")
    tracker.start(stage="request_notes", total_units=10)
    tracker.progress(stage="request_notes", completed=4, total=10, current=5, success=True)
    (work_dir / "heartbeat.json").write_text(
        json.dumps({"timestamp": 995, "stage": "wait_for_response", "label": "5/10"}),
        encoding="utf-8",
    )
    scheduler_status = tmp_path / "scheduler-status.json"
    scheduler_status.write_text(
        json.dumps(
            {
                "updated_at": "1970-01-01T00:16:40+00:00",
                "scheduler": {"status": "running"},
                "tasks": [
                    {
                        "id": "book",
                        "work_dir": str(work_dir),
                        "status": "retry_wait",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    command = f"/usr/bin/python scripts/backfill_study_notes.py --work-dir {work_dir}"
    process_output = [process_line(777, command)]
    now = [1000.0]
    monotonic = [1.0]
    monitor = RuntimeMonitor(
        process_reader=lambda: process_output[0],
        scheduler_status_path=scheduler_status,
        wall_clock=lambda: now[0],
        monotonic_clock=lambda: monotonic[0],
    )
    assert len(monitor.snapshot(force=True)["workflows"]) == 1

    process_output[0] = ""
    now[0] = 1020
    monotonic[0] = 2
    snapshot = monitor.snapshot(force=True)

    assert snapshot["workflows"] == []
    assert snapshot["summary"] == {"active": 0, "healthy": 0, "recovering": 0, "attention": 0}


def test_removed_scheduler_task_does_not_linger_after_process_exit(tmp_path: Path) -> None:
    work_dir = tmp_path / "retired-book" / "work"
    tracker = WorkflowDiagnostics(work_dir, "epub_translation")
    tracker.start(stage="translate_chunks", total_units=10)
    (work_dir / "heartbeat.json").write_text(
        json.dumps({"timestamp": 995, "stage": "wait_for_response", "label": "2/10"}),
        encoding="utf-8",
    )
    scheduler_status = tmp_path / "scheduler-status.json"
    scheduler_status.write_text(
        json.dumps(
            {
                "updated_at": "1970-01-01T00:16:40+00:00",
                "scheduler": {"status": "running"},
                "tasks": [{"id": "retired", "work_dir": str(work_dir), "status": "running"}],
            }
        ),
        encoding="utf-8",
    )
    command = (
        "/usr/bin/python scripts/translate_epub_with_chatgpt_web_to_study_epub.py "
        f"--work-dir {work_dir}"
    )
    process_output = [process_line(777, command)]
    now = [1000.0]
    monitor = RuntimeMonitor(
        process_reader=lambda: process_output[0],
        scheduler_status_path=scheduler_status,
        wall_clock=lambda: now[0],
        monotonic_clock=lambda: now[0],
    )
    assert len(monitor.snapshot(force=True)["workflows"]) == 1

    process_output[0] = ""
    now[0] = 1001
    scheduler_status.write_text(
        json.dumps(
            {
                "updated_at": "1970-01-01T00:16:41+00:00",
                "scheduler": {"status": "running"},
                "tasks": [],
            }
        ),
        encoding="utf-8",
    )

    assert monitor.snapshot(force=True)["workflows"] == []


def test_progress_velocity_uses_recent_completed_events(tmp_path: Path) -> None:
    events = tmp_path / "workflow_events.jsonl"
    events.write_text(
        "\n".join(
            json.dumps(
                {
                    "timestamp": timestamp,
                    "event": "progress",
                    "completed": completed,
                }
            )
            for timestamp, completed in (
                ("2026-08-15T10:00:00+00:00", 10),
                ("2026-08-15T10:30:00+00:00", 20),
                ("2026-08-15T11:00:00+00:00", 30),
            )
        ),
        encoding="utf-8",
    )

    velocity = progress_velocity(events, completed=30, total=50)

    assert velocity["units_per_hour"] == 20
    assert velocity["eta_seconds"] == 3600


def test_runtime_snapshot_includes_scheduler_account_slots(tmp_path: Path) -> None:
    scheduler_status = tmp_path / "scheduler-status.json"
    scheduler_status.write_text(
        json.dumps(
            {
                "updated_at": "1970-01-01T00:16:40+00:00",
                "scheduler": {"status": "running"},
                "operations_audit": {
                    "sequence": 3,
                    "status": "improved",
                    "next_run_at": "1970-01-01T00:46:40+00:00",
                    "summary": {"findings": 1, "new_errors": 6, "actions_applied": 1},
                },
                "accounts": [
                    {
                        "id": "main",
                        "label": "Gemini main",
                        "provider": "gemini",
                        "status": "running",
                        "task_id": "book-a",
                        "message": "Book A",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monitor = RuntimeMonitor(
        process_reader=lambda: "",
        scheduler_status_path=scheduler_status,
        wall_clock=lambda: 1005,
        monotonic_clock=lambda: 1,
    )

    snapshot = monitor.snapshot(force=True)

    assert snapshot["scheduler"] == {
        "status": "running",
        "updated_at": "1970-01-01T00:16:40+00:00",
        "stale": False,
    }
    assert snapshot["accounts"][0]["status"] == "running"
    assert snapshot["accounts"][0]["task_id"] == "book-a"
    assert snapshot["operations_audit"]["sequence"] == 3
    assert snapshot["operations_audit"]["summary"]["actions_applied"] == 1


def test_runtime_account_reflects_worker_rate_limit_cooldown(tmp_path: Path) -> None:
    work_dir = tmp_path / "book" / "work"
    tracker = WorkflowDiagnostics(work_dir, "study_note_backfill")
    tracker.start(stage="request_notes", total_units=10)
    tracker.observe_condition(
        kind="conversation_rate_limit",
        stage="conversation_rate_limit_wait",
        retry_after_sec=1200,
    )
    (work_dir / "heartbeat.json").write_text(
        json.dumps(
            {
                "timestamp": 1000,
                "stage": "conversation_rate_limit_wait",
                "label": "3/10",
                "detail": "remaining=1200s persisted=true",
            }
        ),
        encoding="utf-8",
    )
    scheduler_status = tmp_path / "scheduler-status.json"
    scheduler_status.write_text(
        json.dumps(
            {
                "updated_at": "1970-01-01T00:16:40+00:00",
                "scheduler": {"status": "running"},
                "accounts": [
                    {
                        "id": "chatgpt",
                        "provider": "chatgpt",
                        "status": "running",
                        "pid": 777,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    command = f"/usr/bin/python scripts/backfill_study_notes.py --work-dir {work_dir} --web-provider chatgpt"
    monitor = RuntimeMonitor(
        process_reader=lambda: process_line(777, command),
        scheduler_status_path=scheduler_status,
        wall_clock=lambda: 1005,
        monotonic_clock=lambda: 1,
    )

    snapshot = monitor.snapshot(force=True)

    assert snapshot["accounts"][0]["status"] == "cooldown"
    assert snapshot["accounts"][0]["failure_kind"] == "conversation_rate_limit"


def test_runtime_account_exposes_chatgpt_request_pacing(tmp_path: Path) -> None:
    work_dir = tmp_path / "book" / "work"
    tracker = WorkflowDiagnostics(work_dir, "study_note_backfill")
    tracker.start(stage="request_notes", total_units=10)
    (work_dir / "heartbeat.json").write_text(
        json.dumps(
            {
                "timestamp": 1000,
                "stage": "chatgpt_request_pacing",
                "label": "3/10",
                "detail": "remaining=240s interval=450s incidents_24h=1",
            }
        ),
        encoding="utf-8",
    )
    scheduler_status = tmp_path / "scheduler-status.json"
    scheduler_status.write_text(
        json.dumps(
            {
                "updated_at": "1970-01-01T00:16:40+00:00",
                "scheduler": {"status": "running"},
                "accounts": [
                    {
                        "id": "chatgpt",
                        "provider": "chatgpt",
                        "status": "running",
                        "pid": 778,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    command = f"/usr/bin/python scripts/backfill_study_notes.py --work-dir {work_dir} --web-provider chatgpt"
    monitor = RuntimeMonitor(
        process_reader=lambda: process_line(778, command),
        scheduler_status_path=scheduler_status,
        wall_clock=lambda: 1005,
        monotonic_clock=lambda: 1,
    )

    snapshot = monitor.snapshot(force=True)

    assert snapshot["accounts"][0]["status"] == "pacing"
    assert snapshot["accounts"][0]["message"].startswith("remaining=240s")
