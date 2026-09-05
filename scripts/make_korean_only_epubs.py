#!/usr/bin/env python3
"""Build Korean-only EPUBs from paired Korean/English study EPUBs."""

from __future__ import annotations

import argparse
import re
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from atomic_io import atomic_output_path  # noqa: E402
from epub_integrity import validate_epub  # noqa: E402
from remove_readrobe_text_from_epubs import clone_info, scrub_epub  # noqa: E402
from safe_xml import safe_fromstring  # noqa: E402
from audiobook_studio.epub_xray_policy import assert_no_xray  # noqa: E402
from translation_quality_checks import strict_untranslated_output_findings  # noqa: E402


XHTML_NS = "http://www.w3.org/1999/xhtml"
EPUB_NS = "http://www.idpf.org/2007/ops"
OPF_NS = "http://www.idpf.org/2007/opf"
DC_NS = "http://purl.org/dc/elements/1.1/"
XML_NS = "http://www.w3.org/XML/1998/namespace"

KOREAN_STRUCTURAL_LABELS = {
    "back cover": "뒷표지",
    "copyright": "판권",
    "dedication": "헌사",
    "quote": "인용문",
    "prologue": "프롤로그",
    "table of contents": "목차",
    "contents": "목차",
    "cover": "표지",
    "text": "본문",
}

ET.register_namespace("", XHTML_NS)
ET.register_namespace("epub", EPUB_NS)
ET.register_namespace("dc", DC_NS)


def has_class(element: ET.Element, class_name: str) -> bool:
    return class_name in element.attrib.get("class", "").split()


def remove_class(element: ET.Element, class_name: str) -> None:
    classes = [c for c in element.attrib.get("class", "").split() if c != class_name]
    if classes:
        element.set("class", " ".join(classes))
    else:
        element.attrib.pop("class", None)


def tag_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def element_text(element: ET.Element) -> str:
    return " ".join("".join(element.itertext()).split())


def remove_matching_children(parent: ET.Element, predicate) -> None:
    for child in list(parent):
        remove_matching_children(child, predicate)
        if predicate(child):
            if child.tail and len(parent):
                previous = None
                siblings = list(parent)
                index = siblings.index(child)
                if index > 0:
                    previous = siblings[index - 1]
                if previous is not None:
                    previous.tail = (previous.tail or "") + child.tail
                else:
                    parent.text = (parent.text or "") + child.tail
            parent.remove(child)


def normalize_structural_labels(root: ET.Element) -> int:
    """Translate standalone frontmatter/navigation labels in a [k] EPUB.

    These labels are not paired paragraphs, so the normal ``span.en`` removal
    cannot see them.  The old converter consequently left headings such as
    ``Dedication`` and ``Quote`` in Korean-only output.
    """
    changed = 0
    for element in root.iter():
        if tag_name(element) not in {"title", "h1", "h2", "h3", "a"}:
            continue
        current = element_text(element).strip()
        translated = KOREAN_STRUCTURAL_LABELS.get(current.lower())
        if not translated or current == translated:
            continue
        if list(element):
            for child in list(element):
                element.remove(child)
        element.text = translated
        changed += 1
    return changed


def strip_inline_english_parentheticals(text: str) -> tuple[str, int]:
    removed = 0
    output: list[str] = []
    index = 0

    while index < len(text):
        if text[index] != "(":
            output.append(text[index])
            index += 1
            continue

        depth = 0
        end = index
        while end < len(text):
            if text[end] == "(":
                depth += 1
            elif text[end] == ")":
                depth -= 1
                if depth == 0:
                    break
            end += 1

        if end >= len(text) or depth != 0:
            inner = text[index + 1 :]
            if re.search(r"[A-Za-z]", inner) and not re.search(r"[가-힣]", inner):
                while output and output[-1] == " ":
                    output.pop()
                removed += 1
                break
            output.append(text[index])
            index += 1
            continue

        inner = text[index + 1 : end]
        if re.search(r"[A-Za-z]", inner) and not re.search(r"[가-힣]", inner):
            while output and output[-1] == " ":
                output.pop()
            removed += 1
            index = end + 1
            continue

        output.append(text[index : end + 1])
        index = end + 1

    balanced: list[str] = []
    depth = 0
    for character in "".join(output):
        if character == "(":
            depth += 1
            balanced.append(character)
        elif character == ")":
            if depth:
                depth -= 1
                balanced.append(character)
            else:
                removed += 1
        else:
            balanced.append(character)

    stripped = re.sub(r" {2,}", " ", "".join(balanced))
    stripped = re.sub(r"\.{2,}", ".", stripped)
    return stripped, removed


def strip_inline_english_from_tree(root: ET.Element) -> int:
    removed = 0
    for element in root.iter():
        if element.text:
            element.text, count = strip_inline_english_parentheticals(element.text)
            removed += count
        if element.tail:
            element.tail, count = strip_inline_english_parentheticals(element.tail)
            removed += count
    return removed


def convert_xhtml(data: bytes, remove_inline_parenthetical_english: bool = False) -> tuple[bytes, dict[str, int]]:
    root = safe_fromstring(data)
    stats = {"pairs": 0, "en_removed": 0, "inline_removed": 0, "labels_translated": 0}

    for paragraph in list(root.iter(f"{{{XHTML_NS}}}p")):
        if not has_class(paragraph, "pair"):
            continue
        korean_parts = [
            element_text(child)
            for child in paragraph.iter()
            if child is not paragraph and has_class(child, "ko")
        ]
        if not korean_parts:
            # BUG FIX: paragraph has no Korean translation (untranslated chunk).
            # Previously this was left in place, leaking raw English span.en content.
            # Now we locate the parent and remove this paragraph entirely.
            for parent in root.iter():
                if paragraph in list(parent):
                    if paragraph.tail:
                        siblings = list(parent)
                        idx = siblings.index(paragraph)
                        if idx > 0:
                            siblings[idx - 1].tail = (siblings[idx - 1].tail or "") + paragraph.tail
                        else:
                            parent.text = (parent.text or "") + paragraph.tail
                    parent.remove(paragraph)
                    break
            continue
        tail = paragraph.tail
        attrs = dict(paragraph.attrib)
        paragraph.clear()
        paragraph.tail = tail
        paragraph.attrib.update(attrs)
        remove_class(paragraph, "pair")
        paragraph.text = " ".join(part for part in korean_parts if part)
        stats["pairs"] += 1

    def is_english_or_break(element: ET.Element) -> bool:
        if has_class(element, "en") or element.attrib.get(f"{{{XML_NS}}}lang") == "en":
            stats["en_removed"] += 1
            return True
        return False

    remove_matching_children(root, is_english_or_break)

    if remove_inline_parenthetical_english:
        stats["inline_removed"] += strip_inline_english_from_tree(root)

    stats["labels_translated"] = normalize_structural_labels(root)

    for element in root.iter():
        if has_class(element, "ko"):
            remove_class(element, "ko")
        if element.attrib.get(f"{{{XML_NS}}}lang") == "en":
            element.attrib.pop(f"{{{XML_NS}}}lang", None)

    xml = ET.tostring(root, encoding="utf-8", xml_declaration=True, short_empty_elements=True)
    return xml + b"\n", stats


def is_xray_file(name: str) -> bool:
    """Return True for X-Ray dramatis personae files excluded from [k] EPUBs."""
    lower = name.lower()
    basename = lower.rsplit("/", 1)[-1]
    return basename.startswith("000-xray") or "dramatis-personae" in basename or "dramatis_personae" in basename


def find_untranslated_source_pairs(input_path: Path) -> list[str]:
    """Return bilingual blocks that cannot safely produce a Korean-only EPUB."""

    issues: list[str] = []
    with zipfile.ZipFile(input_path, "r") as archive:
        for name in archive.namelist():
            lower = name.lower()
            if not lower.endswith((".xhtml", ".html", ".htm")) or any(
                marker in lower for marker in ("cover", "nav", "xray", "dramatis-personae")
            ):
                continue
            root = safe_fromstring(archive.read(name))
            for index, paragraph in enumerate(root.iter(f"{{{XHTML_NS}}}p"), start=1):
                if not has_class(paragraph, "pair"):
                    continue
                english = " ".join(
                    element_text(child)
                    for child in paragraph.iter()
                    if has_class(child, "en")
                ).strip()
                korean = " ".join(
                    element_text(child)
                    for child in paragraph.iter()
                    if has_class(child, "ko")
                ).strip()
                if not english:
                    continue
                findings = strict_untranslated_output_findings(
                    {f"{name}:{index}": english}, {f"{name}:{index}": korean}
                )
                if findings:
                    issues.append(f"{name}:{index}")
    return issues


def strip_xray_from_opf(data: bytes) -> bytes:
    """Remove xray manifest item and spine itemref from OPF XML."""
    text = data.decode("utf-8", "replace")
    text = re.sub(
        r'<item\b[^>]*href=["\'][^"\'>]*(?:000-xray|dramatis[_-]personae)[^"\'>]*["\'][^>]*/?>',
        "",
        text,
        flags=re.I,
    )
    text = re.sub(
        r'<itemref\b[^>]*idref=["\'][^"\'>]*xray[^"\'>]*["\'][^>]*/?>',
        "",
        text,
        flags=re.I,
    )
    return text.encode("utf-8")


def strip_xray_from_nav(data: bytes) -> bytes:
    """Remove X-Ray navpoint/li entries from nav.xhtml and toc.ncx."""
    text = data.decode("utf-8", "replace")
    # nav.xhtml: remove <li> linking to xray file
    text = re.sub(
        r'<li[^>]*>\s*<a[^>]*href=["\'][^"\'>]*(?:000-xray|dramatis[_-]personae)[^"\'>]*["\'][^>]*>.*?</a>\s*</li>',
        "",
        text,
        flags=re.S | re.I,
    )
    # toc.ncx: remove <navPoint> linking to xray file
    text = re.sub(
        r'<navPoint\b[^>]*>(?:(?!<navPoint).)*?<content\b[^>]*src=["\'][^"\'>]*(?:000-xray|dramatis[_-]personae)[^"\'>]*["\'][^>]*/>(?:(?!<navPoint).)*?</navPoint>',
        "",
        text,
        flags=re.S | re.I,
    )
    return text.encode("utf-8")


def convert_css(data: bytes) -> bytes:
    text = data.decode("utf-8", "replace")
    text = re.sub(r"\n?span\.en\s*\{[^}]*\}\s*", "\n", text, flags=re.S)
    text = re.sub(r"\n?p\.pair\s*\{[^}]*\}\s*", "\n", text, flags=re.S)
    # 토익 학습 노트(span.study-note)는 k-e 대조 학습본 전용 기능이라 한글 단독본에서는
    # 스타일 자체가 필요 없다 - 노트 span은 convert_xhtml()이 이미 본문에서 제거하므로,
    # 여기서는 이제 쓰이지 않는 CSS 규칙만 정리한다.
    text = re.sub(r"\n?span\.study-note\s*\{[^}]*\}\s*", "\n", text, flags=re.S)
    text = re.sub(r"p\s*\{[^}]*\}", "p { margin: 0 0 0.5em; text-indent: 0; }", text)
    if "letter-spacing" not in text:
        text = text.replace("line-height: 1.58;", "line-height: 1.65;\n  letter-spacing: -0.03em;\n  overflow-wrap: break-word;")
        text = text.replace("line-height: 1.65;", "line-height: 1.65;\n  letter-spacing: -0.03em;\n  overflow-wrap: break-word;")
    if "blockquote" not in text:
        text += "\nblockquote { margin: 1.2em 0 1.2em 1.2em; padding-left: 0.8em; border-left: 3px solid rgba(148, 163, 184, 0.4); font-style: italic; opacity: 0.92; }\n"
    if ".scene-break" not in text:
        text += "\n.scene-break { text-align: center; margin: 1.8em 0; color: #94a3b8; letter-spacing: 0.6em; font-size: 0.9em; }\n"
    text = text.replace("Kindle EPUB", "한국어판")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.encode("utf-8")


def convert_opf(data: bytes, source_name: str) -> bytes:
    text = data.decode("utf-8", "replace")
    identifier = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, source_name + ':korean-only')}"
    modified = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    text = re.sub(
        r"(<dc:identifier\b[^>]*>)(.*?)(</dc:identifier>)",
        rf"\g<1>{identifier}\g<3>",
        text,
        count=1,
        flags=re.S,
    )
    text = re.sub(
        r"(<dc:language\b[^>]*>)(.*?)(</dc:language>)",
        r"\g<1>ko\g<3>",
        text,
        count=1,
        flags=re.S,
    )
    text = re.sub(
        r"(<meta\b[^>]*property=[\"']dcterms:modified[\"'][^>]*>)(.*?)(</meta>)",
        rf"\g<1>{modified}\g<3>",
        text,
        count=1,
        flags=re.S,
    )
    return text.encode("utf-8")


def convert_ncx_labels(data: bytes) -> bytes:
    """Translate standalone NCX labels without changing original targets."""
    text = data.decode("utf-8", "replace")
    for english, korean in KOREAN_STRUCTURAL_LABELS.items():
        text = re.sub(
            rf"(<text\b[^>]*>)\s*{re.escape(english)}\s*(</text>)",
            rf"\g<1>{korean}\g<2>",
            text,
            flags=re.I,
        )
    return text.encode("utf-8")


def output_name(input_name: str) -> str:
    s = input_name
    while re.match(r"^\[[^\]]+\]\s*", s):
        s = re.sub(r"^\[[^\]]+\]\s*", "", s)
    return f"[k] {s}".strip()


def korean_output_path(input_path: Path) -> Path:
    """Mirror a [k-e] source into the standard sibling [k] root."""
    parts = list(input_path.parts)
    try:
        edition_index = len(parts) - 1 - parts[::-1].index("[k-e]")
    except ValueError:
        return input_path.with_name(output_name(input_path.name))
    parts[edition_index] = "[k]"
    return Path(*parts).with_name(output_name(input_path.name))


def uses_structured_pairs(input_path: Path) -> bool:
    with zipfile.ZipFile(input_path, "r") as zin:
        for name in zin.namelist():
            if not name.lower().endswith((".xhtml", ".html", ".htm")):
                continue
            text = zin.read(name).decode("utf-8", "replace")
            if "class=\"en\"" in text or "class='en'" in text or "class=\"pair\"" in text or "class='pair'" in text:
                return True
    return False


def convert_epub(input_path: Path, output_path: Path, overwrite: bool) -> dict[str, int]:
    source_integrity = validate_epub(input_path)
    if not source_integrity.valid:
        raise RuntimeError(
            "Source bilingual EPUB failed integrity validation: "
            + "; ".join(source_integrity.issues[:8])
        )
    untranslated = find_untranslated_source_pairs(input_path)
    if untranslated:
        sample = ", ".join(untranslated[:10])
        raise RuntimeError(
            "Source bilingual EPUB contains untranslated English blocks; refusing to publish [k]. "
            f"Re-translate first ({len(untranslated)} blocks; e.g. {sample})"
        )
    if output_path.exists() and not overwrite:
        cleanup = scrub_epub(output_path)
        if str(cleanup.get("status") or "").startswith("error:"):
            raise RuntimeError(f"Korean EPUB watermark cleanup failed: {cleanup['status']}")
        integrity = validate_epub(output_path)
        if not integrity.valid:
            raise RuntimeError(
                "Existing Korean EPUB failed integrity validation: "
                + "; ".join(integrity.issues[:8])
            )
        return {
            "skipped": 1,
            "pairs": 0,
            "en_removed": 0,
            "inline_removed": 0,
            "watermarks_removed": int(cleanup.get("replacements") or 0),
        }

    remove_inline_parenthetical_english = not uses_structured_pairs(input_path)
    totals = {"skipped": 0, "pairs": 0, "en_removed": 0, "inline_removed": 0}
    with atomic_output_path(output_path) as temp_output:
        with zipfile.ZipFile(input_path, "r") as zin, zipfile.ZipFile(temp_output, "w") as zout:
            zout.comment = zin.comment
            names = zin.namelist()
            if "mimetype" in names:
                original = zin.getinfo("mimetype")
                zout.writestr(
                    clone_info(original, compress_type=zipfile.ZIP_STORED),
                    zin.read("mimetype"),
                )

            for name in names:
                if name == "mimetype":
                    continue
                # ⚡ ZERO X-RAY PRINCIPLE: skip dramatis personae file entirely from [k] epub
                if is_xray_file(name):
                    totals.setdefault("xray_removed", 0)
                    totals["xray_removed"] = totals.get("xray_removed", 0) + 1
                    continue
                data = zin.read(name)
                lower = name.lower()
                if lower.endswith((".xhtml", ".html", ".htm")):
                    data, stats = convert_xhtml(data, remove_inline_parenthetical_english)
                    totals["pairs"] += stats["pairs"]
                    totals["en_removed"] += stats["en_removed"]
                    totals["inline_removed"] += stats["inline_removed"]
                    data = data.replace(b">Kindle EPUB<", ">한국어판<".encode("utf-8"))
                    data = data.replace(b">Front Matter<", ">앞부분<".encode("utf-8"))
                    # Strip xray nav entries from nav.xhtml
                    if "nav" in lower:
                        data = strip_xray_from_nav(data)
                elif lower.endswith(".css"):
                    data = convert_css(data)
                elif lower.endswith(".opf"):
                    data = convert_opf(data, input_path.name)
                    # Strip xray item/itemref from OPF manifest+spine
                    data = strip_xray_from_opf(data)
                elif lower.endswith(".ncx"):
                    data = data.replace(b">Front Matter<", ">앞부분<".encode("utf-8"))
                    data = convert_ncx_labels(data)
                    # Strip xray navPoint from toc.ncx
                    data = strip_xray_from_nav(data)

                original = zin.getinfo(name)
                zout.writestr(clone_info(original), data)

        cleanup = scrub_epub(temp_output)
        if str(cleanup.get("status") or "").startswith("error:"):
            raise RuntimeError(f"Korean EPUB watermark cleanup failed: {cleanup['status']}")
        integrity = validate_epub(temp_output)
        if not integrity.valid:
            raise RuntimeError(
                "Korean EPUB failed integrity validation: "
                + "; ".join(integrity.issues[:8])
            )
        assert_no_xray(temp_output)
        totals["watermarks_removed"] = int(cleanup.get("replacements") or 0)
    return totals


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    folder = args.folder.expanduser()
    epubs = sorted(folder.glob("[[]k-e[]]*.epub"))
    if not epubs:
        raise SystemExit(f"No [k-e] EPUBs found in {folder}")

    print(f"Found {len(epubs)} [k-e] EPUBs in {folder}")
    converted = skipped = total_pairs = total_removed = total_inline_removed = 0
    for input_path in epubs:
        output_path = korean_output_path(input_path)
        stats = convert_epub(input_path, output_path, args.overwrite)
        if stats["skipped"]:
            skipped += 1
            print(f"SKIP {output_path.name}")
            continue
        converted += 1
        total_pairs += stats["pairs"]
        total_removed += stats["en_removed"]
        total_inline_removed += stats["inline_removed"]
        print(
            f"OK   {output_path.name} "
            f"(korean paragraphs: {stats['pairs']}, "
            f"extra English nodes removed: {stats['en_removed']}, "
            f"inline English removed: {stats['inline_removed']})"
        )

    print(
        f"Done. converted={converted}, skipped={skipped}, "
        f"korean_paragraphs={total_pairs}, "
        f"extra_english_nodes_removed={total_removed}, "
        f"inline_english_removed={total_inline_removed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
