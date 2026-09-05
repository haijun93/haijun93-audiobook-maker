#!/usr/bin/env python3
"""scripts/audit_xteink_directory_integrity.py

Audits all files inside /Users/hyeokjunkong/Desktop/소설2/[xteink]/
Identifies any misplaced editions ([k], [k-e], [e]) or incorrectly named files.
"""

from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
XTEINK_DIR = LIB_ROOT / "[xteink]"

def audit_xteink():
    print(f"Inspecting: {XTEINK_DIR}")
    if not XTEINK_DIR.exists():
        print("❌ [xteink] directory does not exist!")
        return

    subdirs = [p for p in XTEINK_DIR.iterdir() if p.is_dir()]
    print("Top-level subdirectories:", [d.name for d in subdirs])

    all_epubs = list(XTEINK_DIR.rglob("*.epub"))
    print(f"Total EPUBs in [xteink]: {len(all_epubs)}")

    mismatched = []
    by_category = {}

    for f in all_epubs:
        rel = f.relative_to(XTEINK_DIR)
        parts = rel.parts
        top_folder = parts[0] if len(parts) > 1 else ""
        fname = f.name

        # Check if file name matches directory
        if top_folder == "[study]" and not fname.startswith("[study]"):
            mismatched.append((str(rel), f"In '[study]' folder but filename starts with '{fname.split()[0]}'"))
            by_category.setdefault("misnamed_in_study", []).append(str(rel))
        elif top_folder == "[e-s]" and not fname.startswith("[e-s]"):
            mismatched.append((str(rel), f"In '[e-s]' folder but filename starts with '{fname.split()[0]}'"))
            by_category.setdefault("misnamed_in_es", []).append(str(rel))
        elif top_folder not in ["[study]", "[e-s]"]:
            mismatched.append((str(rel), f"Misplaced outside [study]/[e-s] (under '{top_folder}')"))
            by_category.setdefault("outside_standard_dirs", []).append(str(rel))

    print("\n==================================================")
    print(f"🚨 Total Mismatched/Misplaced files in [xteink]: {len(mismatched)}")
    print("==================================================")
    for cat, items in by_category.items():
        print(f"  • {cat}: {len(items)} files")
        for it in items[:10]:
            print(f"       - {it}")

if __name__ == "__main__":
    audit_xteink()
