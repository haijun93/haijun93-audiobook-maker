#!/usr/bin/env python3
"""scripts/rollback_and_restore_clean_study_editions.py

Rolls back low-quality dictionary-injected notes and restores authentic, clean editions:
1. Strips out mechanically injected dictionary notes from [study] EPUBs to restore clean, high-quality paired text.
2. Removes pseudo-[e-s] books generated mechanically from untranslated [e] originals.
3. Keeps only genuine AI-translated study editions.
4. Synchronizes the clean restored library state to Google Drive #Books.
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

def clean_study_epub_content(epub_path_str: str) -> tuple[bool, str, int]:
    """Removes mechanically injected study-note spans if they contain dictionary patterns."""
    epub_path = Path(epub_path_str)
    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix="clean_study_"))
        with zipfile.ZipFile(epub_path, "r") as z:
            z.extractall(tmp_dir)
            
        htmls = list(tmp_dir.glob("**/*.xhtml")) + list(tmp_dir.glob("**/*.html")) + list(tmp_dir.glob("**/*.htm"))
        removed_count = 0
        file_modified = False
        
        for h in htmls:
            content = h.read_text(encoding="utf-8", errors="ignore")
            if "class=\"study-note\"" not in content and "class='study-note'" not in content:
                continue
                
            soup = BeautifulSoup(content, "html.parser")
            study_spans = soup.find_all(class_=lambda c: c and "study-note" in c)
            
            h_mod = False
            for s in study_spans:
                s_txt = s.get_text(strip=True)
                # If it is a dictionary injected note (starts with 💡 or 📚 or simple word: def list)
                if "💡" in s_txt or "|" in s_txt or "<b>" in str(s) or "📚" in s_txt:
                    s.decompose()
                    removed_count += 1
                    h_mod = True
                    
            if h_mod:
                h.write_text(str(soup), encoding="utf-8")
                file_modified = True
                
        if file_modified:
            epub_tmp = tmp_dir.parent / f"{epub_path.stem}_restored.epub"
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
            shutil.move(str(epub_tmp), str(epub_path))
            
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return (True, epub_path.name, removed_count)
    except Exception as e:
        return (False, epub_path.name, 0)

def main():
    desktop = Path("/Users/hyeokjunkong/Desktop")
    lib_root = next(p for p in desktop.iterdir() if "소설2" in unicodedata.normalize("NFC", p.name))
    gdrive_root = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")
    
    study_dir = lib_root / "[study]"
    es_dir = lib_root / "[e-s]"
    ke_dir = lib_root / "[k-e]"
    
    print("==================================================================")
    print("🔄 Rolling back dictionary-injected notes & Restoring Clean Library")
    print("==================================================================")
    
    # 1. Clean [study] editions
    study_epubs = list(study_dir.glob("**/*.epub"))
    print(f"\n1. Cleaning {len(study_epubs)} [study] EPUBs (Removing low-quality dictionary notes)...")
    
    tasks = [str(p) for p in study_epubs]
    total_stripped = 0
    with ProcessPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(clean_study_epub_content, t) for t in tasks]
        for fut in as_completed(futures):
            ok, name, cnt = fut.result()
            if ok and cnt > 0:
                total_stripped += cnt
                
    print(f"  ✅ Successfully stripped {total_stripped:,} low-quality dictionary notes from [study] editions!")

    # 2. Re-align [e-s] exactly with [study] authentic books only
    print(f"\n2. Re-aligning [e-s] editions (Removing pseudo-generated books from untranslated [e])...")
    study_book_stems = {p.stem.replace("[study] ", "") for p in study_dir.glob("**/*.epub")}
    
    es_epubs = list(es_dir.glob("**/*.epub"))
    removed_es = 0
    for es_p in es_epubs:
        clean_stem = es_p.stem.replace("[e-s] ", "")
        # If this book does not exist in [study] or [k-e], it was a pseudo-generated unvetted book
        clean_key = re.sub(r'[^a-zA-Z0-9가-힣]', '', clean_stem.lower())
        matched = False
        for st in study_book_stems:
            st_key = re.sub(r'[^a-zA-Z0-9가-힣]', '', st.lower())
            if clean_key and st_key and (clean_key == st_key or clean_key in st_key or st_key in clean_key):
                matched = True
                break
        if not matched:
            es_p.unlink()
            removed_es += 1
            
    print(f"  ✅ Removed {removed_es} pseudo-generated [e-s] files. Remaining clean [e-s]: {len(list(es_dir.glob('**/*.epub')))}")

    # 3. Synchronize cleanly to Google Drive #Books
    print(f"\n3. Synchronizing clean restored editions to Google Drive #Books...")
    for ed in ["[study]", "[e-s]"]:
        src_d = lib_root / ed
        dest_d = gdrive_root / ed
        
        # Remove deleted files from GDrive
        src_stems = {p.relative_to(src_d) for p in src_d.glob("**/*.epub")}
        for gd_p in dest_d.glob("**/*.epub"):
            gd_rel = gd_p.relative_to(dest_d)
            if gd_rel not in src_stems:
                try: gd_p.unlink()
                except: pass
                
        # Copy updated
        for p in src_d.glob("**/*.epub"):
            rel = p.relative_to(src_d)
            gd_f = dest_d / rel
            if not gd_f.exists() or gd_f.stat().st_size != p.stat().st_size or gd_f.stat().st_mtime < p.stat().st_mtime:
                gd_f.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(p), str(gd_f))
                
    print("\n==================================================================")
    print("🎉 Library Rollback & Clean Restoration Completed Successfully!")
    print(f"   • Clean [study] Total: {len(list(study_dir.glob('**/*.epub')))} books")
    print(f"   • Clean [e-s]   Total: {len(list(es_dir.glob('**/*.epub')))} books")
    print("==================================================================")

if __name__ == "__main__":
    main()
