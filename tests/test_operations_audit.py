from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from webui.operations_audit import analyze_task_window, summarize_provider_efficiency


def iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def write_diagnostics(
    work_dir: Path,
    *,
    completed: int,
    total: int = 20,
    status: str = "running",
) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "workflow_diagnostics.json").write_text(
        json.dumps(
            {
                "status": status,
                "progress": {"completed": completed, "total": total},
            }
        ),
        encoding="utf-8",
    )


def write_heartbeat(work_dir: Path, timestamp: float) -> None:
    (work_dir / "heartbeat.json").write_text(
        json.dumps({"timestamp": timestamp, "stage": "wait_for_response"}),
        encoding="utf-8",
    )


def write_errors(work_dir: Path, timestamp: float, kinds: list[str]) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(
            {
                "timestamp": iso(timestamp + index),
                "kind": kind,
                "error": f"error_kind={kind}",
            }
        )
        for index, kind in enumerate(kinds)
    ]
    (work_dir / "adaptive_error_events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze(
    work_dir: Path,
    *,
    now: float = 10_000,
    completed: int = 5,
    baseline_completed: int | None = 4,
    task_status: str = "running",
    diagnostic_status: str = "running",
    started_at: float | None = None,
) -> dict:
    write_diagnostics(work_dir, completed=completed, status=diagnostic_status)
    write_heartbeat(work_dir, now - 5)
    baseline = (
        {"completed": baseline_completed, "audited_at": now - 1800}
        if baseline_completed is not None
        else None
    )
    return analyze_task_window(
        task_id="book",
        title="Book",
        work_dir=work_dir,
        task_state={"status": task_status, "started_at": iso(started_at or now - 3600)},
        account_id="main",
        provider="gemini",
        now=now,
        period_start=now - 1800,
        baseline=baseline,
        interval_seconds=1800,
        heartbeat_stale_seconds=1800,
        provider_error_threshold=6,
        format_error_threshold=3,
    )


def test_audit_reports_healthy_when_progress_continues_without_new_errors(tmp_path: Path) -> None:
    finding = analyze(tmp_path / "work")

    assert finding["kind"] == "healthy"
    assert finding["evidence"]["progress_delta"] == 1
    assert finding["restart_required"] is False


def test_audit_detects_provider_error_burst_that_outpaces_progress(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    write_errors(work_dir, 8_300, ["temporary_service_error"] * 8)

    finding = analyze(work_dir)

    assert finding["kind"] == "provider_error_burst"
    assert finding["severity"] == "error"
    assert finding["restart_required"] is True
    assert finding["cooldown_seconds"] >= 900


def test_audit_detects_checkpoint_stall_with_fresh_heartbeat(tmp_path: Path) -> None:
    finding = analyze(tmp_path / "work", completed=5, baseline_completed=5)

    assert finding["kind"] == "progress_stalled"
    assert finding["restart_required"] is True


def test_audit_tunes_repeated_response_format_errors_without_stopping_progress(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    write_errors(work_dir, 8_300, ["missing_translation_ids"] * 3)

    finding = analyze(work_dir, completed=8, baseline_completed=4)

    assert finding["kind"] == "response_format_error_burst"
    assert finding["action"] == "split_format_retries"
    assert finding["restart_required"] is False


def test_audit_treats_existing_retry_wait_as_managed_recovery(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    write_errors(work_dir, 8_300, ["rate_limit"])

    finding = analyze(
        work_dir,
        task_status="retry_wait",
        diagnostic_status="paused",
    )

    assert finding["kind"] == "recovery_wait"
    assert finding["severity"] == "warning"
    assert finding["action"] == "observe_scheduled_resume"
    assert finding["restart_required"] is False


def test_audit_does_not_treat_error_before_current_run_as_new(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    write_errors(work_dir, 8_300, ["rate_limit"])

    finding = analyze(work_dir, started_at=9_900)

    assert finding["kind"] == "healthy"
    assert finding["evidence"]["new_error_count"] == 0


def test_provider_efficiency_compares_throughput_and_account_restrictions() -> None:
    metrics = summarize_provider_efficiency(
        [
            {
                "provider": "gemini",
                "evidence": {
                    "progress_delta": 23,
                    "new_error_count": 2,
                    "observed_seconds": 1800,
                    "error_counts": {"prompt_interaction_failed": 2},
                },
            },
            {
                "provider": "chatgpt",
                "evidence": {
                    "progress_delta": 0,
                    "new_error_count": 1,
                    "observed_seconds": 1800,
                    "error_counts": {"rate_limit": 1},
                },
            },
        ]
    )

    by_provider = {metric["provider"]: metric for metric in metrics}
    assert by_provider["gemini"]["chunks_per_hour"] == 46
    assert by_provider["gemini"]["error_rate"] == 0.08
    assert by_provider["chatgpt"]["chunks_per_hour"] == 0
    assert by_provider["chatgpt"]["dominant_bottleneck"] == "account_restriction"
