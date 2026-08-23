#!/usr/bin/env python3
"""Investigate and fix all duplicate/nested prefix filenames across the library.

Examples fixed:
- '[k] [k] Housemaid 02 The Housemaids Secret Freida McFadden 2 (4.15).epub'
  -> '[k] Housemaid 02 The Housemaids Secret Freida McFadden 2 (4.15).epub'
- '[study] [study] ...' -> '[study] ...'
- '[k-e] [k-e] ...' -> '[k-e] ...'
"""

from __future__ import annotations

import os
import re
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

def get_canonical_prefix(file_path: Path) -> str:
    parts = file_path.parts
    if "[xteink]" in parts:
        if "[study]" in parts:
            return "[study]"
        elif "[e-s]" in parts:
            return "[e-s]"
    elif "[k]" in parts:
        return "[k]"
    elif "[k-e]" in parts:
        return "[k-e]"
    elif "[study]" in parts:
        return "[study]"
    elif "[e-s]" in parts:
        return "[e-s]"
    elif "[ks]" in parts:
        return "[ks]"
    return ""

def clean_title_strip_all_prefixes(stem: str) -> str:
    s = stem
    # Strip all leading [tag] repeatedly
    while True:
        m = re.match(r"^\[[^\]]+\]\s*", s)
        if m:
            s = s[m.end():]
        else:
            break
    return s.strip()

def fix_all_duplicate_prefixes():
    print("==================================================================")
    print("🔍 INVESTIGATING DUPLICATE / REPEATED PREFIXES IN LIBRARY")
    print("==================================================================")
    
    all_files = list(LIB_ROOT.rglob("*.epub")) + list(LIB_ROOT.rglob("*.pdf")) + list(LIB_ROOT.rglob("*.mobi"))
    print(f"📚 Total Files Scanned: {len(all_files):,}\n")
    
    fixed_count = 0
    duplicate_files = []
    
    for f in all_files:
        filename = f.name
        stem = f.stem
        ext = f.suffix
        
        # Check if filename has repeated prefixes like [k] [k] or multiple brackets at start
        bracket_prefixes = re.findall(r"^(\[[^\]]+\](?:\s*\[[^\]]+\])+)\s*", stem)
        if bracket_prefixes:
            canon_prefix = get_canonical_prefix(f)
            clean_name = clean_title_strip_all_prefixes(stem)
            new_stem = f"{canon_prefix} {clean_name}".strip() if canon_prefix else clean_name
            new_filename = f"{new_stem}{ext}"
            
            if new_filename != filename:
                target_path = f.parent / new_filename
                duplicate_files.append((f, target_path, filename, new_filename))
                
    print(f"⚠️ Found {len(duplicate_files):,} files with duplicate/nested prefix errors:\n")
    
    for idx, (src_p, dst_p, old_name, new_name) in enumerate(duplicate_files, 1):
        print(f"[{idx:>3}] 🔄 Renaming:")
        print(f"      Old: {old_name}")
        print(f"      New: {new_name}")
        
        try:
            if dst_p.exists() and dst_p != src_p:
                # If target already exists and is same or larger, remove src
                if dst_p.stat().st_size >= src_p.stat().st_size:
                    src_p.unlink()
                else:
                    src_p.replace(dst_p)
            else:
                src_p.rename(dst_p)
            fixed_count += 1
        except Exception as e:
            print(f"      ❌ Error renaming: {e}")
            
    print("\n==================================================================")
    print(f"🎉 COMPLETED: Successfully investigated and fixed {fixed_count:,} duplicate prefix files!")
    print("==================================================================")

if __name__ == "__main__":
    fix_all_duplicate_prefixes()
