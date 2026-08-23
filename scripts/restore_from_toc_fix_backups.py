#!/usr/bin/env python3
"""scripts/restore_from_toc_fix_backups.py

Restores any corrupted EPUBs across [k], [k-e], [study], [e-s] directly from pristine backups:
- _toc_fix_backups_20260815_095921/
- [backup_data] 20260807/
- new books from vk/
- _manual_backups/
"""

import shutil
import zipfile
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

BACKUP_SOURCES = [
    LIB_ROOT / "_toc_fix_backups_20260815_095921",
    LIB_ROOT / "[backup_data] 20260807",
    LIB_ROOT / "new books from vk",
    LIB_ROOT / "new books from vk - account2",
    LIB_ROOT / "_manual_backups",
]

def is_valid_zip(p: Path) -> bool:
    if not p.is_file() or p.stat().st_size < 100:
        return False
    try:
        with zipfile.ZipFile(p, "r") as z:
            return z.testzip() is None
    except Exception:
        return False

def restore_all():
    print("==================================================================")
    print("📦 RESTORING ALL DAMAGED EPUBS FROM PRISTINE BACKUP VAULTS")
    print("==================================================================")
    
    # 1. Index all pristine files in backup vaults
    vault_index = {}
    for b_src in BACKUP_SOURCES:
        if b_src.exists():
            for ep in b_src.rglob("*.epub"):
                if is_valid_zip(ep):
                    # Key by filename
                    if ep.name not in vault_index or ep.stat().st_size > vault_index[ep.name].stat().st_size:
                        vault_index[ep.name] = ep

    print(f"📚 Indexed {len(vault_index):,} pristine backup files from vaults.\n")
    
    # 2. Check and repair all active library editions
    editions = ["[k]", "[k-e]", "[study]", "[e-s]", "[e]"]
    total_repaired = 0
    total_still_bad = 0
    
    for ed in editions:
        ed_dir = LIB_ROOT / ed
        if not ed_dir.exists():
            continue
            
        print(f"🔍 Checking edition {ed}...")
        for ep in ed_dir.rglob("*.epub"):
            if not is_valid_zip(ep):
                # Look in vault
                if ep.name in vault_index:
                    shutil.copy2(vault_index[ep.name], ep)
                    total_repaired += 1
                    print(f"  ✅ Repaired {ed}/{ep.name} from vault")
                else:
                    total_still_bad += 1
                    print(f"  ❌ No vault backup for: {ed}/{ep.name}")

    print(f"\n==================================================================")
    print(f"🎉 RESTORATION COMPLETED: {total_repaired} files repaired! (Still bad: {total_still_bad})")
    print("==================================================================")

if __name__ == "__main__":
    restore_all()
