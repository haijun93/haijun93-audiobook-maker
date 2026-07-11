from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from translation_quality_checks import assess_translations, extract_segment_sources  # noqa: E402
from final_epub_quality_audit import assess_epub_pairs  # noqa: E402
import translate_epub_with_chatgpt_web_to_study_epub as translator  # noqa: E402
from translate_epub_with_chatgpt_web_to_study_epub import (  # noqa: E402
    SourceBlock,
    build_chunks,
    build_translation_prompt,
    chunk_has_minor_context,
    load_translation_cache,
    parse_translation_response,
    select_relationship_guide_sample,
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


def test_service_limit_returns_to_batch_without_long_inner_sleep(monkeypatch) -> None:
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
    args = SimpleNamespace(chatgpt_web_max_attempts=5, request_timeout_sec=30)

    with pytest.raises(translator.ChatGPTWebServiceLimitError):
        translator.request_chatgpt_translation(
            context=FakeContext(),
            timeout_error_cls=TimeoutError,
            args=args,
            prompt="translate",
            heartbeat=None,
            label="test",
            prefix="chunk_0001",
        )

    assert slept == []


def test_duplicate_response_ids_are_rejected() -> None:
    response = """<<<B00001>>>
첫 번째 번역
<<<END_B00001>>>
<<<B00001>>>
두 번째 번역
<<<END_B00001>>>"""

    with pytest.raises(RuntimeError, match="중복 번역 ID"):
        parse_translation_response(response, ["B00001"])
