#!/usr/bin/env python3
"""scripts/fix_duplicate_prefixes_library.py

Cleans and normalizes all EPUB filenames across the entire library:
1. Strips repeated prefixes like '[k] [k] ', '[k] [k-e] ', '[k] [e-s] ', etc.
2. Ensures each file has EXACTLY ONE standard prefix corresponding to its edition:
   - [k]     -> '[k] '
   - [k-e]   -> '[k-e] '
   - [study] -> '[study] '
   - [e-s]   -> '[e-s] '
3. Removes redundant duplicate copies and cleans Google Drive #Books.
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

PREFIX_RE = re.compile(r"^(\s*\[(k|k-e|study|e-s|e)\]\s*)+", re.I)


def clean_title(filename: str) -> str:
    name = filename
    if name.endswith(".epub"):
        name = name[:-5]
    # Strip any leading bracket prefixes
    name = PREFIX_RE.sub("", name).strip()
    return name + ".epub"


def main():
    print("==================================================================")
    print("🧹 FIXING REPEATED PREFIXES & CLEANING DUPLICATES IN LIBRARY")
    print("==================================================================")
    
    editions = {
        "[k]": "[k]",
        "[k-e]": "[k-e]",
        "[study]": "[study]",
        "[e-s]": "[e-s]"
    }
    
    total_cleaned = 0
    total_renamed = 0
    total_removed_duplicates = 0
    
    for ed_key, ed_tag in editions.items():
        ed_dir = lib_root / ed_key
        if not ed_dir.exists():
            continue
            
        print(f"\n📂 Processing Edition: {ed_key}")
        epubs = [p for p in ed_dir.rglob("*.epub") if not p.name.startswith("._")]
        
        for epub in sorted(epubs):
            pure_name = clean_title(epub.name)
            expected_name = f"{ed_tag} {pure_name}"
            
            if epub.name == expected_name:
                continue
                
            target_path = epub.with_name(expected_name)
            
            if target_path.exists() and target_path != epub:
                # Target clean file already exists, this is an erroneous duplicate -> remove it
                epub.unlink()
                total_removed_duplicates += 1
                print(f"  🗑️ Removed duplicate: {epub.name}")
            else:
                # Rename to expected clean name
                epub.rename(target_path)
                total_renamed += 1
                print(f"  ✏️ Renamed: {epub.name} -> {expected_name}")
                
    print(f"\n==================================================================")
    print(f"🎉 LOCAL LIBRARY PREFIX CLEANUP COMPLETE!")
    print(f"  - Removed Duplicates : {total_removed_duplicates}")
    print(f"  - Renamed Files      : {total_renamed}")
    print(f"==================================================================")
    
    # Mirror & clean on Google Drive
    print("\n☁️ Synchronizing cleanup to Google Drive #Books...")
    for ed_key in editions:
        g_ed_dir = gdrive_root / ed_key
        l_ed_dir = lib_root / ed_key
        if not g_ed_dir.exists() or not l_ed_dir.exists():
            continue
            
        # Clean obsolete files on GDrive
        for g_epub in g_ed_dir.rglob("*.epub"):
            if g_epub.name.startswith("._"):
                continue
            rel = g_epub.relative_to(g_ed_dir)
            l_equiv = l_ed_dir / rel
            if not l_equiv.exists():
                try:
                    g_epub.unlink()
                    print(f"  ☁️ Removed obsolete GDrive file: {g_epub.name}")
                except Exception:
                    pass
                    
        # Copy newly renamed or clean files to GDrive
        for l_epub in l_ed_dir.rglob("*.epub"):
            if l_epub.name.startswith("._"):
                continue
            rel = l_epub.relative_to(l_ed_dir)
            g_dest = g_ed_dir / rel
            if not g_dest.exists():
                g_dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(l_epub, g_dest)
                    print(f"  ☁️ Uploaded clean file to GDrive: {l_epub.name}")
                except Exception:
                    pass

    print("\n☁️ Google Drive synchronization complete!")


if __name__ == "__main__":
    main()
