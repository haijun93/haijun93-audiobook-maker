#!/usr/bin/env python3
"""Review Korean EPUB prose for high-confidence omissions and translationese candidates."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from final_epub_tone_review import extract_dialogues, iter_korean_blocks, read_metadata, safe_slug
from atomic_io import atomic_write_json, atomic_write_text


LATIN_RE = re.compile(r"[A-Za-z]")
KOREAN_RE = re.compile(r"[가-힣]")
NARRATIVE_POLITE_RE = re.compile(r"(?:요|습니다|습니까|예요|이에요)[.!?…]*$")
MALFORMED_ENDING_RE = re.compile(r"(?:습니다요|습니까요|입니다다|였다요|했어요다|해요다|예요다|이에요다)")
DOUBLE_PASSIVE_RE = re.compile(r"(?:되어졌|보여졌|쓰여졌|불려졌|잊혀졌|생각되어졌|사용되어졌)")
TRANSLATIONESE_PATTERNS = {
    "피동 직역투 '에 의해'": re.compile(r"에 의해(?:서)?"),
    "명사화 직역투 '것이었다'": re.compile(r"것이었다"),
    "과도한 지시대명사 '그것은/그것이'": re.compile(r"그것은|그것이"),
    "직역투 '에 관하여'": re.compile(r"에 관하여|에 관한 것이"),
}
RESIDUE_MARKERS = ("readrobe.com", "[번역 누락]", "content_refusal", "minor_context_refusal")


@dataclass
class LiterarySample:
    category: str
    file: str
    text: str


@dataclass
class LiteraryReview:
    epub: str
    kind: str
    title: str
    creator: str
    created_at: str
    text_blocks: int = 0
    narrative_polite_blocks: int = 0
    malformed_ending_blocks: int = 0
    double_passive_blocks: int = 0
    untranslated_english_blocks: int = 0
    repeated_long_block_count: int = 0
    residue_marker_count: int = 0
    translationese_counts: dict[str, int] = field(default_factory=dict)
    status: str = "checked"
    notes: list[str] = field(default_factory=list)
    samples: list[LiterarySample] = field(default_factory=list)
    report_path: str = ""
    json_path: str = ""


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def add_sample(samples: list[LiterarySample], category: str, file: str, text: str, limit: int = 10) -> None:
    if sum(1 for sample in samples if sample.category == category) >= limit:
        return
    samples.append(LiterarySample(category=category, file=file, text=clean_text(text)[:320]))


def narrative_only(block: str) -> str:
    narrative = block
    for dialogue in extract_dialogues(block):
        for left, right in (("“", "”"), ('"', '"'), ("‘", "’"), ("'", "'")):
            narrative = narrative.replace(f"{left}{dialogue}{right}", " ")
    return clean_text(narrative)


def review_epub_literary_style(
    epub_path: Path,
    *,
    out_dir: Path | None = None,
    kind: str = "",
) -> LiteraryReview:
    epub_path = epub_path.expanduser().resolve()
    title, creator = read_metadata(epub_path)
    blocks = iter_korean_blocks(epub_path)
    samples: list[LiterarySample] = []
    translationese = Counter()
    repeated: dict[str, list[str]] = {}
    narrative_polite = 0
    malformed = 0
    double_passive = 0
    untranslated_english = 0
    residue = 0

    for file_name, block in blocks:
        narrative = narrative_only(block)
        if len(narrative) >= 40 and NARRATIVE_POLITE_RE.search(narrative):
            narrative_polite += 1
            add_sample(samples, "서술문 요체 후보", file_name, narrative)
        if MALFORMED_ENDING_RE.search(block):
            malformed += 1
            add_sample(samples, "비정상 종결어미", file_name, block)
        if DOUBLE_PASSIVE_RE.search(block):
            double_passive += 1
            add_sample(samples, "이중피동 직역투", file_name, block)

        latin_count = len(LATIN_RE.findall(block))
        korean_count = len(KOREAN_RE.findall(block))
        if len(block) >= 80 and latin_count >= 45 and (korean_count == 0 or latin_count > korean_count * 2):
            untranslated_english += 1
            add_sample(samples, "긴 영문 잔여 후보", file_name, block)

        lower = block.lower()
        for marker in RESIDUE_MARKERS:
            hits = lower.count(marker.lower())
            if hits:
                residue += hits
                add_sample(samples, "잔여 마커", file_name, block)

        for label, pattern in TRANSLATIONESE_PATTERNS.items():
            hits = len(pattern.findall(narrative))
            if hits:
                translationese[label] += hits
                add_sample(samples, label, file_name, narrative, limit=5)

        repeated_key = re.sub(r"[^0-9A-Za-z가-힣]+", "", block.lower())
        if len(repeated_key) >= 100:
            repeated.setdefault(repeated_key, []).append(file_name)

    repeated_count = sum(len(files) for files in repeated.values() if len(set(files)) >= 2 and len(files) >= 3)
    if repeated_count:
        for key, files in repeated.items():
            if len(set(files)) >= 2 and len(files) >= 3:
                add_sample(samples, "긴 번역문 반복 후보", files[0], key)

    notes: list[str] = []
    if narrative_polite:
        notes.append("대화 밖 서술문이 '~요/~습니다'로 끝나는 후보를 확인해야 합니다.")
    if translationese:
        notes.append("직역투 통계는 문맥에 따라 정상일 수 있으므로 자동 치환하지 않고 표본 검수 대상으로만 기록했습니다.")
    if untranslated_english:
        notes.append("긴 영문 잔여 후보는 노래명·판권·참고문헌일 수 있어 문맥 확인이 필요합니다.")

    high_confidence = bool(malformed or double_passive or residue or repeated_count or narrative_polite >= 12)
    status = "needs_attention" if high_confidence else "checked"
    review = LiteraryReview(
        epub=str(epub_path),
        kind=kind,
        title=title,
        creator=creator,
        created_at=datetime.now().isoformat(timespec="seconds"),
        text_blocks=len(blocks),
        narrative_polite_blocks=narrative_polite,
        malformed_ending_blocks=malformed,
        double_passive_blocks=double_passive,
        untranslated_english_blocks=untranslated_english,
        repeated_long_block_count=repeated_count,
        residue_marker_count=residue,
        translationese_counts=dict(translationese),
        status=status,
        notes=notes,
        samples=samples,
    )
    if out_dir:
        write_review(review, out_dir)
    return review


def render_markdown(review: LiteraryReview) -> str:
    lines = [
        "# EPUB Literary Translation Review",
        "",
        f"- EPUB: `{review.epub}`",
        f"- Kind: `{review.kind}`",
        f"- Title: {review.title}",
        f"- Creator: {review.creator or '-'}",
        f"- Status: `{review.status}`",
        f"- Created: `{review.created_at}`",
        "",
        "## Counts",
        "",
        f"- text blocks: `{review.text_blocks}`",
        f"- narrative polite candidates: `{review.narrative_polite_blocks}`",
        f"- malformed endings: `{review.malformed_ending_blocks}`",
        f"- double passive candidates: `{review.double_passive_blocks}`",
        f"- long English residue candidates: `{review.untranslated_english_blocks}`",
        f"- repeated long blocks: `{review.repeated_long_block_count}`",
        f"- residue markers: `{review.residue_marker_count}`",
        "",
        "## Translationese Candidates",
        "",
    ]
    if review.translationese_counts:
        lines.extend(f"- {label}: `{count}`" for label, count in review.translationese_counts.items())
    else:
        lines.append("- none")
    if review.notes:
        lines.extend(["", "## Notes", ""])
        lines.extend(f"- {note}" for note in review.notes)
    lines.extend(["", "## Samples", ""])
    if review.samples:
        lines.extend(f"- {sample.category} / `{sample.file}`: {sample.text}" for sample in review.samples)
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def write_review(review: LiteraryReview, out_dir: Path) -> LiteraryReview:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = safe_slug(Path(review.epub).stem)
    report_path = out_dir / f"{stem}.literary_review_{stamp}.md"
    json_path = out_dir / f"{stem}.literary_review_{stamp}.json"
    latest_report = out_dir / f"{stem}.literary_review_latest.md"
    latest_json = out_dir / f"{stem}.literary_review_latest.json"
    review.report_path = str(report_path)
    review.json_path = str(json_path)
    markdown = render_markdown(review)
    atomic_write_json(json_path, asdict(review))
    atomic_write_json(latest_json, asdict(review))
    atomic_write_text(report_path, markdown)
    atomic_write_text(latest_report, markdown)
    return review


def main() -> int:
    parser = argparse.ArgumentParser(description="Review Korean literary translation style in an EPUB.")
    parser.add_argument("epub", type=Path)
    parser.add_argument("--kind", default="")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    review = review_epub_literary_style(args.epub, out_dir=args.out_dir, kind=args.kind)
    print(json.dumps({"status": review.status, "report": review.report_path, "json": review.json_path}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
