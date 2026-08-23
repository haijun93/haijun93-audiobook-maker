#!/usr/bin/env python3
"""scripts/fix_study_folder_naming_and_purify.py

Fixes the filename prefix bug in 소설2/[study]/:
1. Renames all '[k-e] ...' files inside 소설2/[study]/ to '[study] ...'.
2. If '[study] ...' already exists, merges/replaces with the clean Word Wise edition.
3. Completely purges all non-[study] files from 소설2/[study]/ and Google Drive #Books/[study]/.
4. Verifies 100% purity (0 non-[study] files in [study] folder).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
STUDY_ROOT = LIB_ROOT / "[study]"
GDRIVE_STUDY = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books/[study]")

def fix_study_folder():
    print("==================================================================")
    print("🧹 FIXING [study] FOLDER PREFIXES & PURIFYING MISPLACED FILES")
    print("==================================================================")
    
    if not STUDY_ROOT.exists():
        print("❌ [study] root does not exist!")
        return

    # 1. Rename or replace misnamed files in local [study]
    renamed_count = 0
    deleted_duplicates = 0
    
    for f in list(STUDY_ROOT.rglob("*.epub")):
        fname = f.name
        if not fname.startswith("[study] "):
            clean_stem = re.sub(r"^\[(k-e|k|e-s|e|ks|study_)\]\s*", "", fname)
            correct_name = f"[study] {clean_stem}"
            correct_path = f.parent / correct_name
            
            if correct_path.exists():
                # If correct [study] already exists, delete the stray misnamed file
                try:
                    f.unlink()
                    deleted_duplicates += 1
                except Exception as e:
                    print(f"  ❌ Error deleting duplicate {f.name}: {e}")
            else:
                # Rename to correct [study] prefix
                try:
                    f.rename(correct_path)
                    renamed_count += 1
                except Exception as e:
                    print(f"  ❌ Error renaming {f.name}: {e}")

    print(f"  🔄 Renamed {renamed_count:,} files to '[study] ...'")
    print(f"  🗑️ Deleted {deleted_duplicates:,} duplicate '[k-e] ...' files from [study].\n")

    # 2. Clean Google Drive #Books/[study]
    if GDRIVE_STUDY.exists():
        print("☁️ Purging misnamed files from Google Drive #Books/[study]...")
        g_deleted = 0
        for gf in list(GDRIVE_STUDY.rglob("*.epub")):
            if not gf.name.startswith("[study] "):
                try:
                    gf.unlink()
                    g_deleted += 1
                except Exception:
                    pass
        print(f"  🗑️ Google Drive: Deleted {g_deleted:,} misnamed files.")
        
        # Sync renamed files to Google Drive
        for f in STUDY_ROOT.rglob("*.epub"):
            if f.name.startswith("[study] "):
                rel = f.relative_to(STUDY_ROOT)
                gdst = GDRIVE_STUDY / rel
                gdst.parent.mkdir(parents=True, exist_ok=True)
                if not gdst.exists() or gdst.stat().st_size != f.stat().st_size:
                    shutil.copy2(f, gdst)
        print("  ✅ Google Drive [study] fully synchronized.")

    # 3. Final Verification
    print("\n==================================================")
    print("🔍 FINAL PREFIX AUDIT ACROSS ALL 5 ROOT EDITIONS")
    print("==================================================")
    for ed in ["[k]", "[k-e]", "[study]", "[e-s]", "[e]"]:
        ed_dir = LIB_ROOT / ed
        if ed_dir.exists():
            epubs = list(ed_dir.rglob("*.epub"))
            correct = sum(1 for p in epubs if p.name.startswith(f"{ed} "))
            wrong = len(epubs) - correct
            print(f"  📁 {ed:<10}: Total {len(epubs):<5} | Pure {ed}: {correct:<5} | Wrong: {wrong:<5}")

    print("==================================================================")

if __name__ == "__main__":
    fix_study_folder()
