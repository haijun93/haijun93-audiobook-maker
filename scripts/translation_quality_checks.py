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
# Gemini sometimes declines a chunk with a copyright objection ("저작권이 있는 출판 도서의
# 본문을 직접 전량 번역하거나 행 단위로 대조하여 제공해 드리기는 어렵습니다") instead of a
# generic safety refusal. Wording varies per chunk, so this checks proximity of "저작권" to a
# refusal verb rather than an exact phrase - mirrors COPYRIGHT_REFUSAL_RE in
# translate_epub_with_chatgpt_web_to_study_epub.py, which stops this from being accepted live;
# this is the retroactive backstop in case one is ever found already sitting in a cached
# translation (e.g. one produced before that live check existed).
COPYRIGHT_REFUSAL_RE = re.compile(
    r"저작권[^.!?\n]{0,80}(어렵습니다|어려울 것 같습니다|도울 수 없|도와드릴 수 없|도와드리기 어렵|거절)"
    r"|(어렵습니다|어려울 것 같습니다|도울 수 없|도와드릴 수 없|도와드리기 어렵|거절)[^.!?\n]{0,80}저작권"
)
FRONTMATTER_METADATA_RE = re.compile(
    r"^(?:"
    r"a\s+(?:jove|berkley|penguin)\s+book\b|"
    # "Published by X" and "Published in the United States by X" / "Published
    # simultaneously in Canada by Y" both open real publisher-imprint lines; bound
    # the gap so this doesn't drift into matching unrelated narrative sentences.
    r"published\b(?:\s+\S+){0,6}\s+by\b|an\s+imprint\s+of\b|copyright\b|excerpt\s+from\b.*\bcopyright\b|"
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
# Library-of-Congress CIP title-statement lines ("Before I go to sleep : a novel /
# S.J. Watson. — 1st ed.") cite the book's own title and author verbatim between a
# " : " and a " / ", punctuation no narrative sentence combines - a reliable signal
# that whichever parts stay in English (per the title/name-preservation prompt rule)
# aren't an untranslated failure.
CIP_TITLE_STATEMENT_RE = re.compile(r"\s:\s.{1,80}\s/\s")
# Bare company/social domains without a scheme or "www." prefix (e.g. publisher social
# links like "linkedin.com/company/..." dropped into front matter) should be left alone
# just like the https://-prefixed URLs the prose check already exempts below.
BARE_DOMAIN_RE = re.compile(r"\b[a-z0-9][a-z0-9-]{1,62}\.(?:com|net|org|io|co|edu|gov)\b", re.IGNORECASE)
# Publisher mailing addresses ("122 Fifth Avenue New York, NY 10011", "1745 Broadway,
# New York, New York 10019", "50 Victoria Embankment London EC4Y 0DZ") are proper
# nouns/numbers with no real sentence to translate. Covers both US-style zips and UK
# postcodes, and both US and UK street-type words, since UK publisher imprints (Hodder &
# Stoughton, Head of Zeus, etc.) use their own street vocabulary and postcode format.
ADDRESS_RE = re.compile(
    r"\b\d{1,6}\s+(?:[A-Z][a-zA-Z']*\s+){0,3}"
    r"(?:Avenue|Ave\.?|Street|St\.?|Broadway|Boulevard|Blvd\.?|Road|Rd\.?|Drive|Dr\.?|Lane|Ln\.?|Way|Place|Pl\.?|"
    r"Suite|Floor|Embankment|Square|Crescent|Terrace|Close|Gardens?|Mews|Row|Court|Walk|Hill|Green|Park)\b"
    r".{0,40}\b(?:\d{5}(?:-\d{4})?|[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2})\b",
    # Case-insensitive: publisher colophons often spell out the street-type word in
    # all caps ("1935 Brookdale RD, Naperville, IL 60563-2773"), not just "Rd"/"Rd.".
    re.IGNORECASE,
)
# A UK/EU publisher address is often split across several consecutive front-matter
# blocks, one line each ("EU representative: Macmillan Publishers Ireland Ltd, 1st
# Floor,", "The Liffey Trust Centre, 117-126 Sheriff Street Upper,", "Dublin 1 D01
# YC43") - so a single fragment won't have a street number, street-type word, *and*
# postcode together the way ADDRESS_RE expects. Any line that both ends with a trailing
# comma (a real narrative sentence/paragraph block never does) and mentions a building/
# street-type word near a number is almost certainly one line of such a multi-block
# address, not prose that failed to translate.
ADDRESS_CONTINUATION_RE = re.compile(
    r"\d{1,3}(?:st|nd|rd|th)?\b.{0,30}\b(?:Floor|Suite|Centre|Center|Trust|House|Building|"
    r"Avenue|Ave\.?|Street|St\.?|Broadway|Boulevard|Blvd\.?|Road|Rd\.?|Drive|Dr\.?|Lane|Ln\.?|Way|Place|Pl\.?|"
    r"Embankment|Square|Crescent|Terrace|Close|Gardens?|Mews|Row|Court|Walk|Hill|Green|Park)\b",
    re.IGNORECASE,
)


def is_address_continuation_line(text: str) -> bool:
    return text.endswith(",") and bool(ADDRESS_CONTINUATION_RE.search(text))


def is_proper_noun_word(word: str) -> bool:
    return word[0].isupper() or word.lower() in TITLE_SUBTITLE_MINOR_WORDS


def is_name_like_segment(segment: str) -> bool:
    words = re.findall(r"[A-Za-z][A-Za-z'.-]*", segment)
    if not words or len(words) > 5:
        return False
    return sum(1 for word in words if is_proper_noun_word(word)) / len(words) >= 0.8


# Acknowledgements / dedication pages often list dozens of backers or supporters as a
# bare comma-separated run of names ("T B, The Human, RinoZ, Mike Dirks, ...,"), with
# no sentence punctuation at all. Real narrative prose never looks like this, so a long
# run of short, mostly-capitalized comma segments is a name list to leave untranslated,
# not a sentence the model failed to translate.
def is_proper_noun_list(text: str) -> bool:
    if re.search(r"[.!?]", text):
        return False
    segments = [part.strip() for part in text.split(",") if part.strip()]
    if len(segments) < 5:
        return False
    name_like = sum(1 for segment in segments if is_name_like_segment(segment))
    return name_like / len(segments) >= 0.85
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


def is_cip_title_statement_line(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and len(stripped) <= 160 and bool(CIP_TITLE_STATEMENT_RE.search(stripped))


# Chapter epigraphs often cite a song as "<Title> – <Artist>" (en/em dash, or a plain
# ASCII hyphen, no "by" and no quotes), e.g. Rina Kent's "The Wolf in Your Darkest Room
# – Matthew Mayfield" or "Everybody Wants To Rule The World - 3TEETH". Like the
# colon-separated title/subtitle case above, both sides are proper nouns with no
# sentence to translate, so a title-cased phrase on each side of a bare dash should
# also be left as-is rather than flagged as untranslated prose.
def _word_capitalization_ratio(segment: str) -> float:
    words = re.findall(r"[A-Za-z][A-Za-z'’.-]*", segment)
    if not words:
        return 0.0
    capitalized = sum(1 for word in words if word[0].isupper() or word.lower() in TITLE_SUBTITLE_MINOR_WORDS)
    return capitalized / len(words)


def is_song_or_quote_attribution_line(text: str) -> bool:
    stripped = text.strip().strip("\"“”'")
    if not stripped or len(stripped) > 140:
        return False
    if re.search(r"[.!?]", stripped):
        return False
    match = re.fullmatch(r"(.{2,90})\s[-–—]\s(.{2,60})", stripped)
    if not match:
        return False
    title_part, attribution_part = match.groups()
    return (
        _word_capitalization_ratio(title_part) >= 0.8
        and _word_capitalization_ratio(attribution_part) >= 0.8
    )


def find_refusal_marker(text: str) -> str:
    lowered = text.lower()
    marker = next((marker for marker in REFUSAL_MARKERS if marker in lowered), "")
    if marker:
        return marker
    match = COPYRIGHT_REFUSAL_RE.search(text)
    return match.group(0) if match else ""


def count_refusal_markers(text: str) -> int:
    lowered = text.lower()
    return sum(lowered.count(marker) for marker in REFUSAL_MARKERS) + len(COPYRIGHT_REFUSAL_RE.findall(text))


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


# Speculative-fiction dialogue sometimes quotes an invented in-world language verbatim
# (e.g. Dune's Fremen/Chakobsa lines like "Cignoro hrobosa sukares hin mange..."). Such
# lines are meant to stay exactly as written in every language edition - there is
# nothing to translate - but they are plausible-looking Latin-alphabet text long enough
# to otherwise pass the prose gate below, so a correct (unchanged) translation trips the
# untranslated_identity check. Real English prose of any length almost always contains
# several common function words; constructed/foreign language text essentially never
# does, so a very low hit-rate against a broad common-word list is a reliable signal.
ENGLISH_FUNCTION_WORDS = frozenset(
    "the a an of to in on at is are was were be been being and but or not that this "
    "these those he she it they we you i my your his her their our with for from as "
    "by if than then so no yes do does did have has had will would can could should "
    "must when where who what why how there here out up down about into over under "
    "just very more most some any all each other".split()
)


def is_constructed_or_foreign_language_line(text: str) -> bool:
    words = re.findall(r"[A-Za-z']+", text)
    if len(words) < 5:
        return False
    hits = sum(1 for word in words if word.lower() in ENGLISH_FUNCTION_WORDS)
    return (hits / len(words)) < 0.12


# This pipeline only translates English-original books into Korean; a book whose
# original-language text is French/Spanish/German/etc. (or a non-Latin script) would
# just have every block flagged as "untranslated" by a well-behaved translation that
# correctly left proper nouns alone, burning through all book-level retries for a
# reason retrying can never fix. Same signal as is_constructed_or_foreign_language_line
# above, applied to a whole-book sample instead of one line: real English prose of any
# length has a high hit-rate against a broad common-function-word list; other
# Latin-alphabet languages and non-Latin scripts do not.
def is_english_word_sample(sample: str, *, min_words: int = 40, min_hit_rate: float = 0.08) -> bool:
    words = re.findall(r"[A-Za-z']+", sample)
    if len(words) < min_words:
        return False
    hits = sum(1 for word in words if word.lower() in ENGLISH_FUNCTION_WORDS)
    return (hits / len(words)) >= min_hit_rate


def is_prose_source(text: str) -> bool:
    text = compact_text(text)
    if FRONTMATTER_METADATA_RE.search(text):
        return False
    if re.fullmatch(r"[“\"].{2,100}[”\"]\s+by\s+.{2,100}", text, flags=re.IGNORECASE):
        return False
    if re.search(r"(?:https?://|www\.|\bISBN\b|@\w+[.]\w+)", text, flags=re.IGNORECASE):
        return False
    if BARE_DOMAIN_RE.search(text) or ADDRESS_RE.search(text) or is_address_continuation_line(text):
        return False
    if is_proper_noun_list(text):
        return False
    if is_bare_title_subtitle_line(text):
        return False
    if is_cip_title_statement_line(text):
        return False
    if is_song_or_quote_attribution_line(text):
        return False
    if is_constructed_or_foreign_language_line(text):
        return False
    return len(text) >= 35 and len(LATIN_RE.findall(text)) >= 20 and not is_separator_text(text)


def normalized_for_identity(text: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", compact_text(text).lower())


STUDY_NOTE_RE = re.compile(r"\s*※\s*(?:학습|study)?\s*[:：].*$", re.IGNORECASE | re.DOTALL)


def translation_body(text: str) -> str:
    """Return the translation prose without an optional study-note suffix."""

    return compact_text(STUDY_NOTE_RE.sub("", str(text or "")))


def is_allowed_literal_source(text: str) -> bool:
    """Identify source fragments that are intentionally literal.

    Names, addresses, ISBNs, URLs, catalogue title statements, and epigraph
    attributions can remain Latin in a Korean translation. Copyright prose,
    dedications, quotations, headings, and narrative sentences cannot.
    """

    source = compact_text(text)
    if not source:
        return True
    if re.fullmatch(r"(?:ISBN\s*[:：]?\s*)?[0-9Xx][0-9Xx .:/-]{3,}", source):
        return True
    if re.search(r"(?:https?://|www\.|\b\w[\w.-]*\.(?:com|net|org|io|co|edu|gov)\b)", source, re.IGNORECASE):
        return True
    if ADDRESS_RE.search(source) or is_address_continuation_line(source):
        return True
    if is_proper_noun_list(source) or is_cip_title_statement_line(source):
        return True
    if is_bare_title_subtitle_line(source) or is_song_or_quote_attribution_line(source):
        return True
    if is_constructed_or_foreign_language_line(source):
        return True
    return False


def strict_untranslated_output_findings(
    sources: dict[str, str],
    translations: dict[str, str],
) -> list[TranslationFinding]:
    """Find raw English bodies that would leak into a published translation.

    ``assess_translations`` deliberately retains broad metadata exceptions for
    source-analysis reports. Publication requires a stricter rule: if a block
    is not a literal-only fragment, its translation body must contain Korean and
    must not be the source copied verbatim with a Korean study note appended.
    """

    findings: list[TranslationFinding] = []
    for block_id, raw_source in sources.items():
        source = compact_text(raw_source)
        body = translation_body(translations.get(block_id, ""))
        if not source or is_allowed_literal_source(source):
            continue
        if not LATIN_RE.search(source):
            continue
        if not body:
            findings.append(
                TranslationFinding(
                    block_id=block_id,
                    severity="severe",
                    code="missing_translation_output",
                    detail="출판용 번역 본문이 비어 있습니다.",
                )
            )
            continue
        same_text = normalized_for_identity(source) == normalized_for_identity(body)
        no_korean = not KOREAN_RE.search(body)
        if same_text or no_korean:
            findings.append(
                TranslationFinding(
                    block_id=block_id,
                    severity="severe",
                    code="untranslated_output",
                    detail="출판용 번역 본문에 한국어가 없거나 영문 원문이 그대로 남아 있습니다.",
                )
            )
    return findings


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
