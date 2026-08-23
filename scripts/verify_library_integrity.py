#!/usr/bin/env python3
"""scripts/verify_library_integrity.py

Fast parallel validator for all 2,271 EPUBs in the library:
1. Validates 100% of NCX content src references against real XHTML element IDs.
2. Checks that zero duplicate/consecutive h3 scene-subheading tags exist.
3. Reports comprehensive health metrics across [k], [k-e], [study], [e-s].
"""

from __future__ import annotations

import unicodedata
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from bs4 import BeautifulSoup

desktop = Path("/Users/hyeokjunkong/Desktop")
lib_root = next(p for p in desktop.iterdir() if "소설2" in unicodedata.normalize("NFC", p.name))


def verify_single_epub(epub_path: Path) -> tuple[str, bool, int, int]:
    if not epub_path.exists() or epub_path.name.startswith("._"):
        return epub_path.name, True, 0, 0
        
    try:
        with zipfile.ZipFile(epub_path) as z:
            file_ids_map = {}
            for name in z.namelist():
                base_name = name.split("/")[-1]
                if name.endswith((".xhtml", ".html")):
                    soup = BeautifulSoup(z.read(name), "html.parser")
                    file_ids_map[base_name] = {tag["id"] for tag in soup.find_all(id=True)}
                    
            broken = 0
            ncx_files = [n for n in z.namelist() if n.endswith(".ncx")]
            if ncx_files:
                sncx = BeautifulSoup(z.read(ncx_files[0]), "xml")
                for c in sncx.find_all("content"):
                    src = c.get("src", "")
                    if not src:
                        continue
                    base_src = src.split("/")[-1]
                    if "#" in base_src:
                        fname, anchor = base_src.split("#", 1)
                        if fname not in file_ids_map or anchor not in file_ids_map[fname]:
                            broken += 1
                    else:
                        if base_src not in file_ids_map:
                            broken += 1
                            
            dup_h3 = 0
            scene_count = 0
            for name in z.namelist():
                if name.endswith((".xhtml", ".html")) and "nav" not in name and "cover" not in name:
                    soup = BeautifulSoup(z.read(name), "html.parser")
                    h3s = soup.find_all("h3", class_="scene-subheading")
                    scene_count += len(h3s)
                    prev_is_h3 = False
                    for tag in soup.find_all(["h1", "h2", "h3", "p"]):
                        is_h3 = (tag.name == "h3" and "scene-subheading" in tag.get("class", []))
                        if is_h3 and prev_is_h3:
                            dup_h3 += 1
                        prev_is_h3 = is_h3
                        
            is_perfect = (broken == 0 and dup_h3 == 0)
            return epub_path.name, is_perfect, scene_count, broken
    except Exception:
        return epub_path.name, False, 0, 1


def main():
    print("==================================================================")
    print("🌟 4-EDITION LIBRARY SCENE SUBHEADING & TOC INTEGRITY AUDIT")
    print("==================================================================")
    
    grand_total_books = 0
    grand_total_perfect = 0
    grand_total_scenes = 0
    
    for ed in ["[k]", "[k-e]", "[study]", "[e-s]"]:
        epubs = [p for p in (lib_root / ed).rglob("*.epub") if not p.name.startswith("._")]
        with ProcessPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(verify_single_epub, epubs))
            
        perfect_count = sum(1 for _, ok, _, _ in results if ok)
        total_scenes = sum(sc for _, _, sc, _ in results)
        broken_total = sum(br for _, _, _, br in results)
        
        grand_total_books += len(epubs)
        grand_total_perfect += perfect_count
        grand_total_scenes += total_scenes
        
        print(f"📊 [{ed:7}] Total Books: {len(epubs):4} | ✅ 100% PERFECT: {perfect_count:4} | Broken: {len(epubs)-perfect_count:2} | Total Scenes: {total_scenes:6,}")
        
    print("==================================================================")
    print(f"🏆 GRAND TOTAL: {grand_total_books:,} Books | 100% PERFECT: {grand_total_perfect:,} ({grand_total_perfect/grand_total_books*100:.1f}%)")
    print(f"✨ Total Active Verified Scenes: {grand_total_scenes:,}")
    print("==================================================================")


if __name__ == "__main__":
    main()
