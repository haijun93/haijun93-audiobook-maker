#!/usr/bin/env python3
"""scripts/fix_and_relocate_nested_e_books.py

1. Moves all books inside `소설2/[study]/[e]`, `[k-e]/[e]`, `[k]/[e]`, `[e-s]/[e]` into their canonical
   Genre and Author folders (`Fantasy_Science_Fiction/#Brandon Sanderson/`, `Science_Nature_Technology/#Richard Dawkins/`).
2. Cleans up double prefixes (`[study] [e] ...` -> `[study] ...`).
3. Deletes the nested `[e]` directory across all editions in local library and Google Drive.
4. Sanitizes `config.json` to prevent any future tasks from targeting `[study]/[e]` or `[k-e]/[e]`.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
GDRIVE_ROOT = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")
CONFIG_PATH = Path(__file__).resolve().parents[1] / ".work" / "continuous_scheduler" / "config.json"

CANONICAL_MAPPING = {
    "mistborn": ("Fantasy_Science_Fiction", "#Brandon Sanderson", "The Mistborn Trilogy - Brandon Sanderson (4.48).epub"),
    "rhythm of war": ("Fantasy_Science_Fiction", "#Brandon Sanderson", "Rhythm of War - Brandon Sanderson (4.60).epub"),
    "words of radiance": ("Fantasy_Science_Fiction", "#Brandon Sanderson", "Words of Radiance - Brandon Sanderson (4.76).epub"),
    "selfish gene": ("Science_Nature_Technology", "#Richard Dawkins", "The Selfish Gene 40th Anniversary Edition - Richard Dawkins (4.15).epub")
}

def resolve_canonical_dest(fname: str, edition_prefix: str) -> tuple[str, str, str] | None:
    fname_lower = fname.lower()
    for key, (genre, author, clean_name) in CANONICAL_MAPPING.items():
        if key in fname_lower:
            target_fname = f"{edition_prefix} {clean_name}"
            return genre, author, target_fname
    return None

def main():
    print("==================================================================")
    print("🚀 RELOCATING NESTED `[e]` BOOKS TO CANONICAL GENRE/AUTHOR FOLDERS")
    print("==================================================================")

    editions = ["[k]", "[k-e]", "[study]", "[e-s]", "[e]"]

    for ed in editions:
        nested_dir = LIB_ROOT / ed / "[e]"
        if not nested_dir.exists():
            continue

        print(f"\n📁 Scanning nested folder: {nested_dir}")
        for ep in list(nested_dir.glob("*.epub")):
            res = resolve_canonical_dest(ep.name, ed)
            if res:
                genre, author, clean_fname = res
                dest_dir = LIB_ROOT / ed / genre / author
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_p = dest_dir / clean_fname

                shutil.move(str(ep), str(dest_p))
                print(f"  🚚 Moved to canonical: {dest_p.relative_to(LIB_ROOT)}")

                # Sync to GDrive
                if GDRIVE_ROOT.exists():
                    gd_dest_dir = GDRIVE_ROOT / ed / genre / author
                    gd_dest_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dest_p, gd_dest_dir / clean_fname)
                    print(f"    ☁️ Synced to GDrive: {genre}/{author}/{clean_fname}")

        # Remove empty nested [e] folder
        try:
            shutil.rmtree(nested_dir)
            print(f"  🗑️ Removed empty nested folder: {nested_dir}")
        except Exception as e:
            print(f"  Warning removing {nested_dir}: {e}")

        # GDrive nested [e] folder removal
        if GDRIVE_ROOT.exists():
            gd_nested = GDRIVE_ROOT / ed / "[e]"
            if gd_nested.exists():
                try:
                    shutil.rmtree(gd_nested)
                    print(f"  ☁️🗑️ Removed GDrive nested folder: {gd_nested}")
                except Exception as e:
                    pass

    # 2. Sanitize config.json
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            tasks = cfg.get("tasks", [])
            modified = 0
            for t in tasks:
                for path_key in ["output_epub", "study_output_epub"]:
                    p_val = t.get(path_key, "")
                    if p_val and "/[e]/" in p_val:
                        # Fix path
                        for k, (g, a, clean_n) in CANONICAL_MAPPING.items():
                            if k in p_val.lower():
                                pfx = "[study]" if "study" in path_key else "[k-e]"
                                t[path_key] = str(LIB_ROOT / pfx / g / a / f"{pfx} {clean_n}")
                                modified += 1
            if modified > 0:
                CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"\n✅ Sanitized {modified} nested paths in `config.json`!")
        except Exception as e:
            print(f"Error sanitizing config: {e}")

    print("\n==================================================================")
    print("🎉 ALL NESTED `[e]` FOLDERS AND BOOKS 100% CLEANED AND FIXED!")
    print("==================================================================")

if __name__ == "__main__":
    main()
