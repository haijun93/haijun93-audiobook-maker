#!/usr/bin/env python3
"""Repair Presumed Innocent's navigation and synthetic front-matter chapters.

The source EPUB's NCX is technically valid but practically incomplete: it has
    only one generic ``Start`` entry.  The source reading documents still contain
    the authentic section headings and numbered chapter boundaries, so generated
    editions must use those boundaries instead of copying ``Start`` or inventing
    ``1장`` ... ``11장``.  This module reconstructs the supplied retail TOC in
    every edition.
"""

from __future__ import annotations

import html
import os
import re
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup
from heal_xml_unescaped_entities import sanitize_and_fix_html


LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
BOOK_REL = Path("#apple tv original/#Scott Turow")
SOURCE = LIB_ROOT / "[e]" / BOOK_REL / "[e] Presumed Innocent - Scott Turow.epub"
TARGETS = (
    LIB_ROOT / "[k-e]" / BOOK_REL / "[k-e] Presumed Innocent - Scott Turow.epub",
    LIB_ROOT / "[study]" / BOOK_REL / "[study] Presumed Innocent - Scott Turow.epub",
    LIB_ROOT / "[e-s]" / BOOK_REL / "[e-s] Presumed Innocent - Scott Turow.epub",
    LIB_ROOT / "[k]" / BOOK_REL / "[k] Presumed Innocent - Scott Turow.epub",
    LIB_ROOT / "[xteink]/[study_x]" / BOOK_REL / "[study] Presumed Innocent - Scott Turow.epub",
    LIB_ROOT / "[xteink]/[e-s_x]" / BOOK_REL / "[e-s] Presumed Innocent - Scott Turow.epub",
)
NCX_NS = "http://www.daisy.org/z3986/2005/ncx/"
OPF_NS = "http://www.idpf.org/2007/opf"
XHTML_NS = "http://www.w3.org/1999/xhtml"
ET.register_namespace("", NCX_NS)


# The source has a retailer synopsis, but the supplied original TOC begins at
# Cover and does not expose that synopsis as a navigable item.  The numbered
# h4 boundaries are the actual chapter starts in the source and are retained
# as 40 nested TOC entries.
FRONT_SPECS = (
    ("Cover", "표지", "titlepage.xhtml", "cover"),
    ("Title Page", "표제지", "split_001", "title-page"),
    ("Copyright", "판권", "split_002", "copyright"),
    ("Dedication", "헌사", "split_002", "dedication"),
    ("Opening Statement", "모두 진술", "split_003", "opening-statement"),
)
SEASON_SPECS = (
    ("SPRING", "봄", 1, 17, "spring"),
    ("SUMMER", "여름", 18, 36, "summer"),
    ("FALL", "가을", 37, 40, "fall"),
)
BACK_SPECS = (
    ("Closing Argument", "최종 변론", "closing-argument"),
    ("Discover More", "더 알아보기", "discover-more"),
    ("A Preview of Presumed Guilty", "『유죄 추정』 미리보기", "preview"),
    ("Also by Scott Turow", "스콧 투로의 다른 작품", "also-by"),
    ("Raves for Scott Turow and Presumed Innocent", "『스콧 투로와 무죄추정』에 대한 찬사", "raves"),
)

TARGET_CHAPTER_POSITIONS = {
    # Paragraph ordinal (zero based) of the first prose paragraph following
    # each source h4 chapter marker.  Empty OCR spacer paragraphs are omitted
    # by the EPUB builder, so these positions align with generated editions.
    **{number: ("chapter05.xhtml", position) for number, position in {
        1: 0, 2: 62, 3: 160, 4: 192, 5: 280, 6: 380, 7: 402, 8: 466,
    }.items()},
    **{number: ("chapter06.xhtml", position) for number, position in {
        9: 0, 10: 65, 11: 147, 12: 226, 13: 311, 14: 419, 15: 449,
        16: 514, 17: 547,
    }.items()},
    **{number: ("chapter07.xhtml", position) for number, position in {
        18: 14, 19: 176, 20: 242, 21: 256, 22: 329, 23: 387, 24: 450,
        25: 521,
    }.items()},
    **{number: ("chapter08.xhtml", position) for number, position in {
        26: 0, 27: 90, 28: 335, 29: 502, 30: 609, 31: 677,
    }.items()},
    **{number: ("chapter09.xhtml", position) for number, position in {
        32: 0, 33: 184, 34: 469, 35: 593, 36: 708,
    }.items()},
    **{number: ("chapter10.xhtml", position) for number, position in {
        37: 0, 38: 88, 39: 136, 40: 152,
    }.items()},
}


def source_label() -> str:
    with zipfile.ZipFile(SOURCE) as archive:
        root = ET.fromstring(archive.read("toc.ncx"))
        labels = [
            node.text.strip()
            for node in root.findall(f".//{{{NCX_NS}}}navLabel/{{{NCX_NS}}}text")
            if node.text and node.text.strip()
        ]
        if labels == ["Start"]:
            return labels[0]
        if "SPRING" not in labels or "SUMMER" not in labels or "FALL" not in labels:
            raise RuntimeError(f"Unexpected source TOC labels: {labels!r}")
        return labels[0]


def first_reading_href(archive: zipfile.ZipFile) -> str:
    names = set(archive.namelist())
    opf = ET.fromstring(archive.read("OEBPS/content.opf"))
    manifest = {
        item.get("id"): item.get("href", "")
        for item in opf.findall(f"{{{OPF_NS}}}manifest/{{{OPF_NS}}}item")
    }
    for itemref in opf.findall(f"{{{OPF_NS}}}spine/{{{OPF_NS}}}itemref"):
        href = manifest.get(itemref.get("idref", ""), "")
        href_name = Path(href).name.casefold()
        if not href or "cover" in href_name or href_name in {"nav.xhtml", "toc.ncx"}:
            continue
        candidate = f"OEBPS/{href}"
        if candidate in names and candidate.endswith((".xhtml", ".html", ".htm")):
            return href
    raise RuntimeError("Could not find the first reading document in target EPUB")


def edition_kind(target: Path) -> str:
    if "[k]" in target.parts:
        return "k"
    if "[e-s]" in target.parts or "[e-s_x]" in target.parts:
        return "e-s"
    return "bilingual"


TocNode = tuple[str, str, tuple["TocNode", ...]]


def make_node(label: str, href: str, children: tuple[TocNode, ...] = ()) -> TocNode:
    return label, href, children


def flatten_nodes(nodes: tuple[TocNode, ...]) -> list[tuple[str, str]]:
    flattened: list[tuple[str, str]] = []
    for label, href, children in nodes:
        flattened.append((label, href))
        flattened.extend(flatten_nodes(children))
    return flattened


def toc_label(target: Path, english: str, korean: str) -> str:
    kind = edition_kind(target)
    if kind == "k":
        return korean
    if kind == "e-s":
        return english
    return f"{english} / {korean}"


def target_href(target: Path, members: dict[str, bytes], filename: str, anchor: str) -> str:
    member = f"OEBPS/{filename}"
    if member not in members:
        raise RuntimeError(f"Missing generated TOC target {member} in {target}")
    return f"{filename}#{anchor}" if anchor else filename


def toc_entries(target: Path, members: dict[str, bytes]) -> tuple[TocNode, ...]:
    front: list[TocNode] = []
    for english, korean, source_file, anchor in FRONT_SPECS:
        filename = "000-cover.xhtml" if source_file == "titlepage.xhtml" else (
            "chapter02.xhtml" if source_file == "split_001" else
            "chapter03.xhtml" if source_file == "split_002" else "chapter04.xhtml"
        )
        front.append(make_node(
            toc_label(target, english, korean),
            target_href(target, members, filename, "" if source_file == "titlepage.xhtml" else anchor),
        ))

    seasons: list[TocNode] = []
    for english, korean, first, last, anchor in SEASON_SPECS:
        children = tuple(
            make_node(
                toc_label(target, f"Chapter {number}", f"{number}장"),
                target_href(target, members, TARGET_CHAPTER_POSITIONS[number][0], f"chapter-{number:02d}"),
            )
            for number in range(first, last + 1)
        )
        # Section headings remain visible and clickable above their numbered
        # chapters, matching the two-column retail TOC supplied by the user.
        section_file = {"spring": "chapter05.xhtml", "summer": "chapter07.xhtml", "fall": "chapter10.xhtml"}[anchor]
        seasons.append(make_node(
            toc_label(target, english, korean),
            target_href(target, members, section_file, anchor),
            children,
        ))

    back_files = {
        "closing-argument": "chapter11.xhtml",
        "discover-more": "chapter11.xhtml",
        "preview": "chapter11.xhtml",
        "also-by": "chapter11.xhtml",
        "raves": "chapter11.xhtml",
    }
    back = tuple(
        make_node(
            toc_label(target, english, korean),
            target_href(target, members, back_files[anchor], anchor),
        )
        for english, korean, anchor in BACK_SPECS
    )
    return tuple(front) + tuple(seasons) + back


def rewrite_nav(data: bytes, entries: tuple[TocNode, ...]) -> bytes:
    soup = BeautifulSoup(data, "html.parser")
    toc_nav = soup.find("nav", id="toc") or soup.find("nav")
    if toc_nav is None:
        raise RuntimeError("Could not locate the EPUB3 TOC navigation")
    toc_ol = toc_nav.find("ol", recursive=False)
    if toc_ol is None:
        raise RuntimeError("Could not locate the EPUB3 TOC list")
    toc_ol.clear()

    def append(nodes: tuple[TocNode, ...], parent: object) -> None:
        for label, href, children in nodes:
            item = soup.new_tag("li")
            link = soup.new_tag("a", href=href)
            link.string = label
            item.append(link)
            if children:
                child_list = soup.new_tag("ol")
                append(children, child_list)
                item.append(child_list)
            parent.append(item)

    append(entries, toc_ol)
    return str(soup).encode("utf-8")


def rewrite_ncx(data: bytes, entries: tuple[TocNode, ...]) -> bytes:
    root = ET.fromstring(data)
    nav_map = root.find(f"{{{NCX_NS}}}navMap")
    if nav_map is None:
        raise RuntimeError("Target NCX has no navMap")
    for child in list(nav_map):
        nav_map.remove(child)
    order = 0

    def append(nodes: tuple[TocNode, ...]) -> None:
        nonlocal order
        for label, href, children in nodes:
            order += 1
            point = ET.SubElement(
                nav_map,
                f"{{{NCX_NS}}}navPoint",
                {"id": f"navpoint-original-{order:03d}", "playOrder": str(order)},
            )
            nav_label = ET.SubElement(point, f"{{{NCX_NS}}}navLabel")
            ET.SubElement(nav_label, f"{{{NCX_NS}}}text").text = label
            ET.SubElement(point, f"{{{NCX_NS}}}content", {"src": href})
            if children:
                append_children(point, children)

    def append_children(parent: ET.Element, nodes: tuple[TocNode, ...]) -> None:
        nonlocal order
        for label, href, children in nodes:
            order += 1
            point = ET.SubElement(
                parent,
                f"{{{NCX_NS}}}navPoint",
                {"id": f"navpoint-original-{order:03d}", "playOrder": str(order)},
            )
            nav_label = ET.SubElement(point, f"{{{NCX_NS}}}navLabel")
            ET.SubElement(nav_label, f"{{{NCX_NS}}}text").text = label
            ET.SubElement(point, f"{{{NCX_NS}}}content", {"src": href})
            if children:
                append_children(point, children)

    append(entries)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def source_toc_entries(members: dict[str, bytes]) -> tuple[TocNode, ...]:
    """Build the supplied retail hierarchy from source headings and markers."""
    split_names = sorted(
        (
            name
            for name in members
            if re.search(r"_split_\d+\.html$", name, flags=re.IGNORECASE)
        ),
        key=lambda name: int(re.search(r"_split_(\d+)", name, flags=re.IGNORECASE).group(1)),
    )
    if not split_names:
        raise RuntimeError("Could not find source reading documents")

    by_number = {
        int(Path(name).stem.rsplit("_", 1)[-1]): name
        for name in split_names
    }
    if set(by_number) != set(range(11)):
        raise RuntimeError(f"Unexpected source split files: {sorted(by_number)}")

    soups = {number: BeautifulSoup(members[name], "html.parser") for number, name in by_number.items()}
    heading_text = {
        number: [heading.get_text(" ", strip=True) for heading in soup.find_all(["h1", "h2", "h3"])]
        for number, soup in soups.items()
    }
    if heading_text[4] != ["SPRING"] or heading_text[6] != ["SUMMER"] or heading_text[9] != ["FALL"]:
        raise RuntimeError(f"Source season headings are not authentic: {heading_text!r}")
    chapter_markers = {
        int(re.fullmatch(
            r"(?:chapter\s+)?(\d+)", heading.get_text(" ", strip=True), flags=re.IGNORECASE
        ).group(1))
        for soup in soups.values()
        for heading in soup.find_all("h4")
        if re.fullmatch(
            r"(?:chapter\s+)?(\d+)", heading.get_text(" ", strip=True), flags=re.IGNORECASE
        )
    }
    if chapter_markers != set(range(1, 41)):
        raise RuntimeError(f"Source chapter markers are incomplete: {sorted(chapter_markers)}")

    # Add stable fragment IDs to the source itself.  The original h4 markers
    # are invisible in the generated editions, where the corresponding prose
    # paragraph receives the same chapter ID.
    for number, soup in soups.items():
        for heading in soup.find_all("h4"):
            label = heading.get_text(" ", strip=True)
            chapter_match = re.fullmatch(r"(?:chapter\s+)?(\d+)", label, flags=re.IGNORECASE)
            if chapter_match:
                chapter_number = int(chapter_match.group(1))
                heading["id"] = f"chapter-{chapter_number:02d}"
                heading.clear()
                heading.append(f"Chapter {chapter_number}")
        for heading in soup.find_all(["h2", "h4", "h5"]):
            label = heading.get_text(" ", strip=True)
            anchor = {
                "PRESUMED INNOCENT": "title-page",
                "Opening Statement": "opening-statement",
                "SPRING": "spring",
                "SUMMER": "summer",
                "FALL": "fall",
                "Closing Argument": "closing-argument",
                "Also by Scott Turow": "also-by",
                "Copyright © 1987 by Scott Turow": "copyright",
            }.get(label)
            if anchor:
                heading["id"] = anchor
        for paragraph in soup.find_all("p"):
            if paragraph.get_text(" ", strip=True).casefold() == "for my mother":
                paragraph["id"] = "dedication"
        if number == 10:
            # These retail TOC labels are present in the supplied edition's
            # navigation, but this stripped source does not contain their
            # promotional pages.  Keep valid, explicit destinations without
            # fabricating promotional copy.
            body = soup.body
            if body is not None:
                for anchor in ("discover-more", "preview", "raves"):
                    if soup.find(id=anchor) is None:
                        body.append(soup.new_tag("span", id=anchor))
        members[by_number[number]] = str(soup).encode("utf-8")

    def href(number: int, anchor: str = "") -> str:
        filename = by_number[number]
        return f"{filename}#{anchor}" if anchor else filename

    front = (
        make_node("Cover", "titlepage.xhtml"),
        make_node("Title Page", href(1, "title-page")),
        make_node("Copyright", href(2, "copyright")),
        make_node("Dedication", href(2, "dedication")),
        make_node("Opening Statement", href(3, "opening-statement")),
    )
    seasons: list[TocNode] = []
    for english, _korean, first, last, anchor in SEASON_SPECS:
        children = tuple(
            make_node(f"Chapter {number}", href(
                4 if number <= 8 else 5 if number <= 17 else 6 if number <= 25 else
                7 if number <= 31 else 8 if number <= 36 else 9,
                f"chapter-{number:02d}",
            ))
            for number in range(first, last + 1)
        )
        section_number = {"spring": 4, "summer": 6, "fall": 9}[anchor]
        seasons.append(make_node(english, href(section_number, anchor), children))
    back = tuple(
        make_node(english, href(10, anchor))
        for english, _korean, anchor in BACK_SPECS
    )
    return front + tuple(seasons) + back


def add_chapter_markers(
    text: str, target: Path, chapter_positions: list[tuple[int, int]]
) -> str:
    """Insert visible Chapter N/ N장 headings at the real chapter starts."""
    soup = BeautifulSoup(text, "html.parser")
    paragraphs = soup.find_all("p")
    kind = edition_kind(target)
    for number, ordinal in chapter_positions:
        if ordinal >= len(paragraphs):
            raise RuntimeError(
                f"Could not place Chapter {number}: paragraph {ordinal} is outside the document"
            )
        paragraph = paragraphs[ordinal]
        anchor = f"chapter-{number:02d}"
        previous = paragraph.find_previous_sibling()
        if previous is not None and previous.name == "h3" and previous.get("id") == anchor:
            marker = previous
        else:
            marker = soup.find(id=anchor)
            if marker is not None and marker.name == "h3":
                marker.extract()
            else:
                marker = soup.new_tag("h3")
                marker["id"] = anchor
                marker["class"] = ["chapter-marker"]
            paragraph.insert_before(marker)
        marker["id"] = anchor
        marker["class"] = ["chapter-marker"]
        marker.clear()
        if kind == "k":
            marker.string = f"{number}장"
        elif kind == "e-s":
            marker.string = f"Chapter {number}"
        else:
            english = soup.new_tag("span", attrs={"class": "en", "xml:lang": "en"})
            english.string = f"Chapter {number}"
            korean = soup.new_tag("span", attrs={"class": "ko", "xml:lang": "ko"})
            korean.string = f"{number}장"
            marker.append(english)
            marker.append(soup.new_tag("br"))
            marker.append(korean)
        if paragraph.get("id") == anchor:
            del paragraph["id"]
    return str(soup)


def ensure_chapter_marker_css(members: dict[str, bytes]) -> None:
    """Give inserted chapter headings stable, readable EPUB styling."""
    stylesheet = "OEBPS/styles.css"
    if stylesheet not in members:
        return
    css = members[stylesheet].decode("utf-8", "replace")
    if "h3.chapter-marker" not in css:
        css += (
            "\n"
            "h3.chapter-marker { margin: 1.3em 0 0.9em; text-align: center; "
            "font-size: 1.15em; font-weight: 700; }\n"
        )
    members[stylesheet] = css.encode("utf-8")


def ensure_target_frontmatter(text: str, target: Path, *, is_title_page: bool = False) -> str:
    """Restore the source copyright line omitted by the old translator."""
    soup = BeautifulSoup(text, "html.parser")
    heading = soup.find(id="h_2")
    if heading is None:
        return text
    if is_title_page:
        heading["id"] = "title-page"
    if is_title_page or soup.find(id="copyright") is not None:
        return str(soup)
    kind = edition_kind(target)
    if kind == "k":
        copyright_block = soup.new_tag("p")
        copyright_block["id"] = "copyright"
        copyright_block.string = "저작권 © 1987 스콧 투로"
    elif kind == "e-s":
        copyright_block = soup.new_tag("p")
        copyright_block["id"] = "copyright"
        copyright_block.string = "Copyright © 1987 by Scott Turow"
    else:
        copyright_block = soup.new_tag("p", attrs={"class": "pair", "id": "copyright"})
        en = soup.new_tag("span", attrs={"class": "en", "xml:lang": "en"})
        en.string = "Copyright © 1987 by Scott Turow"
        ko = soup.new_tag("span", attrs={"class": "ko", "xml:lang": "ko"})
        ko.string = "저작권 © 1987 스콧 투로"
        copyright_block.append(en)
        copyright_block.append(soup.new_tag("br"))
        copyright_block.append(ko)
    heading.insert_after(copyright_block)
    return str(soup)


def ensure_target_backmatter_anchors(text: str) -> str:
    soup = BeautifulSoup(text, "html.parser")
    body = soup.body
    if body is None:
        return text
    for anchor in ("discover-more", "preview", "also-by", "raves"):
        if soup.find(id=anchor) is None:
            body.append(soup.new_tag("span", id=anchor))
    return str(soup)


def ensure_source_cover_page(members: dict[str, bytes]) -> None:
    """Make the source Cover TOC destination render the packaged cover image."""
    if "titlepage.xhtml" not in members or "cover.jpeg" not in members:
        return
    soup = BeautifulSoup(members["titlepage.xhtml"], "html.parser")
    body = soup.body
    if body is None:
        return
    body["id"] = "cover"
    if body.find("img") is None:
        image = soup.new_tag("img", src="cover.jpeg", alt="Presumed Innocent cover")
        body.append(image)
    members["titlepage.xhtml"] = str(soup).encode("utf-8")


def strip_legal_document_artifacts(text: str) -> str:
    """Remove OCR/table debris from the indictment block in the Summer section."""
    def clean_paragraph(match: re.Match[str]) -> str:
        paragraph = match.group(0)
        visible = html.unescape(re.sub(r"<[^>]+>", "", paragraph))
        visible = re.sub(r"\s+", " ", visible).strip()
        if (re.sub(r"[()\s]", "", visible) == "") or "[번역 누락]" in visible:
            return ""
        return paragraph

    text = re.sub(r"<p\b[^>]*>.*?</p>", clean_paragraph, text, flags=re.IGNORECASE | re.DOTALL)
    # The source uses tiny placeholder images for missing OCR glyphs.  The
    # surrounding narrative identifies the name unambiguously as Rusty K.
    # Sabich, so restore the name in both the caption and indictment.
    text = re.sub(
        r"RO\s*<img\b[^>]*?/?>\s*AT\s+K\.\s*SABICH",
        "RUSTY K. SABICH",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\bO\s+AT\s+K\.\s*SABICH\b", "RUSTY K. SABICH", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<!러스티 )K\. 사비치의 \.O\.", "러스티 K. 사비치", text)
    text = re.sub(r"(?<!러스티 )K\. 사비치\b", "러스티 K. 사비치", text)

    def normalize_people_heading(match: re.Match[str]) -> str:
        heading = match.group(0)
        visible = html.unescape(re.sub(r"<[^>]+>", "", heading))
        if "피고인" in visible and "국민" not in visible:
            return heading.replace("피고인", "국민")
        return heading

    text = re.sub(
        r"<h2\b[^>]*>.*?</h2>",
        normalize_people_heading,
        text,
        count=0,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # The preceding buggy repair could accidentally touch the indictment's
    # sentence while trying to rename the PEOPLE heading; restore that phrase.
    text = text.replace("본 국민은", "본 피고인은")
    text = text.replace("주 수정 법전 제76610조", "개정 주 법전 제76610조")
    text = text.replace("수정 주 법전 제76610조", "개정 주 법전 제76610조")
    text = re.sub(r"A TUE BILL", "A TRUE BILL", text, flags=re.IGNORECASE)
    text = text.replace("RRevised State Statutes", "Revised State Statutes")
    text = re.sub(r"(?<!R)evised State Statutes", "Revised State Statutes", text)
    text = re.sub(r"THE KINDLE COUNTY GAND JUY", "THE KINDLE COUNTY GRAND JURY", text)
    text = re.sub(r"(?<![A-Za-z])aymond\b", "Raymond", text)
    text = re.sub(r"(?<![A-Za-z])obinson\b", "Robinson", text)
    text = text.replace("Section 76610 .S.S.", "Section 76610 R.S.S.")
    return text


def build_source_nav(entries: tuple[TocNode, ...]) -> bytes:
    def render(nodes: tuple[TocNode, ...], indent: str = "    ") -> str:
        lines: list[str] = []
        for label, href, children in nodes:
            lines.append(
                f'{indent}<li><a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>'
            )
            if children:
                lines.append(f"{indent}  <ol>")
                lines.append(render(children, indent + "    "))
                lines.append(f"{indent}  </ol>")
            lines.append(f"{indent}</li>")
        return "\n".join(lines)

    items = render(entries)
    return f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="en-GB" lang="en-GB">
<head><title>Table of Contents</title><meta charset="utf-8"/></head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>Table of Contents</h1>
    <ol>
{items}
    </ol>
  </nav>
  <nav epub:type="landmarks" hidden="hidden">
    <h2>Landmarks</h2>
    <ol><li><a epub:type="bodymatter" href="{html.escape(entries[0][1].split('#', 1)[0], quote=True)}">Start</a></li></ol>
  </nav>
</body>
</html>
'''.encode("utf-8")


def repair_source() -> None:
    with zipfile.ZipFile(SOURCE) as archive:
        infos = archive.infolist()
        members = {info.filename: archive.read(info.filename) for info in infos}
    for name in list(members):
        if re.search(r"_split_006\.html$", name, flags=re.IGNORECASE):
            members[name] = strip_legal_document_artifacts(
                members[name].decode("utf-8", "replace")
            ).encode("utf-8")
    ensure_source_cover_page(members)
    entries = source_toc_entries(members)
    opf = ET.fromstring(members["content.opf"])
    manifest = opf.find(f"{{{OPF_NS}}}manifest")
    if manifest is None:
        raise RuntimeError("Source OPF has no manifest")
    if manifest.find(".//{%s}item[@id='nav']" % OPF_NS) is None:
        ET.SubElement(
            manifest,
            f"{{{OPF_NS}}}item",
            {"id": "nav", "href": "nav.xhtml", "media-type": "application/xhtml+xml", "properties": "nav"},
        )
    opf.set("version", "3.0")
    members["content.opf"] = ET.tostring(opf, encoding="utf-8", xml_declaration=True) + b"\n"
    members["toc.ncx"] = rewrite_ncx(members["toc.ncx"], entries)
    members["nav.xhtml"] = build_source_nav(entries)

    fd, temp_name = tempfile.mkstemp(prefix=f".{SOURCE.stem}.toc-", suffix=".epub", dir=SOURCE.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(temp_path, "w") as output:
            for info in infos:
                compression = zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
                output.writestr(info, members[info.filename], compress_type=compression)
            if "nav.xhtml" not in {info.filename for info in infos}:
                output.writestr("nav.xhtml", members["nav.xhtml"], compress_type=zipfile.ZIP_DEFLATED)
        os.replace(temp_path, SOURCE)
    finally:
        temp_path.unlink(missing_ok=True)
    print(f"UPDATED {SOURCE}")


def normalize_generated_headings(target: Path, members: dict[str, bytes]) -> None:
    """Remove synthetic chapter numbers and restore source section headings.

    ``chapter02`` and ``chapter03`` are intentionally short in the source:
    they are the title page and dedication.  The old ``2장``/``3장`` wrappers
    made them look like empty chapters.  ``chapter04`` and ``chapter11`` start
    with a paragraph heading, so an anchor is added without changing its body
    semantics.
    """
    section_labels = {
        "chapter05.xhtml": toc_label(target, "SPRING", "봄"),
        "chapter07.xhtml": toc_label(target, "SUMMER", "여름"),
        "chapter10.xhtml": toc_label(target, "FALL", "가을"),
        "chapter11.xhtml": toc_label(target, "Closing Argument", "최종 변론"),
    }
    for index in range(1, 12):
        name = f"OEBPS/chapter{index:02d}.xhtml"
        data = members.get(name)
        if data is None:
            continue
        text = data.decode("utf-8", "replace")
        if index == 1:
            label = toc_label(target, "Synopsis", "시놉시스")
            text = re.sub(
                r'(<h1\b[^>]*\bid=["\']h_1["\'][^>]*>).*?(</h1>)',
                lambda match, heading_label=label: (
                    f"{match.group(1)}{html.escape(heading_label)}{match.group(2)}"
                ),
                text,
                count=1,
                flags=re.IGNORECASE | re.DOTALL,
            )
        else:
            text = re.sub(
                r'\s*<h1\b[^>]*\bid=["\']h_1["\'][^>]*>\s*\d+장\s*</h1>\s*',
                "\n",
                text,
                count=1,
                flags=re.IGNORECASE,
            )

        title_label = section_labels.get(Path(name).name, "본문")
        text = re.sub(
            r'(<title>).*?(</title>)',
            rf"\1{html.escape(title_label)}\2",
            text,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # Correct OCR damage in the actual source section headings.  These are
        # heading-only replacements; the narrative body is not mechanically
        # rewritten here.
        for broken, corrected in {
            "PESUMED INNOCENT": "PRESUMED INNOCENT",
            "SCOTT TUOW": "SCOTT TUROW",
            "SPING": "SPRING",
        }.items():
            text = re.sub(re.escape(broken), corrected, text, flags=re.IGNORECASE)
        # The repair is intentionally idempotent: a previous run may already
        # have turned SUMME into SUMMER, so a plain replacement would create
        # SUMMERR on every subsequent run.
        text = re.sub(r"SUMME(?:R)+", "SUMMER", text, flags=re.IGNORECASE)
        if index == 7:
            text = strip_legal_document_artifacts(text)

        if index == 2:
            text = ensure_target_frontmatter(text, target, is_title_page=True)
        elif index == 3:
            text = ensure_target_frontmatter(text, target)
            soup = BeautifulSoup(text, "html.parser")
            dedication = next(
                (paragraph for paragraph in soup.find_all("p")
                 if "어머니께" in paragraph.get_text(" ", strip=True)
                 or "For my mother" in paragraph.get_text(" ", strip=True)),
                None,
            )
            if dedication is not None:
                dedication["id"] = "dedication"
            text = str(soup)
        elif index in {4, 5, 7, 10, 11}:
            soup = BeautifulSoup(text, "html.parser")
            first = soup.find("h2") if index in {5, 7, 10} else soup.find("p")
            if first is not None:
                first["id"] = {
                    4: "opening-statement",
                    5: "spring",
                    7: "summer",
                    10: "fall",
                    11: "closing-argument",
                }[index]
            text = str(soup)
            if index == 11:
                text = ensure_target_backmatter_anchors(text)

        if index in {5, 6, 7, 8, 9, 10}:
            paragraph_positions = [
                (number, position)
                for number, (filename, position) in TARGET_CHAPTER_POSITIONS.items()
                if filename == Path(name).name
            ]
            text = add_chapter_markers(text, target, paragraph_positions)

        ensure_chapter_marker_css(members)

        if index in {4, 11}:
            # Add a stable fragment to the first body paragraph, which is the
            # authentic Opening/Closing Argument heading in the source.
            anchor = "opening-statement" if index == 4 else "closing-argument"
            if re.search(rf'<p\b[^>]*\bid=["\']{anchor}["\']', text, flags=re.IGNORECASE):
                members[name] = text.encode("utf-8")
                continue
            section_pattern = re.compile(
                r'(<section\b[^>]*>\s*)(<p\b(?![^>]*\bid=)[^>]*>)',
                re.IGNORECASE | re.DOTALL,
            )

            def add_heading_anchor(
                match: re.Match[str], heading_anchor: str = anchor
            ) -> str:
                opening = match.group(2)
                return match.group(1) + re.sub(
                    r"<p\b",
                    f'<p id="{heading_anchor}"',
                    opening,
                    count=1,
                    flags=re.IGNORECASE,
                )

            text, count = section_pattern.subn(add_heading_anchor, text, count=1)
            if count != 1:
                raise RuntimeError(f"Could not anchor section heading in {name} of {target}")
        members[name] = text.encode("utf-8")


def repair_target(target: Path) -> None:
    if not target.is_file():
        raise FileNotFoundError(target)
    with zipfile.ZipFile(target) as archive:
        infos = archive.infolist()
        members = {info.filename: archive.read(info.filename) for info in infos}
        first_reading_href(archive)  # Validate that the target has a readable spine.
    # Older AI Word Wise output occasionally contains orphaned </rb>/<rt>
    # closers or nested ruby tags.  Repair only malformed chapter XHTML and
    # leave already-valid files byte-for-byte unchanged.
    for name, data in list(members.items()):
        if "chapter" not in Path(name).stem.casefold() or not name.casefold().endswith((".xhtml", ".html", ".htm")):
            continue
        try:
            ET.fromstring(data)
        except ET.ParseError:
            repaired = sanitize_and_fix_html(data)
            ET.fromstring(repaired)
            members[name] = repaired
    if "OEBPS/nav.xhtml" not in members or "OEBPS/toc.ncx" not in members:
        raise RuntimeError(f"Missing generated TOC members in {target}")
    normalize_generated_headings(target, members)
    entries = toc_entries(target, members)
    members["OEBPS/nav.xhtml"] = rewrite_nav(members["OEBPS/nav.xhtml"], entries)
    members["OEBPS/toc.ncx"] = rewrite_ncx(members["OEBPS/toc.ncx"], entries)

    fd, temp_name = tempfile.mkstemp(prefix=f".{target.stem}.toc-", suffix=".epub", dir=target.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(temp_path, "w") as output:
            for info in infos:
                compression = zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
                output.writestr(info, members[info.filename], compress_type=compression)
        os.replace(temp_path, target)
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> None:
    source_label()  # Fail closed if the authoritative source changes unexpectedly.
    repair_source()
    # Repair source-derived editions first; Xteink is rebuilt below from the
    # healed [study]/[e-s] pair so it cannot retain malformed source markup.
    for target in TARGETS[:4]:
        repair_target(target)
        print(f"UPDATED {target}")
    from build_xteink_dedicated_editions import build_xteink_book_pair

    study = TARGETS[1]
    english_study = TARGETS[2]
    build_xteink_book_pair(study, english_study, xteink_root=LIB_ROOT / "[xteink]")
    for target in TARGETS[4:]:
        repair_target(target)
        print(f"UPDATED {target}")


if __name__ == "__main__":
    main()
