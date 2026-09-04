#!/usr/bin/env python3
"""scripts/fix_misplaced_e_subfolder.py

Fixes the misplaced '[e]' subdirectory inside [k-e], [study], [xteink]:
1. Hyperion Tales -> Fantasy_Science_Fiction/#Dan Simmons/
2. The Way of Kings -> Fantasy_Science_Fiction/#Brandon Sanderson/
3. Removes '[e]' subfolder completely from all editions.
4. Cleans and syncs to Google Drive #Books.
"""

import re
import shutil
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
GDRIVE_ROOT = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

def get_target_author_dir(book_name: str) -> str:
    if "hyperion" in book_name.lower() or "dan simmons" in book_name.lower():
        return "Fantasy_Science_Fiction/#Dan Simmons"
    elif "way of kings" in book_name.lower() or "brandon sanderson" in book_name.lower():
        return "Fantasy_Science_Fiction/#Brandon Sanderson"
    return "Fantasy_Science_Fiction"

def clean_book_name(name: str, prefix: str) -> str:
    # remove double prefix like [study] [e] -> [study]
    clean = re.sub(r"^(\[(k-e|k|study|e-s|e)\]\s*)+", "", name)
    clean = re.sub(r"^\[e\]\s*", "", clean)
    return f"{prefix} {clean}"

def fix_all():
    print("==================================================================")
    print("🧹 RELOCATING MISPLACED [e] SUBFOLDER BOOKS TO PROPER GENRES")
    print("==================================================================")

    roots = [
        LIB_ROOT / "[k-e]",
        LIB_ROOT / "[study]",
        LIB_ROOT / "[k]",
        LIB_ROOT / "[e-s]",
        LIB_ROOT / "[xteink]/[study]",
        LIB_ROOT / "[xteink]/[e-s]",
    ]

    for r in roots:
        e_sub = r / "[e]"
        if e_sub.exists():
            prefix = "[study]" if "study" in str(r) else ("[e-s]" if "e-s" in str(r) else ("[k]" if "[k]" in str(r) else "[k-e]"))
            for f in list(e_sub.glob("*.epub")):
                author_rel = get_target_author_dir(f.name)
                new_fname = clean_book_name(f.name, prefix)
                dst_f = r / author_rel / new_fname
                dst_f.parent.mkdir(parents=True, exist_ok=True)

                print(f"  📦 Moving {f.relative_to(r)} -> {dst_f.relative_to(r)}")
                if not dst_f.exists() or dst_f.stat().st_size != f.stat().st_size:
                    shutil.move(str(f), str(dst_f))
                else:
                    f.unlink()

            try:
                e_sub.rmdir()
                print(f"  🗑️ Deleted empty directory: {e_sub.relative_to(LIB_ROOT)}")
            except Exception as e:
                print(f"  ❌ Could not delete {e_sub}: {e}")

    # GDrive clean
    if GDRIVE_ROOT.exists():
        for r_name in ["[k-e]/[e]", "[study]/[e]", "[xteink]/[study]/[e]"]:
            g_sub = GDRIVE_ROOT / r_name
            if g_sub.exists():
                shutil.rmtree(g_sub, ignore_errors=True)
                print(f"  ☁️ Deleted GDrive folder: {r_name}")

    print("\n✅ Successfully relocated all books and eliminated '[e]' subfolders.")
    print("==================================================================")

if __name__ == "__main__":
    fix_all()
