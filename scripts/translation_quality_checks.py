#!/usr/bin/env python3
"""Deterministic source/translation checks shared by translation and final audit."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field


KOREAN_RE = re.compile(r"[가-힣]")
LATIN_RE = re.compile(r"[A-Za-z]")
NUMBER_RE = re.compile(r"(?<![A-Za-z])\d+(?:[.,:]\d+)*(?![A-Za-z])")
SEGMENT_RE = re.compile(r"<<<([^>]+)>>[>]\s*(.*?)\s*<<<END_\1>>>", re.DOTALL)
# Internal chunk-marker syntax (current <<<Bxxxxx>>> convention, and the older [[[BEGIN:...]]]
# convention some cached translations were produced with) should never survive into a finished
# translation. Seeing it means a chunk failed to split back into its per-block pieces and several
# blocks' text got concatenated into one - a real, visible defect a reader would spot immediately.
MARKER_LEAK_RE = re.compile(r"<<<(?:B\d{4,}|END_B\d{4,})>>>|\[\[\[(?:BEGIN|END)\b")
REFUSAL_MARKERS = (
    "content can't be shown for safety reasons",
    "content can’t be shown for safety reasons",
    "i can't assist with that",
    "i can’t assist with that",
    "i can't help with that",
    "i can’t help with that",
    "i'm unable to help",
    "i’m unable to help",
    "i cannot assist",
    "i'm sorry, but i can't assist",
    "i’m sorry, but i can’t assist",
    "i'm sorry, but i can't help",
    "i’m sorry, but i can’t help",
    "i'm sorry, but i can't provide",
    "i’m sorry, but i can’t provide",
    "i'm sorry, but i can't comply",
    "i’m sorry, but i can’t comply",
    "i'm sorry, but i can't translate",
    "i’m sorry, but i can’t translate",
    "i can't fulfill this request",
    "i can’t fulfill this request",
    "요청하신 내용에는 도움을 드릴 수 없",
    "해당 요청에는 응답할 수 없",
    "번역 응답이 거절",
    "content_refusal",
    "minor_context_refusal",
)
FRONTMATTER_METADATA_RE = re.compile(
    r"^(?:"
    r"a\s+(?:jove|berkley|penguin)\s+book\b|"
    r"published\s+by\b|an\s+imprint\s+of\b|copyright\b|excerpt\s+from\b.*\bcopyright\b|"
    r".+\s+©\s+\d{4}\s+by\b|"
    r".+\b(?:colophon|trademark)s?\b|library\s+of\s+congress\b|"
    r"(?:names?|title|description|identifiers?|subjects?|classification):\s|"
    r"lc\s+(?:ebook\s+)?record\b|first\s+edition\b|cover\s+(?:art|illustration|design)\b|"
    r"book\s+design\b|this\s+is\s+a\s+work\s+of\s+fiction\b|"
    r"penguin\s+random\s+house\s+supports\s+copyright\b|"
    r"first\s+published\b|all\s+rights\s+reserved\b|the\s+moral\s+right\b|"
    r"(?:a\s+)?catalogue\s+record\b|cataloguing[\s-]in[\s-]publication\b|"
    r"chapter\s+illustrations?:"
    r")",
    re.IGNORECASE,
)
# Bare company/social domains without a scheme or "www." prefix (e.g. publisher social
# links like "linkedin.com/company/..." dropped into front matter) should be left alone
# just like the https://-prefixed URLs the prose check already exempts below.
BARE_DOMAIN_RE = re.compile(r"\b[a-z0-9][a-z0-9-]{1,62}\.(?:com|net|org|io|co|edu|gov)\b", re.IGNORECASE)
# Publisher mailing addresses ("122 Fifth Avenue New York, NY 10011", "1745 Broadway,
# New York, New York 10019") are proper nouns/numbers with no real sentence to translate.
ADDRESS_RE = re.compile(
    r"\b\d{1,6}\s+(?:[A-Z][a-zA-Z']*\s+){0,3}"
    r"(?:Avenue|Ave\.?|Street|St\.?|Broadway|Boulevard|Blvd\.?|Road|Rd\.?|Drive|Dr\.?|Lane|Ln\.?|Way|Place|Pl\.?|Suite|Floor)\b"
    r".{0,40}\b\d{5}(?:-\d{4})?\b",
)
# A short quoted-or-bare "Title: Subtitle" line (in-story document titles, "also by"
# bibliography entries) has no sentence punctuation to translate and should keep its
# official English title per the translation prompt's title-preservation rule.
TITLE_SUBTITLE_MINOR_WORDS = {
    "a", "an", "the", "of", "in", "on", "for", "and", "or", "to", "from", "with", "at", "by",
}


def is_bare_title_subtitle_line(text: str) -> bool:
    stripped = text.strip().strip("\"“”'")
    if not stripped or len(stripped) > 140 or ":" not in stripped:
        return False
    if re.search(r"[.!?]", stripped):
        return False
    words = re.findall(r"[A-Za-z][A-Za-z'’-]*", stripped)
    if len(words) < 3:
        return False
    capitalized = sum(1 for word in words if word[0].isupper() or word.lower() in TITLE_SUBTITLE_MINOR_WORDS)
    return capitalized / len(words) >= 0.9


def find_refusal_marker(text: str) -> str:
    lowered = text.lower()
    return next((marker for marker in REFUSAL_MARKERS if marker in lowered), "")


def count_refusal_markers(text: str) -> int:
    lowered = text.lower()
    return sum(lowered.count(marker) for marker in REFUSAL_MARKERS)


@dataclass
class TranslationFinding:
    block_id: str
    severity: str
    code: str
    detail: str


@dataclass
class TranslationAssessment:
    checked_blocks: int = 0
    severe_count: int = 0
    warning_count: int = 0
    severe_ids: list[str] = field(default_factory=list)
    warning_ids: list[str] = field(default_factory=list)
    findings: list[TranslationFinding] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def extract_segment_sources(text: str) -> dict[str, str]:
    return {match.group(1): compact_text(match.group(2)) for match in SEGMENT_RE.finditer(text)}


def is_separator_text(text: str) -> bool:
    return bool(re.fullmatch(r"[\*\-–—_~·•\s]{1,120}", compact_text(text)))


def is_prose_source(text: str) -> bool:
    text = compact_text(text)
    if FRONTMATTER_METADATA_RE.search(text):
        return False
    if re.fullmatch(r"[“\"].{2,100}[”\"]\s+by\s+.{2,100}", text, flags=re.IGNORECASE):
        return False
    if re.search(r"(?:https?://|www\.|\bISBN\b|@\w+[.]\w+)", text, flags=re.IGNORECASE):
        return False
    if BARE_DOMAIN_RE.search(text) or ADDRESS_RE.search(text):
        return False
    if is_bare_title_subtitle_line(text):
        return False
    return len(text) >= 35 and len(LATIN_RE.findall(text)) >= 20 and not is_separator_text(text)


def normalized_for_identity(text: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", compact_text(text).lower())


def assess_translations(
    sources: dict[str, str],
    translations: dict[str, str],
    *,
    max_findings: int = 120,
) -> TranslationAssessment:
    assessment = TranslationAssessment(checked_blocks=len(sources))
    target_groups: dict[str, list[tuple[str, str]]] = defaultdict(list)

    def add(block_id: str, severity: str, code: str, detail: str) -> None:
        if severity == "severe":
            assessment.severe_count += 1
            if block_id not in assessment.severe_ids:
                assessment.severe_ids.append(block_id)
        else:
            assessment.warning_count += 1
            if block_id not in assessment.warning_ids:
                assessment.warning_ids.append(block_id)
        if len(assessment.findings) < max_findings:
            assessment.findings.append(
                TranslationFinding(block_id=block_id, severity=severity, code=code, detail=detail)
            )

    for block_id, raw_source in sources.items():
        source = compact_text(raw_source)
        target = compact_text(translations.get(block_id, ""))
        if not target:
            add(block_id, "severe", "missing_translation", "번역이 비어 있습니다.")
            continue

        leaked_marker = MARKER_LEAK_RE.search(target)
        if leaked_marker:
            add(
                block_id,
                "severe",
                "leaked_marker_syntax",
                f"내부 처리용 청크 마커가 번역 결과에 그대로 남아 있습니다(여러 블록이 하나로 뒤섞였을 가능성): {leaked_marker.group(0)[:40]}",
            )

        if is_separator_text(source):
            continue

        marker = find_refusal_marker(target)
        if marker:
            add(block_id, "severe", "refusal_residue", f"서비스 거절 문구 후보가 포함되어 있습니다: {marker}")

        if is_prose_source(source):
            source_identity = normalized_for_identity(source)
            target_identity = normalized_for_identity(target)
            korean_count = len(KOREAN_RE.findall(target))
            latin_count = len(LATIN_RE.findall(target))
            if source_identity and source_identity == target_identity:
                add(block_id, "severe", "untranslated_identity", "영어 원문이 번역 없이 그대로 남아 있습니다.")
            elif korean_count == 0 and latin_count >= 20:
                add(block_id, "severe", "untranslated_latin", "한국어 없이 영문 중심 문장이 남아 있습니다.")

            length_ratio = len(target) / max(1, len(source))
            if len(source) >= 120 and len(target) < 28 and length_ratio < 0.12:
                add(
                    block_id,
                    "severe",
                    "likely_truncation",
                    f"원문 대비 번역이 지나치게 짧습니다: source={len(source)}, target={len(target)}, ratio={length_ratio:.2f}",
                )
            elif len(source) >= 80 and (length_ratio < 0.18 or length_ratio > 3.8):
                add(
                    block_id,
                    "warning",
                    "length_outlier",
                    f"원문/번역 길이 비율 확인이 필요합니다: source={len(source)}, target={len(target)}, ratio={length_ratio:.2f}",
                )

            source_numbers = NUMBER_RE.findall(source)
            target_numbers = NUMBER_RE.findall(target)
            missing_numbers = [number for number in source_numbers if number not in target_numbers]
            if missing_numbers:
                add(
                    block_id,
                    "warning",
                    "number_mismatch",
                    f"원문의 숫자가 번역에서 보이지 않습니다: {', '.join(missing_numbers[:8])}",
                )

            quote_source = source.count('"') + source.count("“") + source.count("”")
            quote_target = target.count('"') + target.count("“") + target.count("”")
            if quote_source >= 2 and quote_target == 0 and len(source) >= 80:
                add(block_id, "warning", "dialogue_quote_loss", "원문 대화 인용부호가 번역에서 사라졌습니다.")

        target_key = normalized_for_identity(target)
        if len(target_key) >= 35:
            target_groups[target_key].append((block_id, normalized_for_identity(source)))

    for rows in target_groups.values():
        source_values = {source for _block_id, source in rows}
        if len(rows) < 3 or len(source_values) < 2:
            continue
        for block_id, _source in rows:
            add(
                block_id,
                "severe",
                "repeated_translation",
                f"서로 다른 원문에 동일한 긴 번역이 {len(rows)}회 반복되었습니다.",
            )

    return assessment
