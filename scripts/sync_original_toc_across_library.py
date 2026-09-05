#!/usr/bin/env python3
"""Synchronize every library EPUB's TOC with its English original.

The older TOC healer generated synthetic scene entries (``제N막``), which
changed the author's navigation.  This tool treats ``[e]`` as the source of
truth and copies only the original EPUB's navigation documents to matching
editions.  It never invents chapter names or links.
"""

from __future__ import annotations

import argparse
import os
import posixpath
import re
import tempfile
import unicodedata
import zipfile
import zlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audiobook_studio.epub_xray_policy import (  # noqa: E402
    is_xray_member,
    strip_xray_references,
)


EDITION_NAMES = ("[e]", "[k]", "[k-e]", "[study]", "[e-s]", "[xteink]")
PREFIX_RE = re.compile(r"^\[(?:e|k|k-e|study|e-s|ks|study_x|e-s_x)\]\s*", re.I)
HREF_RE = re.compile(r"(?:href|src)\s*=\s*['\"]([^'\"]+)['\"]", re.I)


def clean_filename(name: str) -> str:
    name = PREFIX_RE.sub("", name)
    return unicodedata.normalize("NFC", name).casefold()


def book_key(path: Path, edition_root: Path) -> tuple[str, str]:
    rel = path.relative_to(edition_root)
    return (str(rel.parent).casefold(), clean_filename(rel.name))


def epub_index(root: Path) -> dict[tuple[str, str], Path]:
    result: dict[tuple[str, str], Path] = {}
    if not root.is_dir():
        return result
    for path in root.rglob("*.epub"):
        if path.name.startswith("._") or not path.is_file():
            continue
        result.setdefault(book_key(path, root), path)
    return result


def toc_members(names: list[str]) -> tuple[str | None, str | None]:
    nav = next((n for n in names if Path(n).name.casefold() in {"nav.xhtml", "toc.xhtml"}), None)
    ncx = next((n for n in names if Path(n).suffix.casefold() == ".ncx"), None)
    return nav, ncx


def references_are_valid(data: bytes, member: str, names: set[str]) -> bool:
    """Reject copied TOCs whose local links cannot exist in the target EPUB."""
    text = data.decode("utf-8", "replace")
    base = Path(member).parent
    for href in HREF_RE.findall(text):
        if not href or href.startswith(("#", "http:", "https:", "mailto:", "data:")):
            continue
        href_path = href.split("#", 1)[0]
        try:
            normalized = posixpath.normpath(posixpath.join(base.as_posix(), href_path))
        except (TypeError, ValueError):
            return False
        if normalized not in names:
            return False
    return True


def synchronize_book(source: Path, targets: list[Path], *, apply: bool) -> tuple[int, int, str]:
    """Return ``(changed, skipped, reason)`` for one source book."""
    try:
        with zipfile.ZipFile(source, "r") as archive:
            source_names = archive.namelist()
            source_nav, source_ncx = toc_members(source_names)
            if not source_nav and not source_ncx:
                return 0, len(targets), "source_has_no_toc"
            toc_data: dict[str, bytes] = {}
            for member in (source_nav, source_ncx):
                if member:
                    toc_data[Path(member).name.casefold()] = archive.read(member)
    except (OSError, zipfile.BadZipFile, KeyError, zlib.error) as exc:
        return 0, len(targets), f"source_error:{type(exc).__name__}"

    changed = skipped = 0
    for target in targets:
        try:
            with zipfile.ZipFile(target, "r") as archive:
                infos = archive.infolist()
                names = {info.filename for info in infos}
                target_nav, target_ncx = toc_members(list(names))
                replacements: dict[str, bytes] = {}
                for target_member in (target_nav, target_ncx):
                    if not target_member:
                        continue
                    source_bytes = toc_data.get(Path(target_member).name.casefold())
                    if source_bytes is None:
                        continue
                    source_bytes = strip_xray_references(target_member, source_bytes)
                    if references_are_valid(source_bytes, target_member, names):
                        replacements[target_member] = source_bytes

                # Also remove legacy X-Ray files/references while this archive
                # is open.  Clean archives are left byte-for-byte untouched.
                output: list[tuple[zipfile.ZipInfo, bytes]] = []
                archive_changed = False
                for info in infos:
                    if is_xray_member(info.filename):
                        archive_changed = True
                        continue
                    original_data = archive.read(info.filename)
                    data = original_data
                    if info.filename in replacements:
                        data = replacements[info.filename]
                    cleaned = strip_xray_references(info.filename, data)
                    if cleaned != data or data != original_data:
                        archive_changed = True
                    output.append((info, cleaned))
                if not archive_changed:
                    skipped += 1
                    continue
        except (OSError, zipfile.BadZipFile, zlib.error, KeyError):
            skipped += 1
            continue

        if not apply:
            changed += 1
            continue

        fd, temp_name = tempfile.mkstemp(prefix=f".{target.stem}.toc-", suffix=".epub", dir=target.parent)
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            with zipfile.ZipFile(temp_path, "w") as out:
                for info, data in output:
                    compression = zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
                    out.writestr(info, data, compress_type=compression)
            os.replace(temp_path, target)
            changed += 1
        finally:
            temp_path.unlink(missing_ok=True)
    return changed, skipped, "ok"


def run(library_root: Path, *, apply: bool) -> dict[str, int]:
    roots = {name: library_root / name for name in EDITION_NAMES}
    roots.update({
        "[study_x]": library_root / "[xteink]" / "[study_x]",
        "[e-s_x]": library_root / "[xteink]" / "[e-s_x]",
    })
    original_index = epub_index(roots["[e]"])
    target_indexes = {name: epub_index(root) for name, root in roots.items() if name != "[e]" and root.is_dir()}
    totals = {"source_books": len(original_index), "matched_books": 0, "changed": 0, "skipped": 0}

    for key, source in original_index.items():
        targets = [index[key] for index in target_indexes.values() if key in index]
        if not targets:
            continue
        totals["matched_books"] += len(targets)
        changed, skipped, _ = synchronize_book(source, targets, apply=apply)
        totals["changed"] += changed
        totals["skipped"] += skipped
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-root", type=Path, default=Path("/Users/hyeokjunkong/Desktop/소설2"))
    parser.add_argument("--apply", action="store_true", help="Rewrite EPUBs; without this flag only report changes")
    args = parser.parse_args()
    result = run(args.library_root.expanduser(), apply=args.apply)
    mode = "APPLIED" if args.apply else "DRY-RUN"
    print(f"[{mode}] original books: {result['source_books']:,}")
    print(f"Matched edition files: {result['matched_books']:,}")
    print(f"Would change/changed: {result['changed']:,}; skipped: {result['skipped']:,}")


if __name__ == "__main__":
    main()
