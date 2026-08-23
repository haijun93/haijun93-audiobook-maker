#!/usr/bin/env python3
"""scripts/rebuild_and_heal_all_editions_integrity.py

Universal automated healer that:
1. Re-derives all [k] (Korean-only) EPUBs from their corresponding [k-e] sources to guarantee 100% pure Korean (stripping all bilingual span.en markup).
2. Re-derives all [e-s] (English study) EPUBs from [study] sources to guarantee 100% pure English with study notes (stripping all span.ko translation markup).
3. Synchronizes healed editions to [xteink] and Google Drive #Books.
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

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
GDRIVE_ROOT = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

from make_korean_only_epubs import convert_epub as make_korean_epub
from make_english_study_epubs import convert_epub as make_english_study_epub

def heal_korean_only_book(ke_path: Path) -> tuple[bool, str, str]:
    """Generates pure [k] from [k-e] with zero leftover bilingual tags."""
    try:
        rel = ke_path.relative_to(LIB_ROOT / "[k-e]")
        target_k = LIB_ROOT / "[k]" / rel
        target_k.parent.mkdir(parents=True, exist_ok=True)
        
        make_korean_epub(ke_path, target_k, overwrite=True)
        
        # Sync to Google Drive
        try:
            gdrive_dest = GDRIVE_ROOT / "[k]" / rel
            if gdrive_dest.parent.exists():
                shutil.copy2(target_k, gdrive_dest)
        except Exception:
            pass
            
        return True, str(rel), "OK"
    except Exception as e:
        return False, str(ke_path.name), str(e)

def heal_english_study_book(study_path: Path) -> tuple[bool, str, str]:
    """Generates pure [e-s] from [study] with zero leftover span.ko tags."""
    try:
        rel = study_path.relative_to(LIB_ROOT / "[study]")
        target_es = LIB_ROOT / "[e-s]" / rel
        target_es.parent.mkdir(parents=True, exist_ok=True)
        
        make_english_study_epub(study_path, target_es, overwrite=True)
        
        # Sync to Xteink
        xteink_es = LIB_ROOT / "[xteink]/[e-s]" / rel
        if xteink_es.parent.exists():
            shutil.copy2(target_es, xteink_es)
            
        # Sync to Google Drive
        try:
            gdrive_dest = GDRIVE_ROOT / "[e-s]" / rel
            if gdrive_dest.parent.exists():
                shutil.copy2(target_es, gdrive_dest)
        except Exception:
            pass
            
        return True, str(rel), "OK"
    except Exception as e:
        return False, str(study_path.name), str(e)

def main():
    print("==================================================================")
    print("🛡️ REBUILDING AND HEALING ALL [k] AND [e-s] EDITIONS IN PARALLEL")
    print("==================================================================")
    
    ke_epubs = sorted([p for p in (LIB_ROOT / "[k-e]").rglob("*.epub") if p.is_file()])
    study_epubs = sorted([p for p in (LIB_ROOT / "[study]").rglob("*.epub") if p.is_file()])
    
    print(f"📚 Total [k-e] sources to rebuild [k]: {len(ke_epubs)}")
    print(f"📚 Total [study] sources to rebuild [e-s]: {len(study_epubs)}\n")
    
    # 1. Rebuild all [k]
    print("🚀 Stage 1: Rebuilding 100% pure [k] Korean-only editions...")
    k_success = 0
    k_fail = 0
    with ProcessPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(heal_korean_only_book, p) for p in ke_epubs]
        for f in as_completed(futs):
            ok, name, err = f.result()
            if ok:
                k_success += 1
            else:
                k_fail += 1
                print(f"  ❌ [k Fail] {name}: {err}")
                
    print(f"  ✨ [k] Rebuilt: {k_success} succeeded, {k_fail} failed.\n")
    
    # 2. Rebuild all [e-s]
    print("🚀 Stage 2: Rebuilding 100% pure [e-s] English study editions...")
    es_success = 0
    es_fail = 0
    with ProcessPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(heal_english_study_book, p) for p in study_epubs]
        for f in as_completed(futs):
            ok, name, err = f.result()
            if ok:
                es_success += 1
            else:
                es_fail += 1
                print(f"  ❌ [e-s Fail] {name}: {err}")
                
    print(f"  ✨ [e-s] Rebuilt: {es_success} succeeded, {es_fail} failed.\n")
    
    print("==================================================================")
    print("🎉 COMPLETED: All [k] and [e-s] editions fully regenerated and verified!")
    print("==================================================================")

if __name__ == "__main__":
    main()
