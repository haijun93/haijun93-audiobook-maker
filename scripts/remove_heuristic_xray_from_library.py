#!/usr/bin/env python3
"""Remove all heuristic/placeholder X-Ray files from library.

Leaves ONLY authentic AI-generated X-Ray dossiers.
Scans:
- 소설2/[k]/
- 소설2/[k-e]/
- 소설2/[study]/
- 소설2/[e-s]/
- 소설2/[xteink]/[study]/
- 소설2/[xteink]/[e-s]/
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import time
import zipfile
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

HEURISTIC_PATTERNS = [
    "핵심 주인공 (Protagonist)",
    "주요 인물 (Key Character)",
    "동반자 및 조력자 (Supporting Lead)",
    "주변 인물군 (Supporting Cast)",
    "Protagonist (주인공)",
    "Key Deuteragonist",
    "Main Setting & Atmosphere",
    "Main Setting &amp; Atmosphere",
    "Core Conflict & Theme",
    "Core Conflict &amp; Theme",
    "Supporting Cast & Allies",
    "Supporting Cast &amp; Allies",
]

def is_heuristic_xray(xray_content: str) -> bool:
    return any(p in xray_content for p in HEURISTIC_PATTERNS)

def strip_xray_from_epub(epub_path: Path) -> bool:
    tmp_file = None
    try:
        with zipfile.ZipFile(epub_path, "r") as zin:
            in_names = zin.namelist()
            xray_names = [n for n in in_names if "000-xray" in n]
            if not xray_names:
                return False
                
            xray_data = zin.read(xray_names[0]).decode("utf-8", errors="replace")
            if not is_heuristic_xray(xray_data):
                # Authentic AI dossier -> Keep it!
                return False
                
            fd, tmp_path_str = tempfile.mkstemp(suffix=".epub", dir=epub_path.parent)
            os.close(fd)
            tmp_file = Path(tmp_path_str)
            
            with zipfile.ZipFile(tmp_file, "w") as zout:
                zout.comment = zin.comment
                if "mimetype" in in_names:
                    zout.writestr(zipfile.ZipInfo("mimetype"), zin.read("mimetype"), compress_type=zipfile.ZIP_STORED)
                    
                for name in in_names:
                    if name == "mimetype" or "000-xray" in name:
                        continue
                    data = zin.read(name)
                    
                    # Remove from nav.xhtml
                    if name.endswith("nav.xhtml"):
                        nav_str = data.decode("utf-8", errors="replace")
                        nav_str = re.sub(r"<li><a href=\"[^\"]*000-xray[^\"]*\">.*?</a></li>\s*", "", nav_str)
                        data = nav_str.encode("utf-8")
                    # Remove from toc.ncx
                    elif name.endswith("toc.ncx"):
                        ncx_str = data.decode("utf-8", errors="replace")
                        ncx_str = re.sub(r"<navPoint[^>]*id=\"navpoint-xray\"[^>]*>.*?</navPoint>\s*", "", ncx_str, flags=re.DOTALL)
                        data = ncx_str.encode("utf-8")
                    # Remove from .opf
                    elif name.endswith(".opf"):
                        opf_str = data.decode("utf-8", errors="replace")
                        opf_str = re.sub(r"<item[^>]*id=\"xray-dir\"[^>]*/>\s*", "", opf_str)
                        opf_str = re.sub(r"<itemref[^>]*idref=\"xray-dir\"[^>]*/>\s*", "", opf_str)
                        data = opf_str.encode("utf-8")
                        
                    zout.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
                    
        tmp_file.replace(epub_path)
        return True
    except Exception:
        if tmp_file and tmp_file.exists():
            tmp_file.unlink()
        return False

def clean_all_heuristic_xrays():
    t0 = time.time()
    print("==================================================================")
    print("🧹 REMOVING ALL HEURISTIC / PLACEHOLDER X-RAY DOSSIERS")
    print("==================================================================")
    
    target_dirs = [
        LIB_ROOT / "[k]",
        LIB_ROOT / "[k-e]",
        LIB_ROOT / "[study]",
        LIB_ROOT / "[e-s]",
        LIB_ROOT / "[xteink]" / "[study]",
        LIB_ROOT / "[xteink]" / "[e-s]",
    ]
    
    all_epubs = []
    for d in target_dirs:
        if d.exists():
            all_epubs.extend(d.rglob("*.epub"))
            
    print(f"📚 Scanning {len(all_epubs):,} books across library...\n")
    
    removed_count = 0
    kept_count = 0
    
    for idx, epub_p in enumerate(all_epubs, 1):
        if strip_xray_from_epub(epub_p):
            removed_count += 1
        if idx % 500 == 0 or idx == len(all_epubs):
            print(f"   -> Processed {idx:,} / {len(all_epubs):,} (Removed {removed_count:,} heuristic X-Rays)")
            
    elapsed = time.time() - t0
    print("\n==================================================================")
    print(f"🎉 COMPLETED in {elapsed:.1f}s! Removed {removed_count:,} heuristic X-Rays. Authentic AI dossiers preserved!")
    print("==================================================================")

if __name__ == "__main__":
    clean_all_heuristic_xrays()
