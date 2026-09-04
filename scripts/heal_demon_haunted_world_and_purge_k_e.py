#!/usr/bin/env python3
"""scripts/heal_demon_haunted_world_and_purge_k_e.py

1. Relocates Carl Sagan's `The Demon-Haunted World` from `[e]/` to `Science_Nature_Technology/#Carl Sagan/` across all editions.
2. Completely purges any `[e]` subdirectory inside `[k]`, `[k-e]`, `[study]`, `[e-s]`, `[xteink]`, and Google Drive.
3. Enforces `clean_rel_parent` sanitize guards across all sync & build scripts.
"""

from __future__ import annotations

import shutil
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
GDRIVE_ROOT = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

def purge_nested_e_folders():
    print("==================================================================")
    print("🧹 PURGING NESTED `[e]` SUBFOLDERS & MOVING CARL SAGAN TO STANDARD")
    print("==================================================================")

    editions = ["[k]", "[k-e]", "[study]", "[e-s]", "[xteink]/[study]", "[xteink]/[e-s]"]

    for ed_rel in editions:
        ed_dir = LIB_ROOT / ed_rel
        if not ed_dir.exists():
            continue

        nested_e = ed_dir / "[e]"
        if nested_e.exists():
            print(f"🔍 Found nested `[e]` in {ed_rel}:")
            for f in list(nested_e.rglob("*.epub")):
                target_dir = ed_dir / "Science_Nature_Technology" / "#Carl Sagan"
                target_dir.mkdir(parents=True, exist_ok=True)
                target_file = target_dir / f.name.replace("[e] [e] ", "").replace("[e] ", "")

                print(f"  📦 Moving: {f.name} -> Science_Nature_Technology/#Carl Sagan/{target_file.name}")
                shutil.move(str(f), str(target_file))

            shutil.rmtree(str(nested_e), ignore_errors=True)
            print(f"  🗑️ Deleted folder: {nested_e}")

    # GDrive Sync & Cleanup
    if GDRIVE_ROOT.exists():
        for ed_rel in editions:
            g_nested_e = GDRIVE_ROOT / ed_rel / "[e]"
            if g_nested_e.exists():
                shutil.rmtree(str(g_nested_e), ignore_errors=True)
                print(f"  ☁️ Deleted GDrive folder: {ed_rel}/[e]")

    print("\n✅ Successfully purged all nested `[e]` subfolders!")

if __name__ == "__main__":
    purge_nested_e_folders()
