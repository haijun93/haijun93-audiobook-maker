#!/usr/bin/env python3
"""scripts/reorganize_and_purify_xteink.py

Completely purifies the /Users/hyeokjunkong/Desktop/소설2/[xteink]/ directory:
1. Deletes all alien/mismatched files ([k-e], [k], [e], [study_] or [study] in [e-s], etc.)
2. Accurately synchronizes genuine [study] edition files from 소설2/[study]/ into [xteink]/[study]/
3. Accurately synchronizes genuine [e-s] edition files from 소설2/[e-s]/ into [xteink]/[e-s]/
4. Syncs the purified [xteink] structure to Google Drive #Books.
5. Verifies 100% purity (0 mismatched files).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
XTEINK_ROOT = LIB_ROOT / "[xteink]"
STUDY_SRC = LIB_ROOT / "[study]"
ES_SRC = LIB_ROOT / "[e-s]"

GDRIVE_XTEINK = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books/[xteink]")

def purify_xteink():
    print("==================================================================")
    print("🧹 PURIFYING AND REORGANIZING [xteink] DIRECTORY")
    print("==================================================================")
    
    if not XTEINK_ROOT.exists():
        XTEINK_ROOT.mkdir(parents=True, exist_ok=True)

    # 1. Scan and delete all mismatched / alien files
    deleted_count = 0
    all_xteink_files = list(XTEINK_ROOT.rglob("*"))
    for f in all_xteink_files:
        if f.is_file():
            rel = f.relative_to(XTEINK_ROOT)
            parts = rel.parts
            top_dir = parts[0] if parts else ""
            fname = f.name
            
            should_delete = False
            if not fname.endswith(".epub"):
                should_delete = True
            elif top_dir == "[study]" and not fname.startswith("[study]"):
                should_delete = True
            elif top_dir == "[e-s]" and not fname.startswith("[e-s]"):
                should_delete = True
            elif top_dir not in ["[study]", "[e-s]"]:
                should_delete = True
                
            if should_delete:
                try:
                    f.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(f"  ❌ Error deleting {f}: {e}")

    print(f"🗑️ Deleted {deleted_count:,} mismatched/alien files from [xteink].\n")

    # 2. Clean empty directories
    for d in sorted(list(XTEINK_ROOT.rglob("*")), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            try:
                d.rmdir()
            except Exception:
                pass

    # 3. Synchronize pure [study] files
    print("📦 Synchronizing authentic [study] files into [xteink]/[study]...")
    study_synced = 0
    if STUDY_SRC.exists():
        for src_f in STUDY_SRC.rglob("*.epub"):
            if src_f.name.startswith("[study]"):
                rel = src_f.relative_to(STUDY_SRC)
                dst_f = XTEINK_ROOT / "[study]" / rel
                dst_f.parent.mkdir(parents=True, exist_ok=True)
                if not dst_f.exists() or dst_f.stat().st_size != src_f.stat().st_size:
                    shutil.copy2(src_f, dst_f)
                study_synced += 1
    print(f"  ✅ [xteink]/[study] now contains {study_synced:,} authentic study books.\n")

    # 4. Synchronize pure [e-s] files
    print("📦 Synchronizing authentic [e-s] files into [xteink]/[e-s]...")
    es_synced = 0
    if ES_SRC.exists():
        for src_f in ES_SRC.rglob("*.epub"):
            if src_f.name.startswith("[e-s]"):
                rel = src_f.relative_to(ES_SRC)
                dst_f = XTEINK_ROOT / "[e-s]" / rel
                dst_f.parent.mkdir(parents=True, exist_ok=True)
                if not dst_f.exists() or dst_f.stat().st_size != src_f.stat().st_size:
                    shutil.copy2(src_f, dst_f)
                es_synced += 1
    print(f"  ✅ [xteink]/[e-s] now contains {es_synced:,} authentic English study books.\n")

    # 5. Clean Google Drive #Books/[xteink] if available
    if GDRIVE_XTEINK.exists():
        print("☁️ Synchronizing purified [xteink] to Google Drive #Books/[xteink]...")
        # Delete alien files in GDrive
        for gf in GDRIVE_XTEINK.rglob("*"):
            if gf.is_file():
                rel = gf.relative_to(GDRIVE_XTEINK)
                top_dir = rel.parts[0] if rel.parts else ""
                if top_dir == "[study]" and not gf.name.startswith("[study]"):
                    gf.unlink(missing_ok=True)
                elif top_dir == "[e-s]" and not gf.name.startswith("[e-s]"):
                    gf.unlink(missing_ok=True)
                elif top_dir not in ["[study]", "[e-s]"]:
                    gf.unlink(missing_ok=True)
                    
        # Copy newly synced
        for f in XTEINK_ROOT.rglob("*.epub"):
            rel = f.relative_to(XTEINK_ROOT)
            gdst = GDRIVE_XTEINK / rel
            gdst.parent.mkdir(parents=True, exist_ok=True)
            if not gdst.exists() or gdst.stat().st_size != f.stat().st_size:
                shutil.copy2(f, gdst)
        print("  ✅ Google Drive [xteink] fully synced.")

    # 6. Final verification
    print("\n==================================================")
    print("🔍 FINAL PURITY VERIFICATION FOR [xteink]")
    print("==================================================")
    final_study_files = list((XTEINK_ROOT / "[study]").rglob("*.epub"))
    final_es_files = list((XTEINK_ROOT / "[e-s]").rglob("*.epub"))
    
    study_mismatches = [f.name for f in final_study_files if not f.name.startswith("[study]")]
    es_mismatches = [f.name for f in final_es_files if not f.name.startswith("[e-s]")]
    
    print(f"📖 [xteink]/[study]: {len(final_study_files):,} books (Mismatched: {len(study_mismatches)})")
    print(f"📖 [xteink]/[e-s]  : {len(final_es_files):,} books (Mismatched: {len(es_mismatches)})")
    
    if len(study_mismatches) == 0 and len(es_mismatches) == 0:
        print("\n🎉 SUCCESS: [xteink] directory is 100% PURE, CLEAN, AND VERIFIED!")
    else:
        print(f"\n⚠️ WARNING: Found remaining mismatches: study={study_mismatches[:5]}, es={es_mismatches[:5]}")
    print("==================================================================")

if __name__ == "__main__":
    purify_xteink()
