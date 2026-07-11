#!/usr/bin/env python3
"""Create a relationship-guide-based final dialogue tone review for an EPUB."""

from __future__ import annotations

import argparse
import html
import json
import re
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

from atomic_io import atomic_write_json, atomic_write_text


TEXT_SUFFIXES = (".xhtml", ".html", ".htm")
QUOTE_RE = re.compile(r"[“\"]([^“”\"]{2,260})[”\"]|[‘']([^‘’']{2,180})[’']")
POLITE_END_RE = re.compile(r"(요|(?<!아)니다|니까|세요|십시오|어요|아요|해요|예요|이에요|군요|네요)[.!?…]*$")
CASUAL_END_RE = re.compile(r"(어|아|해|야|지|네|군|거야|잖아|겠어|했어|한다|했다|다)[.!?…]*$")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
TITLE_RE = re.compile(r"(선생님|교수님|박사님|사장님|원장님|형사님|변호사님|의사 선생님)")
INTIMATE_RE = re.compile(r"(자기야|예쁜|내 거|네가|넌|너는|너를|너한테|널|너랑|우리 둘|사랑)")
KOREAN_RE = re.compile(r"[가-힣]")
ENGLISH_NAME_RE = re.compile(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?\b")
NARRATIVE_POLITE_END_RE = re.compile(r"(요|습니다|습니까|예요|이에요)[.!?…]*$")


@dataclass
class ToneSample:
    category: str
    file: str
    text: str


@dataclass
class ToneReview:
    epub: str
    kind: str
    title: str
    creator: str
    relationship_guide: str
    relationship_rule_count: int
    relationship_rules: list[str]
    text_blocks: int
    dialogue_count: int
    polite_dialogues: int
    casual_dialogues: int
    other_dialogues: int
    mixed_tone_dialogues: int
    title_casual_dialogues: int
    intimate_polite_dialogues: int
    narrative_polite_blocks: int
    english_name_residue: dict[str, int]
    status: str
    notes: list[str] = field(default_factory=list)
    samples: list[ToneSample] = field(default_factory=list)
    report_path: str = ""
    json_path: str = ""


def clean_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def text_content(node) -> str:
    return clean_text(node.get_text(" ", strip=True))


def read_metadata(epub_path: Path) -> tuple[str, str]:
    try:
        with zipfile.ZipFile(epub_path) as archive:
            opf_name = next((name for name in archive.namelist() if name.lower().endswith(".opf")), "")
            if not opf_name:
                return epub_path.stem, ""
            root = ET.fromstring(archive.read(opf_name))
    except Exception:
        return epub_path.stem, ""
    ns = {"dc": "http://purl.org/dc/elements/1.1/"}
    title_node = root.find(".//dc:title", ns)
    creator_node = root.find(".//dc:creator", ns)
    title = clean_text("".join(title_node.itertext())) if title_node is not None else epub_path.stem
    creator = clean_text("".join(creator_node.itertext())) if creator_node is not None else ""
    return title, creator


def iter_korean_blocks(epub_path: Path) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    with zipfile.ZipFile(epub_path) as archive:
        for name in archive.namelist():
            lower = name.lower()
            if not lower.endswith(TEXT_SUFFIXES):
                continue
            if lower.endswith(("nav.xhtml", "cover.xhtml")) or "toc" in lower:
                continue
            soup = BeautifulSoup(archive.read(name), "xml")
            for node in soup.select(".en"):
                node.decompose()
            ko_nodes = soup.select(".ko")
            if ko_nodes:
                for node in ko_nodes:
                    text = text_content(node)
                    if text and KOREAN_RE.search(text):
                        blocks.append((name, text))
                continue
            for node in soup.find_all(["p", "h1", "h2", "h3", "li", "blockquote"]):
                text = text_content(node)
                if text and KOREAN_RE.search(text):
                    blocks.append((name, text))
    return blocks


def classify_dialogue(text: str) -> str:
    value = clean_text(text)
    if POLITE_END_RE.search(value):
        return "polite"
    if CASUAL_END_RE.search(value):
        return "casual"
    return "other"


def sentence_tones(text: str) -> set[str]:
    tones: set[str] = set()
    for sentence in SENTENCE_SPLIT_RE.split(clean_text(text)):
        tone = classify_dialogue(sentence)
        if tone in {"polite", "casual"}:
            tones.add(tone)
    return tones


def extract_dialogues(text: str) -> list[str]:
    dialogues: list[str] = []
    for match in QUOTE_RE.finditer(text):
        value = match.group(1) or match.group(2) or ""
        value = clean_text(value)
        if value:
            dialogues.append(value)
    return dialogues


def extract_relationship_rules(guide_path: Path | None) -> tuple[str, list[str]]:
    if not guide_path or not guide_path.exists():
        return "", []
    guide = guide_path.read_text(encoding="utf-8", errors="replace").strip()
    rules: list[str] = []
    in_rules = False
    for raw_line in guide.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("["):
            in_rules = "말투" in line
            continue
        if in_rules and re.search(r"(->|→|반말|존댓말|격식|높임|낮춤)", line):
            rules.append(line.lstrip("- ").strip())
    if len(rules) <= 1 and guide:
        section = guide
        if "[말투 규칙]" in section:
            section = section.split("[말투 규칙]", 1)[1]
        if "[주의할 호칭과 일관성]" in section:
            section = section.split("[주의할 호칭과 일관성]", 1)[0]
        compact = re.sub(r"\s+", " ", section).strip()
        rule_pattern = re.compile(
            r"([A-Za-z가-힣0-9/·(), ]{1,80}(?:->|→)[A-Za-z가-힣0-9/·(), ]{1,80}:"
            r".{1,220}?)(?=\s+[A-Za-z가-힣0-9/·(), ]{1,80}(?:->|→)|$)"
        )
        parsed = [clean_text(match.group(1)).strip(" -") for match in rule_pattern.finditer(compact)]
        if len(parsed) > len(rules):
            rules = parsed
    if not rules:
        for raw_line in guide.splitlines():
            line = raw_line.strip().lstrip("- ").strip()
            if re.search(r"(->|→|반말|존댓말|격식|높임|낮춤)", line):
                rules.append(line)
    return guide, rules[:40]


def add_sample(samples: list[ToneSample], category: str, file: str, text: str, limit: int = 8) -> None:
    if sum(1 for sample in samples if sample.category == category) >= limit:
        return
    samples.append(ToneSample(category=category, file=file, text=text[:260]))


def review_epub_tone(
    epub_path: Path,
    *,
    relationship_guide: Path | None = None,
    out_dir: Path | None = None,
    kind: str = "",
) -> ToneReview:
    epub_path = epub_path.expanduser().resolve()
    title, creator = read_metadata(epub_path)
    guide_text, rules = extract_relationship_rules(relationship_guide)
    blocks = iter_korean_blocks(epub_path)

    dialogue_counter: Counter[str] = Counter()
    english_counter: Counter[str] = Counter()
    mixed_tone = 0
    title_casual = 0
    intimate_polite = 0
    narrative_polite = 0
    samples: list[ToneSample] = []

    english_stopwords = {
        "Chapter",
        "Part",
        "Books",
        "Copyright",
        "Acknowledgments",
        "Epilogue",
        "Prologue",
        "Kindle",
        "Amazon",
        "New York",
        "United States",
    }

    for file_name, block in blocks:
        for name in ENGLISH_NAME_RE.findall(block):
            if name not in english_stopwords:
                english_counter[name] += 1

        dialogues = extract_dialogues(block)
        for dialogue in dialogues:
            tone = classify_dialogue(dialogue)
            dialogue_counter[tone] += 1
            tones = sentence_tones(dialogue)
            if {"polite", "casual"}.issubset(tones):
                mixed_tone += 1
                add_sample(samples, "존대/반말 혼합 후보", file_name, dialogue)
            if tone == "casual" and TITLE_RE.search(dialogue):
                title_casual += 1
                add_sample(samples, "존칭 호칭+반말 후보", file_name, dialogue)
            if tone == "polite" and INTIMATE_RE.search(dialogue):
                intimate_polite += 1
                add_sample(samples, "친밀 호칭+존댓말 후보", file_name, dialogue)

        narrative = block
        for dialogue in dialogues:
            narrative = narrative.replace(f"“{dialogue}”", " ").replace(f'"{dialogue}"', " ")
        narrative = clean_text(narrative)
        if len(narrative) >= 40 and NARRATIVE_POLITE_END_RE.search(narrative):
            narrative_polite += 1
            add_sample(samples, "서술문 요체 후보", file_name, narrative)

    total_dialogues = sum(dialogue_counter.values())
    residue = dict(english_counter.most_common(30))
    notes: list[str] = []
    if not guide_text:
        notes.append("관계/말투 가이드 파일을 찾지 못해 휴리스틱 말투 검수만 수행했습니다.")
    if rules:
        notes.append(f"관계/말투 규칙 {len(rules)}개를 기준으로 최종 점검했습니다.")
    if total_dialogues < 30:
        notes.append("대화문 표본이 적어 말투 검수 신뢰도가 낮습니다.")
    if narrative_polite:
        notes.append("서술문이 대화체처럼 '~요'로 끝나는 후보가 있어 독백/서술 문체 확인이 필요합니다.")
    if residue:
        notes.append("본문에 영문 고유명사 후보가 남아 있어 음역 통일 여부 확인이 필요합니다.")

    high_risk = (
        narrative_polite >= 12
        or mixed_tone >= 20
        or intimate_polite >= 20
        or title_casual >= 20
        or sum(residue.values()) >= 60
        or not guide_text
    )
    status = "needs_attention" if high_risk else "checked"

    review = ToneReview(
        epub=str(epub_path),
        kind=kind or infer_kind(epub_path),
        title=title,
        creator=creator,
        relationship_guide=str(relationship_guide) if relationship_guide else "",
        relationship_rule_count=len(rules),
        relationship_rules=rules,
        text_blocks=len(blocks),
        dialogue_count=total_dialogues,
        polite_dialogues=dialogue_counter["polite"],
        casual_dialogues=dialogue_counter["casual"],
        other_dialogues=dialogue_counter["other"],
        mixed_tone_dialogues=mixed_tone,
        title_casual_dialogues=title_casual,
        intimate_polite_dialogues=intimate_polite,
        narrative_polite_blocks=narrative_polite,
        english_name_residue=residue,
        status=status,
        notes=notes,
        samples=samples,
    )

    if out_dir:
        write_review(review, out_dir)
    return review


def infer_kind(path: Path) -> str:
    name = path.name.lower()
    if name.startswith("[k-e]"):
        return "k-e"
    if name.startswith("[k]"):
        return "k"
    return "epub"


def safe_slug(text: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", text).strip("_")
    return re.sub(r"_+", "_", slug)[:120] or "epub"


def render_markdown(review: ToneReview) -> str:
    lines = [
        "# EPUB 최종 대화톤 점검",
        "",
        f"- 파일: `{review.epub}`",
        f"- 종류: `{review.kind}`",
        f"- 제목: {review.title}",
        f"- 저자: {review.creator or '-'}",
        f"- 상태: `{review.status}`",
        f"- 관계/말투 가이드: `{review.relationship_guide or '없음'}`",
        f"- 점검 시각: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## 인물관계 기반 규칙",
        "",
    ]
    if review.relationship_rules:
        lines.extend(f"- {rule}" for rule in review.relationship_rules[:25])
    else:
        lines.append("- 추출된 말투 규칙 없음")
    lines.extend(
        [
            "",
            "## 대화톤 통계",
            "",
            f"- 본문 블록: {review.text_blocks}",
            f"- 대화문: {review.dialogue_count}",
            f"- 존댓말 후보: {review.polite_dialogues}",
            f"- 반말 후보: {review.casual_dialogues}",
            f"- 기타/판정 보류: {review.other_dialogues}",
            f"- 존대/반말 혼합 후보: {review.mixed_tone_dialogues}",
            f"- 존칭 호칭+반말 후보: {review.title_casual_dialogues}",
            f"- 친밀 호칭+존댓말 후보: {review.intimate_polite_dialogues}",
            f"- 서술문 요체 후보: {review.narrative_polite_blocks}",
            "",
            "## 참고",
            "",
        ]
    )
    if review.notes:
        lines.extend(f"- {note}" for note in review.notes)
    else:
        lines.append("- 특별한 고위험 패턴은 자동 검수에서 발견되지 않았습니다.")
    if review.english_name_residue:
        lines.extend(["", "## 영문 고유명사 잔여 후보", ""])
        lines.extend(f"- {name}: {count}" for name, count in list(review.english_name_residue.items())[:20])
    lines.extend(["", "## 표본", ""])
    if review.samples:
        for sample in review.samples:
            lines.append(f"- {sample.category} / `{sample.file}`: {sample.text}")
    else:
        lines.append("- 고위험 표본 없음")
    return "\n".join(lines).rstrip() + "\n"


def write_review(review: ToneReview, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = safe_slug(Path(review.epub).stem)
    report_path = out_dir / f"{stem}.tone_review_{stamp}.md"
    json_path = out_dir / f"{stem}.tone_review_{stamp}.json"
    review.report_path = str(report_path)
    review.json_path = str(json_path)
    atomic_write_text(report_path, render_markdown(review))
    atomic_write_json(json_path, asdict(review))

    latest_report = out_dir / f"{stem}.tone_review_latest.md"
    latest_json = out_dir / f"{stem}.tone_review_latest.json"
    atomic_write_text(latest_report, render_markdown(review))
    atomic_write_json(latest_json, asdict(review))


def main() -> int:
    parser = argparse.ArgumentParser(description="Final relationship-guide-based dialogue tone review for EPUBs.")
    parser.add_argument("epub", type=Path)
    parser.add_argument("--relationship-guide", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--kind", default="")
    args = parser.parse_args()

    review = review_epub_tone(
        args.epub,
        relationship_guide=args.relationship_guide,
        out_dir=args.out_dir,
        kind=args.kind,
    )
    print(json.dumps({"status": review.status, "report": review.report_path, "json": review.json_path}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
