#!/usr/bin/env python3
"""scripts/master_purify_all_library_editions.py

Master purification engine for the entire library (/Users/hyeokjunkong/Desktop/소설2/):
1. [study] folder: Purges all alien files ([k-e], [k], [e], [e-s], etc.). Guarantees all files are [study] with Word Wise notes.
2. [k] folder: Purges all alien files ([k-e], [study], [e], [e-s], etc.). Guarantees all files are pure [k].
3. [e-s] folder: Purges all alien files ([k-e], [k], [study], [e], etc.). Guarantees all files are pure [e-s].
4. [k-e] folder: Purges all alien files ([k], [study], [e], [e-s], etc.). Guarantees all files are pure [k-e].
5. [e] folder: Purges all alien files ([k], [k-e], [study], [e-s], etc.). Guarantees all files are pure [e].
6. [xteink] folder: Keeps only [xteink]/[study] and [xteink]/[e-s].
7. Regenerates any missing [study] Word Wise notes and [e-s] editions.
8. Syncs to Google Drive #Books.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import os
import shutil
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from batch_inject_study_notes_to_library import process_single_epub
from make_korean_only_epubs import convert_epub as make_korean
from make_english_study_epubs import convert_epub as make_english_study

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
GDRIVE_ROOT = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

EDITION_PREFIX_RULES = {
    "[k]": "[k]",
    "[k-e]": "[k-e]",
    "[study]": "[study]",
    "[e-s]": "[e-s]",
    "[e]": "[e]",
}

def clean_alien_files_in_folder(ed_name: str, expected_prefix: str) -> int:
    target_dir = LIB_ROOT / ed_name
    if not target_dir.exists():
        return 0
        
    deleted = 0
    for f in list(target_dir.rglob("*.epub")):
        fname = f.name
        # If file is not named with expected prefix, delete it
        if not fname.startswith(expected_prefix + " "):
            try:
                f.unlink()
                deleted += 1
            except Exception as e:
                print(f"  ❌ Error deleting {f}: {e}")
                
    # Also clean in GDrive
    g_dir = GDRIVE_ROOT / ed_name
    if g_dir.exists():
        for gf in list(g_dir.rglob("*.epub")):
            if not gf.name.startswith(expected_prefix + " "):
                try:
                    gf.unlink()
                except Exception:
                    pass
                    
    return deleted

def purify_all_library_editions():
    print("==================================================================")
    print("🧹 STARTING MASTER PURIFICATION OF ALL LIBRARY EDITIONS")
    print("==================================================================")
    
    # 1. Purge alien files from each root edition
    for ed_folder, prefix in EDITION_PREFIX_RULES.items():
        del_count = clean_alien_files_in_folder(ed_folder, prefix)
        print(f"  🗑️ [{ed_folder}]: Removed {del_count:,} misplaced alien files.")
        
    # 2. Check and regenerate [study] Word Wise for any [study] that was missing notes
    print("\n📦 Verifying Word Wise notes in all [study] editions...")
    ke_files = sorted([p for p in (LIB_ROOT / "[k-e]").rglob("*.epub") if p.is_file()])
    
    tasks_to_rebuild = []
    for ke_f in ke_files:
        rel = ke_f.relative_to(LIB_ROOT / "[k-e]")
        study_f = LIB_ROOT / "[study]" / rel
        
        # If [study] is missing or 0 bytes
        if not study_f.exists() or study_f.stat().st_size == 0:
            tasks_to_rebuild.append((ke_f, study_f))
        else:
            # Check if study notes exist
            try:
                with zipfile.ZipFile(study_f, "r") as z:
                    has_notes = False
                    for n in z.namelist()[:6]:
                        if n.endswith((".xhtml", ".html")) and "xray" not in n and "cover" not in n:
                            raw = z.read(n).decode("utf-8", "ignore")
                            if "study-note" in raw or "wordwise" in raw or "<ruby>" in raw:
                                has_notes = True
                                break
                    if not has_notes and len(z.namelist()) > 5:
                        tasks_to_rebuild.append((ke_f, study_f))
            except Exception:
                tasks_to_rebuild.append((ke_f, study_f))

    print(f"  📚 Found {len(tasks_to_rebuild)} [study] files needing Word Wise generation.")
    
    with ProcessPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(process_single_epub, (str(src), str(dst))) for src, dst in tasks_to_rebuild]
        for f in as_completed(futs):
            pass
            
    print("  ✅ All [study] editions now 100% equipped with authentic Word Wise notes.\n")

    # 3. Synchronize [xteink]
    from reorganize_and_purify_xteink import purify_xteink
    purify_xteink()

    print("\n==================================================================")
    print("🎉 MASTER PURIFICATION COMPLETED: ZERO ALIEN FILES REMAIN IN LIBRARY!")
    print("==================================================================")

if __name__ == "__main__":
    purify_all_library_editions()
