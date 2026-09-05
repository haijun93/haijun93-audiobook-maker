"""Shared zero-X-Ray policy for every EPUB publication path.

The library policy is intentionally stronger than the old "remove heuristic
X-Ray" behavior: no X-Ray dossier, manifest item, spine reference, or TOC
link may survive in any published EPUB.
"""

from __future__ import annotations

import os
import re
import tempfile
import zipfile
from pathlib import Path


XRAY_NAME_RE = re.compile(r"(?:x[-_]?ray|dramatis[-_\s]+personae)", re.IGNORECASE)
XRAY_LABEL_RE = re.compile(r"(?:x[-_]?ray|등장인물\s*(?:및|·)\s*용어\s*도감|dramatis\s+personae)", re.IGNORECASE)


def is_xray_member(name: str) -> bool:
    """Return whether *name* is an X-Ray dossier member."""

    return bool(XRAY_NAME_RE.search(Path(name).name))


def _remove_tag_references(text: str, tag_names: tuple[str, ...]) -> str:
    """Remove XML tags whose attributes reference an X-Ray member."""

    tag_pattern = "|".join(tag_names)
    attr_pattern = r"(?:href|id|idref|src)\s*=\s*['\"][^'\"]*"
    pattern = re.compile(
        rf"<(?P<tag>{tag_pattern})\b(?=[^>]*?(?:{attr_pattern}{XRAY_NAME_RE.pattern}|{XRAY_LABEL_RE.pattern}))[^>]*?/?>\s*",
        re.IGNORECASE | re.DOTALL,
    )
    return pattern.sub("", text)


def strip_xray_references(name: str, data: bytes) -> bytes:
    """Remove X-Ray references from OPF, nav, and NCX members.

    EPUBs encountered in the legacy library are not all serialized identically,
    so this uses a conservative tag-level fallback instead of requiring every
    input to be parseable before cleanup. The final EPUB is parsed by the normal
    integrity gates afterwards.
    """

    lower = name.lower()
    if not lower.endswith((".opf", ".ncx", ".xhtml", ".html", ".htm")):
        return data
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", "replace")

    if lower.endswith(".opf"):
        text = _remove_tag_references(text, ("item", "itemref", "reference"))
    elif lower.endswith(".ncx"):
        # navPoint can contain nested navPoint elements. The look-ahead ensures
        # only the X-Ray point is removed; non-X-Ray points are untouched.
        text = re.sub(
            r"<navPoint\b(?=[^>]*(?:x[-_]?ray|dramatis[-_]personae))[^>]*>.*?</navPoint>\s*",
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        text = re.sub(
            rf"<navPoint\b[^>]*>.*?(?:{XRAY_NAME_RE.pattern}|등장인물\s*(?:및|·)\s*용어\s*도감).*?</navPoint>\s*",
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
    elif "nav" in Path(name).name.lower():
        # nav.xhtml entries are normally flat. This also handles the common
        # legacy formatting where attributes and whitespace differ.
        text = re.sub(
            rf"<li\b[^>]*>.*?(?:{XRAY_NAME_RE.pattern}|등장인물\s*(?:및|·)\s*용어\s*도감).*?</li>\s*",
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

    return text.encode("utf-8")


def purge_xray_from_epub(epub_path: Path | str) -> bool:
    """Atomically remove all X-Ray artifacts from one EPUB.

    Returns ``True`` when the archive changed. The source archive remains
    untouched if reading or repacking fails.
    """

    path = Path(epub_path).expanduser()
    # Avoid rewriting thousands of clean archives (especially on a synced
    # Google Drive volume).  Only candidates with an X-Ray member or a related
    # navigation reference need the expensive atomic repack below.
    with zipfile.ZipFile(path, "r") as probe:
        probe_names = probe.namelist()
        if not any(is_xray_member(name) for name in probe_names):
            for name in probe_names:
                lower = name.lower()
                if not (lower.endswith((".opf", ".ncx")) or "nav" in Path(name).name.lower()):
                    continue
                text = probe.read(name).decode("utf-8", "replace")
                if XRAY_NAME_RE.search(text) or XRAY_LABEL_RE.search(text):
                    break
            else:
                return False
    changed = False
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.stem}.xray-purge-", suffix=".epub", dir=path.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(path, "r") as source, zipfile.ZipFile(temp_path, "w") as target:
            target.comment = source.comment
            for info in source.infolist():
                name = info.filename
                if is_xray_member(name):
                    changed = True
                    continue
                data = source.read(name)
                cleaned = strip_xray_references(name, data)
                if cleaned != data:
                    changed = True
                compression = zipfile.ZIP_STORED if name == "mimetype" else zipfile.ZIP_DEFLATED
                target.writestr(info if name == "mimetype" else name, cleaned, compress_type=compression)
        if changed:
            os.replace(temp_path, path)
        else:
            temp_path.unlink(missing_ok=True)
        return changed
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def archive_has_xray(epub_path: Path | str) -> bool:
    """Check member names and publication-navigation references for X-Ray."""

    with zipfile.ZipFile(Path(epub_path), "r") as archive:
        for name in archive.namelist():
            if is_xray_member(name):
                return True
            lower = name.lower()
            if lower.endswith((".opf", ".ncx")) or "nav" in Path(name).name.lower():
                text = archive.read(name).decode("utf-8", "replace")
                if XRAY_NAME_RE.search(text) or XRAY_LABEL_RE.search(text):
                    return True
    return False


def assert_no_xray(epub_path: Path | str) -> None:
    if archive_has_xray(epub_path):
        raise RuntimeError(f"X-Ray artifact or navigation reference remains: {epub_path}")
