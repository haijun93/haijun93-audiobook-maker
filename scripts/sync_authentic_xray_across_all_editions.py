#!/usr/bin/env python3
"""Sync authentic AI X-Ray files across all library editions."""

from __future__ import annotations

import re
import tempfile
import time
import zipfile
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

def clean_name(stem: str) -> str:
    s = re.sub(r"^\[(study|e-s|ks|kindle|k|k-e|xteink)\]\s*", "", stem)
    while re.match(r"^\[[^\]]+\]\s*", s):
        s = re.sub(r"^\[[^\]]+\]\s*", "", s)
    s = re.sub(r"\s*\(\d+\.\d+\)$", "", s).strip()
    return s

def get_authentic_xrays_from_source(source_dir: Path) -> dict[str, tuple[str, Path]]:
    xrays = {}
    for ep in source_dir.rglob("*.epub"):
        try:
            with zipfile.ZipFile(ep, "r") as z:
                x_files = [n for n in z.namelist() if "000-xray" in n]
                if x_files:
                    data = z.read(x_files[0]).decode("utf-8", errors="replace")
                    if "xray-entity-card" in data and not any(h in data for h in ["Protagonist (주인공)", "핵심 주인공 (Protagonist)"]):
                        key = clean_name(ep.stem).lower()
                        xrays[key] = (data, ep)
        except Exception:
            pass
    return xrays

def inject_xray_data_to_epub(epub_path: Path, xray_xhtml: str) -> bool:
    tmp_file = None
    try:
        with zipfile.ZipFile(epub_path, "r") as zin:
            in_names = zin.namelist()
            fd, tmp_str = tempfile.mkstemp(suffix=".epub", dir=epub_path.parent)
            import os
            os.close(fd)
            tmp_file = Path(tmp_str)
            
            with zipfile.ZipFile(tmp_file, "w") as zout:
                zout.comment = zin.comment
                if "mimetype" in in_names:
                    zout.writestr(zipfile.ZipInfo("mimetype"), zin.read("mimetype"), compress_type=zipfile.ZIP_STORED)
                    
                xray_path = "OEBPS/000-xray-dramatis-personae.xhtml" if any(n.startswith("OEBPS/") for n in in_names) else "000-xray-dramatis-personae.xhtml"
                zout.writestr(xray_path, xray_xhtml.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
                
                for name in in_names:
                    if name == "mimetype" or "000-xray" in name:
                        continue
                    data = zin.read(name)
                    if name.endswith("nav.xhtml"):
                        nav_str = data.decode("utf-8", errors="replace")
                        if "000-xray-dramatis-personae.xhtml" not in nav_str:
                            xray_li = f'<li><a href="000-xray-dramatis-personae.xhtml">⚡ X-Ray: 등장인물 및 용어 도감</a></li>\n      '
                            nav_str = re.sub(r"(<ol[^>]*>)", rf"\1\n      {xray_li}", nav_str, count=1)
                        data = nav_str.encode("utf-8")
                    elif name.endswith("toc.ncx"):
                        ncx_str = data.decode("utf-8", errors="replace")
                        if "000-xray-dramatis-personae.xhtml" not in ncx_str:
                            xray_navpoint = f'<navPoint id="navpoint-xray" playOrder="1">\n    <navLabel><text>⚡ X-Ray: 등장인물 및 용어 도감</text></navLabel>\n    <content src="000-xray-dramatis-personae.xhtml"/>\n  </navPoint>\n  '
                            ncx_str = re.sub(r"(<navMap[^>]*>)", rf"\1\n  {xray_navpoint}", ncx_str, count=1)
                        data = ncx_str.encode("utf-8")
                    elif name.endswith(".opf"):
                        opf_str = data.decode("utf-8", errors="replace")
                        if "000-xray-dramatis-personae.xhtml" not in opf_str:
                            item_tag = '<item id="xray-dir" href="000-xray-dramatis-personae.xhtml" media-type="application/xhtml+xml"/>\n'
                            itemref_tag = '<itemref idref="xray-dir"/>\n'
                            opf_str = re.sub(r"(<manifest[^>]*>)", rf"\1\n    {item_tag}", opf_str, count=1)
                            opf_str = re.sub(r"(<spine[^>]*>)", rf"\1\n    {itemref_tag}", opf_str, count=1)
                        data = opf_str.encode("utf-8")
                    zout.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
        tmp_file.replace(epub_path)
        return True
    except Exception:
        if tmp_file and tmp_file.exists():
            tmp_file.unlink()
        return False

def sync_all():
    print("Collecting authentic X-Rays from [study] and [k-e]...")
    source_xrays = get_authentic_xrays_from_source(LIB_ROOT / "[study]")
    source_xrays.update(get_authentic_xrays_from_source(LIB_ROOT / "[k-e]"))
    print(f"Found {len(source_xrays):,} unique authentic AI X-Ray dossiers!\n")
    
    target_editions = ["[k]", "[k-e]", "[study]", "[e-s]", "[xteink]/[study]", "[xteink]/[e-s]"]
    for ed in target_editions:
        ed_dir = LIB_ROOT / ed
        if not ed_dir.exists():
            continue
        synced = 0
        epubs = list(ed_dir.rglob("*.epub"))
        for ep in epubs:
            k = clean_name(ep.stem).lower()
            if k in source_xrays:
                x_data, _ = source_xrays[k]
                if inject_xray_data_to_epub(ep, x_data):
                    synced += 1
        print(f"  • {ed:<25}: Synced {synced:>4} / {len(epubs):>} books")

if __name__ == "__main__":
    sync_all()
