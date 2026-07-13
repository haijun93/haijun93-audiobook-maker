#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


DEFAULT_FOLDER = Path(str(Path.home()) + "/Desktop/소설/#[k-e]")
NOVEL_ROOT = Path(str(Path.home()) + "/Desktop/소설")
WORK_DIR = Path(".work")

TAG_RE = re.compile(r"<[^>]+>")
BODY_RE = re.compile(r"<body\b[^>]*>(.*?)</body>", re.I | re.S)
QUOTE_RE = re.compile(r"[“\"]([^“”\"]{2,220})[”\"]|[‘']([^‘’']{2,220})[’']")
INLINE_EN_RE = re.compile(r"\(([A-Za-z][^()]{8,})\)")
POLITE_RE = re.compile(r"(요|니다|니까|세요|십시오|어요|아요|해요|예요|이에요|군요|네요)[.!?…]*$")
CASUAL_RE = re.compile(r"(어|아|해|야|지|네|군|거야|잖아|겠어|했어|한다|했다|다)[.!?…]*$")
HANGUL_RE = re.compile(r"[가-힣]")
EN_WORD_RE = re.compile(r"[A-Za-z]{2,}")

RESPECT_TERMS = (
    "씨",
    "님",
    "선생",
    "박사",
    "교수",
    "사장",
    "대표",
    "회장",
    "부장",
    "과장",
    "경감",
    "형사",
    "판사",
    "검사",
    "변호사",
    "장군",
    "대장",
    "소장",
    "대령",
    "대통령",
    "시장",
    "의원",
    "목사",
    "신부",
    "아버지",
    "어머니",
    "할아버지",
    "할머니",
)
CASUAL_PRONOUN_RE = re.compile(
    r"(?<![가-힣])(?:"
    r"너|너는|너를|너의|너희|널|네가|니가|자네|얘|야"
    r")(?![가-힣])"
)
POLITE_HINTS = ("요", "습니다", "습니까", "세요", "십시오")


@dataclass
class DialogueSample:
    level: str
    reason: str
    text: str


def clean_text(text: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    text = TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def body_texts(path: Path) -> list[str]:
    texts: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            lower = name.lower()
            if not lower.endswith((".xhtml", ".html", ".htm")):
                continue
            raw = archive.read(name).decode("utf-8", "replace")
            body_match = BODY_RE.search(raw)
            source = body_match.group(1) if body_match else raw
            cleaned = clean_text(source)
            if cleaned:
                texts.append(cleaned)
    return texts


def base_title(path: Path) -> str:
    stem = path.stem
    for prefix in ("[k-e] ", "[k-e]", "[k] ", "[k]"):
        if stem.startswith(prefix):
            return stem[len(prefix) :].strip()
    return stem


def normalized(text: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", text.lower())


def find_relationship_guides() -> dict[str, Path]:
    guides: dict[str, Path] = {}
    for path in NOVEL_ROOT.glob("**/relationship_guide.txt"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            continue
        if len(text) < 300:
            continue
        key = normalized(path.parent.name.replace("_chatgpt_translate_work", ""))
        if key and key not in guides:
            guides[key] = path
    return guides


def match_guide(title: str, guides: dict[str, Path]) -> Path | None:
    title_key = normalized(title)
    best: tuple[int, Path] | None = None
    for key, path in guides.items():
        if title_key in key:
            score = len(title_key)
        elif key in title_key:
            score = len(key)
        else:
            continue
        if best is None or score > best[0]:
            best = (score, path)
    return best[1] if best else None


def guide_excerpt(path: Path | None, max_chars: int) -> str:
    if path is None or max_chars <= 0:
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def classify_dialogue(text: str) -> str:
    stripped = text.strip()
    if POLITE_RE.search(stripped):
        return "polite"
    if CASUAL_RE.search(stripped):
        return "casual"
    return "other"


def dialogue_samples(texts: list[str], max_each: int) -> tuple[list[DialogueSample], dict[str, int]]:
    samples: list[DialogueSample] = []
    counts = {"polite": 0, "casual": 0, "other": 0, "risk": 0}
    kept = {"polite": 0, "casual": 0, "other": 0, "risk": 0}
    seen: set[str] = set()

    def add(level: str, reason: str, quote: str) -> None:
        quote = quote.strip()
        if len(quote) < 2 or quote in seen:
            return
        if not HANGUL_RE.search(quote):
            return
        seen.add(quote)
        samples.append(DialogueSample(level=level, reason=reason, text=quote))
        kept[level] += 1

    for text in texts:
        for match in QUOTE_RE.finditer(text):
            quote = (match.group(1) or match.group(2) or "").strip()
            level = classify_dialogue(quote)
            counts[level] += 1

            has_respect_term = any(term in quote for term in RESPECT_TERMS)
            has_casual_pronoun = bool(CASUAL_PRONOUN_RE.search(quote))
            has_polite_hint = any(term in quote for term in POLITE_HINTS)
            if level == "casual" and has_respect_term and kept["risk"] < max_each:
                counts["risk"] += 1
                add("risk", "존칭/직함 호칭과 반말 종결이 함께 나타남", quote)
                continue
            if level == "polite" and has_casual_pronoun and kept["risk"] < max_each:
                counts["risk"] += 1
                add("risk", "친밀/하대 대명사와 존대 종결이 함께 나타남", quote)
                continue
            if has_polite_hint and has_casual_pronoun and kept["risk"] < max_each:
                counts["risk"] += 1
                add("risk", "대명사와 종결어미가 충돌할 수 있음", quote)
                continue

            if kept[level] < max_each:
                add(level, f"{level} 대화 표본", quote)

    return samples, counts


def english_parenthetical_samples(texts: list[str], max_samples: int) -> tuple[list[str], int, int]:
    candidates: list[str] = []
    likely_leftovers = 0
    seen: set[str] = set()
    for text in texts:
        for match in INLINE_EN_RE.finditer(text):
            candidate = match.group(1).strip()
            words = EN_WORD_RE.findall(candidate)
            if len(words) >= 4:
                likely_leftovers += 1
            if candidate not in seen and len(candidates) < max_samples:
                candidates.append(candidate)
                seen.add(candidate)
    return candidates, sum(1 for text in texts for _ in INLINE_EN_RE.finditer(text)), likely_leftovers


def latest_audit_json(out_dir: Path) -> Path | None:
    paths = sorted(out_dir.glob("epub_translation_audit_*.json"))
    return paths[-1] if paths else None


def load_audit(path: Path | None) -> dict[str, dict]:
    if not path or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["name"]: item for item in data.get("audits", [])}


def shorten(text: str, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def render_report(
    *,
    folder: Path,
    audit_json: Path | None,
    audits: dict[str, dict],
    max_each: int,
    guide_chars: int,
) -> str:
    guides = find_relationship_guides()
    k_files = sorted(folder.glob("[[]k[]]*.epub"))
    lines: list[str] = [
        "# EPUB 추가 검수 표본 보고서",
        "",
        f"- 대상 폴더: `{folder}`",
        f"- 생성 시각: {datetime.now().isoformat(timespec='seconds')}",
        f"- 기준 구조 검수 JSON: `{audit_json}`" if audit_json else "- 기준 구조 검수 JSON: 없음",
        f"- 한글판 EPUB: {len(k_files)}개",
        f"- 작품당 대화 표본 상한: {max_each}개/분류",
        "",
        "## 전체 구조 검수 요약",
        "",
    ]

    issue_rows = [item for item in audits.values() if item.get("issues")]
    lines.append(f"- 구조/목차/한영쌍 이슈 파일: {len(issue_rows)}개")
    for item in issue_rows:
        lines.append(f"  - `{item['name']}`: {'; '.join(item.get('issues') or [])}")
    if not issue_rows:
        lines.append("- 구조/목차/한영쌍 이슈 없음")

    lines.extend(["", "## 작품별 말투/잔여 영어 표본", ""])
    for path in k_files:
        title = base_title(path)
        guide_path = match_guide(title, guides)
        guide = guide_excerpt(guide_path, guide_chars)
        texts = body_texts(path)
        samples, counts = dialogue_samples(texts, max_each=max_each)
        en_samples, en_total, en_likely_leftovers = english_parenthetical_samples(texts, max_samples=max_each)
        audit = audits.get(path.name, {})
        ke_audit = audits.get(f"[k-e] {title}.epub", {})

        lines.append(f"### {title}")
        lines.append(f"- `[k]` 파일: `{path.name}`")
        lines.append(f"- 관계/말투 가이드: `{guide_path}`" if guide_path else "- 관계/말투 가이드: 찾지 못함")
        if guide:
            lines.append(f"- 관계/말투 가이드 발췌: {shorten(guide, guide_chars)}")
        lines.append(
            "- 구조 검수: "
            + ("OK" if not audit.get("issues") else "; ".join(audit.get("issues") or []))
            + " / `[k-e]`: "
            + ("OK" if not ke_audit.get("issues") else "; ".join(ke_audit.get("issues") or []))
        )
        lines.append(
            f"- 대화 감지: polite={counts['polite']}, casual={counts['casual']}, other={counts['other']}, risk={counts['risk']}"
        )
        if en_total:
            lines.append(f"- `[k]` 괄호 속 영어 후보: total={en_total}, 긴 영어문장 후보={en_likely_leftovers}")
            for candidate in en_samples:
                lines.append(f"  - `{shorten(candidate, 140)}`")
        if samples:
            lines.append("- 말투 표본:")
            for sample in samples:
                lines.append(f"  - `{sample.level}` / {sample.reason}: {shorten(sample.text)}")
        else:
            lines.append("- 말투 표본: 대화문을 충분히 찾지 못함")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract review samples from translated EPUBs.")
    parser.add_argument("folder", nargs="?", type=Path, default=DEFAULT_FOLDER)
    parser.add_argument("--out-dir", type=Path, default=WORK_DIR)
    parser.add_argument("--audit-json", type=Path)
    parser.add_argument("--max-each", type=int, default=6)
    parser.add_argument("--guide-chars", type=int, default=900)
    args = parser.parse_args()

    folder = args.folder.expanduser()
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    audit_json = args.audit_json or latest_audit_json(out_dir)
    audits = load_audit(audit_json)
    report = render_report(
        folder=folder,
        audit_json=audit_json,
        audits=audits,
        max_each=max(1, args.max_each),
        guide_chars=max(0, args.guide_chars),
    )
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"epub_review_samples_{stamp}.md"
    out_path.write_text(report, encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
