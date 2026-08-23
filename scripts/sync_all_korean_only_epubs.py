#!/usr/bin/env python3
"""scripts/sync_all_korean_only_epubs.py

Synchronizes the [k] edition (Korean-only) with [k-e] across the entire library:
1. Finds all [k-e] EPUBs in /Users/hyeokjunkong/Desktop/소설2/[k-e]
2. Checks if corresponding [k] EPUB exists in /Users/hyeokjunkong/Desktop/소설2/[k]
3. Converts [k-e] -> [k] (Korean-only) with full integrity and clean scene subheadings.
4. Synchronizes newly generated [k] EPUBs to Google Drive #Books/[k].
"""

from __future__ import annotations

import os
import shutil
import sys
import unicodedata
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, "/Users/hyeokjunkong/Desktop/myproject_python/haijun93-audiobook-maker")
sys.path.insert(0, "/Users/hyeokjunkong/Desktop/myproject_python/haijun93-audiobook-maker/scripts")

from scripts.make_korean_only_epubs import convert_epub, output_name

desktop = Path("/Users/hyeokjunkong/Desktop")
lib_root = next(p for p in desktop.iterdir() if "소설2" in unicodedata.normalize("NFC", p.name))
ke_root = lib_root / "[k-e]"
k_root = lib_root / "[k]"
gdrive_root = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")


def sync_single_book(ke_path: Path) -> tuple[str, str]:
    if not ke_path.exists() or ke_path.name.startswith("._"):
        return ke_path.name, "skipped_dotfile"
        
    rel = ke_path.relative_to(ke_root)
    # Output path in [k]
    k_filename = output_name(ke_path.name)
    k_path = k_root / rel.parent / k_filename
    
    if k_path.exists():
        return ke_path.name, "already_exists"
        
    try:
        k_path.parent.mkdir(parents=True, exist_ok=True)
        stats = convert_epub(ke_path, k_path, overwrite=True)
        if stats.get("skipped"):
            return ke_path.name, "convert_skipped"
            
        # Copy to GDrive
        gdrive_k_path = gdrive_root / "[k]" / rel.parent / k_filename
        gdrive_k_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(k_path, gdrive_k_path)
        
        return ke_path.name, "success"
    except Exception as e:
        return ke_path.name, f"error: {e}"


def main():
    print("==================================================================")
    print("🚀 SYNCHRONIZING [k] (KOREAN-ONLY) EDITIONS WITH [k-e] LIBRARY")
    print("==================================================================")
    
    all_ke_epubs = [p for p in ke_root.rglob("*.epub") if not p.name.startswith("._")]
    print(f"Total [k-e] EPUBs in Library: {len(all_ke_epubs)}")
    
    tasks = []
    for ke in all_ke_epubs:
        rel = ke.relative_to(ke_root)
        k_filename = output_name(ke.name)
        k_path = k_root / rel.parent / k_filename
        if not k_path.exists():
            tasks.append(ke)
            
    print(f"Missing in [k] to generate: {len(tasks)} books\n")
    if not tasks:
        print("🎉 [k] is already 100% synchronized with [k-e]!")
        return
        
    success_count = 0
    err_count = 0
    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(sync_single_book, ke): ke for ke in tasks}
        
        for i, future in enumerate(as_completed(futures), start=1):
            name, status = future.result()
            if status == "success":
                success_count += 1
                print(f"  [{i:3}/{len(tasks)}] ✅ Generated [k]: {name}")
            elif status.startswith("error"):
                err_count += 1
                print(f"  [{i:3}/{len(tasks)}] ❌ Failed: {name} ({status})")
                
    print(f"\n==================================================================")
    print(f"🎉 [k] SYNCHRONIZATION COMPLETE!")
    print(f"  - Newly Generated & Synced : {success_count} books")
    print(f"  - Errors                   : {err_count}")
    
    total_k = len([p for p in k_root.rglob("*.epub") if not p.name.startswith("._")])
    total_ke = len(all_ke_epubs)
    print(f"  - Final Library Count      : [k] {total_k} books / [k-e] {total_ke} books")
    print("==================================================================")


if __name__ == "__main__":
    main()
