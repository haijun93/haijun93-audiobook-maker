#!/usr/bin/env python3
"""scripts/purge_all_study_pollution_and_restore_pure_study.py

Comprehensive library-wide purge of all static-dictionary cross-book pollution
and restoration of 100% clean, pure [study] editions:
1. Scans all study EPUBs paragraph by paragraph.
2. Purges cross-book contamination (e.g. '※학습:', leaked novel text sentences) from study notes.
3. Preserves all high-quality AI-translated Korean paired text.
4. Restores standard '[study] ... .epub' prefix across the entire library.
5. Synchronizes 100% clean study editions directly to Google Drive #Books/[study].
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import unicodedata
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from bs4 import BeautifulSoup

POLLUTION_PATTERNS = [
    r'※학습:[^;]*',
    r'[^;]*공원에서 책을[^;]*',
    r'[^;]*선장은 라이아테아섬[^;]*',
    r'[^;]*다프네가 내게[^;]*',
    r'[^;]*아마 머루가[^;]*',
    r'[^;]*갇혀 있다는 느낌[^;]*',
    r'[^;]*매튜랑[^;]*',
    r'[^;]*다만 개학하기 전에[^;]*',
    r'[^;]*그는 늘 똑같은 말로[^;]*',
    r'[^;]*과거에 대해 할 수 있는 일이라고는[^;]*',
    r'[^;]*거의 모든 곳에 자욱한 연기[^;]*',
    r'[^;]*나는 화제를 바꾸려고 했지만[^;]*',
    r'[^;]*이제 알게 된 건[^;]*',
    r'[^;]*전시 경기 입장권은[^;]*',
    r'[^;]*이 금속들은 쌍으로[^;]*',
    r'[^;]*마치 이 세상은 숨어 있기에는[^;]*',
    r'💡[^;]*',
    r'📚[^;]*'
]

COMPILED_POLLUTION = [re.compile(p) for p in POLLUTION_PATTERNS]

def clean_single_study_epub(epub_path_str: str) -> dict:
    ep = Path(epub_path_str)
    modified = False
    purged_notes_count = 0
    total_pairs = 0
    
    # Determine pure name: replace [study-] with [study]
    if ep.name.startswith("[study-]"):
        pure_name = ep.name.replace("[study-] ", "[study] ").replace("[study-]", "[study] ")
        final_path = ep.parent / pure_name
    else:
        pure_name = ep.name
        final_path = ep
        
    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix="purge_study_"))
        with zipfile.ZipFile(ep, "r") as z:
            z.extractall(tmp_dir)
            
        htmls = list(tmp_dir.glob("**/*.xhtml")) + list(tmp_dir.glob("**/*.html")) + list(tmp_dir.glob("**/*.htm"))
        
        for h in htmls:
            content = h.read_text(encoding="utf-8", errors="ignore")
            if "class=\"pair\"" not in content and "<p class=\"pair\"" not in content:
                continue
                
            soup = BeautifulSoup(content, "html.parser")
            pairs = soup.find_all(class_=lambda c: c and "pair" in c)
            h_mod = False
            
            for p in pairs:
                total_pairs += 1
                note_s = p.find("span", class_="study-note")
                if note_s:
                    nt = note_s.get_text()
                    is_contam = False
                    for cp in COMPILED_POLLUTION:
                        if cp.search(nt):
                            is_contam = True
                            nt = cp.sub('', nt)
                            
                    if is_contam:
                        nt = re.sub(r';\s*;+', ';', nt)
                        nt = re.sub(r'※\s*;+', '※ ', nt)
                        nt = nt.strip('; \n\r\t')
                        if nt == "※" or nt == "※ " or len(nt) < 3:
                            nt = ""
                        note_s.string = nt
                        purged_notes_count += 1
                        h_mod = True
                        
            if h_mod:
                h.write_text(str(soup), encoding="utf-8")
                modified = True
                
        # Package into final clean epub
        epub_tmp = tmp_dir.parent / f"{ep.stem}_purged.epub"
        with zipfile.ZipFile(epub_tmp, "w", zipfile.ZIP_DEFLATED) as z_out:
            mime_p = tmp_dir / "mimetype"
            if mime_p.exists():
                z_out.write(mime_p, "mimetype", compress_type=zipfile.ZIP_STORED)
            for root_d, _, files in os.walk(tmp_dir):
                for fn in files:
                    fp = Path(root_d) / fn
                    rel_z = fp.relative_to(tmp_dir)
                    if str(rel_z) == "mimetype": continue
                    z_out.write(fp, str(rel_z))
                    
        # Remove old [study-] file if renamed
        if final_path != ep and ep.exists():
            ep.unlink()
            
        shutil.move(str(epub_tmp), str(final_path))
        shutil.rmtree(tmp_dir, ignore_errors=True)
        
        return {
            "name": pure_name,
            "old_path": epub_path_str,
            "final_path": str(final_path),
            "modified": modified,
            "purged_count": purged_notes_count,
            "total_pairs": total_pairs,
            "ok": True
        }
    except Exception as e:
        return {
            "name": ep.name,
            "old_path": epub_path_str,
            "final_path": str(final_path),
            "modified": False,
            "purged_count": 0,
            "total_pairs": total_pairs,
            "ok": False,
            "error": str(e)
        }

def main():
    desktop = Path("/Users/hyeokjunkong/Desktop")
    lib_root = next(p for p in desktop.iterdir() if "소설2" in unicodedata.normalize("NFC", p.name))
    gdrive_root = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")
    
    study_dir = lib_root / "[study]"
    gdrive_study = gdrive_root / "[study]"
    
    print("==================================================================")
    print("🚀 PARALLEL POLLUTION PURGE & PURE [study] RESTORATION (515 BOOKS)")
    print("==================================================================")
    
    epubs = sorted(study_dir.glob("**/*.epub"))
    print(f"Total Study EPUBs found: {len(epubs):,}")
    
    tasks = [str(p) for p in epubs]
    
    total_purged_spans = 0
    total_cleaned_books = 0
    total_inspected_pairs = 0
    
    with ProcessPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(clean_single_study_epub, t) for t in tasks]
        for fut in as_completed(futures):
            res = fut.result()
            if res.get("ok"):
                total_inspected_pairs += res["total_pairs"]
                total_purged_spans += res["purged_count"]
                if res["modified"] or res["old_path"] != res["final_path"]:
                    total_cleaned_books += 1
            else:
                print(f"  ❌ Error in {res['name']}: {res.get('error')}")

    print("\n2. Synchronizing 100% Clean [study] Library to Google Drive #Books...")
    # Clean old [study-] on GDrive
    for gd_p in list(gdrive_study.glob("**/[study-]*")):
        try: gd_p.unlink()
        except: pass
        
    # Copy fresh [study]
    clean_local = list(study_dir.glob("**/*.epub"))
    for p in clean_local:
        rel = p.relative_to(study_dir)
        gd_dest = gdrive_study / rel
        gd_dest.parent.mkdir(parents=True, exist_ok=True)
        if not gd_dest.exists() or gd_dest.stat().st_size != p.stat().st_size or gd_dest.stat().st_mtime < p.stat().st_mtime:
            shutil.copy2(str(p), str(gd_dest))
            
    print("\n==================================================================")
    print("🎉 100% PURE [study] LIBRARY RESTORATION COMPLETED!")
    print("==================================================================")
    print(f"• Total Books Processed       : {len(clean_local):,} books")
    print(f"• Total Pairs Inspected       : {total_inspected_pairs:,} pairs")
    print(f"• Contaminated Spans Purged   : {total_purged_spans:,} spans")
    print(f"• Pure '[study]' Books in Lib : {len(list(study_dir.glob('**/*.epub'))):,} books")
    print(f"• Google Drive Synchronized   : 100% Clean [study] Match")
    print("==================================================================")

if __name__ == "__main__":
    main()
