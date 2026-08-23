#!/usr/bin/env python3
"""scripts/clean_all_corrupted_prefixes_library.py

Comprehensive Prefix Sanitizer across the entire 4-edition library:
1. Strips all corrupted / duplicated prefix combinations:
   e.g. '[study] [study-]', '[e-s] [e-s-]', '[k] [k-e]', '[study-]', '[e-s-]', etc.
2. Extracts pure book title.
3. Attaches EXACTLY ONE clean standard edition prefix:
   - [k]     -> '[k] '
   - [k-e]   -> '[k-e] '
   - [study] -> '[study] '
   - [e-s]   -> '[e-s] '
4. Resolves collisions, deletes duplicate obsolete files, and mirrors to Google Drive #Books.
"""

from __future__ import annotations

import os
import re
import shutil
import unicodedata
from pathlib import Path

desktop = Path("/Users/hyeokjunkong/Desktop")
lib_root = next(p for p in desktop.iterdir() if "소설2" in unicodedata.normalize("NFC", p.name))
gdrive_root = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

# Match any leading bracket prefixes including trailing dashes, e.g. [study-], [e-s-], [k-e], [k], [e]
CORRUPTED_PREFIX_PATTERN = re.compile(
    r"^(\s*\[\s*(k|k-e|study|e-s|e)\s*[-\s]*\]\s*)+",
    re.IGNORECASE
)


def extract_pure_title(filename: str) -> str:
    name = filename
    if name.lower().endswith(".epub"):
        name = name[:-5]
        
    while True:
        m = CORRUPTED_PREFIX_PATTERN.match(name)
        if m:
            name = name[m.end():].strip()
        else:
            break
            
    # Also strip any accidental leading dashes or symbols after prefix
    name = re.sub(r"^[-_–—\s]+", "", name).strip()
    return name + ".epub"


def main():
    print("==================================================================")
    print("🧹 COMPREHENSIVE PREFIX SANITIZATION & DEDUPLICATION (LIBRARY)")
    print("==================================================================")
    
    editions = {
        "[k]": "[k]",
        "[k-e]": "[k-e]",
        "[study]": "[study]",
        "[e-s]": "[e-s]"
    }
    
    total_scanned = 0
    total_renamed = 0
    total_duplicates_removed = 0
    
    for ed_key, ed_prefix in editions.items():
        ed_dir = lib_root / ed_key
        if not ed_dir.exists():
            continue
            
        print(f"\n📂 Sanitizing Edition: {ed_key}")
        epubs = [p for p in ed_dir.rglob("*.epub") if not p.name.startswith("._")]
        total_scanned += len(epubs)
        
        for epub in sorted(epubs):
            pure_title = extract_pure_title(epub.name)
            clean_name = f"{ed_prefix} {pure_title}"
            
            if epub.name == clean_name:
                continue
                
            clean_path = epub.with_name(clean_name)
            
            if clean_path.exists() and clean_path != epub:
                # Clean version already exists -> remove duplicate corrupted version
                epub.unlink()
                total_duplicates_removed += 1
                print(f"  🗑️ Removed duplicate: {epub.name}")
            else:
                # Rename corrupted prefix to clean name
                epub.rename(clean_path)
                total_renamed += 1
                print(f"  ✨ Renamed: {epub.name} \n           -> {clean_name}")
                
    print("\n==================================================================")
    print(f"🎉 LOCAL LIBRARY PREFIX SANITIZATION COMPLETE!")
    print(f"  - Total Files Scanned        : {total_scanned}")
    print(f"  - Files Renamed to Clean     : {total_renamed}")
    print(f"  - Corrupted Duplicates Purged: {total_duplicates_removed}")
    print("==================================================================")
    
    # Sync with Google Drive #Books
    print("\n☁️ Synchronizing sanitization to Google Drive #Books...")
    for ed_key in editions:
        g_ed_dir = gdrive_root / ed_key
        l_ed_dir = lib_root / ed_key
        if not g_ed_dir.exists() or not l_ed_dir.exists():
            continue
            
        # 1. Remove obsolete corrupted files from GDrive
        for g_epub in g_ed_dir.rglob("*.epub"):
            if g_epub.name.startswith("._"):
                continue
            rel = g_epub.relative_to(g_ed_dir)
            l_equiv = l_ed_dir / rel
            if not l_equiv.exists():
                try:
                    g_epub.unlink()
                    print(f"  ☁️ Purged from GDrive: {g_epub.name}")
                except Exception:
                    pass
                    
        # 2. Upload clean files to GDrive
        for l_epub in l_ed_dir.rglob("*.epub"):
            if l_epub.name.startswith("._"):
                continue
            rel = l_epub.relative_to(l_ed_dir)
            g_dest = g_ed_dir / rel
            if not g_dest.exists():
                g_dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(l_epub, g_dest)
                    print(f"  ☁️ Uploaded clean: {l_epub.name}")
                except Exception:
                    pass

    print("\n☁️ Google Drive synchronization complete!")


if __name__ == "__main__":
    main()
