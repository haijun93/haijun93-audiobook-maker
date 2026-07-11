#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import io
import os
import posixpath
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

from book_cover_lookup import find_online_cover


CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
OPF_NS = "http://www.idpf.org/2007/opf"
DC_NS = "http://purl.org/dc/elements/1.1/"
DEFAULT_SKIP_DIRS = {"_chatgpt_translate_work", "_batch_logs", "__MACOSX"}


@dataclass
class CoverCandidate:
    item: ET.Element
    href: str
    zip_path: str


@dataclass
class CoverResult:
    path: Path
    status: str
    detail: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add recognized cover images/pages to EPUBs that are missing them.")
    parser.add_argument("root", type=Path, help="Root folder or single EPUB file")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change without writing files")
    parser.add_argument("--include-work-dirs", action="store_true", help="Also scan temporary work/log folders")
    parser.add_argument("--no-online", action="store_true", help="Do not search online book metadata APIs for covers")
    return parser.parse_args()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if tag.startswith("{") else tag


def namespace_uri(tag: str) -> str:
    if tag.startswith("{"):
        return tag[1:].split("}", 1)[0]
    return ""


def qname(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}" if namespace else name


def direct_child(parent: ET.Element, name: str) -> ET.Element | None:
    for child in list(parent):
        if local_name(child.tag) == name:
            return child
    return None


def direct_children(parent: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(parent) if local_name(child.tag) == name]


def read_opf_path(archive: zipfile.ZipFile) -> str:
    container = ET.fromstring(archive.read("META-INF/container.xml"))
    for node in container.iter():
        if local_name(node.tag) == "rootfile":
            full_path = (node.attrib.get("full-path") or "").strip()
            if full_path:
                return full_path
    raise RuntimeError("container.xml does not contain a package document path")


def zip_dirname(path: str) -> str:
    return posixpath.dirname(path)


def resolve_href(opf_path: str, href: str) -> str:
    clean_href = unquote((href or "").split("#", 1)[0])
    base = zip_dirname(opf_path)
    joined = posixpath.join(base, clean_href) if base else clean_href
    return posixpath.normpath(joined).lstrip("./")


def media_type_from_href(href: str) -> str:
    suffix = Path(href).suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".gif":
        return "image/gif"
    if suffix == ".svg":
        return "image/svg+xml"
    if suffix == ".webp":
        return "image/webp"
    return "application/octet-stream"


def extension_from_media_type(media_type: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/svg+xml": ".svg",
        "image/webp": ".webp",
    }.get(media_type, ".jpg")


def is_image_item(item: ET.Element) -> bool:
    media_type = item.attrib.get("media-type") or media_type_from_href(item.attrib.get("href", ""))
    return media_type.startswith("image/")


def properties(item: ET.Element) -> set[str]:
    return {part for part in item.attrib.get("properties", "").split() if part}


def set_properties(item: ET.Element, values: Iterable[str]) -> None:
    cleaned = sorted({value for value in values if value})
    if cleaned:
        item.set("properties", " ".join(cleaned))
    elif "properties" in item.attrib:
        del item.attrib["properties"]


def manifest_items(manifest: ET.Element) -> list[ET.Element]:
    return [child for child in list(manifest) if local_name(child.tag) == "item"]


def item_by_id(manifest: ET.Element) -> dict[str, ET.Element]:
    return {item.attrib.get("id", ""): item for item in manifest_items(manifest) if item.attrib.get("id")}


def text_content(root: ET.Element, name: str) -> str:
    for node in root.iter():
        if local_name(node.tag) == name and node.text:
            text = re.sub(r"\s+", " ", node.text).strip()
            if text:
                return text
    return ""


def has_recognized_cover(
    metadata: ET.Element,
    manifest: ET.Element,
    opf_path: str,
    names: set[str],
) -> bool:
    by_id = item_by_id(manifest)
    for meta in direct_children(metadata, "meta"):
        if meta.attrib.get("name", "").lower() != "cover":
            continue
        item = by_id.get(meta.attrib.get("content", ""))
        if item is None or not is_image_item(item):
            continue
        if resolve_href(opf_path, item.attrib.get("href", "")) in names:
            return True

    for item in manifest_items(manifest):
        if "cover-image" not in properties(item) or not is_image_item(item):
            continue
        if resolve_href(opf_path, item.attrib.get("href", "")) in names:
            return True
    return False


def find_existing_cover_candidate(manifest: ET.Element, opf_path: str, names: set[str]) -> CoverCandidate | None:
    candidates: list[ET.Element] = []
    for item in manifest_items(manifest):
        if not is_image_item(item):
            continue
        marker = f"{item.attrib.get('id', '')} {item.attrib.get('href', '')}".lower()
        if "cover" in marker:
            candidates.append(item)
    for item in manifest_items(manifest):
        if not is_image_item(item) or item in candidates:
            continue
        href = item.attrib.get("href", "").lower()
        if any(token in href for token in ("front", "titlepage", "jacket")):
            candidates.append(item)

    for item in candidates:
        href = item.attrib.get("href", "")
        zip_path = resolve_href(opf_path, href)
        if zip_path in names:
            return CoverCandidate(item=item, href=href, zip_path=zip_path)
    return None


def unique_id(manifest: ET.Element, preferred: str) -> str:
    used = set(item_by_id(manifest))
    if preferred not in used:
        return preferred
    index = 1
    while f"{preferred}-{index}" in used:
        index += 1
    return f"{preferred}-{index}"


def unique_href(opf_path: str, names: set[str], manifest: ET.Element, preferred: str) -> str:
    used_hrefs = {item.attrib.get("href", "") for item in manifest_items(manifest)}
    stem = Path(preferred).stem
    suffix = Path(preferred).suffix
    candidate = preferred
    index = 1
    while candidate in used_hrefs or resolve_href(opf_path, candidate) in names:
        candidate = f"{stem}-{index}{suffix}"
        index += 1
    return candidate


def font_candidates() -> list[Path]:
    return [
        Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
        Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/System/Library/Fonts/Supplemental/Times New Roman.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
    ]


def load_font(size: int) -> ImageFont.ImageFont:
    for path in font_candidates():
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except Exception:
                continue
    return ImageFont.load_default(size=size)


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    words = text.split(" ")
    lines: list[str] = []
    line = ""
    for word in words:
        trial = word if not line else f"{line} {word}"
        if text_width(draw, trial, font) <= max_width:
            line = trial
            continue
        if line:
            lines.append(line)
            line = ""
        if text_width(draw, word, font) <= max_width:
            line = word
            continue
        chunk = ""
        for char in word:
            trial_chunk = chunk + char
            if chunk and text_width(draw, trial_chunk, font) > max_width:
                lines.append(chunk)
                chunk = char
            else:
                chunk = trial_chunk
        line = chunk
    if line:
        lines.append(line)
    return lines


def render_cover_jpeg(title: str, creator: str) -> bytes:
    width, height = 1600, 2560
    image = Image.new("RGB", (width, height), "#f4efe6")
    draw = ImageDraw.Draw(image)
    draw.rectangle((105, 105, width - 105, height - 105), outline="#2f3a44", width=14)
    draw.rectangle((155, 155, width - 155, height - 155), outline="#9f8f72", width=4)

    title = (title or "Untitled").strip()
    creator = (creator or "").strip()
    max_width = 1180
    title_font = load_font(104)
    title_lines = wrap_text(draw, title, title_font, max_width)
    for size in range(100, 47, -6):
        title_font = load_font(size)
        title_lines = wrap_text(draw, title, title_font, max_width)
        line_height = int(size * 1.25)
        if len(title_lines) <= 8 and len(title_lines) * line_height <= 760:
            break

    line_height = int(getattr(title_font, "size", 72) * 1.25)
    total_height = len(title_lines) * line_height
    y = 820 - total_height // 2
    for line in title_lines[:10]:
        x = (width - text_width(draw, line, title_font)) // 2
        draw.text((x, y), line, font=title_font, fill="#1f2933")
        y += line_height

    if creator:
        creator_font = load_font(54)
        creator_lines = wrap_text(draw, creator, creator_font, max_width)
        y = max(y + 90, 1170)
        for line in creator_lines[:3]:
            x = (width - text_width(draw, line, creator_font)) // 2
            draw.text((x, y), line, font=creator_font, fill="#4b5563")
            y += 72

    label_font = load_font(46)
    label = "Korean-English Study EPUB"
    x = (width - text_width(draw, label, label_font)) // 2
    draw.text((x, 1860), label, font=label_font, fill="#5b6470")

    out = io.BytesIO()
    image.save(out, format="JPEG", quality=92, optimize=True)
    return out.getvalue()


def cover_xhtml(image_href: str, title: str) -> bytes:
    safe_href = html.escape(image_href, quote=True)
    safe_title = html.escape(title or "Cover", quote=True)
    text = f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
  <title>Cover</title>
  <meta charset="utf-8" />
  <style type="text/css">
    html, body {{ margin: 0; padding: 0; height: 100%; }}
    body {{ text-align: center; }}
    section {{ height: 100%; page-break-after: always; }}
    img {{ display: block; margin: 0 auto; max-width: 100%; max-height: 100%; }}
  </style>
</head>
<body epub:type="cover">
  <section>
    <img src="{safe_href}" alt="{safe_title}" />
  </section>
</body>
</html>
'''
    return text.encode("utf-8")


def clone_zipinfo(info: zipfile.ZipInfo) -> zipfile.ZipInfo:
    cloned = zipfile.ZipInfo(info.filename, date_time=info.date_time)
    cloned.comment = info.comment
    cloned.extra = info.extra
    cloned.internal_attr = info.internal_attr
    cloned.external_attr = info.external_attr
    cloned.create_system = info.create_system
    cloned.compress_type = info.compress_type
    return cloned


def write_epub(
    epub_path: Path,
    infos: list[zipfile.ZipInfo],
    original_data: dict[str, bytes],
    replacements: dict[str, bytes],
    additions: dict[str, bytes],
) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=epub_path.stem + ".", suffix=".epub", dir=str(epub_path.parent))
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(temp_path, "w") as archive:
            written: set[str] = set()
            if "mimetype" in original_data:
                info = zipfile.ZipInfo("mimetype")
                info.compress_type = zipfile.ZIP_STORED
                archive.writestr(info, replacements.get("mimetype", original_data["mimetype"]))
                written.add("mimetype")
            for info in infos:
                if info.filename in written:
                    continue
                data = replacements.get(info.filename, original_data[info.filename])
                cloned = clone_zipinfo(info)
                archive.writestr(cloned, data)
                written.add(info.filename)
            for name, data in additions.items():
                if name in written:
                    continue
                info = zipfile.ZipInfo(name)
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data)
                written.add(name)
        os.replace(temp_path, epub_path)
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        finally:
            raise


def add_cover(epub_path: Path, dry_run: bool = False, cache_dir: Path | None = None, online: bool = True) -> CoverResult:
    with zipfile.ZipFile(epub_path) as archive:
        infos = archive.infolist()
        original_data = {info.filename: archive.read(info.filename) for info in infos}
        names = set(original_data)
        opf_path = read_opf_path(archive)

    root = ET.fromstring(original_data[opf_path])
    opf_ns = namespace_uri(root.tag) or OPF_NS
    ET.register_namespace("", opf_ns)
    ET.register_namespace("dc", DC_NS)

    metadata = direct_child(root, "metadata")
    manifest = direct_child(root, "manifest")
    spine = direct_child(root, "spine")
    if metadata is None or manifest is None or spine is None:
        return CoverResult(epub_path, "error", "missing metadata/manifest/spine")

    if has_recognized_cover(metadata, manifest, opf_path, names):
        return CoverResult(epub_path, "skip", "cover already recognized")

    title = text_content(root, "title") or epub_path.stem
    creator = text_content(root, "creator")

    candidate = find_existing_cover_candidate(manifest, opf_path, names)
    additions: dict[str, bytes] = {}
    if candidate is None:
        online_cover = find_online_cover(title, creator, cache_dir=cache_dir) if online else None
        cover_image_id = unique_id(manifest, "cover-image")
        cover_image_href = unique_href(
            opf_path,
            names,
            manifest,
            "cover" + extension_from_media_type(online_cover.media_type if online_cover else "image/jpeg"),
        )
        cover_image_path = resolve_href(opf_path, cover_image_href)
        additions[cover_image_path] = online_cover.data if online_cover else render_cover_jpeg(title, creator)
        media_type = online_cover.media_type if online_cover else "image/jpeg"
        cover_item = ET.SubElement(
            manifest,
            qname(opf_ns, "item"),
            {
                "id": cover_image_id,
                "href": cover_image_href,
                "media-type": media_type,
                "properties": "cover-image",
            },
        )
        image_href = cover_image_href
        source = online_cover.source if online_cover else "generated jpeg"
    else:
        cover_item = candidate.item
        cover_image_id = cover_item.attrib.get("id") or unique_id(manifest, "cover-image")
        cover_item.set("id", cover_image_id)
        cover_item.set("media-type", cover_item.attrib.get("media-type") or media_type_from_href(candidate.href))
        image_href = candidate.href
        source = f"existing image {candidate.zip_path}"

    for item in manifest_items(manifest):
        item_props = properties(item)
        if item is cover_item:
            item_props.add("cover-image")
        else:
            item_props.discard("cover-image")
        set_properties(item, item_props)

    for meta in list(metadata):
        if local_name(meta.tag) == "meta" and meta.attrib.get("name", "").lower() == "cover":
            metadata.remove(meta)
    ET.SubElement(metadata, qname(opf_ns, "meta"), {"name": "cover", "content": cover_image_id})

    cover_page_id = unique_id(manifest, "cover")
    cover_page_href = unique_href(opf_path, names | set(additions), manifest, "cover.xhtml")
    cover_page_path = resolve_href(opf_path, cover_page_href)
    additions[cover_page_path] = cover_xhtml(image_href, title)
    ET.SubElement(
        manifest,
        qname(opf_ns, "item"),
        {
            "id": cover_page_id,
            "href": cover_page_href,
            "media-type": "application/xhtml+xml",
        },
    )
    spine.insert(0, ET.Element(qname(opf_ns, "itemref"), {"idref": cover_page_id, "linear": "yes"}))

    guide = direct_child(root, "guide")
    if guide is None:
        guide = ET.SubElement(root, qname(opf_ns, "guide"))
    for reference in list(guide):
        if local_name(reference.tag) == "reference" and reference.attrib.get("type") == "cover":
            guide.remove(reference)
    ET.SubElement(guide, qname(opf_ns, "reference"), {"type": "cover", "title": "Cover", "href": cover_page_href})

    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    replacements = {opf_path: xml_bytes}
    if dry_run:
        return CoverResult(epub_path, "would-add", source)

    write_epub(epub_path, infos, original_data, replacements, additions)
    return CoverResult(epub_path, "added", source)


def iter_epubs(root: Path, include_work_dirs: bool) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() == ".epub" else []
    paths: list[Path] = []
    for path in root.rglob("*.epub"):
        if not include_work_dirs and any(part in DEFAULT_SKIP_DIRS for part in path.parts):
            continue
        paths.append(path)
    return sorted(paths, key=lambda item: str(item).lower())


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()
    epubs = iter_epubs(root, args.include_work_dirs)
    counts: dict[str, int] = {}
    for epub in epubs:
        if not epub.exists():
            counts["skip"] = counts.get("skip", 0) + 1
            continue
        try:
            result = add_cover(
                epub,
                dry_run=args.dry_run,
                cache_dir=root / "_cover_cache",
                online=not args.no_online,
            )
        except Exception as exc:
            result = CoverResult(epub, "error", str(exc))
        counts[result.status] = counts.get(result.status, 0) + 1
        if result.status != "skip":
            print(f"{result.status}\t{result.path}\t{result.detail}")
    print(
        "SUMMARY "
        + " ".join(f"{key}={counts.get(key, 0)}" for key in ["added", "would-add", "skip", "error"])
        + f" total={len(epubs)}"
    )
    return 1 if counts.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
