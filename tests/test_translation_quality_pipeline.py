from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from translation_quality_checks import (  # noqa: E402
    assess_translations,
    count_refusal_markers,
    extract_segment_sources,
)
from final_epub_quality_audit import assess_epub_pairs  # noqa: E402
import translate_epub_with_chatgpt_web_to_study_epub as translator  # noqa: E402
import run_soseol2_chatgpt_k_e_batch as batch  # noqa: E402
from translate_epub_with_chatgpt_web_to_study_epub import (  # noqa: E402
    SourceBlock,
    build_chunks,
    build_translation_prompt,
    chunk_has_minor_context,
    load_translation_cache,
    parse_translation_response,
    resolve_web_provider,
    select_relationship_guide_sample,
    strip_source_watermarks,
    translation_prompt_for_provider,
    validate_chunk_translations,
)


def test_untranslated_prose_and_truncation_are_severe() -> None:
    sources = {
        "B1": "This is a sufficiently long English prose sentence that should have been translated into Korean for the reader.",
        "B2": "He crossed the crowded room, found the letter beneath the lamp, read every line twice, checked the signature, and waited in silence before he finally spoke to the others.",
    }
    translations = {
        "B1": sources["B1"],
        "B2": "그가 말했다.",
    }

    result = assess_translations(sources, translations)

    assert result.severe_count == 2
    assert {finding.code for finding in result.findings} == {"untranslated_identity", "likely_truncation"}


def test_song_credit_can_intentionally_remain_in_english() -> None:
    source = '“Breath of Life” by Florence & The Machine'

    result = assess_translations({"B1": source}, {"B1": source})

    assert result.severe_count == 0


@pytest.mark.parametrize(
    "source",
    [
        "An imprint of Penguin Random House LLC",
        "Excerpt from Love on the Brain copyright © 2021 by Ali Hazelwood",
        "LESSONS IN SIN © 2021 by Pam Godwin",
        "This is a work of fiction. Names, characters, places, and incidents are products of the author's imagination.",
        "First published in the UK in 2024 by Head of Zeus Ltd, part of Bloomsbury Publishing Plc.",
        "The moral right of Ian Green to be identified as the author of this work has been asserted in accordance with the Copyright, Designs and Patents Act of 1988.",
        "All rights reserved. No part of this publication may be reproduced, stored in a retrieval system, or transmitted in any form or by any means, electronic, mechanical, photocopying, recording, or otherwise, without the prior permission of both the copyright owner and the above publisher of this book.",
        "A catalogue record for this book is available from the British Library.",
        "Chapter Illustrations: Shutterstock",
    ],
)
def test_frontmatter_metadata_may_preserve_official_english(source: str) -> None:
    result = assess_translations({"B1": source}, {"B1": source})

    assert result.severe_count == 0


@pytest.mark.parametrize(
    "source",
    [
        "Barnes & Noble, Inc. 122 Fifth Avenue New York, NY 10011",
        "1745 Broadway, New York, New York 10019",
        "linkedin.com/company/penguin-random-house-uk",
    ],
)
def test_publisher_address_and_bare_domain_may_remain_untranslated(source: str) -> None:
    result = assess_translations({"B1": source}, {"B1": source})

    assert result.severe_count == 0


@pytest.mark.parametrize(
    "source",
    [
        "The Anthropocene Reviewed: Essays on a Human-Centered Planet",
        "“Earl Aubec of Malador: Outline for a Series of Four Fantasy Novels”",
    ],
)
def test_bare_title_subtitle_line_may_remain_untranslated(source: str) -> None:
    result = assess_translations({"B1": source}, {"B1": source})

    assert result.severe_count == 0


def test_title_case_heuristic_does_not_shield_real_untranslated_dialogue() -> None:
    source = "He looked at her and said: I never wanted any of this to happen between us and I am truly sorry for everything"

    result = assess_translations({"B1": source}, {"B1": source})

    assert result.severe_count == 1
    assert result.findings[0].code == "untranslated_identity"


def test_repeated_long_translation_is_detected() -> None:
    sources = {
        "B1": "The first source paragraph contains a distinct event and enough words to count as prose.",
        "B2": "The second source paragraph describes something entirely different from the first event.",
        "B3": "The third source paragraph changes the setting, the speaker, and the action once again.",
    }
    repeated = "그는 같은 말을 되풀이했고, 서로 다른 세 장면이 모두 똑같은 문장으로 잘못 번역되어 버렸다."

    result = assess_translations(sources, {block_id: repeated for block_id in sources})

    assert result.severe_count == 3
    assert all(finding.code == "repeated_translation" for finding in result.findings)


def test_normal_fiction_dialogue_is_not_mistaken_for_refusal() -> None:
    dialogue = "I can’t, okay? I’m sorry, but I can’t focus on anything because I had an incredible night."

    assert count_refusal_markers(dialogue) == 0


def test_actual_service_refusal_is_detected() -> None:
    refusal = "I’m sorry, but I can’t help with that request."
    result = assess_translations({"B1": "Translate this paragraph."}, {"B1": refusal})

    assert count_refusal_markers(refusal) >= 1
    assert any(finding.code == "refusal_residue" for finding in result.findings)


def test_segment_extraction_and_chunk_context() -> None:
    blocks = [SourceBlock(id=f"B{i:05d}", text=f"Source sentence number {i} with surrounding context.") for i in range(1, 8)]
    chunks = build_chunks(blocks, max_chars=200)

    assert len(chunks) > 1
    assert chunks[1].context_before
    assert chunks[0].context_after
    assert extract_segment_sources(chunks[0].text)

    prompt = build_translation_prompt(chunks[1], len(chunks), "Test Book")
    assert "앞뒤 문맥(번역 출력 대상 아님)" in prompt
    assert "문맥 문장은 출력하거나 현재 SEGMENT에 합치지 않습니다" in prompt


def test_relationship_sample_covers_late_book_dialogue() -> None:
    blocks = [SourceBlock(id=f"B{i:05d}", text=f"Narrative block {i}.") for i in range(1, 501)]
    blocks[-2] = SourceBlock(id="B00499", text='Late Character said, "This relationship changes near the ending."')

    sample = select_relationship_guide_sample(blocks, max_chars=20000)

    assert "B00499" in sample
    assert "Late Character" in sample


def test_batch_termination_stops_active_translation_process_group() -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        start_new_session=True,
    )

    batch.terminate_process_group(process, grace_seconds=0.1)

    assert process.poll() is not None


def test_epub_pair_audit_works_without_source_cache() -> None:
    texts = {
        "OEBPS/chapter.xhtml": """<?xml version="1.0" encoding="utf-8"?>
        <html xmlns="http://www.w3.org/1999/xhtml"><body>
          <p class="pair"><span class="ko">This English prose sentence was accidentally left untranslated and should be detected by the final EPUB audit.</span><span class="en">This English prose sentence was accidentally left untranslated and should be detected by the final EPUB audit.</span></p>
        </body></html>"""
    }

    assessment = assess_epub_pairs(texts)

    assert assessment.checked_blocks == 1
    assert assessment.severe_count == 1
    assert assessment.findings[0].code == "untranslated_identity"


def test_epub_pair_audit_ignores_empty_layout_pairs() -> None:
    texts = {
        "OEBPS/chapter.xhtml": """<?xml version="1.0" encoding="utf-8"?>
        <html xmlns="http://www.w3.org/1999/xhtml"><body>
          <p class="pair"><span class="ko"></span><br/><span class="en"></span></p>
        </body></html>"""
    }

    assessment = assess_epub_pairs(texts)

    assert assessment.checked_blocks == 0
    assert assessment.severe_count == 0


def test_default_prompt_does_not_unnecessarily_raise_sensitive_topics() -> None:
    chunk = build_chunks(
        [SourceBlock(id="B00001", text="She entered the library and returned the book to the front desk.")],
        max_chars=1000,
    )[0]

    prompt = build_translation_prompt(chunk, 1, "Test Book")

    assert "미성년자/청소년" not in prompt
    assert "성적 장면" not in prompt
    assert "노골적 표현" not in prompt


def test_minor_safety_mode_requires_minor_and_sensitive_context() -> None:
    school_only = build_chunks(
        [SourceBlock(id="B00001", text="The sixteen-year-old student walked into class and opened her notebook.")],
        max_chars=1000,
    )[0]
    sensitive = build_chunks(
        [SourceBlock(id="B00001", text="The report described sexual assault involving a sixteen-year-old victim.")],
        max_chars=1000,
    )[0]

    assert chunk_has_minor_context(school_only) is False
    assert chunk_has_minor_context(sensitive) is True


def test_non_explicit_minor_translation_can_be_short_without_retry_loop() -> None:
    source = (
        "The report described sexual assault involving a sixteen-year-old victim and contained a long, "
        "explicit account of the event, its coercive context, and the harm that followed afterward."
    )
    chunk = build_chunks([SourceBlock(id="B00001", text=source)], max_chars=1000)[0]

    quality = validate_chunk_translations(
        chunk,
        {"B00001": "보고서는 열여섯 살 피해자가 겪은 성폭력과 그로 인한 피해를 절제해 서술했다."},
        allow_non_explicit_compression=True,
    )

    assert quality["checked_blocks"] == 1


def test_translation_cache_ignores_noncanonical_chunk_json(tmp_path: Path) -> None:
    translations = tmp_path / "translations"
    translations.mkdir()
    (translations / "chunk_0001.json").write_text(
        '{"translations":{"B00001":"정상 번역"}}', encoding="utf-8"
    )
    (translations / "chunk_0001_part_01.json").write_text(
        '{"translations":{"B00001":"잘못 덮어쓴 번역"}}', encoding="utf-8"
    )

    assert load_translation_cache(tmp_path) == {"B00001": "정상 번역"}


def test_legacy_provider_account_limit_returns_to_batch_without_long_inner_sleep(monkeypatch) -> None:
    class FakePage:
        url = "https://chatgpt.com/c/test"

        def close(self) -> None:
            return None

    class FakeContext:
        def new_page(self):
            return FakePage()

    monkeypatch.setattr(translator, "prepare_chatgpt_web_page", lambda *args, **kwargs: None)
    monkeypatch.setattr(translator, "send_chatgpt_web_prompt", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        translator,
        "wait_for_chatgpt_web_response",
        lambda *args, **kwargs: (
            "message",
            "Our systems have detected unusual activity coming from your system. Please try again later.",
        ),
    )
    slept: list[float] = []
    monkeypatch.setattr(translator.time, "sleep", lambda seconds: slept.append(seconds))
    args = SimpleNamespace(web_provider="chatgpt", chatgpt_web_max_attempts=5, request_timeout_sec=30)

    with pytest.raises(translator.WebServiceLimitError, match="error_kind=account_unavailable"):
        translator.request_web_translation(
            context=FakeContext(),
            timeout_error_cls=TimeoutError,
            args=args,
            prompt="translate",
            heartbeat=None,
            label="test",
            prefix="chunk_0001",
        )

    assert slept == []


def test_new_translation_work_defaults_to_gemini_and_honors_existing_pin(tmp_path: Path) -> None:
    args = SimpleNamespace(web_provider=None)

    assert resolve_web_provider(args, tmp_path) == "gemini"
    assert translator.active_web_provider(SimpleNamespace()) == "gemini"

    (tmp_path / translator.WEB_PROVIDER_MARKER).write_text("chatgpt\n", encoding="utf-8")
    assert resolve_web_provider(args, tmp_path) == "chatgpt"
    assert resolve_web_provider(SimpleNamespace(web_provider="gemini"), tmp_path) == "gemini"


def test_overnight_fallback_switches_gemini_to_chatgpt_and_back(monkeypatch, tmp_path: Path) -> None:
    real_datetime = translator.datetime

    class FrozenDatetime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return real_datetime(2026, 7, 17, 22, 0, tzinfo=tz)

    monkeypatch.setattr(translator, "datetime", FrozenDatetime)
    args = SimpleNamespace(web_provider="gemini", disable_overnight_web_fallback=False)

    assert translator.resolve_session_provider(args, tmp_path) == "gemini"

    translator.mark_gemini_temporarily_down(tmp_path)
    assert translator.resolve_session_provider(args, tmp_path) == "chatgpt"

    state = translator._read_fallback_state(translator.provider_fallback_state_dir(args, tmp_path))
    assert "gemini_down_until" in state

    class LaterDatetime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return real_datetime(2026, 7, 17, 22, 20, tzinfo=tz)

    monkeypatch.setattr(translator, "datetime", LaterDatetime)
    assert translator.resolve_session_provider(args, tmp_path) == "gemini"


def test_overnight_fallback_shares_gemini_down_state_across_a_batch(monkeypatch, tmp_path: Path) -> None:
    real_datetime = translator.datetime

    class FrozenDatetime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return real_datetime(2026, 7, 17, 22, 0, tzinfo=tz)

    monkeypatch.setattr(translator, "datetime", FrozenDatetime)
    batch_root = tmp_path / "batch"
    book_a = tmp_path / "book_a"
    book_b = tmp_path / "book_b"
    args = SimpleNamespace(
        web_provider="gemini",
        disable_overnight_web_fallback=False,
        provider_fallback_state_dir=str(batch_root),
    )

    translator.mark_gemini_temporarily_down(translator.provider_fallback_state_dir(args, book_a))

    # A different book in the same batch immediately sees Gemini is down too.
    assert translator.resolve_session_provider(args, book_b) == "chatgpt"


def test_gemini_translation_backend_collects_response(monkeypatch) -> None:
    class FakePage:
        url = "https://gemini.google.com/app/conversation-123"

        def close(self) -> None:
            return None

    class FakeContext:
        def new_page(self):
            return FakePage()

    prepared: list[str] = []
    monkeypatch.setattr(translator, "prepare_gemini_web_page", lambda *args, **kwargs: prepared.append("yes"))
    monkeypatch.setattr(translator, "send_gemini_web_prompt", lambda *args, **kwargs: (2, 1))
    monkeypatch.setattr(
        translator,
        "wait_for_gemini_web_response",
        lambda *args, **kwargs: "<<<B00001>>>\n자연스러운 번역입니다.\n<<<END_B00001>>>",
    )
    args = SimpleNamespace(web_provider="gemini", web_max_attempts=2, request_timeout_sec=30)

    conversation_id, response = translator.request_web_translation(
        context=FakeContext(),
        timeout_error_cls=TimeoutError,
        args=args,
        prompt="translate",
        heartbeat=None,
        label="test",
        prefix="chunk_0001",
    )

    assert prepared == ["yes"]
    assert conversation_id == "conversation-123"
    assert "자연스러운 번역" in response


def test_gemini_prompt_uses_markers_that_survive_html_rendering() -> None:
    prompt = "<<<B00001>>>\nSource\n<<<END_B00001>>>"

    converted = translation_prompt_for_provider(prompt, "gemini")

    assert converted == "[[[BEGIN:B00001]]]\nSource\n[[[END:B00001]]]"
    assert translation_prompt_for_provider(prompt, "chatgpt") == prompt


def test_gemini_marker_and_legacy_rendered_marker_responses_parse() -> None:
    current = "[[[BEGIN:B00001]]]\n현재 번역\n[[[END:B00001]]]"
    legacy_rendered = "<<>>\n이전 응답 복구\n<<<END_B00001>>>"

    assert parse_translation_response(current, ["B00001"]) == {"B00001": "현재 번역"}
    assert parse_translation_response(legacy_rendered, ["B00001"]) == {"B00001": "이전 응답 복구"}


def test_gemini_service_limit_returns_to_batch_without_inner_sleep(monkeypatch) -> None:
    class FakePage:
        url = "https://gemini.google.com/app/conversation-123"

        def close(self) -> None:
            return None

    class FakeContext:
        def new_page(self):
            return FakePage()

    monkeypatch.setattr(translator, "prepare_gemini_web_page", lambda *args, **kwargs: None)
    monkeypatch.setattr(translator, "send_gemini_web_prompt", lambda *args, **kwargs: (0, 0))
    monkeypatch.setattr(
        translator,
        "wait_for_gemini_web_response",
        lambda *args, **kwargs: "You've reached your limit. Please try again later.",
    )
    slept: list[float] = []
    monkeypatch.setattr(translator.time, "sleep", lambda seconds: slept.append(seconds))
    args = SimpleNamespace(web_provider="gemini", web_max_attempts=3, request_timeout_sec=30)

    with pytest.raises(translator.WebServiceLimitError, match="Gemini error_kind=usage_limit"):
        translator.request_web_translation(
            context=FakeContext(),
            timeout_error_cls=TimeoutError,
            args=args,
            prompt="translate",
            heartbeat=None,
            label="test",
            prefix="chunk_0001",
        )

    assert slept == []


@pytest.mark.parametrize(
    ("detail", "attempt", "expected"),
    [
        ("Gemini error_kind=usage_limit", 1, 1800),
        ("Gemini error_kind=rate_limit", 1, 300),
        ("Gemini error_kind=temporary_service_error", 2, 30),
        ("kind=missing_translation_ids", 3, 5),
        ("kind=prompt_too_long", 1, 5),
        ("unknown failure", 1, 120),
    ],
)
def test_gemini_batch_cooldown_depends_on_error_kind(detail: str, attempt: int, expected: int) -> None:
    args = SimpleNamespace(cooldown_seconds=900)

    assert batch.translation_retry_cooldown(args, attempt, detail) == expected


def test_successful_gemini_subchunks_resume_after_later_part_failure(tmp_path: Path, monkeypatch) -> None:
    blocks = [
        SourceBlock(
            id=f"B{index:05d}",
            text=(f"Distinct source passage {index} describes a separate scene and action. " * 6).strip(),
        )
        for index in range(1, 7)
    ]
    chunk = build_chunks(blocks, max_chars=10000)[0]
    args = SimpleNamespace(
        max_chars_per_chunk=3500,
        inter_request_delay_sec=0,
        web_provider="gemini",
    )
    failed_run_calls: list[str] = []

    def response_for_prompt(prompt: str) -> str:
        ids = list(dict.fromkeys(re.findall(r"<<<(B\d+)>>>", prompt)))
        return "\n".join(
            f"<<<{block_id}>>>\n"
            + (f"{block_id}에 해당하는 서로 다른 장면을 충분한 길이의 자연스러운 한국어 문장으로 정확하게 옮긴 번역이다. " * 5)
            + f"\n<<<END_{block_id}>>>"
            for block_id in ids
        )

    def fail_second_part(**kwargs):
        prefix = kwargs["prefix"]
        failed_run_calls.append(prefix)
        if prefix.endswith("part_02"):
            return "conversation", "응답 형식 누락"
        return "conversation", response_for_prompt(kwargs["prompt"])

    monkeypatch.setattr(translator, "request_web_translation", fail_second_part)
    monkeypatch.setattr(translator.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="누락되거나 빈 번역 ID"):
        translator.translate_refused_chunk_in_subchunks(
            context=None,
            timeout_error_cls=TimeoutError,
            args=args,
            work_dir=tmp_path,
            book_title="Test Book",
            relationship_guide="",
            chunk=chunk,
            chunk_count=1,
            heartbeat=None,
            fallback_reason="missing_translation_ids",
        )

    part_one = translator.subchunk_translation_path(tmp_path, "chunk_0001_part_01")
    assert part_one.exists()

    resumed_calls: list[str] = []

    def succeed_remaining(**kwargs):
        resumed_calls.append(kwargs["prefix"])
        return "conversation", response_for_prompt(kwargs["prompt"])

    monkeypatch.setattr(translator, "request_web_translation", succeed_remaining)
    translator.translate_refused_chunk_in_subchunks(
        context=None,
        timeout_error_cls=TimeoutError,
        args=args,
        work_dir=tmp_path,
        book_title="Test Book",
        relationship_guide="",
        chunk=chunk,
        chunk_count=1,
        heartbeat=None,
        fallback_reason="missing_translation_ids",
    )

    assert "chunk_0001_part_01" not in resumed_calls
    assert translator.chunk_translation_path(tmp_path, 1).exists()


def test_duplicate_response_ids_are_rejected() -> None:
    response = """<<<B00001>>>
첫 번째 번역
<<<END_B00001>>>
<<<B00001>>>
두 번째 번역
<<<END_B00001>>>"""

    with pytest.raises(RuntimeError, match="중복 번역 ID"):
        parse_translation_response(response, ["B00001"])


def test_terminology_glossary_parses_multiline_section() -> None:
    guide = """[인물관계 요약]
- test

[말투 규칙]
- test

[주의할 호칭과 일관성]
- test

[고유명사 표기]
- Henry -> 헨리
- Sarah -> 사라
"""
    glossary = translator.parse_terminology_glossary(guide)
    assert glossary == {"Henry": "헨리", "Sarah": "사라"}


def test_terminology_consistency_flags_inconsistent_rendering() -> None:
    glossary = {"Henry": "헨리"}
    blocks = [
        translator.SourceBlock(id="B00001", text="Henry looked at Sarah and smiled."),
        translator.SourceBlock(id="B00002", text="Henry walked away quietly."),
    ]
    consistent = {"B00001": "헨리는 사라를 보며 미소 지었다.", "B00002": "헨리는 조용히 걸어갔다."}
    inconsistent = {"B00001": "헨리는 사라를 보며 미소 지었다.", "B00002": "핸리는 조용히 걸어갔다."}

    assert translator.check_terminology_consistency(blocks, consistent, glossary) == []

    findings = translator.check_terminology_consistency(blocks, inconsistent, glossary)
    assert len(findings) == 1
    assert findings[0].block_id == "B00002"
    assert findings[0].name == "Henry"


def test_readrobe_watermark_is_removed_during_epub_build() -> None:
    assert strip_source_watermarks("Visit readrobe.com for more") == "Visit for more"
    assert strip_source_watermarks("READROBE.COM") == ""
    assert strip_source_watermarks("리드로브닷컴") == ""
    assert strip_source_watermarks("Visit www.readrobe . com now") == "Visit now"


def test_oceanofpdf_watermark_paragraphs_are_dropped_before_translation() -> None:
    xhtml = (
        b"<html><body>"
        b"<p>Real chapter content that should survive.</p>"
        b'<div><p><a href="https://oceanofpdf.com"><i>OceanofPDF.com</i></a></p></div>'
        b"<p>More real content.</p>"
        b"</body></html>"
    )

    blocks = translator.blocks_from_xhtml(xhtml)

    assert blocks == ["Real chapter content that should survive.", "More real content."]
