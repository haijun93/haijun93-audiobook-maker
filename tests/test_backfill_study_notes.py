from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import backfill_study_notes as backfill  # noqa: E402


def make_chunk() -> backfill.pipeline.TranslationChunk:
    blocks = [
        backfill.pipeline.SourceBlock(id="B00001", text="A useful phrase appears here."),
        backfill.pipeline.SourceBlock(id="B00002", text="Oh."),
    ]
    return backfill.pipeline.build_chunks(blocks, max_chars=2000)[0]


def test_cached_note_chunk_accepts_explicit_empty_note(tmp_path: Path) -> None:
    path = tmp_path / "chunk_0001.json"
    path.write_text(
        json.dumps({"translations": {"B00001": "useful phrase - 유용한 표현", "B00002": ""}}),
        encoding="utf-8",
    )

    assert backfill.cached_note_chunk_is_complete(path, ["B00001", "B00002"]) is True
    assert backfill.cached_note_chunk_is_complete(path, ["B00001", "B00002", "B00003"]) is False


def test_note_prompt_example_does_not_duplicate_a_real_block_id() -> None:
    prompt = backfill.build_note_prompt(make_chunk(), 1, "Test Book")

    assert "<<<EXAMPLE_ID>>>" in prompt
    assert prompt.count("<<<B00001>>>") == 1


def test_study_note_missing_ids_are_classified_for_targeted_retry() -> None:
    error = RuntimeError("notes_chunk_0001 학습노트 응답에서 누락된 ID: B00001, B00002")

    assert backfill.pipeline.classify_translation_web_error(error)[0] == "missing_translation_ids"


def test_gemini_two_angle_marker_variant_is_recovered() -> None:
    response = (
        "<<>>\nuseful phrase - 유용한 표현\n<<END:B00001>>\n"
        "<<>>\n\n<<END:B00002>>"
    )

    notes = backfill.pipeline.parse_translation_response(response, ["B00001", "B00002"])

    assert notes == {"B00001": "useful phrase - 유용한 표현", "B00002": ""}


def test_note_chunk_retries_duplicate_id_response(monkeypatch, tmp_path: Path) -> None:
    chunk = make_chunk()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "responses").mkdir()
    responses = iter(
        [
            """<<<B00001>>>\nfirst\n<<<END_B00001>>>\n<<<B00001>>>\nduplicate\n<<<END_B00001>>>""",
            """<<<B00001>>>\nuseful phrase - 유용한 표현\n<<<END_B00001>>>\n<<<B00002>>>\n\n<<<END_B00002>>>""",
        ]
    )
    calls: list[str] = []

    def fake_request(**kwargs):
        calls.append(kwargs["prompt"])
        return "conversation", next(responses)

    monkeypatch.setattr(backfill.pipeline, "request_web_translation", fake_request)
    monkeypatch.setattr(backfill.time, "sleep", lambda _seconds: None)

    conversation_id, notes = backfill.request_note_chunk(
        context=None,
        timeout_error_cls=TimeoutError,
        args=SimpleNamespace(),
        prompt="base prompt",
        refusal_retry_prompt="retry prompt",
        chunk=chunk,
        chunk_count=1,
        work_dir=tmp_path,
        max_attempts=3,
    )

    assert conversation_id == "conversation"
    assert notes == {"B00001": "useful phrase - 유용한 표현", "B00002": ""}
    assert len(calls) == 2
    assert "각각 정확히 한 번씩" in calls[1]


def test_note_chunk_does_not_retry_account_pause(monkeypatch, tmp_path: Path) -> None:
    chunk = make_chunk()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "responses").mkdir()
    calls = 0

    def fail_request(**_kwargs):
        nonlocal calls
        calls += 1
        raise backfill.pipeline.WebServiceLimitError(
            "chatgpt",
            "account_unavailable",
            "pause_for_account_recovery",
            "account restricted",
        )

    monkeypatch.setattr(backfill.pipeline, "request_web_translation", fail_request)

    with pytest.raises(backfill.pipeline.WebServiceLimitError):
        backfill.request_note_chunk(
            context=None,
            timeout_error_cls=TimeoutError,
            args=SimpleNamespace(),
            prompt="base prompt",
            refusal_retry_prompt="retry prompt",
            chunk=chunk,
            chunk_count=1,
            work_dir=tmp_path,
            max_attempts=3,
        )

    assert calls == 1


def test_note_chunk_splits_all_missing_ids_across_remaining_attempts(monkeypatch, tmp_path: Path) -> None:
    chunk = make_chunk()
    prompt = backfill.build_note_prompt(chunk, 1, "Test Book")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "responses").mkdir()
    responses = iter(
        [
            "format lost all ids",
            "<<<B00001>>>\nuseful phrase - 유용한 표현\n<<<END_B00001>>>",
            "<<<B00002>>>\n\n<<<END_B00002>>>",
        ]
    )
    calls: list[str] = []

    def fake_request(**kwargs):
        calls.append(kwargs["prompt"])
        return "conversation", next(responses)

    monkeypatch.setattr(backfill.pipeline, "request_web_translation", fake_request)
    monkeypatch.setattr(backfill.time, "sleep", lambda _seconds: None)

    _conversation_id, notes = backfill.request_note_chunk(
        context=None,
        timeout_error_cls=TimeoutError,
        args=SimpleNamespace(),
        prompt=prompt,
        refusal_retry_prompt=prompt,
        chunk=chunk,
        chunk_count=1,
        work_dir=tmp_path,
        max_attempts=3,
    )

    assert notes == {"B00001": "useful phrase - 유용한 표현", "B00002": ""}
    assert "<<<B00001>>>" in calls[1] and "<<<B00002>>>" not in calls[1]
    assert "<<<B00002>>>" in calls[2] and "<<<B00001>>>" not in calls[2]


def test_note_chunk_propagates_gemini_outage_without_content_retry(monkeypatch, tmp_path: Path) -> None:
    chunk = make_chunk()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "responses").mkdir()
    calls = 0

    def fail_request(**_kwargs):
        nonlocal calls
        calls += 1
        raise backfill.pipeline.OvernightProviderSwitch("gemini_outage")

    monkeypatch.setattr(backfill.pipeline, "request_web_translation", fail_request)

    with pytest.raises(backfill.pipeline.OvernightProviderSwitch):
        backfill.request_note_chunk(
            context=None,
            timeout_error_cls=TimeoutError,
            args=SimpleNamespace(),
            prompt=backfill.build_note_prompt(chunk, 1, "Test Book"),
            refusal_retry_prompt="retry prompt",
            chunk=chunk,
            chunk_count=1,
            work_dir=tmp_path,
            max_attempts=3,
        )

    assert calls == 1
