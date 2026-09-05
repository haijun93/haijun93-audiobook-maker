#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import zipfile
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from safe_xml import safe_fromstring


EPUB_FOLDER = Path(str(Path.home()) + "/Desktop/소설/#[k-e]")
NOVEL_ROOT = Path(str(Path.home()) + "/Desktop/소설")


CLASS_RE = re.compile(r"class=[\"']([^\"']+)[\"']")
TAG_RE = re.compile(r"<[^>]+>")
QUOTE_RE = re.compile(r"[“\"]([^“”\"]{2,240})[”\"]")
POLITE_RE = re.compile(r"(요|니다|니까|세요|십시오|어요|아요|해요|예요|이에요|군요|네요)[.!?…]*$")
CASUAL_RE = re.compile(r"(어|아|해|야|지|네|군|거야|잖아|겠어|했어|한다|했다|다)[.!?…]*$")
INLINE_EN_RE = re.compile(r"\([A-Za-z][^()]{8,}\)")
HREF_RE = re.compile(r"\bhref=[\"']([^\"']+)[\"']")
NCX_SRC_RE = re.compile(r"<content\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.I)


def has_class(text: str, class_name: str) -> int:
    count = 0
    for match in CLASS_RE.finditer(text):
        if class_name in match.group(1).split():
            count += 1
    return count


def class_texts(text: str, class_name: str) -> list[str]:
    matches: list[str] = []
    pattern = re.compile(
        rf"<[^>]*class=[\"'][^\"']*\b{re.escape(class_name)}\b[^\"']*[\"'][^>]*>(.*?)</[^>]+>",
        re.S,
    )
    for match in pattern.finditer(text):
        matches.append(clean_text(match.group(1)))
    return matches


def meaningful_count(values: list[str], pattern: str) -> int:
    regex = re.compile(pattern)
    return sum(1 for value in values if regex.search(value))


def clean_text(text: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    text = TAG_RE.sub(" ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
    )
    return re.sub(r"\s+", " ", text).strip()


def base_title(path: Path) -> str:
    name = path.stem
    for prefix in ("[k-e] ", "[k-e]", "[k] ", "[k]"):
        if name.startswith(prefix):
            return name[len(prefix) :].strip()
    return name


def normalized(text: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", text.lower())


def output_name_for_k(title: str) -> str:
    return f"[k] {title}.epub"


def classify_dialogue(dialogue: str) -> str:
    text = dialogue.strip()
    if POLITE_RE.search(text):
        return "polite"
    if CASUAL_RE.search(text):
        return "casual"
    return "other"


def text_files(archive: zipfile.ZipFile) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in archive.namelist():
        lower = name.lower()
        if lower.endswith((".xhtml", ".html", ".htm", ".opf", ".ncx", ".css")):
            result[name] = archive.read(name).decode("utf-8", "replace")
    return result


@dataclass
class EpubAudit:
    name: str
    kind: str
    title: str
    exists: bool
    size: int = 0
    mimetype_first: bool = False
    xml_ok: bool = False
    opf_count: int = 0
    nav_count: int = 0
    ncx_count: int = 0
    nav_items: int = 0
    ncx_points: int = 0
    broken_nav_links: int = 0
    broken_ncx_links: int = 0
    missing_markers: int = 0
    ko_blocks: int = 0
    en_blocks: int = 0
    meaningful_ko_blocks: int = 0
    meaningful_en_blocks: int = 0
    pair_blocks: int = 0
    inline_english_parentheticals: int = 0
    dialogue_count: int = 0
    polite_dialogues: int = 0
    casual_dialogues: int = 0
    other_dialogues: int = 0
    issues: list[str] | None = None
    notes: list[str] | None = None


def audit_epub(path: Path, kind: str) -> EpubAudit:
    audit = EpubAudit(
        name=path.name,
        kind=kind,
        title=base_title(path),
        exists=path.exists(),
        issues=[],
        notes=[],
    )
    if not path.exists():
        audit.issues.append("파일 없음")
        return audit
    audit.size = path.stat().st_size
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            audit.mimetype_first = names[:1] == ["mimetype"]
            texts = text_files(archive)
            audit.opf_count = sum(1 for name in names if name.lower().endswith(".opf"))
            audit.nav_count = sum(1 for name in names if name.lower().endswith("nav.xhtml"))
            audit.ncx_count = sum(1 for name in names if name.lower().endswith(".ncx"))
            audit.nav_items = sum(text.count("<li") for name, text in texts.items() if name.lower().endswith("nav.xhtml"))
            audit.ncx_points = sum(text.count("<navPoint") for name, text in texts.items() if name.lower().endswith(".ncx"))
            name_set = set(names)
            for name, text in texts.items():
                lower = name.lower()
                if lower.endswith("nav.xhtml"):
                    nav_dir = Path(name).parent
                    for href in HREF_RE.findall(text):
                        target = unquote(href.split("#", 1)[0])
                        if not target or re.match(r"^[a-z]+:", target, re.I):
                            continue
                        full = str(nav_dir / target) if str(nav_dir) != "." else target
                        if full not in name_set:
                            audit.broken_nav_links += 1
                if lower.endswith(".ncx"):
                    ncx_dir = Path(name).parent
                    for src in NCX_SRC_RE.findall(text):
                        target = unquote(src.split("#", 1)[0])
                        if not target or re.match(r"^[a-z]+:", target, re.I):
                            continue
                        full = str(ncx_dir / target) if str(ncx_dir) != "." else target
                        if full not in name_set:
                            audit.broken_ncx_links += 1
            audit.missing_markers = sum(text.count("[번역 누락]") for text in texts.values())
            audit.ko_blocks = sum(has_class(text, "ko") for text in texts.values())
            audit.en_blocks = sum(has_class(text, "en") for text in texts.values())
            ko_texts = [value for text in texts.values() for value in class_texts(text, "ko")]
            en_texts = [value for text in texts.values() for value in class_texts(text, "en")]
            audit.meaningful_ko_blocks = meaningful_count(ko_texts, r"[가-힣A-Za-z0-9]")
            audit.meaningful_en_blocks = meaningful_count(en_texts, r"[A-Za-z0-9]")
            audit.pair_blocks = sum(has_class(text, "pair") for text in texts.values())
            audit.inline_english_parentheticals = sum(len(INLINE_EN_RE.findall(clean_text(text))) for text in texts.values())

            xml_parse_errors: list[str] = []
            for name, text in texts.items():
                if name.lower().endswith((".xhtml", ".html", ".htm", ".opf", ".ncx")):
                    try:
                        safe_fromstring(text.encode("utf-8"))
                    except Exception as exc:
                        xml_parse_errors.append(f"{name}: {exc}")
            audit.xml_ok = not xml_parse_errors
            if xml_parse_errors:
                audit.issues.extend(f"XML 파싱 오류: {error}" for error in xml_parse_errors[:3])

            body_text = "\n".join(clean_text(text) for name, text in texts.items() if name.lower().endswith((".xhtml", ".html", ".htm")))
            dialogues = QUOTE_RE.findall(body_text)
            audit.dialogue_count = len(dialogues)
            for dialogue in dialogues:
                kind_name = classify_dialogue(dialogue)
                if kind_name == "polite":
                    audit.polite_dialogues += 1
                elif kind_name == "casual":
                    audit.casual_dialogues += 1
                else:
                    audit.other_dialogues += 1
    except Exception as exc:
        audit.issues.append(f"EPUB 읽기 오류: {exc}")
        return audit

    if not audit.mimetype_first:
        audit.issues.append("mimetype이 ZIP 첫 항목이 아님")
    if audit.opf_count <= 0:
        audit.issues.append("OPF 없음")
    if audit.nav_count <= 0 or audit.nav_items <= 0:
        audit.issues.append("EPUB nav.xhtml 목차 없음 또는 비어 있음")
    if audit.ncx_count <= 0 or audit.ncx_points <= 0:
        audit.issues.append("toc.ncx 목차 없음 또는 비어 있음")
    if audit.broken_nav_links:
        audit.issues.append(f"nav.xhtml 깨진 링크 {audit.broken_nav_links}개")
    if audit.broken_ncx_links:
        audit.issues.append(f"toc.ncx 깨진 링크 {audit.broken_ncx_links}개")
    if audit.missing_markers:
        audit.issues.append(f"번역 누락 마커 {audit.missing_markers}개")

    if kind == "k-e":
        if audit.ko_blocks <= 0 or audit.en_blocks <= 0:
            if audit.inline_english_parentheticals > 100:
                audit.notes.append("구형 인라인 한영 형식: ko/en class 대신 한국어 문장 뒤 괄호 영어가 사용됨")
            else:
                audit.issues.append("한영 학습용 ko/en 블록 없음")
        elif audit.ko_blocks != audit.en_blocks:
            if audit.meaningful_ko_blocks == audit.meaningful_en_blocks:
                audit.notes.append(
                    f"ko/en class 수는 다르지만 의미 있는 문장 수는 일치함: "
                    f"ko={audit.ko_blocks}, en={audit.en_blocks}"
                )
            else:
                audit.issues.append(
                    f"한영 블록 수 불일치: ko={audit.ko_blocks}, en={audit.en_blocks}, "
                    f"meaningful_ko={audit.meaningful_ko_blocks}, meaningful_en={audit.meaningful_en_blocks}"
                )
    elif kind == "k":
        if audit.en_blocks:
            audit.issues.append(f"한글판에 영어 블록 class=en {audit.en_blocks}개 남음")
        if audit.pair_blocks:
            audit.issues.append(f"한글판에 학습용 pair 블록 {audit.pair_blocks}개 남음")
        if audit.inline_english_parentheticals > 20:
            audit.notes.append(f"괄호 속 영어 후보 {audit.inline_english_parentheticals}개: 고유명사/출판정보인지 표본 확인 필요")

    if audit.dialogue_count >= 50:
        total_classified = audit.polite_dialogues + audit.casual_dialogues
        if total_classified:
            polite_ratio = audit.polite_dialogues / total_classified
            if 0.25 <= polite_ratio <= 0.75:
                audit.notes.append(
                    "대화체에 존대/반말이 모두 많이 나타남: 인물관계 기반 표본 검수 필요"
                )
    else:
        audit.notes.append("대화 표본이 적어 말투 검수 신뢰 낮음")

    return audit


def find_relationship_guides() -> dict[str, str]:
    guides: dict[str, str] = {}
    for path in NOVEL_ROOT.glob("**/relationship_guide.txt"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            continue
        if len(text) < 300:
            continue
        key = normalized(path.parent.name.replace("_chatgpt_translate_work", ""))
        guides[key] = str(path)
    return guides


def match_guide(title: str, guides: dict[str, str]) -> str | None:
    title_key = normalized(title)
    if not title_key:
        return None
    best: tuple[int, str] | None = None
    for key, path in guides.items():
        if title_key and title_key in key:
            score = len(title_key)
        elif key and key in title_key:
            score = len(key)
        else:
            continue
        if best is None or score > best[0]:
            best = (score, path)
    return best[1] if best else None


def render_report(folder: Path, audits: list[EpubAudit], guides: dict[str, str]) -> str:
    now = datetime.now().isoformat(timespec="seconds")
    k_e = [item for item in audits if item.kind == "k-e"]
    k = [item for item in audits if item.kind == "k"]
    by_title: dict[str, dict[str, EpubAudit]] = {}
    for item in audits:
        by_title.setdefault(item.title, {})[item.kind] = item

    missing_k = sorted(title for title, row in by_title.items() if "k-e" in row and "k" not in row)
    missing_ke = sorted(title for title, row in by_title.items() if "k" in row and "k-e" not in row)
    issues = [item for item in audits if item.issues]

    lines = [
        "# EPUB 번역 검수 보고서",
        "",
        f"- 대상 폴더: `{folder}`",
        f"- 생성 시각: {now}",
        f"- `[k-e]` 파일: {len(k_e)}개",
        f"- `[k]` 파일: {len(k)}개",
        f"- 구조/목차/쌍 검수 이슈 파일: {len(issues)}개",
        f"- `[k]` 누락 작품: {len(missing_k)}개",
        f"- `[k-e]` 누락 작품: {len(missing_ke)}개",
        "",
        "## 요약",
        "",
    ]
    if missing_k:
        lines.append("### `[k]` 한글 전용본 누락")
        lines.extend(f"- {title}" for title in missing_k)
        lines.append("")
    if missing_ke:
        lines.append("### `[k-e]` 한영본 누락")
        lines.extend(f"- {title}" for title in missing_ke)
        lines.append("")
    if issues:
        lines.append("### 구조 검수 이슈")
        for item in issues:
            lines.append(f"- `{item.name}`: " + "; ".join(item.issues or []))
        lines.append("")
    else:
        lines.append("구조 검수 이슈는 없습니다.")
        lines.append("")

    lines.append("## 작품별 상세")
    lines.append("")
    for title in sorted(by_title):
        row = by_title[title]
        guide = match_guide(title, guides)
        lines.append(f"### {title}")
        lines.append(f"- 관계/말투 가이드: `{guide}`" if guide else "- 관계/말투 가이드: 찾지 못함")
        for kind in ("k-e", "k"):
            item = row.get(kind)
            if not item:
                lines.append(f"- `{kind}`: 없음")
                continue
            status = "OK" if not item.issues else "ISSUE"
            lines.append(
                f"- `{kind}`: {status}, size={item.size}, nav={item.nav_items}/{item.ncx_points}, "
                f"broken_nav={item.broken_nav_links}/{item.broken_ncx_links}, "
                f"ko={item.ko_blocks}, en={item.en_blocks}, meaningful={item.meaningful_ko_blocks}/{item.meaningful_en_blocks}, pair={item.pair_blocks}, "
                f"dialogue={item.dialogue_count}, polite={item.polite_dialogues}, casual={item.casual_dialogues}"
            )
            if item.issues:
                lines.append(f"  - 이슈: {'; '.join(item.issues)}")
            if item.notes:
                lines.append(f"  - 참고: {'; '.join(item.notes)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit translated Kindle study EPUBs.")
    parser.add_argument("folder", nargs="?", type=Path, default=EPUB_FOLDER)
    parser.add_argument("--out-dir", type=Path, default=Path(".work"))
    args = parser.parse_args()

    folder = args.folder.expanduser()
    epubs = sorted(folder.glob("*.epub"))
    audits: list[EpubAudit] = []
    for path in epubs:
        if path.name.startswith("[k-e]"):
            audits.append(audit_epub(path, "k-e"))
        elif path.name.startswith("[k]"):
            audits.append(audit_epub(path, "k"))

    guides = find_relationship_guides()
    report = render_report(folder, audits, guides)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = args.out_dir / f"epub_translation_audit_{stamp}.md"
    json_path = args.out_dir / f"epub_translation_audit_{stamp}.json"
    report_path.write_text(report, encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "folder": str(folder),
                "audits": [asdict(item) for item in audits],
                "relationship_guides": guides,
                "report": str(report_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(report_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
