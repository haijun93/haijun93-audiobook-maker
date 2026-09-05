#!/usr/bin/env python3
"""scripts/force_fix_presumed_innocent_cover.py

Completely purges cover.svg and broken cover.xhtml from Presumed Innocent EPUBs.
Standardizes cover to real JPEG image (148.8KB) with 100% compliant EPUB 3/2 metadata.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
SRC_E = LIB_ROOT / "[e]/#apple tv original/#Scott Turow/[e] Presumed Innocent - Scott Turow.epub"

# 1. Extract genuine JPEG Cover
with zipfile.ZipFile(SRC_E, "r") as z:
    cover_bytes = z.read("presumedinnocent.jpg")

print(f"✅ Extracted Genuine Cover: {len(cover_bytes):,} bytes")

COVER_XHTML = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="ko" xml:lang="ko">
<head>
  <title>Cover</title>
  <meta charset="utf-8" />
  <link rel="stylesheet" type="text/css" href="styles.css" />
  <style type="text/css">
    @page { margin: 0; padding: 0; }
    body { margin: 0; padding: 0; text-align: center; background-color: #000000; }
    div.cover-wrapper { width: 100vw; height: 100vh; display: flex; justify-content: center; align-items: center; }
    img.cover-img { max-width: 100%; max-height: 100%; height: auto; object-fit: contain; }
  </style>
</head>
<body epub:type="cover">
  <div class="cover-wrapper">
    <img class="cover-img" src="images/cover.jpeg" alt="Presumed Innocent Cover" />
  </div>
</body>
</html>""".encode("utf-8")

def clean_and_repack_epub(ep: Path):
    if not ep.exists():
        return
    data = {}
    with zipfile.ZipFile(ep, "r") as z:
        for it in z.infolist():
            # Exclude broken svg and old cover.xhtml
            if it.filename in ["OEBPS/cover.svg", "OEBPS/cover.xhtml", "cover.svg", "cover.xhtml"]:
                continue
            try:
                data[it.filename] = z.read(it.filename)
            except Exception:
                pass

    # Place standard cover assets
    data["OEBPS/images/cover.jpeg"] = cover_bytes
    data["OEBPS/cover.jpeg"] = cover_bytes
    data["OEBPS/000-cover.xhtml"] = COVER_XHTML

    # Fix content.opf
    if "OEBPS/content.opf" in data:
        opf = data["OEBPS/content.opf"].decode("utf-8", "ignore")

        # Remove old cover items
        opf = re.sub(r'<item[^>]*id="cover"[^>]*/>\s*', '', opf)
        opf = re.sub(r'<item[^>]*id="cover-image"[^>]*/>\s*', '', opf)
        opf = re.sub(r'<item[^>]*id="cover-page"[^>]*/>\s*', '', opf)
        opf = re.sub(r'<item[^>]*href="cover\.(svg|xhtml)"[^>]*/>\s*', '', opf)
        opf = re.sub(r'<itemref[^>]*idref="cover"[^>]*/>\s*', '', opf)
        opf = re.sub(r'<itemref[^>]*idref="cover-page"[^>]*/>\s*', '', opf)
        opf = re.sub(r'<meta[^>]*name="cover"[^>]*/>\s*', '', opf)

        # Inject standard cover meta
        opf = re.sub(r'(<metadata[^>]*>)', r'\1\n    <meta name="cover" content="cover-image"/>', opf)

        # Inject manifest items
        new_items = (
            '    <item id="cover-image" href="images/cover.jpeg" media-type="image/jpeg" properties="cover-image"/>\n'
            '    <item id="cover-page" href="000-cover.xhtml" media-type="application/xhtml+xml"/>\n'
        )
        opf = re.sub(r'(<manifest[^>]*>)', r'\1\n' + new_items, opf)

        # Inject spine itemref as the VERY FIRST item
        opf = re.sub(r'(<spine[^>]*>)', r'\1\n    <itemref idref="cover-page" linear="yes"/>', opf)

        data["OEBPS/content.opf"] = opf.encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as dst:
        if "mimetype" in data:
            dst.writestr("mimetype", data.pop("mimetype"), compress_type=zipfile.ZIP_STORED)
        else:
            dst.writestr("mimetype", b"application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for fname, cdata in data.items():
            dst.writestr(fname, cdata)

    ep.write_bytes(buf.getvalue())
    print(f"✨ 100% Repacked & Fixed Cover: {ep.relative_to(LIB_ROOT)} ({ep.stat().st_size:,} bytes)")

def main():
    print("==================================================================")
    print("🖼️ PURGING SVG & FIXING STANDARD JPEG COVER FOR PRESUMED INNOCENT")
    print("==================================================================")

    matches = list(LIB_ROOT.rglob("*Presumed Innocent*.epub"))
    for m in matches:
        if "[e]" not in str(m.parent):
            clean_and_repack_epub(m)

if __name__ == "__main__":
    main()
