#!/usr/bin/env python3
"""scripts/perfect_presumed_innocent_cover_and_publish.py

Extracts high-definition cover image (148.8KB) from [e] Presumed Innocent,
injects standard 3-tier cover manifest and 000-cover.xhtml into all editions:
- `[study]`
- `[e-s]`
- `[k-e]`
- `[k]`
- `[xteink]/[study]`
- `[xteink]/[e-s]`
"""

from __future__ import annotations

import io
import re
import sys
import zipfile
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from audiobook_studio.ultimate_integrity_sentinel import conduct_ultimate_integrity_audit, format_sentinel_report

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
SRC_E = LIB_ROOT / "[e]/#apple tv original/#Scott Turow/[e] Presumed Innocent - Scott Turow.epub"

# 1. Extract HD Cover
with zipfile.ZipFile(SRC_E, "r") as z:
    if "presumedinnocent.jpg" in z.namelist():
        cover_bytes = z.read("presumedinnocent.jpg")
    else:
        cover_bytes = z.read("cover.jpeg")

print(f"✅ Extracted HD Cover Image: {len(cover_bytes):,} bytes")

COVER_XHTML = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="ko" xml:lang="ko">
<head>
  <title>표지 (Cover)</title>
  <meta charset="utf-8" />
  <link rel="stylesheet" type="text/css" href="styles.css" />
  <style type="text/css">
    @page { margin: 0; padding: 0; }
    body { margin: 0; padding: 0; text-align: center; background-color: #000000; }
    .cover-container { width: 100vw; height: 100vh; display: flex; justify-content: center; align-items: center; }
    img.cover-image { max-width: 100%; max-height: 100%; object-fit: contain; }
  </style>
</head>
<body epub:type="cover">
  <div class="cover-container">
    <img class="cover-image" src="images/cover.jpeg" alt="Presumed Innocent - Scott Turow Cover" />
  </div>
</body>
</html>""".encode("utf-8")

def perfect_cover_for_epub(ep: Path, edition_name: str):
    if not ep.exists():
        return
    data = {}
    with zipfile.ZipFile(ep, "r") as z:
        for it in z.infolist():
            try:
                data[it.filename] = z.read(it.filename)
            except Exception:
                pass

    # Place cover image and xhtml
    data["OEBPS/images/cover.jpeg"] = cover_bytes
    data["OEBPS/000-cover.xhtml"] = COVER_XHTML

    # Update content.opf
    if "OEBPS/content.opf" in data:
        opf_txt = data["OEBPS/content.opf"].decode("utf-8", "ignore")

        # Ensure metadata has cover meta
        if '<meta name="cover"' not in opf_txt and '<meta content="cover-image" name="cover"' not in opf_txt:
            opf_txt = re.sub(r'(<metadata[^>]*>)', r'\1\n    <meta name="cover" content="cover-image"/>', opf_txt)

        # Ensure manifest has cover-image & cover-page
        if 'id="cover-image"' not in opf_txt:
            opf_txt = re.sub(r'(<manifest[^>]*>)', r'\1\n    <item id="cover-image" href="images/cover.jpeg" media-type="image/jpeg" properties="cover-image"/>\n    <item id="cover-page" href="000-cover.xhtml" media-type="application/xhtml+xml"/>', opf_txt)

        # Ensure spine has cover-page at top
        if '<itemref idref="cover-page"' not in opf_txt:
            opf_txt = re.sub(r'(<spine[^>]*>)', r'\1\n    <itemref idref="cover-page"/>', opf_txt)

        data["OEBPS/content.opf"] = opf_txt.encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as dst:
        if "mimetype" in data:
            dst.writestr("mimetype", data.pop("mimetype"), compress_type=zipfile.ZIP_STORED)
        else:
            dst.writestr("mimetype", b"application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for fname, cdata in data.items():
            dst.writestr(fname, cdata)

    ep.write_bytes(buf.getvalue())
    print(f"✨ Perfected cover in: {ep.relative_to(LIB_ROOT)} ({ep.stat().st_size:,} bytes)")

def main():
    print("==================================================================")
    print("🖼️ PERFECTING COVER FOR ALL EDITIONS OF PRESUMED INNOCENT")
    print("==================================================================")

    matches = list(LIB_ROOT.rglob("*Presumed Innocent*.epub"))
    for m in matches:
        if "[e]" not in str(m.parent):
            perfect_cover_for_epub(m, "[study]")

    target_study = LIB_ROOT / "[study]/#apple tv original/#Scott Turow/[study] Presumed Innocent - Scott Turow.epub"
    print("\n🏛️ RUNNING TIER-2 SENTINEL AUDIT ON [study] PRESUMED INNOCENT:")
    rep = conduct_ultimate_integrity_audit(target_study, "[study]")
    print(format_sentinel_report(rep))

if __name__ == "__main__":
    main()
