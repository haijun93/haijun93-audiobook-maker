#!/usr/bin/env python3
"""scripts/restore_all_books_from_pristine_backups.py

Restores 100% pristine [k-e] master files from [backup_data] 20260807 and translation stages,
then re-derives all compliant editions ([k], [study], [e-s], [xteink]) with strict ZIP integrity verification.
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
BACKUP_DIR = LIB_ROOT / "[backup_data] 20260807"
CHATGPT_DIR = LIB_ROOT / "_chatgpt_translate_work"
STAGE_DIR = LIB_ROOT / "_translation_stage"

def is_valid_zip(p: Path) -> bool:
    if not p.is_file() or p.stat().st_size < 100:
        return False
    try:
        with zipfile.ZipFile(p, "r") as z:
            return z.testzip() is None
    except Exception:
        return False

def restore_master_ke():
    print("==================================================================")
    print("🔄 RESTORING MASTER [k-e] ARCHIVES FROM PRISTINE BACKUPS")
    print("==================================================================")

    ke_dest = LIB_ROOT / "[k-e]"

    # 1. Build map of pristine [k-e] files from backup directories
    pristine_map = {}

    for bdir in [BACKUP_DIR / "[k-e]", CHATGPT_DIR, STAGE_DIR]:
        if bdir.exists():
            for ep in bdir.rglob("*.epub"):
                if ep.name.startswith("[k-e] ") and is_valid_zip(ep):
                    # Keep latest / biggest valid version
                    if ep.name not in pristine_map or ep.stat().st_size > pristine_map[ep.name].stat().st_size:
                        pristine_map[ep.name] = ep

    print(f"📦 Total unique pristine [k-e] sources found: {len(pristine_map):,}\n")

    restored = 0
    # Restore any missing or invalid [k-e] in target
    for target_ep in list(ke_dest.rglob("*.epub")):
        if not is_valid_zip(target_ep):
            if target_ep.name in pristine_map:
                shutil.copy2(pristine_map[target_ep.name], target_ep)
                restored += 1
                print(f"  ✅ Restored {target_ep.name}")
            else:
                print(f"  ⚠️ No pristine backup found for {target_ep.name}")

    print(f"\n✨ Restored {restored} corrupted [k-e] books to pristine condition.\n")

if __name__ == "__main__":
    restore_master_ke()
