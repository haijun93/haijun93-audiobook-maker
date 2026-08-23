#!/usr/bin/env python3
"""scripts/rebuild_flawed_study_and_es.py

Rebuilds all flawed [study] EPUBs cleanly from [k-e] with sanitized XML,
and then generates 100% compliant [e-s] editions.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
from batch_inject_study_notes_to_library import process_single_epub
from make_english_study_epubs import convert_epub as make_english_study_epub

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
GDRIVE_ROOT = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

def heal_single_study_and_es(ke_path: Path) -> tuple[bool, str, str]:
    try:
        rel = ke_path.relative_to(LIB_ROOT / "[k-e]")
        study_path = LIB_ROOT / "[study]" / rel
        es_path = LIB_ROOT / "[e-s]" / rel
        
        # 1. Build clean [study] from [k-e]
        study_path.parent.mkdir(parents=True, exist_ok=True)
        res_ok, _, err = process_single_epub((str(ke_path), str(study_path)))
        if not res_ok:
            return False, str(rel), f"Failed to build [study]: {err}"
            
        # 2. Build clean [e-s] from [study]
        es_path.parent.mkdir(parents=True, exist_ok=True)
        make_english_study_epub(study_path, es_path, overwrite=True)
        
        # 3. Sync to Xteink
        xteink_study = LIB_ROOT / "[xteink]/[study]" / rel
        xteink_es = LIB_ROOT / "[xteink]/[e-s]" / rel
        if xteink_study.parent.exists():
            shutil.copy2(study_path, xteink_study)
        if xteink_es.parent.exists():
            shutil.copy2(es_path, xteink_es)
            
        # 4. Sync to Google Drive
        try:
            g_study = GDRIVE_ROOT / "[study]" / rel
            g_es = GDRIVE_ROOT / "[e-s]" / rel
            if g_study.parent.exists():
                shutil.copy2(study_path, g_study)
            if g_es.parent.exists():
                shutil.copy2(es_path, g_es)
        except Exception:
            pass
            
        return True, str(rel), "OK"
    except Exception as e:
        return False, str(ke_path.name), str(e)

def main():
    print("==================================================================")
    print("🔧 REBUILDING CLEAN [study] AND [e-s] FROM [k-e] IN PARALLEL")
    print("==================================================================")
    
    ke_epubs = sorted([p for p in (LIB_ROOT / "[k-e]").rglob("*.epub") if p.is_file()])
    print(f"📚 Total [k-e] sources to rebuild: {len(ke_epubs)}\n")
    
    success = 0
    fail = 0
    with ProcessPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(heal_single_study_and_es, p) for p in ke_epubs]
        for f in as_completed(futs):
            ok, name, err = f.result()
            if ok:
                success += 1
            else:
                fail += 1
                print(f"  ❌ [Fail] {name}: {err}")
                
    print(f"\n==================================================================")
    print(f"🎉 COMPLETED: Successfully rebuilt {success} [study] & [e-s] books! (Failed: {fail})")
    print("==================================================================")

if __name__ == "__main__":
    main()
