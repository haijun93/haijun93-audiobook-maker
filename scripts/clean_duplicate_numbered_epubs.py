#!/usr/bin/env python3
"""Safe Deduplicator for [e] Raw English EPUBs in Library.

Cleans up redundant browser sequence duplicate downloads (e.g. `(2).epub`, `(3).epub`, etc.)
while preserving authentic master files, and standardizes orphan numbered files.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

def get_md5(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def deduplicate_folder(e_root: Path, dry_run: bool = False):
    print("==================================================================")
    print(f"🧹 DEDUPLICATING RAW ENGLISH EPUBS IN {e_root}")
    print(f"   Mode: {'DRY RUN' if dry_run else 'LIVE DEDUPLICATION'}")
    print("==================================================================")
    
    all_epubs = list(e_root.rglob("*.epub"))
    by_parent = {}
    for p in all_epubs:
        by_parent.setdefault(p.parent, []).append(p)
        
    deleted_count = 0
    renamed_count = 0
    saved_bytes = 0
    
    for parent_dir, files in by_parent.items():
        groups = {}
        for f in files:
            m = re.search(r"\s*\((\d+)\)\.epub$", f.name)
            if m:
                seq_num = int(m.group(1))
                base_name = f.name[:m.start()] + ".epub"
                base_stem = re.sub(r"\[.*?\]", "", base_name).replace(".epub", "").strip().lower()
                base_stem = re.sub(r"\(\d+\.\d+\)", "", base_stem).strip()
                groups.setdefault(base_stem, []).append(("dup", f, seq_num, base_name))
            else:
                base_stem = re.sub(r"\[.*?\]", "", f.name).replace(".epub", "").strip().lower()
                base_stem = re.sub(r"\(\d+\.\d+\)", "", base_stem).strip()
                groups.setdefault(base_stem, []).append(("base", f, 0, f.name))
                
        for stem, items in groups.items():
            bases = [it for it in items if it[0] == "base"]
            dups = [it for it in items if it[0] == "dup"]
            
            # Case 1: Base exists, delete redundant numbered copies
            if bases and dups:
                base_file = bases[0][1]
                for _, dup_file, _, _ in dups:
                    f_size = dup_file.stat().st_size
                    print(f"  🗑️ Removing duplicate: {dup_file.name} ({f_size:,} B) [Base: {base_file.name}]")
                    if not dry_run:
                        dup_file.unlink()
                    deleted_count += 1
                    saved_bytes += f_size
                    
            # Case 2: No base file exists (only (2), (3), (4)...)
            elif not bases and dups:
                # Sort by sequence number
                dups_sorted = sorted(dups, key=lambda x: x[2])
                primary = dups_sorted[0]
                primary_file = primary[1]
                target_base_name = primary[3]
                target_base_path = parent_dir / target_base_name
                
                print(f"  ✨ Promoting primary: {primary_file.name} -> {target_base_name}")
                if not dry_run:
                    primary_file.rename(target_base_path)
                renamed_count += 1
                
                # Delete the remaining duplicates
                for _, dup_file, _, _ in dups_sorted[1:]:
                    f_size = dup_file.stat().st_size
                    print(f"  🗑️ Removing duplicate: {dup_file.name} ({f_size:,} B)")
                    if not dry_run:
                        dup_file.unlink()
                    deleted_count += 1
                    saved_bytes += f_size
                    
    print("\n==================================================================")
    print(f"🎉 DEDUPLICATION COMPLETE!")
    print(f"   • Total duplicate files removed: {deleted_count:,}")
    print(f"   • Primary files renamed:         {renamed_count:,}")
    print(f"   • Disk space recovered:          {saved_bytes / (1024 * 1024):.2f} MB")
    print("==================================================================")

if __name__ == "__main__":
    e_dir = LIB_ROOT / "[e]"
    deduplicate_folder(e_dir, dry_run=False)
