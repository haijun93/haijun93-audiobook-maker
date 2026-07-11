#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from book_cover_lookup import OnlineCover, find_online_cover  # noqa: E402
from ensure_missing_epub_covers import (  # noqa: E402
    DEFAULT_SKIP_DIRS,
    CoverResult,
    direct_child,
    direct_children,
    extension_from_media_type,
    has_recognized_cover,
    item_by_id,
    local_name,
    manifest_items,
    media_type_from_href,
    namespace_uri,
    properties,
    qname,
    read_opf_path,
    resolve_href,
    set_properties,
    text_content,
    unique_href,
    write_epub,
)


TITLE_ALIAS_RULES: tuple[tuple[tuple[str, ...], tuple[str, str]], ...] = (
    (("guns", "germs", "steel"), ("Guns, Germs, and Steel", "Jared Diamond")),
    (("지켜보고",), ("The Housemaid Is Watching", "Freida McFadden")),
    (("비밀",), ("The Housemaid's Secret", "Freida McFadden")),
    (("housemaid", "secret"), ("The Housemaid's Secret", "Freida McFadden")),
    (("housemaid", "watching"), ("The Housemaid Is Watching", "Freida McFadden")),
    (("housemaid",), ("The Housemaid", "Freida McFadden")),
    (("11분",), ("Eleven Minutes", "Paulo Coelho")),
    (("eleven", "minutes"), ("Eleven Minutes", "Paulo Coelho")),
    (("환상", "코엘료"), ("The Valkyries", "Paulo Coelho")),
    (("valkyries",), ("The Valkyries", "Paulo Coelho")),
    (("for", "you", "only", "you"), ("For You and Only You", "Caroline Kepnes")),
    (("alchemist",), ("The Alchemist", "Paulo Coelho")),
    (("연금술사",), ("The Alchemist", "Paulo Coelho")),
    (("향수",), ("Perfume: The Story of a Murderer", "Patrick Suskind")),
    (("perfume",), ("Perfume: The Story of a Murderer", "Patrick Suskind")),
    (("우주전쟁",), ("The War of the Worlds", "H G Wells")),
    (("war", "worlds"), ("The War of the Worlds", "H G Wells")),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replace locally generated EPUB covers with online book covers.")
    parser.add_argument("root", type=Path, help="Root folder or single EPUB file")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--include-work-dirs", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of replacements to write")
    return parser.parse_args()


def iter_epubs(root: Path, include_work_dirs: bool) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() == ".epub" else []
    paths: list[Path] = []
    for path in root.rglob("*.epub"):
        if not include_work_dirs and any(part in DEFAULT_SKIP_DIRS for part in path.parts):
            continue
        paths.append(path)
    return sorted(paths, key=lambda item: str(item).lower())


def recognized_cover_item(metadata: ET.Element, manifest: ET.Element, opf_path: str, names: set[str]) -> ET.Element | None:
    by_id = item_by_id(manifest)
    for meta in direct_children(metadata, "meta"):
        if meta.attrib.get("name", "").lower() != "cover":
            continue
        item = by_id.get(meta.attrib.get("content", ""))
        if item is not None and resolve_href(opf_path, item.attrib.get("href", "")) in names:
            return item
    for item in manifest_items(manifest):
        if "cover-image" in properties(item) and resolve_href(opf_path, item.attrib.get("href", "")) in names:
            return item
    return None


def close_color(rgb: tuple[int, int, int], target: tuple[int, int, int], tolerance: int = 18) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(rgb[:3], target))


def is_generated_image(data: bytes, media_type: str, zip_path: str) -> bool:
    lower_data = data[:4096].lower()
    if media_type == "image/svg+xml" or zip_path.lower().endswith(".svg"):
        return b"korean-english study" in lower_data or b"korean study epub" in lower_data
    try:
        from io import BytesIO

        with Image.open(BytesIO(data)) as image:
            rgb = image.convert("RGB")
            if rgb.size != (1600, 2560):
                return False
            samples = [
                rgb.getpixel((20, 20)),
                rgb.getpixel((80, 80)),
                rgb.getpixel((200, 200)),
            ]
    except Exception:
        return False
    return sum(close_color(sample, (244, 239, 230), tolerance=24) for sample in samples) >= 2


def update_html_references(text: bytes, old_href: str, new_href: str) -> bytes:
    decoded = text.decode("utf-8", "replace")
    decoded = decoded.replace(old_href, new_href)
    decoded = decoded.replace(html.escape(old_href, quote=True), html.escape(new_href, quote=True))
    return decoded.encode("utf-8")


def filename_title(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r"^\s*\[[^\]]+\]\s*", "", stem)
    stem = re.sub(r"^\s*\d{1,3}[\s._-]+", "", stem)
    stem = re.sub(r"_+", " ", stem)
    stem = re.sub(r"\b(18|19|20)\d{2}\b", " ", stem)
    stem = re.sub(r"\s+", " ", stem)
    parts = [part.strip() for part in re.split(r"\s+-\s+", stem) if part.strip()]
    if len(parts) >= 2:
        left_words = parts[0].split()
        right_words = parts[1].split()
        if len(left_words) <= 3 and len(right_words) >= 4 and parts[0].lower().split()[0] not in {"the", "a", "an"}:
            stem = parts[1]
        else:
            stem = parts[0]
    stem = re.sub(r"\s+by\s+.+$", "", stem, flags=re.I)
    return stem.strip(" -_") or path.stem


def is_non_book_study_epub(path: Path, title: str) -> bool:
    marker = f"{path.as_posix()} {title}".lower()
    return any(
        token in marker
        for token in (
            "/opencourse/",
            "/[s]/",
            "sentence inline english",
            "ted transcript",
            "native daily english",
            "노동법",
        )
    )


def author_candidates(creator: str) -> list[str]:
    text = re.sub(r"\s+", " ", creator or "").strip()
    candidates: list[str] = []

    def add(value: str) -> None:
        value = re.sub(r"\s+", " ", value).strip(" ,-")
        if value and value not in candidates:
            candidates.append(value)

    add(text)
    left = re.split(r"\s+-\s+", text, maxsplit=1)[0]
    left = re.sub(r"\b(?:book|volume|vol|series)\b.*$", "", left, flags=re.I)
    left = re.sub(r"\b\d{1,3}\b", "", left)
    add(left)
    if "," in left:
        parts = [part.strip() for part in left.split(",") if part.strip()]
        if len(parts) >= 2:
            add(" ".join(parts[1:] + parts[:1]))
    if "" not in candidates:
        candidates.append("")
    return candidates


def online_cover_for_epub(title: str, creator: str, epub_path: Path, cache_dir: Path) -> OnlineCover | None:
    candidates: list[str] = []
    marker = f"{title} {epub_path.name}".lower()
    for tokens, (alias_title, alias_author) in TITLE_ALIAS_RULES:
        if all(token.lower() in marker for token in tokens):
            cover = find_online_cover(alias_title, alias_author, cache_dir=cache_dir)
            if cover:
                return cover

    file_title = filename_title(epub_path)
    ordered = (file_title, title) if re.search(r"[A-Za-z]", file_title) else (title, file_title)
    for candidate in ordered:
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    for candidate in candidates:
        for author in author_candidates(creator):
            cover = find_online_cover(candidate, author, cache_dir=cache_dir)
            if cover:
                return cover
    return None


def replace_generated_cover(epub_path: Path, cache_dir: Path, dry_run: bool = False) -> CoverResult:
    with zipfile.ZipFile(epub_path) as archive:
        infos = archive.infolist()
        original_data = {info.filename: archive.read(info.filename) for info in infos}
        names = set(original_data)
        opf_path = read_opf_path(archive)

    root = ET.fromstring(original_data[opf_path])
    opf_ns = namespace_uri(root.tag) or "http://www.idpf.org/2007/opf"
    ET.register_namespace("", opf_ns)
    ET.register_namespace("dc", "http://purl.org/dc/elements/1.1/")

    metadata = direct_child(root, "metadata")
    manifest = direct_child(root, "manifest")
    if metadata is None or manifest is None:
        return CoverResult(epub_path, "error", "missing metadata/manifest")
    if not has_recognized_cover(metadata, manifest, opf_path, names):
        return CoverResult(epub_path, "skip", "no recognized cover")

    cover_item = recognized_cover_item(metadata, manifest, opf_path, names)
    if cover_item is None:
        return CoverResult(epub_path, "skip", "no cover item")
    old_href = cover_item.attrib.get("href", "")
    old_zip_path = resolve_href(opf_path, old_href)
    old_media_type = cover_item.attrib.get("media-type") or media_type_from_href(old_href)
    if old_zip_path not in original_data:
        return CoverResult(epub_path, "skip", "cover file missing")
    if not is_generated_image(original_data[old_zip_path], old_media_type, old_zip_path):
        return CoverResult(epub_path, "skip", "cover is not generated")

    title = text_content(root, "title") or epub_path.stem
    creator = text_content(root, "creator")
    if is_non_book_study_epub(epub_path, title):
        return CoverResult(epub_path, "skip", "non-book study material")
    online_cover: OnlineCover | None = online_cover_for_epub(title, creator, epub_path, cache_dir)
    if online_cover is None:
        return CoverResult(epub_path, "no-match", title)

    new_href = unique_href(
        opf_path,
        names,
        manifest,
        "real-cover" + extension_from_media_type(online_cover.media_type),
    )
    new_zip_path = resolve_href(opf_path, new_href)
    additions = {new_zip_path: online_cover.data}
    replacements: dict[str, bytes] = {}

    cover_item.set("href", new_href)
    cover_item.set("media-type", online_cover.media_type)
    set_properties(cover_item, properties(cover_item) | {"cover-image"})

    for meta in list(metadata):
        if local_name(meta.tag) == "meta" and meta.attrib.get("name", "").lower() == "codex:cover-source":
            metadata.remove(meta)
    ET.SubElement(metadata, qname(opf_ns, "meta"), {"name": "codex:cover-source", "content": online_cover.source})

    for name, data in original_data.items():
        if not name.lower().endswith((".xhtml", ".html", ".htm")):
            continue
        if old_href.encode("utf-8") in data or html.escape(old_href, quote=True).encode("utf-8") in data:
            replacements[name] = update_html_references(data, old_href, new_href)

    replacements[opf_path] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    if dry_run:
        return CoverResult(epub_path, "would-replace", online_cover.source)
    write_epub(epub_path, infos, original_data, replacements, additions)
    return CoverResult(epub_path, "replaced", online_cover.source)


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()
    epubs = iter_epubs(root, args.include_work_dirs)
    cache_dir = root / "_cover_cache" if root.is_dir() else root.parent / "_cover_cache"
    counts: dict[str, int] = {}
    written = 0
    reported = 0
    for epub in epubs:
        if args.limit and reported >= args.limit:
            break
        if not epub.exists():
            counts["skip"] = counts.get("skip", 0) + 1
            continue
        try:
            result = replace_generated_cover(epub, cache_dir=cache_dir, dry_run=args.dry_run)
        except Exception as exc:
            result = CoverResult(epub, "error", str(exc))
        counts[result.status] = counts.get(result.status, 0) + 1
        if result.status not in {"skip"}:
            print(f"{result.status}\t{result.path}\t{result.detail}", flush=True)
            reported += 1
        if result.status == "replaced":
            written += 1
    print(
        "SUMMARY "
        + " ".join(f"{key}={counts.get(key, 0)}" for key in ["replaced", "would-replace", "no-match", "skip", "error"])
        + f" scanned={sum(counts.values())}"
    )
    return 1 if counts.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
