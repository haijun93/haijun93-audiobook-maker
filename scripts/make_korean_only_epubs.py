#!/usr/bin/env python3
"""Build Korean-only EPUBs from paired Korean/English study EPUBs."""

from __future__ import annotations

import argparse
import re
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from atomic_io import atomic_output_path
from epub_integrity import validate_epub
from remove_readrobe_text_from_epubs import clone_info, scrub_epub
from safe_xml import safe_fromstring


XHTML_NS = "http://www.w3.org/1999/xhtml"
EPUB_NS = "http://www.idpf.org/2007/ops"
OPF_NS = "http://www.idpf.org/2007/opf"
DC_NS = "http://purl.org/dc/elements/1.1/"
XML_NS = "http://www.w3.org/XML/1998/namespace"

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
    stats = {"pairs": 0, "en_removed": 0, "inline_removed": 0}

    for paragraph in root.iter(f"{{{XHTML_NS}}}p"):
        if not has_class(paragraph, "pair"):
            continue
        korean_parts = [
            element_text(child)
            for child in paragraph.iter()
            if child is not paragraph and has_class(child, "ko")
        ]
        if not korean_parts:
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

    for element in root.iter():
        if has_class(element, "ko"):
            remove_class(element, "ko")
        if element.attrib.get(f"{{{XML_NS}}}lang") == "en":
            element.attrib.pop(f"{{{XML_NS}}}lang", None)

    xml = ET.tostring(root, encoding="utf-8", xml_declaration=True, short_empty_elements=True)
    return xml + b"\n", stats


def convert_css(data: bytes) -> bytes:
    text = data.decode("utf-8", "replace")
    text = re.sub(r"\n?span\.en\s*\{[^}]*\}\s*", "\n", text, flags=re.S)
    text = re.sub(r"\n?p\.pair\s*\{[^}]*\}\s*", "\n", text, flags=re.S)
    # 토익 학습 노트(span.study-note)는 k-e 대조 학습본 전용 기능이라 한글 단독본에서는
    # 스타일 자체가 필요 없다 - 노트 span은 convert_xhtml()이 이미 본문에서 제거하므로,
    # 여기서는 이제 쓰이지 않는 CSS 규칙만 정리한다.
    text = re.sub(r"\n?span\.study-note\s*\{[^}]*\}\s*", "\n", text, flags=re.S)
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


def output_name(input_name: str) -> str:
    if input_name.startswith("[k-e] "):
        return "[k] " + input_name[len("[k-e] ") :]
    if input_name.startswith("[k-e]"):
        return "[k]" + input_name[len("[k-e]") :]
    return "[k] " + input_name


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
                data = zin.read(name)
                lower = name.lower()
                if lower.endswith((".xhtml", ".html", ".htm")):
                    data, stats = convert_xhtml(data, remove_inline_parenthetical_english)
                    totals["pairs"] += stats["pairs"]
                    totals["en_removed"] += stats["en_removed"]
                    totals["inline_removed"] += stats["inline_removed"]
                    data = data.replace(b">Kindle EPUB<", ">한국어판<".encode("utf-8"))
                    data = data.replace(b">Front Matter<", ">앞부분<".encode("utf-8"))
                elif lower.endswith(".css"):
                    data = convert_css(data)
                elif lower.endswith(".opf"):
                    data = convert_opf(data, input_path.name)
                elif lower.endswith(".ncx"):
                    data = data.replace(b">Front Matter<", ">앞부분<".encode("utf-8"))

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
        output_path = input_path.with_name(output_name(input_path.name))
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
