from __future__ import annotations

import errno
import json
import os
import platform
import re
import shutil
import sys
import traceback
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from webui.storage import atomic_write_json


DIAGNOSTICS_SCHEMA_VERSION = 1
DIAGNOSTICS_FILE = "workflow_diagnostics.json"
EVENTS_FILE = "workflow_events.jsonl"
MAX_INCIDENTS = 50
MAX_RUN_HISTORY = 12


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class FailureDiagnosis:
    kind: str
    category: str
    root_cause: str
    scope: str
    severity: str
    action: str
    automatic: bool
    safe_to_resume: bool
    retry_after_sec: int
    attempt_limit: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_DIAGNOSES: dict[str, FailureDiagnosis] = {
    "conversation_rate_limit": FailureDiagnosis(
        "conversation_rate_limit", "provider_capacity", "The active conversation is temporarily throttled.",
        "conversation", "warning", "Start a fresh conversation, cool down briefly, and resume from cache.",
        True, True, 180, 3,
    ),
    "usage_limit": FailureDiagnosis(
        "usage_limit", "provider_capacity", "The configured or provider usage window is exhausted.",
        "account", "warning", "Wait for the usage window to reset, then resume from cache.",
        False, True, 1800, 1,
    ),
    "rate_limit": FailureDiagnosis(
        "rate_limit", "provider_capacity", "The provider is throttling this account or conversation.",
        "account", "warning", "Pause requests and resume after the provider cooldown.",
        False, True, 300, 1,
    ),
    "account_unavailable": FailureDiagnosis(
        "account_unavailable", "provider_account", "The provider restricted or disabled the active account.",
        "account", "critical", "Verify the account in the browser profile before resuming.",
        False, True, 900, 1,
    ),
    "session_expired": FailureDiagnosis(
        "session_expired", "provider_session", "The saved browser session is no longer authenticated.",
        "session", "error", "Sign in again with the same browser profile, then resume.",
        False, True, 60, 1,
    ),
    "region_unavailable": FailureDiagnosis(
        "region_unavailable", "provider_region", "The provider is unavailable for the active region or account.",
        "account", "critical", "Use an available account or provider, then resume from cache.",
        False, True, 900, 1,
    ),
    "profile_in_use": FailureDiagnosis(
        "profile_in_use", "local_concurrency", "Another process owns the same persistent browser profile.",
        "process", "warning", "Wait for the profile owner to finish or stop the duplicate process.",
        False, True, 30, 1,
    ),
    "missing_credentials": FailureDiagnosis(
        "missing_credentials", "provider_credentials", "A required provider API key or login credential is missing.",
        "account", "critical", "Configure the credential or sign in with the selected browser profile, then resume.",
        False, True, 0, 1,
    ),
    "missing_dependency": FailureDiagnosis(
        "missing_dependency", "local_dependency", "A required local executable or Python dependency is unavailable.",
        "system", "critical", "Install or configure the named dependency, then resume from existing checkpoints.",
        False, True, 0, 1,
    ),
    "browser_launch_failed": FailureDiagnosis(
        "browser_launch_failed", "browser_runtime", "The persistent browser process could not start or remain available.",
        "process", "error", "Close stale browser processes, verify the profile, and retry once from checkpoints.",
        True, True, 10, 2,
    ),
    "temporary_service_error": FailureDiagnosis(
        "temporary_service_error", "provider_transient", "The provider returned a temporary service failure.",
        "request", "warning", "Retry with exponential backoff or switch provider when allowed.",
        True, True, 15, 5,
    ),
    "gemini_outage": FailureDiagnosis(
        "gemini_outage", "provider_transient", "Gemini returned a burst of temporary service failures.",
        "account", "warning", "Cool down the affected Gemini profile, then resume from checkpoints.",
        False, True, 300, 1,
    ),
    "network_error": FailureDiagnosis(
        "network_error", "network", "The browser could not reliably reach the provider.",
        "request", "warning", "Reopen the page and retry after a short delay.",
        True, True, 5, 4,
    ),
    "timeout_or_empty_response": FailureDiagnosis(
        "timeout_or_empty_response", "provider_timeout", "The provider did not finish a usable response in time.",
        "request", "warning", "Start a fresh request and retry with backoff.",
        True, True, 10, 3,
    ),
    "prompt_interaction_failed": FailureDiagnosis(
        "prompt_interaction_failed", "browser_interaction", "The provider page was not ready for prompt submission.",
        "session", "warning", "Reload the page, wait for controls to settle, and retry.",
        True, True, 8, 3,
    ),
    "missing_message_id": FailureDiagnosis(
        "missing_message_id", "response_integrity", "The response arrived without a stable provider message identifier.",
        "request", "warning", "Retry in a fresh conversation and retain the raw response as evidence.",
        True, True, 5, 2,
    ),
    "missing_translation_ids": FailureDiagnosis(
        "missing_translation_ids", "response_integrity", "The model response omitted or duplicated required segment IDs.",
        "chunk", "error", "Retry with a strict format reminder, then split the chunk if needed.",
        True, True, 2, 3,
    ),
    "translation_quality_failure": FailureDiagnosis(
        "translation_quality_failure", "content_quality", "The response failed translation quality checks.",
        "chunk", "error", "Retry in a fresh conversation with smaller subchunks.",
        True, True, 2, 3,
    ),
    "content_refusal": FailureDiagnosis(
        "content_refusal", "provider_policy", "The provider declined the literary transformation request.",
        "chunk", "warning", "Use the literary-context prompt, then smaller subchunks or the configured local fallback.",
        True, True, 2, 3,
    ),
    "minor_context_refusal": FailureDiagnosis(
        "minor_context_refusal", "provider_policy", "The provider declined a context involving a minor.",
        "chunk", "warning", "Use the non-explicit context prompt, then split or use the configured local fallback.",
        True, True, 2, 3,
    ),
    "prompt_too_long": FailureDiagnosis(
        "prompt_too_long", "request_shape", "The request exceeds the provider context or input limit.",
        "chunk", "error", "Reduce the chunk size and retry without discarding completed cache entries.",
        True, True, 1, 2,
    ),
    "source_cache_mismatch": FailureDiagnosis(
        "source_cache_mismatch", "input_integrity", "Source block IDs do not match the preserved translation cache.",
        "input", "critical", "Select the matching legacy manifest or use the deployed bilingual EPUB as the source.",
        False, False, 0, 1,
    ),
    "invalid_input": FailureDiagnosis(
        "invalid_input", "input_integrity", "The input is missing, unreadable, unsupported, or structurally invalid.",
        "input", "critical", "Repair or replace the input before restarting the workflow.",
        False, False, 0, 1,
    ),
    "output_validation_failed": FailureDiagnosis(
        "output_validation_failed", "output_integrity", "A generated artifact failed integrity or cleanup validation.",
        "output", "critical", "Keep the previous artifact, inspect validation evidence, and rebuild after correction.",
        False, True, 0, 1,
    ),
    "disk_full": FailureDiagnosis(
        "disk_full", "local_resource", "The destination filesystem has insufficient free space.",
        "system", "critical", "Free disk space and resume from the existing cache.",
        False, True, 0, 1,
    ),
    "permission_denied": FailureDiagnosis(
        "permission_denied", "local_permission", "The process cannot read or write a required path.",
        "system", "critical", "Correct file ownership or permissions before resuming.",
        False, True, 0, 1,
    ),
    "child_process_failed": FailureDiagnosis(
        "child_process_failed", "subprocess", "A child workflow exited without a more specific diagnosis.",
        "process", "error", "Inspect the child diagnostic file and log before one conservative retry.",
        True, True, 15, 2,
    ),
    "heartbeat_stale": FailureDiagnosis(
        "heartbeat_stale", "process_health", "The process is alive but has not reported progress within the health window.",
        "process", "warning", "Inspect the current stage and process log before deciding whether to stop or resume it.",
        False, True, 0, 1,
    ),
    "progress_stalled": FailureDiagnosis(
        "progress_stalled", "process_health", "The process remained alive without completing a checkpoint.",
        "process", "warning", "Restart once from the last completed checkpoint with safer request settings.",
        False, True, 60, 1,
    ),
    "unknown_error": FailureDiagnosis(
        "unknown_error", "unknown", "The failure did not match the current error taxonomy.",
        "workflow", "error", "Inspect the traceback and evidence before retrying more than once.",
        True, True, 15, 2,
    ),
}


def _explicit_error_kind(message: str) -> str | None:
    match = re.search(r"error_kind=([a-z_]+)", message.lower())
    return match.group(1) if match else None


def infer_failure_kind(error: BaseException | str, explicit_kind: str | None = None) -> str:
    if explicit_kind:
        return explicit_kind if explicit_kind in _DIAGNOSES else "unknown_error"
    message = str(error)
    lowered = message.lower()
    structured = _explicit_error_kind(message)
    if structured:
        return structured if structured in _DIAGNOSES else "unknown_error"
    if isinstance(error, PermissionError) or "permission denied" in lowered:
        return "permission_denied"
    if isinstance(error, OSError) and getattr(error, "errno", None) == errno.ENOSPC:
        return "disk_full"
    if "no space left" in lowered or "disk full" in lowered:
        return "disk_full"
    if "error_kind=profile_in_use" in lowered or "profile is already in use" in lowered:
        return "profile_in_use"
    if any(marker in lowered for marker in ("api key", "api_key", "credential")) and any(
        marker in lowered for marker in ("missing", "not found", "찾지 못", "필요")
    ):
        return "missing_credentials"
    if ("로그인" in message and "세션" in message) or any(
        marker in lowered for marker in ("session expired", "sign in again", "not authenticated")
    ):
        return "session_expired"
    if any(marker in lowered for marker in ("ffmpeg", "ffprobe", "chrome executable", "python dependency")) and any(
        marker in lowered for marker in ("not found", "missing", "install", "찾지 못", "필요")
    ):
        return "missing_dependency"
    if any(marker in lowered for marker in ("browser closed", "browser launch", "target page, context or browser has been closed")):
        return "browser_launch_failed"
    # Playwright의 Locator.fill/click 타임아웃 오류는 실패한 호출의 인자(우리가 보낸 프롬프트
    # 원문)를 "Call log:"에 그대로 에코해서 남긴다. 그 프롬프트 안에는 모델이 번역을 거절하지
    # 말라고 지시하는 문장("...번역을 거절할 필요가 없습니다")이 들어있어서, 실제로는 UI
    # 상호작용 타임아웃일 뿐인데 아래 "거절" 텍스트 검사에 걸려 content_refusal로 오분류되는
    # 사례가 실제로 있었다(2026-08-16, Dark Notes가 프롬프트 입력창 fill 타임아웃을 15번
    # content_refusal로 오판정당해 재시도만 반복했다). 이런 구조적 타임아웃 신호는 프롬프트
    # 내용 기반 판정보다 먼저 확인한다.
    if "call log:" in lowered and ("timeout" in lowered and "exceeded" in lowered):
        return "prompt_interaction_failed"
    if "429" in lowered or "rate limit" in lowered or "요청 제한" in message:
        return "rate_limit"
    if "gemini_outage" in lowered:
        return "gemini_outage"
    if "캐시에 없는 블록" in message or "cache mismatch" in lowered or "source cache" in lowered:
        return "source_cache_mismatch"
    if any(marker in lowered for marker in ("input epub", "unsupported book format", "no supported source")):
        return "invalid_input"
    if any(marker in message for marker in ("찾지 못했습니다", "섹션을 하나도 추출", "원본 소스")):
        return "invalid_input"
    if any(marker in lowered for marker in ("validation failed", "integrity failed", "watermark cleanup")):
        return "output_validation_failed"
    if "워터마크 삭제 검증" in message or "epub를 만들 수 없습니다" in message:
        return "output_validation_failed"
    if "누락" in message and ("id" in lowered or "번역" in message or "학습노트" in message):
        return "missing_translation_ids"
    if "translation_quality_failed" in lowered or "quality check" in lowered:
        return "translation_quality_failure"
    if "거절" in message or "refusal" in lowered or "can't help with that" in lowered:
        return "content_refusal"
    if "prompt" in lowered and any(marker in lowered for marker in ("too long", "interaction", "textbox")):
        return "prompt_too_long" if "too long" in lowered else "prompt_interaction_failed"
    if "message_id" in lowered:
        return "missing_message_id"
    if any(marker in lowered for marker in ("timeout", "timed out", "empty response")) or "시간 초과" in message:
        return "timeout_or_empty_response"
    if any(marker in lowered for marker in ("network", "connection reset", "connection refused", "dns")):
        return "network_error"
    if error.__class__.__name__ == "CalledProcessError":
        return "child_process_failed"
    return "unknown_error"


def diagnose_failure(error: BaseException | str, *, explicit_kind: str | None = None) -> FailureDiagnosis:
    return _DIAGNOSES[infer_failure_kind(error, explicit_kind)]


def runtime_evidence(work_dir: Path, paths: dict[str, Path | None] | None = None) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "pid": os.getpid(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "work_dir": str(work_dir),
    }
    try:
        usage = shutil.disk_usage(work_dir)
        evidence["disk_free_bytes"] = usage.free
    except OSError:
        pass
    path_evidence: dict[str, Any] = {}
    for label, value in (paths or {}).items():
        if value is None:
            continue
        path = Path(value)
        entry: dict[str, Any] = {"path": str(path), "exists": path.exists()}
        try:
            if path.is_file():
                entry["size_bytes"] = path.stat().st_size
        except OSError as exc:
            entry["inspection_error"] = str(exc)[:300]
        path_evidence[label] = entry
    if path_evidence:
        evidence["paths"] = path_evidence
    return evidence


def load_workflow_diagnostics(path_or_dir: Path) -> dict[str, Any]:
    path = Path(path_or_dir)
    if path.is_dir() or path.suffix.lower() != ".json":
        path = path / DIAGNOSTICS_FILE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


class WorkflowDiagnostics:
    def __init__(self, work_dir: Path, workflow: str):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.work_dir / DIAGNOSTICS_FILE
        self.events_path = self.work_dir / EVENTS_FILE
        self.workflow = workflow
        self._state = load_workflow_diagnostics(self.path)
        self.run_id = str(self._state.get("run_id") or uuid.uuid4().hex)

    def _append_event(self, event: dict[str, Any]) -> None:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _write(self, event_type: str, **event_fields: Any) -> None:
        now = utc_now()
        self._state["updated_at"] = now
        atomic_write_json(self.path, self._state)
        self._append_event(
            {
                "timestamp": now,
                "run_id": self.run_id,
                "workflow": self.workflow,
                "event": event_type,
                **event_fields,
            }
        )

    def start(
        self,
        *,
        stage: str,
        total_units: int | None = None,
        metadata: dict[str, Any] | None = None,
        evidence_paths: dict[str, Path | None] | None = None,
    ) -> None:
        now = utc_now()
        previous = self._state
        self.run_id = uuid.uuid4().hex
        history = list(previous.get("run_history") or []) if isinstance(previous, dict) else []
        if previous.get("run_id") and previous.get("run_id") != self.run_id:
            history.append(
                {
                    "run_id": previous.get("run_id"),
                    "started_at": previous.get("started_at"),
                    "updated_at": previous.get("updated_at"),
                    "status": previous.get("status"),
                    "diagnosis": previous.get("diagnosis"),
                }
            )
        lifetime_counts = dict(previous.get("lifetime_failure_counts") or {})
        self._state = {
            "schema_version": DIAGNOSTICS_SCHEMA_VERSION,
            "workflow": self.workflow,
            "run_id": self.run_id,
            "status": "running",
            "started_at": now,
            "updated_at": now,
            "current_stage": stage,
            "progress": {"completed": 0, "total": total_units, "current": None},
            "health": {
                "state": "healthy",
                "consecutive_failures": 0,
                "total_failures": 0,
                "last_success_at": now,
            },
            "diagnosis": None,
            "recovery": None,
            "incidents": [],
            "lifetime_failure_counts": lifetime_counts,
            "metadata": metadata or {},
            "runtime": runtime_evidence(self.work_dir, evidence_paths),
            "run_history": history[-MAX_RUN_HISTORY:],
        }
        self._write("workflow_started", stage=stage, total_units=total_units)

    def progress(
        self,
        *,
        stage: str,
        completed: int | None = None,
        total: int | None = None,
        current: str | int | None = None,
        detail: str = "",
        success: bool = False,
    ) -> None:
        if not self._state.get("run_id"):
            self.start(stage=stage, total_units=total)
        self._state["status"] = "running"
        self._state["current_stage"] = stage
        progress = self._state.setdefault("progress", {})
        if completed is not None:
            progress["completed"] = completed
        if total is not None:
            progress["total"] = total
        progress["current"] = current
        if detail:
            progress["detail"] = detail[:1000]
        if success:
            health = self._state.setdefault("health", {})
            health["state"] = "healthy"
            health["consecutive_failures"] = 0
            health["last_success_at"] = utc_now()
            self._state["diagnosis"] = None
            self._state["recovery"] = None
        self._write("progress", stage=stage, completed=completed, total=total, current=current)

    def record_failure(
        self,
        error: BaseException | str,
        *,
        stage: str,
        attempt: int = 1,
        max_attempts: int = 3,
        explicit_kind: str | None = None,
        explicit_action: str | None = None,
        evidence: dict[str, Any] | None = None,
        traceback_text: str | None = None,
    ) -> dict[str, Any]:
        if not self._state.get("run_id"):
            self.start(stage=stage)
        diagnosis = diagnose_failure(error, explicit_kind=explicit_kind)
        health = self._state.setdefault("health", {})
        previous_diagnosis = self._state.get("diagnosis") or {}
        same_cause = previous_diagnosis.get("kind") == diagnosis.kind
        streak = int(health.get("consecutive_failures") or 0) + 1 if same_cause else 1
        total_failures = int(health.get("total_failures") or 0) + 1
        effective_limit = max(1, min(max_attempts, diagnosis.attempt_limit))
        should_retry = diagnosis.automatic and attempt < effective_limit and streak < effective_limit
        recovery = {
            "automatic_retry": should_retry,
            "attempt": attempt,
            "attempt_limit": effective_limit,
            "retry_after_sec": diagnosis.retry_after_sec if should_retry else 0,
            "safe_to_resume": diagnosis.safe_to_resume,
            "action": explicit_action or diagnosis.action,
            "circuit_open": diagnosis.automatic and not should_retry,
        }
        state_status = "retrying" if should_retry else ("paused" if diagnosis.safe_to_resume else "failed")
        now = utc_now()
        incident = {
            "timestamp": now,
            "stage": stage,
            "attempt": attempt,
            "kind": diagnosis.kind,
            "category": diagnosis.category,
            "error": str(error)[:2000],
            "evidence": evidence or {},
        }
        if traceback_text:
            incident["traceback"] = traceback_text[-6000:]
        incidents = list(self._state.get("incidents") or [])
        incidents.append(incident)
        counts = dict(self._state.get("lifetime_failure_counts") or {})
        counts[diagnosis.kind] = int(counts.get(diagnosis.kind) or 0) + 1
        self._state.update(
            {
                "status": state_status,
                "current_stage": stage,
                "diagnosis": diagnosis.to_dict(),
                "recovery": recovery,
                "incidents": incidents[-MAX_INCIDENTS:],
                "lifetime_failure_counts": counts,
            }
        )
        health.update(
            {
                "state": "degraded" if should_retry else state_status,
                "consecutive_failures": streak,
                "total_failures": total_failures,
                "last_failure_at": now,
            }
        )
        self._write(
            "failure",
            stage=stage,
            kind=diagnosis.kind,
            attempt=attempt,
            automatic_retry=should_retry,
        )
        return {"diagnosis": diagnosis.to_dict(), "recovery": recovery, "status": state_status}

    def observe_condition(
        self,
        *,
        kind: str,
        stage: str,
        detail: str = "",
        retry_after_sec: int | None = None,
    ) -> None:
        if not self._state.get("run_id"):
            self.start(stage=stage)
        diagnosis = diagnose_failure(f"error_kind={kind}", explicit_kind=kind)
        health = self._state.setdefault("health", {})
        health["state"] = "degraded"
        health["observed_condition_at"] = utc_now()
        recovery = {
            "automatic_retry": True,
            "attempt": None,
            "attempt_limit": diagnosis.attempt_limit,
            "retry_after_sec": diagnosis.retry_after_sec
            if retry_after_sec is None
            else max(0, retry_after_sec),
            "safe_to_resume": diagnosis.safe_to_resume,
            "action": diagnosis.action,
            "circuit_open": False,
        }
        self._state.update(
            {
                "status": "running",
                "current_stage": stage,
                "diagnosis": diagnosis.to_dict(),
                "recovery": recovery,
                "observed_condition": {"kind": kind, "stage": stage, "detail": detail[:1000]},
            }
        )
        self._write("condition_observed", stage=stage, kind=kind, detail=detail[:500])

    def observe_heartbeat(self, payload: dict[str, object]) -> None:
        stage = str(payload.get("stage") or "")
        detail = str(payload.get("detail") or "")
        if "conversation_rate_limit" in stage:
            kind = "conversation_rate_limit"
        elif "rate_limit" in stage:
            kind = "rate_limit"
        elif any(marker in stage for marker in ("temporary_error", "notice_retry", "provider_switch")):
            kind = "temporary_service_error"
        else:
            return
        retry_after = None
        match = re.search(r"(?:remaining|sleep_sec|retry_in)=([0-9]+)", detail)
        if match:
            retry_after = int(match.group(1))
        self.observe_condition(
            kind=kind,
            stage=stage,
            detail=detail,
            retry_after_sec=retry_after,
        )

    def record_current_exception(
        self,
        error: BaseException,
        *,
        stage: str,
        explicit_kind: str | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.record_failure(
            error,
            stage=stage,
            attempt=1,
            max_attempts=1,
            explicit_kind=explicit_kind,
            evidence=evidence,
            traceback_text="".join(traceback.format_exception(type(error), error, error.__traceback__)),
        )

    def complete(self, *, stage: str = "complete", artifacts: dict[str, Any] | None = None) -> None:
        health = self._state.setdefault("health", {})
        health.update({"state": "healthy", "consecutive_failures": 0, "last_success_at": utc_now()})
        self._state.update(
            {
                "status": "complete",
                "current_stage": stage,
                "diagnosis": None,
                "recovery": None,
                "completed_at": utc_now(),
            }
        )
        if artifacts is not None:
            self._state["artifacts"] = artifacts
        self._write("workflow_completed", stage=stage)
