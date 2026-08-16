#!/usr/bin/env python3
"""Build English-plus-study-notes EPUBs ([e-s]) from paired [study] EPUBs.

[e-s] keeps the English sentence and the optional "※학습:" note that
`translate_epub_with_chatgpt_web_to_study_epub.build_epub(include_study_notes=True)`
already embeds in `[study]` output, and drops the Korean translation line -
mirroring how `make_korean_only_epubs.py` keeps only the Korean side of the
same `<p class="pair">`/`<h2>` markup.
"""

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


def convert_xhtml(data: bytes) -> tuple[bytes, dict[str, int]]:
    root = safe_fromstring(data)
    stats = {"pairs": 0, "notes_kept": 0, "ko_removed": 0}

    for paragraph in root.iter(f"{{{XHTML_NS}}}p"):
        if not has_class(paragraph, "pair"):
            continue
        english_parts = [
            element_text(child)
            for child in paragraph
            if child is not paragraph and has_class(child, "en")
        ]
        if not english_parts:
            continue
        note_parts = [
            element_text(child)
            for child in paragraph
            if child is not paragraph and has_class(child, "study-note")
        ]
        tail = paragraph.tail
        attrs = dict(paragraph.attrib)
        paragraph.clear()
        paragraph.tail = tail
        paragraph.attrib.update(attrs)
        remove_class(paragraph, "pair")
        paragraph.text = " ".join(part for part in english_parts if part)
        note_text = " ".join(part for part in note_parts if part)
        if note_text:
            ET.SubElement(paragraph, f"{{{XHTML_NS}}}br")
            note_span = ET.SubElement(paragraph, f"{{{XHTML_NS}}}span")
            note_span.set("class", "study-note")
            note_span.set(f"{{{XML_NS}}}lang", "ko")
            note_span.text = note_text
            stats["notes_kept"] += 1
        stats["pairs"] += 1

    def is_korean(element: ET.Element) -> bool:
        if has_class(element, "ko"):
            stats["ko_removed"] += 1
            return True
        return False

    remove_matching_children(root, is_korean)

    if root.tag == f"{{{XHTML_NS}}}html":
        if root.attrib.get(f"{{{XML_NS}}}lang") == "ko":
            root.set(f"{{{XML_NS}}}lang", "en")
        if root.attrib.get("lang") == "ko":
            root.set("lang", "en")

    xml = ET.tostring(root, encoding="utf-8", xml_declaration=True, short_empty_elements=True)
    return xml + b"\n", stats


def convert_css(data: bytes) -> bytes:
    text = data.decode("utf-8", "replace")
    # 영어가 이제 본문이므로, [study]에서 영어를 부차적으로 보이게 하던 회색/축소 스타일과
    # 더 이상 쓰이지 않는 p.pair 레이아웃 규칙을 지운다. span.study-note 스타일은 그대로
    # 남겨 학습 노트가 계속 눈에 띄게 한다.
    text = re.sub(r"\n?span\.en\s*\{[^}]*\}\s*", "\n", text, flags=re.S)
    text = re.sub(r"\n?p\.pair\s*\{[^}]*\}\s*", "\n", text, flags=re.S)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.encode("utf-8")


def convert_opf(data: bytes, source_name: str) -> bytes:
    text = data.decode("utf-8", "replace")
    identifier = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, source_name + ':english-study-only')}"
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
        r"\g<1>en\g<3>",
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
    if input_name.startswith("[study] "):
        return "[e-s] " + input_name[len("[study] ") :]
    if input_name.startswith("[study]"):
        return "[e-s]" + input_name[len("[study]") :]
    return "[e-s] " + input_name


def convert_epub(input_path: Path, output_path: Path, overwrite: bool) -> dict[str, int]:
    source_integrity = validate_epub(input_path)
    if not source_integrity.valid:
        raise RuntimeError(
            "Source [study] EPUB failed integrity validation: "
            + "; ".join(source_integrity.issues[:8])
        )
    if output_path.exists() and not overwrite:
        cleanup = scrub_epub(output_path)
        if str(cleanup.get("status") or "").startswith("error:"):
            raise RuntimeError(f"[e-s] EPUB watermark cleanup failed: {cleanup['status']}")
        integrity = validate_epub(output_path)
        if not integrity.valid:
            raise RuntimeError(
                "Existing [e-s] EPUB failed integrity validation: "
                + "; ".join(integrity.issues[:8])
            )
        return {
            "skipped": 1,
            "pairs": 0,
            "notes_kept": 0,
            "ko_removed": 0,
            "watermarks_removed": int(cleanup.get("replacements") or 0),
        }

    totals = {"skipped": 0, "pairs": 0, "notes_kept": 0, "ko_removed": 0}
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
                    data, stats = convert_xhtml(data)
                    totals["pairs"] += stats["pairs"]
                    totals["notes_kept"] += stats["notes_kept"]
                    totals["ko_removed"] += stats["ko_removed"]
                elif lower.endswith(".css"):
                    data = convert_css(data)
                elif lower.endswith(".opf"):
                    data = convert_opf(data, input_path.name)

                original = zin.getinfo(name)
                zout.writestr(clone_info(original), data)
        cleanup = scrub_epub(temp_output)
        if str(cleanup.get("status") or "").startswith("error:"):
            raise RuntimeError(f"[e-s] EPUB watermark cleanup failed: {cleanup['status']}")
        integrity = validate_epub(temp_output)
        if not integrity.valid:
            raise RuntimeError(
                "[e-s] EPUB failed integrity validation: " + "; ".join(integrity.issues[:8])
            )
        totals["watermarks_removed"] = int(cleanup.get("replacements") or 0)
    return totals


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study_root", type=Path, help="[study] EPUB이 있는 폴더(하위 폴더 포함해 재귀 탐색)")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="[e-s] 결과를 저장할 폴더. 생략하면 study_root와 같은 위치의 형제 [e-s] 폴더를 쓴다.",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    study_root = args.study_root.expanduser().resolve()
    if not study_root.is_dir():
        raise SystemExit(f"[study] 폴더를 찾지 못했습니다: {study_root}")
    output_root = (
        args.output_root.expanduser().resolve()
        if args.output_root is not None
        else study_root.parent / "[e-s]"
    )

    epubs = sorted(study_root.rglob("[[]study[]]*.epub"))
    if not epubs:
        raise SystemExit(f"{study_root} 안에서 [study] EPUB을 찾지 못했습니다")

    print(f"Found {len(epubs)} [study] EPUBs under {study_root}")
    converted = skipped = total_pairs = total_notes = total_ko_removed = 0
    for input_path in epubs:
        relative_dir = input_path.relative_to(study_root).parent
        output_dir = output_root / relative_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / output_name(input_path.name)
        stats = convert_epub(input_path, output_path, args.overwrite)
        if stats["skipped"]:
            skipped += 1
            print(f"SKIP {output_path}")
            continue
        converted += 1
        total_pairs += stats["pairs"]
        total_notes += stats["notes_kept"]
        total_ko_removed += stats["ko_removed"]
        print(
            f"OK   {output_path} "
            f"(english paragraphs: {stats['pairs']}, "
            f"study notes kept: {stats['notes_kept']}, "
            f"korean spans removed: {stats['ko_removed']})"
        )

    print(
        f"Done. converted={converted}, skipped={skipped}, "
        f"english_paragraphs={total_pairs}, "
        f"study_notes_kept={total_notes}, "
        f"korean_spans_removed={total_ko_removed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
