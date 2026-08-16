from __future__ import annotations

import json
from pathlib import Path

from webui.workflow_diagnostics import WorkflowDiagnostics, diagnose_failure, load_workflow_diagnostics


def test_diagnoses_structured_provider_pause() -> None:
    diagnosis = diagnose_failure(
        RuntimeError("ChatGPT error_kind=account_unavailable retry_action=pause_for_account_recovery")
    )

    assert diagnosis.kind == "account_unavailable"
    assert diagnosis.automatic is False
    assert diagnosis.safe_to_resume is True


def test_diagnostics_opens_circuit_for_repeated_format_failure(tmp_path: Path) -> None:
    tracker = WorkflowDiagnostics(tmp_path, "study_note_backfill")
    tracker.start(stage="request_notes", total_units=10)

    first = tracker.record_failure(
        RuntimeError("응답에서 누락된 ID: B00001"),
        stage="request_notes",
        attempt=1,
        max_attempts=3,
    )
    second = tracker.record_failure(
        RuntimeError("응답에서 누락된 ID: B00001"),
        stage="request_notes",
        attempt=2,
        max_attempts=3,
    )
    third = tracker.record_failure(
        RuntimeError("응답에서 누락된 ID: B00001"),
        stage="request_notes",
        attempt=3,
        max_attempts=3,
    )

    assert first["recovery"]["automatic_retry"] is True
    assert second["recovery"]["automatic_retry"] is True
    assert third["recovery"]["automatic_retry"] is False
    assert third["recovery"]["circuit_open"] is True


def test_progress_resets_failure_streak_and_completion_is_durable(tmp_path: Path) -> None:
    tracker = WorkflowDiagnostics(tmp_path, "epub_translation")
    tracker.start(stage="translate", total_units=2)
    tracker.record_failure(RuntimeError("network connection reset"), stage="translate", max_attempts=3)
    tracker.progress(stage="translate", completed=1, total=2, current=2, success=True)
    tracker.complete(artifacts={"output": "book.epub"})

    payload = load_workflow_diagnostics(tmp_path)
    assert payload["status"] == "complete"
    assert payload["health"]["consecutive_failures"] == 0
    assert payload["artifacts"] == {"output": "book.epub"}
    assert json.loads((tmp_path / "workflow_events.jsonl").read_text().splitlines()[-1])["event"] == "workflow_completed"


def test_invalid_source_is_not_automatically_retried(tmp_path: Path) -> None:
    tracker = WorkflowDiagnostics(tmp_path, "epub_translation")
    result = tracker.record_failure(
        RuntimeError("입력 EPUB를 찾지 못했습니다: missing.epub"),
        stage="validate_input",
        max_attempts=3,
    )

    assert result["diagnosis"]["kind"] == "invalid_input"
    assert result["recovery"]["automatic_retry"] is False
    assert result["recovery"]["safe_to_resume"] is False


def test_rate_limit_heartbeat_marks_running_workflow_degraded(tmp_path: Path) -> None:
    tracker = WorkflowDiagnostics(tmp_path, "study_note_backfill")
    tracker.start(stage="request_notes", total_units=10)

    tracker.observe_heartbeat(
        {
            "stage": "conversation_rate_limit_wait",
            "detail": "remaining=172s text=Please start a new chat",
        }
    )

    payload = load_workflow_diagnostics(tmp_path)
    assert payload["status"] == "running"
    assert payload["health"]["state"] == "degraded"
    assert payload["diagnosis"]["kind"] == "conversation_rate_limit"
    assert payload["recovery"]["automatic_retry"] is True
    assert payload["recovery"]["retry_after_sec"] == 172


def test_runtime_failures_are_classified_for_actionable_recovery() -> None:
    assert diagnose_failure(RuntimeError("Gemini API key를 찾지 못했습니다")).kind == "missing_credentials"
    assert diagnose_failure(RuntimeError("최종 합치기에는 ffmpeg가 필요합니다")).kind == "missing_dependency"
    assert diagnose_failure(RuntimeError("Chrome 에 로그인된 세션을 찾지 못했습니다")).kind == "session_expired"
    assert diagnose_failure(RuntimeError("HTTP 429 rate limit")).kind == "rate_limit"
