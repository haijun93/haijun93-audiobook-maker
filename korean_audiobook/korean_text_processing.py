from __future__ import annotations

import re
from dataclasses import dataclass, field

from .config import ProcessingConfig
from .utils import slugify


CHAPTER_PATTERNS = (
    re.compile(r"^\s*제\s*\d+\s*장(?:\s*[:.\-]\s*.*)?$"),
    re.compile(r"^\s*chapter\s+\d+\b.*$", re.IGNORECASE),
    re.compile(r"^\s*(프롤로그|에필로그|서문|후기|작가의 말|감사의 말)\s*$"),
)
OPEN_QUOTES = "\"'“‘("
DIALOGUE_PREFIXES = ("\"", "'", "“", "‘", "-", "—", "―")
SENTENCE_ENDINGS = ".?!…"
DIGITS = ("영", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구")
SMALL_UNITS = ("", "십", "백", "천")
LARGE_UNITS = ("", "만", "억", "조")
UNIT_ALIASES = {
    "km": "킬로미터",
    "m": "미터",
    "cm": "센티미터",
    "mm": "밀리미터",
    "kg": "킬로그램",
    "g": "그램",
    "mg": "밀리그램",
    "L": "리터",
    "l": "리터",
    "mL": "밀리리터",
    "ml": "밀리리터",
    "℃": "도",
    "°C": "도",
}


@dataclass
class NarrationChunk:
    chunk_id: str
    chapter_index: int
    chapter_title: str
    paragraph_index: int
    chunk_index: int
    text: str
    pause_ms: int
    is_dialogue: bool = False


@dataclass
class ChapterPlan:
    index: int
    title: str
    slug: str
    chunks: list[NarrationChunk] = field(default_factory=list)


@dataclass
class DocumentPlan:
    chapters: list[ChapterPlan]

    @property
    def total_chunks(self) -> int:
        return sum(len(chapter.chunks) for chapter in self.chapters)


def is_chapter_heading(text: str) -> bool:
    stripped = text.strip()
    if not stripped or "\n" in stripped or len(stripped) > 80:
        return False
    return any(pattern.match(stripped) for pattern in CHAPTER_PATTERNS)


def normalize_text(text: str, config: ProcessingConfig) -> str:
    value = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    value = value.translate(
        str.maketrans(
            {
                "“": "\"",
                "”": "\"",
                "‘": "'",
                "’": "'",
                "，": ",",
                "。": ".",
                "！": "!",
                "？": "?",
                "；": ";",
                "：": ":",
            }
        )
    )
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = re.sub(r"\.{3,}", "…", value)
    value = re.sub(r"!{2,}", "!", value)
    value = re.sub(r"\?{2,}", "?", value)
    normalized_lines: list[str] = []
    for raw_line in value.split("\n"):
        line = re.sub(r"\s*([,;:])\s*", r"\1 ", raw_line)
        line = re.sub(r"\s*([.!?…])\s*", r"\1 ", line)
        normalized_lines.append(line.strip())
    value = "\n".join(normalized_lines)
    value = re.sub(r" +\n", "\n", value)
    value = value.strip()

    if config.normalize_dates:
        value = normalize_dates(value)
        value = normalize_times(value)
    if config.normalize_units:
        value = normalize_units(value)
        value = normalize_currency_and_percent(value)
    if config.normalize_numbers:
        value = normalize_standalone_numbers(value)
    return re.sub(r"[ \t]{2,}", " ", value).strip()


def normalize_dates(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        year = int_to_korean(int(match.group(1)))
        month = int_to_korean(int(match.group(2)))
        day = int_to_korean(int(match.group(3)))
        return f"{year}년 {month}월 {day}일"

    return re.sub(r"\b(\d{4})[./-](\d{1,2})[./-](\d{1,2})\b", replace, text)


def normalize_times(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        hour = int_to_korean(int(match.group(1)))
        minute = int_to_korean(int(match.group(2)))
        second = match.group(3)
        if second is None:
            return f"{hour}시 {minute}분"
        second_k = int_to_korean(int(second))
        return f"{hour}시 {minute}분 {second_k}초"

    return re.sub(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b", replace, text)


def normalize_units(text: str) -> str:
    unit_pattern = "|".join(sorted((re.escape(unit) for unit in UNIT_ALIASES), key=len, reverse=True))

    def replace(match: re.Match[str]) -> str:
        number = number_to_korean(match.group(1))
        unit = UNIT_ALIASES[match.group(2)]
        return f"{number}{unit}"

    return re.sub(rf"(?<![A-Za-z가-힣])(-?\d[\d,]*(?:\.\d+)?)\s*({unit_pattern})(?![A-Za-z])", replace, text)


def normalize_currency_and_percent(text: str) -> str:
    def percent_replace(match: re.Match[str]) -> str:
        return f"{number_to_korean(match.group(1))}퍼센트"

    def won_replace(match: re.Match[str]) -> str:
        return f"{number_to_korean(match.group(1))}원"

    def dollar_replace(match: re.Match[str]) -> str:
        return f"{number_to_korean(match.group(1))}달러"

    text = re.sub(r"(-?\d[\d,]*(?:\.\d+)?)\s*%", percent_replace, text)
    text = re.sub(r"₩\s*(-?\d[\d,]*(?:\.\d+)?)", won_replace, text)
    text = re.sub(r"\$\s*(-?\d[\d,]*(?:\.\d+)?)", dollar_replace, text)
    return text


def normalize_standalone_numbers(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        token = match.group(1)
        if re.fullmatch(r"0\d+", token):
            return " ".join(DIGITS[int(char)] for char in token)
        return number_to_korean(token)

    return re.sub(r"(?<![A-Za-z가-힣])(-?\d[\d,]*(?:\.\d+)?)(?![A-Za-z가-힣])", replace, text)


def number_to_korean(token: str) -> str:
    cleaned = token.replace(",", "")
    if cleaned.startswith("-"):
        return "마이너스 " + number_to_korean(cleaned[1:])
    if "." in cleaned:
        whole, fraction = cleaned.split(".", 1)
        whole_text = int_to_korean(int(whole)) if whole else DIGITS[0]
        fraction_text = "".join(DIGITS[int(char)] for char in fraction if char.isdigit())
        return f"{whole_text}점 {fraction_text}".strip()
    return int_to_korean(int(cleaned))


def int_to_korean(value: int) -> str:
    if value == 0:
        return DIGITS[0]

    parts: list[str] = []
    unit_index = 0
    remainder = value
    while remainder > 0:
        chunk = remainder % 10000
        if chunk:
            chunk_text = small_number_to_korean(chunk)
            parts.append(f"{chunk_text}{LARGE_UNITS[unit_index]}")
        remainder //= 10000
        unit_index += 1
    return "".join(reversed(parts))


def small_number_to_korean(value: int) -> str:
    digits = f"{value:04d}"
    pieces: list[str] = []
    for index, raw_digit in enumerate(digits):
        digit = int(raw_digit)
        if digit == 0:
            continue
        unit = SMALL_UNITS[3 - index]
        if digit == 1 and unit:
            pieces.append(unit)
        else:
            pieces.append(f"{DIGITS[digit]}{unit}")
    return "".join(pieces)


def split_sentences(paragraph: str) -> list[str]:
    flat = re.sub(r"\s+", " ", paragraph.strip())
    if not flat:
        return []
    matches = re.findall(r'.+?(?:[.!?…]+["\')\]]*|$)', flat)
    return [match.strip() for match in matches if match.strip()]


def is_dialogue(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith(DIALOGUE_PREFIXES)


def split_long_sentence(sentence: str, max_chars: int) -> list[str]:
    if len(sentence) <= max_chars:
        return [sentence.strip()]

    fragments: list[str] = []
    remaining = sentence.strip()
    while len(remaining) > max_chars:
        split_at = choose_split_index(remaining, max_chars)
        fragment = remaining[:split_at].strip()
        if not fragment:
            split_at = max_chars
            fragment = remaining[:split_at].strip()
        fragments.append(fragment)
        remaining = remaining[split_at:].strip()
    if remaining:
        fragments.append(remaining)
    return fragments


def choose_split_index(text: str, max_chars: int) -> int:
    floor = max(24, int(max_chars * 0.45))
    punctuation_candidates = [match.end() for match in re.finditer(r"[,;:]\s+", text)]
    connective_candidates = [
        match.start()
        for match in re.finditer(r"\s+(?:그리고|하지만|그러나|그래서|또는|또한|한편|게다가|그러면)\s+", text)
    ]
    space_candidates = [match.start() for match in re.finditer(r"\s+", text)]

    for candidates in (punctuation_candidates, connective_candidates, space_candidates):
        valid = [value for value in candidates if floor <= value <= max_chars]
        if valid:
            return valid[-1]
    return max_chars


def infer_pause_ms(text: str, *, config: ProcessingConfig, paragraph_end: bool, forced_soft_break: bool) -> int:
    if paragraph_end:
        return config.paragraph_gap_ms
    if forced_soft_break or text.rstrip().endswith((",", ";", ":")):
        return config.comma_gap_ms
    base = config.sentence_gap_ms
    if is_dialogue(text):
        base = max(base, config.dialogue_gap_ms)
    if text.rstrip().endswith(("?", "!", "…")):
        base += 80
    return base


def build_document_plan(text: str, config: ProcessingConfig) -> DocumentPlan:
    normalized = normalize_text(text, config)
    paragraphs = [block.strip() for block in re.split(r"\n\s*\n+", normalized) if block.strip()]

    chapters: list[ChapterPlan] = []
    current_title = "본문"
    current_paragraphs: list[str] = []
    for block in paragraphs:
        if is_chapter_heading(block):
            if current_paragraphs:
                chapters.append(build_chapter_plan(len(chapters) + 1, current_title, current_paragraphs, config))
                current_paragraphs = []
            current_title = block.strip()
            continue
        current_paragraphs.append(block)
    if current_paragraphs or not chapters:
        chapters.append(build_chapter_plan(len(chapters) + 1, current_title, current_paragraphs, config))
    chapters = [chapter for chapter in chapters if chapter.chunks]
    return DocumentPlan(chapters=chapters)


def build_chapter_plan(index: int, title: str, paragraphs: list[str], config: ProcessingConfig) -> ChapterPlan:
    slug = slugify(f"{index:03d}_{title}", fallback=f"{index:03d}")
    chapter = ChapterPlan(index=index, title=title, slug=slug)
    chunk_counter = 0
    for paragraph_index, paragraph in enumerate(paragraphs, start=1):
        sentences = split_sentences(paragraph)
        if not sentences:
            continue
        for sentence_index, sentence in enumerate(sentences):
            fragments = split_long_sentence(sentence, config.max_chunk_chars)
            for fragment_index, fragment in enumerate(fragments):
                chunk_counter += 1
                paragraph_end = sentence_index == len(sentences) - 1 and fragment_index == len(fragments) - 1
                pause_ms = infer_pause_ms(
                    fragment,
                    config=config,
                    paragraph_end=paragraph_end,
                    forced_soft_break=fragment_index < len(fragments) - 1,
                )
                chunk_id = f"{index:03d}-{paragraph_index:04d}-{chunk_counter:05d}"
                chapter.chunks.append(
                    NarrationChunk(
                        chunk_id=chunk_id,
                        chapter_index=index,
                        chapter_title=title,
                        paragraph_index=paragraph_index,
                        chunk_index=chunk_counter,
                        text=fragment,
                        pause_ms=pause_ms,
                        is_dialogue=is_dialogue(fragment),
                    )
                )
    if chapter.chunks:
        chapter.chunks[-1].pause_ms = config.chapter_gap_ms
    return chapter
