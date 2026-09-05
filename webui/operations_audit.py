from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


ACTIVE_TASK_STATES = {"running", "external", "reconnecting"}
INTERRUPTED_TASK_STATES = {"blocked", "failed", "paused"}
PROVIDER_ERROR_KINDS = {
    "gemini_outage",
    "network_error",
    "service_unavailable",
    "temporary_service_error",
    "timeout_or_empty_response",
}
ACCOUNT_ERROR_KINDS = {
    "account_mismatch",
    "account_unavailable",
    "conversation_rate_limit",
    "rate_limit",
    "region_unavailable",
    "session_expired",
    "usage_limit",
}
FORMAT_ERROR_KINDS = {
    "missing_translation_ids",
    "translation_quality_failure",
}


def parse_audit_timestamp(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except (TypeError, ValueError):
        return None


def read_jsonl_since(path: Path, since: float) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    records: list[dict[str, Any]] = []
    for line in lines:
        try:
            payload = json.loads(line)
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        timestamp = parse_audit_timestamp(payload.get("timestamp"))
        if timestamp is not None and timestamp >= since:
            records.append(payload)
    return records


def _normalized_error_kind(event: Mapping[str, Any]) -> str:
    kind = str(event.get("kind") or "unknown_error")
    error = str(event.get("error") or "")
    lowered = error.lower()
    if "gemini_outage" in lowered:
        return "gemini_outage"
    if "누락된 id" in lowered or "중복 번역 id" in lowered:
        return "missing_translation_ids"
    if kind == "unknown_web_provider_error":
        return "unknown_error"
    return kind


def _new_error_events(work_dir: Path, since: float) -> list[dict[str, Any]]:
    adaptive = read_jsonl_since(work_dir / "adaptive_error_events.jsonl", since)
    if adaptive:
        return [
            {**event, "kind": _normalized_error_kind(event), "source": "adaptive"}
            for event in adaptive
        ]
    workflow = read_jsonl_since(work_dir / "workflow_events.jsonl", since)
    return [
        {**event, "kind": _normalized_error_kind(event), "source": "workflow"}
        for event in workflow
        if event.get("event") in {"failure", "condition_observed"}
    ]


def _progress_events(work_dir: Path, since: float) -> list[tuple[float, int]]:
    samples: list[tuple[float, int]] = []
    for event in read_jsonl_since(work_dir / "workflow_events.jsonl", since):
        completed = event.get("completed")
        timestamp = parse_audit_timestamp(event.get("timestamp"))
        if (
            event.get("event") == "progress"
            and isinstance(completed, int)
            and timestamp is not None
        ):
            if not samples or completed >= samples[-1][1]:
                samples.append((timestamp, completed))
    return samples


def _heartbeat_age(work_dir: Path, now: float) -> float | None:
    path = work_dir / "heartbeat.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        payload = {}
    timestamp = parse_audit_timestamp(payload.get("timestamp")) if isinstance(payload, dict) else None
    if timestamp is None:
        try:
            timestamp = path.stat().st_mtime
        except OSError:
            return None
    return max(0.0, now - timestamp)


def analyze_task_window(
    *,
    task_id: str,
    title: str,
    work_dir: Path,
    task_state: Mapping[str, Any],
    account_id: str | None,
    provider: str | None,
    now: float,
    period_start: float,
    baseline: Mapping[str, Any] | None,
    interval_seconds: int,
    heartbeat_stale_seconds: int,
    provider_error_threshold: int,
    format_error_threshold: int,
) -> dict[str, Any]:
    diagnostics_path = work_dir / "workflow_diagnostics.json"
    try:
        diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        diagnostics = {}
    if not isinstance(diagnostics, dict):
        diagnostics = {}

    progress = diagnostics.get("progress") if isinstance(diagnostics.get("progress"), dict) else {}
    completed = progress.get("completed") if isinstance(progress.get("completed"), int) else None
    total = progress.get("total") if isinstance(progress.get("total"), int) else None
    baseline_completed = baseline.get("completed") if isinstance(baseline, Mapping) else None
    started_at = parse_audit_timestamp(task_state.get("started_at"))
    baseline_at = (
        parse_audit_timestamp(baseline.get("audited_at"))
        if isinstance(baseline, Mapping)
        else None
    )
    event_period_start = max(period_start, baseline_at or 0, started_at or 0)
    progress_events = _progress_events(work_dir, period_start)
    samples = [completed_value for _timestamp, completed_value in progress_events]
    if isinstance(completed, int) and isinstance(baseline_completed, int):
        progress_delta = max(0, completed - baseline_completed)
    elif len(samples) >= 2:
        progress_delta = max(0, samples[-1] - samples[0])
    else:
        progress_delta = 0

    heartbeat_age = _heartbeat_age(work_dir, now)
    error_events = _new_error_events(work_dir, event_period_start)
    error_counts = Counter(str(event.get("kind") or "unknown_error") for event in error_events)
    provider_errors = sum(error_counts[kind] for kind in PROVIDER_ERROR_KINDS)
    account_errors = sum(error_counts[kind] for kind in ACCOUNT_ERROR_KINDS)
    format_errors = sum(error_counts[kind] for kind in FORMAT_ERROR_KINDS)
    status = str(task_state.get("status") or "pending")
    diagnostic_status = str(diagnostics.get("status") or "")
    active = status in ACTIVE_TASK_STATES
    observed_seconds = max(0.0, now - max(period_start, started_at or period_start))
    mature_window = baseline is not None and observed_seconds >= max(60, interval_seconds * 0.8)
    throughput_completed = (
        max(0, progress_events[-1][1] - progress_events[0][1])
        if len(progress_events) >= 2
        else 0
    )
    throughput_observed_seconds = (
        max(0.0, progress_events[-1][0] - progress_events[0][0])
        if len(progress_events) >= 2
        else 0.0
    )
    chunks_per_hour = (
        throughput_completed * 3600 / throughput_observed_seconds
        if throughput_completed > 0 and throughput_observed_seconds > 0
        else 0.0
    )
    seconds_per_chunk = (
        throughput_observed_seconds / throughput_completed
        if throughput_completed > 0 and throughput_observed_seconds > 0
        else None
    )
    error_rate = (
        len(error_events) / (progress_delta + len(error_events))
        if progress_delta + len(error_events) > 0
        else 0.0
    )

    kind = "healthy"
    severity = "info"
    root_cause = "No new delay, interruption, or error was detected in this audit window."
    action = "none"
    cooldown_seconds = 0
    restart_required = False

    if heartbeat_age is not None and heartbeat_age >= heartbeat_stale_seconds and active:
        kind = "heartbeat_stale"
        severity = "error"
        root_cause = "The worker is alive but its progress heartbeat exceeded the health limit."
        action = "restart_from_checkpoint"
        restart_required = True
    elif status in INTERRUPTED_TASK_STATES or (
        active and diagnostic_status in {"failed", "paused"}
    ):
        kind = "workflow_interrupted"
        severity = "error"
        root_cause = "The workflow entered a stopped or circuit-open state during this audit window."
        action = "schedule_safe_resume"
    elif status == "retry_wait":
        kind = "recovery_wait"
        severity = "warning"
        root_cause = "The scheduler already isolated this task and scheduled a controlled retry."
        action = "observe_scheduled_resume"
    elif account_errors:
        kind = error_counts.most_common(1)[0][0]
        severity = "error"
        root_cause = "The provider reported a new account, session, usage, or rate restriction."
        action = "cooldown_and_restart"
        cooldown_seconds = max(15 * 60, interval_seconds)
        restart_required = active
    elif provider_errors >= provider_error_threshold:
        kind = "provider_error_burst"
        severity = "error" if progress_delta == 0 or provider_errors >= max(1, progress_delta) * 2 else "warning"
        root_cause = "Transient provider failures repeated faster than useful progress was completed."
        action = "cooldown_and_restart" if severity == "error" else "increase_request_pacing"
        cooldown_seconds = max(10 * 60, interval_seconds // 2) if severity == "error" else 0
        restart_required = severity == "error" and active
    elif active and mature_window and progress_delta == 0:
        kind = "progress_stalled"
        severity = "error"
        root_cause = "The worker remained active for the audit window without completing a checkpoint."
        action = "restart_from_checkpoint"
        restart_required = True
    elif format_errors >= format_error_threshold:
        kind = "response_format_error_burst"
        severity = "warning"
        root_cause = "The provider repeatedly omitted or duplicated required response identifiers."
        action = "split_format_retries"
    elif error_events:
        kind = "new_errors_observed"
        severity = "warning"
        root_cause = "New errors occurred, but useful progress continued and no stop threshold was reached."
        action = "monitor_and_tune"

    return {
        "task_id": task_id,
        "title": title,
        "account_id": account_id,
        "provider": provider,
        "status": status,
        "kind": kind,
        "severity": severity,
        "root_cause": root_cause,
        "action": action,
        "restart_required": restart_required,
        "cooldown_seconds": cooldown_seconds,
        "evidence": {
            "completed": completed,
            "total": total,
            "progress_delta": progress_delta,
            "heartbeat_age_seconds": round(heartbeat_age, 1) if heartbeat_age is not None else None,
            "new_error_count": len(error_events),
            "error_counts": dict(sorted(error_counts.items())),
            "observed_seconds": round(observed_seconds),
            "throughput_completed": throughput_completed,
            "throughput_observed_seconds": round(throughput_observed_seconds),
            "chunks_per_hour": round(chunks_per_hour, 2),
            "seconds_per_chunk": round(seconds_per_chunk, 1) if seconds_per_chunk is not None else None,
            "error_rate": round(error_rate, 4),
            "error_period_start": event_period_start,
        },
        "baseline": {
            "completed": completed,
            "audited_at": now,
        },
    }


def summarize_provider_efficiency(findings: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for finding in findings:
        provider = str(finding.get("provider") or "").strip()
        evidence = finding.get("evidence")
        if not provider or not isinstance(evidence, Mapping):
            continue
        completed = int(
            evidence.get("throughput_completed")
            if evidence.get("throughput_completed") is not None
            else evidence.get("progress_delta")
            or 0
        )
        errors = int(evidence.get("new_error_count") or 0)
        observed_seconds = float(
            evidence.get("throughput_observed_seconds")
            if evidence.get("throughput_observed_seconds") is not None
            else evidence.get("observed_seconds")
            or 0
        )
        if completed <= 0 and errors <= 0 and observed_seconds <= 0:
            continue
        bucket = buckets.setdefault(
            provider,
            {
                "provider": provider,
                "tasks_observed": 0,
                "completed_chunks": 0,
                "new_errors": 0,
                "observed_worker_seconds": 0.0,
                "account_restriction_errors": 0,
                "provider_errors": 0,
            },
        )
        bucket["tasks_observed"] += 1
        bucket["completed_chunks"] += completed
        bucket["new_errors"] += errors
        bucket["observed_worker_seconds"] += observed_seconds
        error_counts = evidence.get("error_counts")
        if isinstance(error_counts, Mapping):
            bucket["account_restriction_errors"] += sum(
                int(error_counts.get(kind) or 0) for kind in ACCOUNT_ERROR_KINDS
            )
            bucket["provider_errors"] += sum(
                int(error_counts.get(kind) or 0) for kind in PROVIDER_ERROR_KINDS
            )

    summaries: list[dict[str, Any]] = []
    for provider, bucket in sorted(buckets.items()):
        completed = int(bucket["completed_chunks"])
        errors = int(bucket["new_errors"])
        observed_seconds = float(bucket.pop("observed_worker_seconds"))
        if int(bucket["account_restriction_errors"]):
            bottleneck = "account_restriction"
        elif int(bucket["provider_errors"]):
            bottleneck = "provider_errors"
        elif completed <= 0:
            bottleneck = "no_completed_checkpoint"
        else:
            bottleneck = "none"
        summaries.append(
            {
                **bucket,
                "provider": provider,
                "observed_worker_seconds": round(observed_seconds),
                "chunks_per_hour": round(
                    completed * 3600 / observed_seconds if observed_seconds > 0 else 0.0,
                    2,
                ),
                "seconds_per_chunk": round(
                    observed_seconds / completed if completed > 0 else 0.0,
                    1,
                ),
                "error_rate": round(
                    errors / (completed + errors) if completed + errors > 0 else 0.0,
                    4,
                ),
                "dominant_bottleneck": bottleneck,
            }
        )
    return summaries
