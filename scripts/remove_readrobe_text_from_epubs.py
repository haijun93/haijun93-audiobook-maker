#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

from atomic_io import atomic_output_path


TEXT_EXTENSIONS = (
    ".xhtml",
    ".html",
    ".htm",
    ".xml",
    ".opf",
    ".ncx",
    ".css",
    ".txt",
    ".svg",
    ".js",
    ".json",
)
WATERMARK_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:www\s*\.\s*)?readrobe\s*(?:\.\s*|\s+)com(?![A-Za-z0-9])"
    r"|리드\s*로브\s*(?:닷\s*컴|\.\s*(?:com|컴)|dot\s*com)",
    re.I,
)
# Compatibility alias for existing importers.
READROBE_PATTERN = WATERMARK_PATTERN


def decode_text(data: bytes) -> tuple[str, str]:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16"), "utf-16"
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig"), "utf-8-sig"
    declaration = data[:256].decode("ascii", "ignore")
    match = re.search(r"encoding\s*=\s*['\"]([^'\"]+)", declaration, re.I)
    encoding = match.group(1) if match else "utf-8"
    return data.decode(encoding), encoding


def scrub_text(text: str) -> tuple[str, int]:
    text, count = WATERMARK_PATTERN.subn("", text)
    if not count:
        return text, 0
    text = re.sub(r"(?is)<p\b([^>]*)>\s*</p>", "", text)
    text = re.sub(r"(?is)<h([1-6])\b([^>]*)>\s*</h\1>", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+([,.;:!?])", r"\1", text)
    text = re.sub(r">\s+<", "><", text)
    return text, count


def clone_info(original: zipfile.ZipInfo, *, compress_type: int | None = None) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(original.filename, original.date_time)
    info.compress_type = original.compress_type if compress_type is None else compress_type
    info.comment = original.comment
    info.extra = original.extra
    info.internal_attr = original.internal_attr
    info.external_attr = original.external_attr
    info.create_system = original.create_system
    return info


def scrub_epub(path: Path, *, dry_run: bool = False) -> dict[str, int | str]:
    totals: dict[str, int | str] = {"files_changed": 0, "replacements": 0, "status": "unchanged"}
    try:
        with zipfile.ZipFile(path, "r") as zin:
            names = zin.namelist()
            changed_entries: dict[str, bytes] = {}
            for name in names:
                lower = name.lower()
                if not lower.endswith(TEXT_EXTENSIONS):
                    continue
                data = zin.read(name)
                text, encoding = decode_text(data)
                scrubbed, count = scrub_text(text)
                if count:
                    changed_entries[name] = scrubbed.encode(encoding)
                    totals["files_changed"] = int(totals["files_changed"]) + 1
                    totals["replacements"] = int(totals["replacements"]) + count

            if not changed_entries:
                return totals
            if dry_run:
                totals["status"] = "dry-run"
                return totals

            with atomic_output_path(path) as tmp_path:
                with zipfile.ZipFile(tmp_path, "w") as zout:
                    zout.comment = zin.comment
                    if "mimetype" in names:
                        original = zin.getinfo("mimetype")
                        zout.writestr(
                            clone_info(original, compress_type=zipfile.ZIP_STORED),
                            zin.read("mimetype"),
                        )
                    for name in names:
                        if name == "mimetype":
                            continue
                        original = zin.getinfo(name)
                        data = changed_entries.get(name)
                        if data is None:
                            data = zin.read(name)
                        zout.writestr(clone_info(original), data)
                with zipfile.ZipFile(tmp_path) as check:
                    check_names = check.namelist()
                    if check.testzip() is not None:
                        raise RuntimeError("EPUB CRC verification failed")
                    if "mimetype" in check_names and check_names[:1] != ["mimetype"]:
                        raise RuntimeError("EPUB mimetype is not the first entry")
                    for name in check_names:
                        if not name.lower().endswith(TEXT_EXTENSIONS):
                            continue
                        text, _encoding = decode_text(check.read(name))
                        if WATERMARK_PATTERN.search(text):
                            raise RuntimeError(f"watermark remains in {name}")
        totals["status"] = "updated"
        return totals
    except Exception as exc:
        return {"files_changed": 0, "replacements": 0, "status": f"error: {exc}"}


def iter_epubs(paths: list[Path]) -> list[Path]:
    epubs: list[Path] = []
    for path in paths:
        path = path.expanduser()
        if path.is_dir():
            epubs.extend(sorted(path.rglob("*.epub")))
        elif path.suffix.lower() == ".epub":
            epubs.append(path)
    return epubs


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove readrobe.com watermark text from EPUB internals.")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    total_books = total_changed = total_replacements = errors = 0
    for epub in iter_epubs(args.paths):
        total_books += 1
        result = scrub_epub(epub, dry_run=args.dry_run)
        status = str(result["status"])
        replacements = int(result["replacements"])
        if status.startswith("error:"):
            errors += 1
        if replacements:
            total_changed += 1
            total_replacements += replacements
            if not args.quiet:
                print(f"{status} {replacements:5d} {epub}")
    print(
        f"books={total_books} changed={total_changed} "
        f"replacements={total_replacements} errors={errors}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
