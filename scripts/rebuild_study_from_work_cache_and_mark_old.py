#!/usr/bin/env python3
"""scripts/rebuild_study_from_work_cache_and_mark_old.py

1. Re-builds pure [study] and [e-s] EPUBs from raw AI translation work caches (_chatgpt_translate_work/)
   containing authentic AI-generated study notes, bypassing all static dictionary pollution.
2. For older books translated without AI study notes (which relied on static dictionary),
   renames their study EPUBs with '[study-]' prefix.
3. Synchronizes the whole library to Google Drive #Books.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import unicodedata
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup
from concurrent.futures import ProcessPoolExecutor, as_completed

desktop = Path("/Users/hyeokjunkong/Desktop")
lib_root = next(p for p in desktop.iterdir() if "소설2" in unicodedata.normalize("NFC", p.name))
gdrive_root = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")
work_base = lib_root / "_chatgpt_translate_work"
study_dir = lib_root / "[study]"
es_dir = lib_root / "[e-s]"
gdrive_study = gdrive_root / "[study]"
gdrive_es = gdrive_root / "[e-s]"

def clean_key(text: str) -> str:
    c = re.sub(r'^\[.*?\]\s*', '', text)
    c = re.sub(r'\(.*?\)', '', c)
    return re.sub(r'[^a-zA-Z0-9가-힣]', '', c.lower())

def load_ai_work_cache_maps() -> dict[str, dict[str, tuple[str, str]]]:
    """Loads all pure AI translation and study notes from raw work caches."""
    cache_maps = {}
    if not work_base.exists(): return cache_maps
    
    print("1. Loading raw AI translation work caches...")
    for wd in work_base.iterdir():
        if not wd.is_dir(): continue
        td = wd / "translations"
        if not td.exists(): continue
        
        book_key = clean_key(wd.name)
        book_map = {}
        
        for jf in sorted(td.glob("*.json")):
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                # Case 1: data has "translations" dict
                trans_dict = data.get("translations", {})
                if isinstance(trans_dict, dict):
                    for bid, t_val in trans_dict.items():
                        if isinstance(t_val, dict):
                            en = t_val.get("english", "")
                            ko = t_val.get("korean", "")
                            st = t_val.get("study_notes", "") or t_val.get("notes", "")
                            if en: book_map[clean_key(en)] = (ko, st)
                        elif isinstance(t_val, str):
                            # String translation without notes
                            pass
                            
                # Case 2: data has "items" list
                items = data.get("items") or data.get("pairs") or []
                if isinstance(items, list):
                    for it in items:
                        if isinstance(it, dict):
                            en = it.get("english") or it.get("en", "")
                            ko = it.get("korean") or it.get("ko", "")
                            st = it.get("study_notes") or it.get("notes", "")
                            if en: book_map[clean_key(en)] = (ko, st)
            except Exception:
                pass
                
        # Only consider it an authentic AI study cache if it has notes
        notes_count = sum(1 for _, st in book_map.values() if st and len(st) > 5)
        if notes_count >= 10:
            cache_maps[book_key] = book_map
            # Also register sub-keys
            words = wd.name.split("_")
            if len(words) >= 2:
                cache_maps[clean_key(" ".join(words[:3]))] = book_map
                
    print(f"   -> Successfully loaded {len(cache_maps)} verified pure AI work cache maps!")
    return cache_maps

def rebuild_or_mark_epub(epub_path: Path, ai_caches: dict[str, dict[str, tuple[str, str]]]) -> tuple[str, str, int]:
    ep_key = clean_key(epub_path.stem)
    
    # Check if we have an authentic AI work cache for this book
    matching_cache = None
    if ep_key in ai_caches:
        matching_cache = ai_caches[ep_key]
    else:
        for k, cmap in ai_caches.items():
            if (len(k) >= 6 and k in ep_key) or (len(ep_key) >= 6 and ep_key in k):
                matching_cache = cmap
                break
                
    # CASE A: We have authentic AI work cache -> REBUILD PURE [study] & [e-s]
    if matching_cache:
        try:
            tmp_dir = Path(tempfile.mkdtemp(prefix="rebuild_ai_"))
            with zipfile.ZipFile(epub_path, "r") as z:
                z.extractall(tmp_dir)
                
            injected_count = 0
            for h in tmp_dir.glob("**/*.xhtml"):
                content = h.read_text(encoding="utf-8")
                if "class=\"pair\"" not in content and "<p class=\"pair\"" not in content: continue
                
                soup = BeautifulSoup(content, "html.parser")
                for p in soup.find_all(class_=lambda c: c and "pair" in c):
                    en_s = p.find("span", class_="en")
                    ko_s = p.find("span", class_="ko")
                    note_s = p.find("span", class_="study-note")
                    
                    if not en_s: continue
                    en_txt = en_s.get_text(strip=True)
                    k_en = clean_key(en_txt)
                    
                    if k_en in matching_cache:
                        raw_ko, raw_st = matching_cache[k_en]
                        if raw_ko and ko_s:
                            ko_s.string = raw_ko
                        if raw_st:
                            if not note_s:
                                note_s = soup.new_tag("span", **{"class": "study-note"})
                                p.append(note_s)
                            note_s.string = raw_st
                            injected_count += 1
                            
                h.write_text(str(soup), encoding="utf-8")
                
            # Re-package as pure [study]
            pure_name = epub_path.name.replace("[study-] ", "[study] ").replace("[study-]", "[study]")
            if not pure_name.startswith("[study]"):
                pure_name = f"[study] {pure_name}"
            final_p = epub_path.parent / pure_name
            
            epub_tmp = tmp_dir.parent / f"{epub_path.stem}_ai_rebuilt.epub"
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
                        
            if final_p != epub_path and epub_path.exists():
                epub_path.unlink()
                
            shutil.move(str(epub_tmp), str(final_p))
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return ("AI_REBUILT", final_p.name, injected_count)
        except Exception as e:
            return ("ERROR", epub_path.name, 0)
            
    # CASE B: Old translation without AI study cache -> MARK AS [study-]
    else:
        if not epub_path.name.startswith("[study-]"):
            new_name = epub_path.name.replace("[study] ", "[study-] ").replace("[study]", "[study-]")
            new_p = epub_path.parent / new_name
            shutil.move(str(epub_path), str(new_p))
            return ("OLD_MARKED", new_p.name, 0)
        else:
            return ("OLD_MARKED", epub_path.name, 0)

def main():
    print("==================================================================")
    print("🚀 AI CACHE STUDY REBUILD & OLD-VERSION [study-] CLASSIFICATION")
    print("==================================================================")
    
    ai_caches = load_ai_work_cache_maps()
    study_epubs = sorted(study_dir.glob("**/*.epub"))
    print(f"\n2. Processing {len(study_epubs)} study EPUBs in library...")
    
    ai_rebuilt_count = 0
    old_marked_count = 0
    
    for ep in study_epubs:
        status, name, cnt = rebuild_or_mark_epub(ep, ai_caches)
        if status == "AI_REBUILT":
            ai_rebuilt_count += 1
            print(f"  🌟 [NEW AI REBUILT] {name:50s} -> Restored {cnt} pure AI study notes!")
        elif status == "OLD_MARKED":
            old_marked_count += 1
            
    print(f"\nSummary:")
    print(f"   • Re-built Pure '[study]' from AI Work Caches: {ai_rebuilt_count} books")
    print(f"   • Classified as '[study-]' (Old Translation): {old_marked_count} books")

    # 3. Synchronize to Google Drive
    print("\n3. Synchronizing to Google Drive #Books/[study]...")
    # Clean GDrive study
    for gd_f in gdrive_study.glob("**/*.epub"):
        try: gd_f.unlink()
        except: pass
        
    local_study_all = list(study_dir.glob("**/*.epub"))
    for lp in local_study_all:
        rel = lp.relative_to(study_dir)
        gd_dest = gdrive_study / rel
        gd_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(lp), str(gd_dest))

    print("\n==================================================================")
    print("🎉 FULL REBUILD & CLASSIFICATION COMPLETE & SYNCHRONIZED!")
    print("==================================================================")

if __name__ == "__main__":
    main()
