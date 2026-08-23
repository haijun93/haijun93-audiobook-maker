#!/usr/bin/env python3
"""Deep Purge of all invalid/heuristic/pronoun-filled X-Rays from entire library.

Deletes any X-Ray that contains:
1. Pronouns / Invalid Names: 'You', 'His', 'She', 'He', 'They', 'The', 'This', 'That', 'When', 'There', 'What', 'Then', 'Chapter', 'With', 'From', 'Into', 'About', 'After', 'Before', 'Could', 'Would', 'Should'
2. Heuristic Templates: '작품의 사건과 갈등을 이끌어가는 핵심 주역. 내면의 결핍과 목표를 향해 나아가며 극적인 선택의 기로에 선다.'
3. Generic Placeholders: 'Protagonist (주인공)', 'Key Deuteragonist', etc.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

INVALID_NAME_TOKENS = {
    "you", "his", "she", "he", "it", "they", "their", "her", "him", "them",
    "but", "and", "the", "this", "that", "when", "there", "what", "then",
    "chapter", "with", "from", "into", "about", "after", "before", "could",
    "would", "should", "where", "while", "suddenly", "because", "although"
}

TEMPLATE_SIGNATURES = [
    "작품의 사건과 갈등을 이끌어가는 핵심 주역",
    "서사의 긴장감과 반전을 촉발하는 핵심 인물",
    "위기의 순간 조력과 신뢰를 형성하는 핵심 파트너십",
    "Protagonist (주인공)",
    "Key Deuteragonist",
    "Main Setting & Atmosphere",
    "핵심 주인공 (Protagonist)",
    "동반자 및 조력자 (Supporting Lead)"
]

def is_invalid_xray(xray_content: str) -> bool:
    # 1. Check template signatures
    if any(sig in xray_content for sig in TEMPLATE_SIGNATURES):
        return True
        
    # 2. Check character names
    soup = BeautifulSoup(xray_content, "html.parser")
    name_elements = soup.select(".xray-entity-name")
    for el in name_elements:
        name_text = el.get_text().strip().lower()
        if name_text in INVALID_NAME_TOKENS:
            return True
        # Check if single word pronoun
        words = name_text.split()
        if len(words) == 1 and words[0] in INVALID_NAME_TOKENS:
            return True
            
    return False

def strip_xray_from_epub(epub_path: Path) -> bool:
    tmp_file = None
    try:
        with zipfile.ZipFile(epub_path, "r") as zin:
            in_names = zin.namelist()
            xray_names = [n for n in in_names if "000-xray" in n]
            if not xray_names:
                return False
                
            xray_data = zin.read(xray_names[0]).decode("utf-8", errors="replace")
            if not is_invalid_xray(xray_data):
                # Valid authentic AI dossier -> Keep!
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
                    
                    if name.endswith("nav.xhtml"):
                        nav_str = data.decode("utf-8", errors="replace")
                        nav_str = re.sub(r"<li><a href=\"[^\"]*000-xray[^\"]*\">.*?</a></li>\s*", "", nav_str)
                        data = nav_str.encode("utf-8")
                    elif name.endswith("toc.ncx"):
                        ncx_str = data.decode("utf-8", errors="replace")
                        ncx_str = re.sub(r"<navPoint[^>]*id=\"navpoint-xray\"[^>]*>.*?</navPoint>\s*", "", ncx_str, flags=re.DOTALL)
                        data = ncx_str.encode("utf-8")
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

def purge_all():
    t0 = time.time()
    print("==================================================================", flush=True)
    print("🧹 DEEP PURGING ALL INVALID / PRONOUN-FILLED X-RAY DOSSIERS", flush=True)
    print("==================================================================", flush=True)
    
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
            
    print(f"📚 Scanning {len(all_epubs):,} books across library...\n", flush=True)
    
    purged_cnt = 0
    for idx, epub_p in enumerate(all_epubs, 1):
        if strip_xray_from_epub(epub_p):
            purged_cnt += 1
        if idx % 500 == 0 or idx == len(all_epubs):
            print(f"   -> Processed {idx:,} / {len(all_epubs):,} (Purged {purged_cnt:,} invalid X-Rays)", flush=True)
            
    elapsed = time.time() - t0
    print("\n==================================================================", flush=True)
    print(f"🎉 COMPLETED in {elapsed:.1f}s! Purged {purged_cnt:,} invalid X-Rays from library!", flush=True)
    print("==================================================================", flush=True)

if __name__ == "__main__":
    purge_all()
