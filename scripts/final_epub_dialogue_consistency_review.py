#!/usr/bin/env python3
"""Second-pass dialogue review focused on local register continuity."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from final_epub_tone_review import (
    classify_dialogue,
    clean_text,
    extract_dialogues,
    extract_relationship_rules,
    infer_kind,
    iter_korean_blocks,
    read_metadata,
    safe_slug,
    sentence_tones,
)
from atomic_io import atomic_write_json, atomic_write_text


CASUAL_PRONOUN_RE = re.compile(r"(?<![가-힣])(?:너|너는|너를|너의|너희|널|네가|니가|자네)(?![가-힣])")
POLITE_END_RE = re.compile(r"(?:요|습니다|습니까|세요|십시오|예요|이에요)[.!?…]*$")
TITLE_RE = re.compile(r"(?:선생님|교수님|박사님|사장님|원장님|형사님|변호사님|의사 선생님)")
# See final_epub_tone_review.CASUAL_END_RE for why the bare "야" alternative excludes a
# trailing ellipsis/2+ dots: it is otherwise indistinguishable from the "-아야/-어야"
# connective cut off mid-clause ("들어봐야….").
CASUAL_END_RE = re.compile(r"(?:어|아|가|야(?!\s*(?:\.{2,}|…))|해|했어|거야|잖아|겠어|한다|했다|다)[.!?…]*$")


@dataclass
class ConsistencySample:
    category: str
    file: str
    text: str


@dataclass
class DialogueConsistencyReview:
    epub: str
    kind: str
    title: str
    creator: str
    created_at: str
    review_version: int = 1
    pass_index: int = 2
    relationship_guide: str = ""
    relationship_rule_count: int = 0
    dialogue_count: int = 0
    mixed_register_dialogues: int = 0
    casual_pronoun_polite_dialogues: int = 0
    title_casual_dialogues: int = 0
    local_register_switches: int = 0
    files_with_dialogue: int = 0
    status: str = "checked"
    notes: list[str] = field(default_factory=list)
    samples: list[ConsistencySample] = field(default_factory=list)
    report_path: str = ""
    json_path: str = ""


def add_sample(
    samples: list[ConsistencySample], category: str, file_name: str, text: str, limit: int = 10
) -> None:
    if sum(1 for sample in samples if sample.category == category) >= limit:
        return
    samples.append(ConsistencySample(category=category, file=file_name, text=clean_text(text)[:320]))


def review_dialogue_consistency(
    epub_path: Path,
    *,
    relationship_guide: Path | None = None,
    out_dir: Path | None = None,
    kind: str = "",
) -> DialogueConsistencyReview:
    epub_path = epub_path.expanduser().resolve()
    title, creator = read_metadata(epub_path)
    guide_text, rules = extract_relationship_rules(relationship_guide)
    blocks = iter_korean_blocks(epub_path)
    dialogues_by_file: dict[str, list[str]] = {}
    samples: list[ConsistencySample] = []
    counts = Counter()

    for file_name, block in blocks:
        dialogues = extract_dialogues(block)
        if not dialogues:
            continue
        dialogues_by_file.setdefault(file_name, []).extend(dialogues)
        for dialogue in dialogues:
            counts["dialogue"] += 1
            tones = sentence_tones(dialogue)
            if {"polite", "casual"}.issubset(tones):
                counts["mixed"] += 1
                add_sample(samples, "한 대사 안의 존대/반말 혼합", file_name, dialogue)
            if CASUAL_PRONOUN_RE.search(dialogue) and POLITE_END_RE.search(dialogue):
                counts["casual_pronoun_polite"] += 1
                add_sample(samples, "반말 대명사와 존댓말 종결 충돌", file_name, dialogue)
            if TITLE_RE.search(dialogue) and CASUAL_END_RE.search(dialogue):
                counts["title_casual"] += 1
                add_sample(samples, "존칭 호칭과 반말 종결 충돌", file_name, dialogue)

    local_switches = 0
    for file_name, dialogues in dialogues_by_file.items():
        tones = [classify_dialogue(dialogue) for dialogue in dialogues]
        for index in range(1, len(tones)):
            if {tones[index - 1], tones[index]} == {"polite", "casual"}:
                local_switches += 1
                if index >= 2 and tones[index - 2] == tones[index - 1]:
                    add_sample(
                        samples,
                        "인접 대화의 말투 급변 후보",
                        file_name,
                        f"{dialogues[index - 1]} / {dialogues[index]}",
                        limit=8,
                    )

    notes: list[str] = []
    if not guide_text:
        notes.append("인물관계 가이드가 없어 2차 검수 신뢰도가 낮습니다.")
    if local_switches:
        notes.append("인접 대화 말투 전환은 화자 교대나 관계 변화일 수 있으므로 자동 수정하지 않습니다.")
    if rules:
        notes.append(f"관계별 말투 규칙 {len(rules)}개와 대조했습니다.")

    high_confidence = (
        not guide_text
        or counts["casual_pronoun_polite"] >= 8
        or counts["title_casual"] >= 8
        or counts["mixed"] >= 20
    )
    review = DialogueConsistencyReview(
        epub=str(epub_path),
        kind=kind or infer_kind(epub_path),
        title=title,
        creator=creator,
        created_at=datetime.now().isoformat(timespec="seconds"),
        relationship_guide=str(relationship_guide or ""),
        relationship_rule_count=len(rules),
        dialogue_count=counts["dialogue"],
        mixed_register_dialogues=counts["mixed"],
        casual_pronoun_polite_dialogues=counts["casual_pronoun_polite"],
        title_casual_dialogues=counts["title_casual"],
        local_register_switches=local_switches,
        files_with_dialogue=len(dialogues_by_file),
        status="needs_attention" if high_confidence else "checked",
        notes=notes,
        samples=samples,
    )
    if out_dir:
        write_review(review, out_dir)
    return review


def render_markdown(review: DialogueConsistencyReview) -> str:
    lines = [
        "# EPUB Dialogue Consistency Review - Pass 2",
        "",
        f"- EPUB: `{review.epub}`",
        f"- kind: `{review.kind}`",
        f"- title: {review.title}",
        f"- creator: {review.creator or '-'}",
        f"- status: `{review.status}`",
        f"- created: `{review.created_at}`",
        f"- relationship rules: `{review.relationship_rule_count}`",
        "",
        "## Counts",
        "",
        f"- dialogues: `{review.dialogue_count}`",
        f"- mixed register: `{review.mixed_register_dialogues}`",
        f"- casual pronoun + polite ending: `{review.casual_pronoun_polite_dialogues}`",
        f"- title + casual ending: `{review.title_casual_dialogues}`",
        f"- local register switches: `{review.local_register_switches}`",
        f"- files with dialogue: `{review.files_with_dialogue}`",
        "",
        "## Notes",
        "",
    ]
    lines.extend(f"- {note}" for note in review.notes) if review.notes else lines.append("- none")
    lines.extend(["", "## Samples", ""])
    if review.samples:
        lines.extend(f"- {sample.category} / `{sample.file}`: {sample.text}" for sample in review.samples)
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def write_review(review: DialogueConsistencyReview, out_dir: Path) -> DialogueConsistencyReview:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = safe_slug(Path(review.epub).stem)
    report_path = out_dir / f"{stem}.dialogue_pass2_{stamp}.md"
    json_path = out_dir / f"{stem}.dialogue_pass2_{stamp}.json"
    latest_report = out_dir / f"{stem}.dialogue_pass2_latest.md"
    latest_json = out_dir / f"{stem}.dialogue_pass2_latest.json"
    review.report_path = str(report_path)
    review.json_path = str(json_path)
    markdown = render_markdown(review)
    atomic_write_json(json_path, asdict(review))
    atomic_write_json(latest_json, asdict(review))
    atomic_write_text(report_path, markdown)
    atomic_write_text(latest_report, markdown)
    return review


def main() -> int:
    parser = argparse.ArgumentParser(description="Second-pass EPUB dialogue consistency review.")
    parser.add_argument("epub", type=Path)
    parser.add_argument("--relationship-guide", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--kind", default="")
    args = parser.parse_args()
    review = review_dialogue_consistency(
        args.epub,
        relationship_guide=args.relationship_guide,
        out_dir=args.out_dir,
        kind=args.kind,
    )
    print(json.dumps({"status": review.status, "report": review.report_path, "json": review.json_path}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
