#!/usr/bin/env python3
"""scripts/build_all_authentic_es_from_pure_study.py

1. Derives 100% authentic [e-s] (English Original + AI Contextual Study Notes) EPUBs
   directly from all verified [study] (New Version) EPUBs across the library.
2. Ensures identical relative paths, metadata, styling, and TOC structure.
3. Automatically names old-version derived files with '[e-s-]' prefix.
4. Synchronizes the whole [e-s] library directly to Google Drive #Books/[e-s].
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

desktop = Path("/Users/hyeokjunkong/Desktop")
lib_root = next(p for p in desktop.iterdir() if "소설2" in unicodedata.normalize("NFC", p.name))
gdrive_root = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

study_dir = lib_root / "[study]"
es_dir = lib_root / "[e-s]"
gdrive_es = gdrive_root / "[e-s]"

ES_CUSTOM_CSS = """
/* English + TOEIC 700+ Study Notes Edition Styling */
@charset "UTF-8";
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.7;
    margin: 1.5em;
    color: #1a1a1a;
    background-color: #fdfdfd;
}
p.pair {
    margin-bottom: 1.2em;
    padding: 0.4em 0;
}
span.en {
    display: block;
    font-size: 1.05em;
    color: #111827;
    font-weight: 500;
    line-height: 1.6;
}
span.study-note {
    display: block;
    margin-top: 0.3em;
    padding: 0.25em 0.6em;
    font-size: 0.88em;
    color: #0369a1;
    background-color: #f0f9ff;
    border-left: 3px solid #0ea5e9;
    border-radius: 2px;
    line-height: 1.45;
}
"""

def derive_es_from_study(study_epub_str: str) -> dict:
    ep = Path(study_epub_str)
    rel_p = ep.relative_to(study_dir)
    
    # Determine target filename and prefix
    is_pure_new = ep.name.startswith("[study]") and not ep.name.startswith("[study-]")
    if is_pure_new:
        target_name = ep.name.replace("[study] ", "[e-s] ").replace("[study]", "[e-s]")
    else:
        target_name = ep.name.replace("[study-] ", "[e-s-] ").replace("[study-]", "[e-s-]")
        
    out_epub = es_dir / rel_p.parent / target_name
    out_epub.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix="make_es_"))
        with zipfile.ZipFile(ep, "r") as z:
            z.extractall(tmp_dir)
            
        # Update CSS if exists or add ES_CUSTOM_CSS
        for css_f in tmp_dir.glob("**/*.css"):
            css_f.write_text(ES_CUSTOM_CSS, encoding="utf-8")
            
        htmls = list(tmp_dir.glob("**/*.xhtml")) + list(tmp_dir.glob("**/*.html"))
        transformed_pairs = 0
        
        for h in htmls:
            content = h.read_text(encoding="utf-8", errors="ignore")
            if "class=\"pair\"" not in content and "<p class=\"pair\"" not in content:
                continue
                
            soup = BeautifulSoup(content, "html.parser")
            h_mod = False
            
            for p in soup.find_all(class_=lambda c: c and "pair" in c):
                ko_span = p.find("span", class_="ko")
                if ko_span:
                    ko_span.decompose() # Remove Korean text in [e-s] edition
                    transformed_pairs += 1
                    h_mod = True
                    
            if h_mod:
                h.write_text(str(soup), encoding="utf-8")
                
        # Package into new e-s epub
        tmp_out = tmp_dir.parent / f"{ep.stem}_derived.epub"
        with zipfile.ZipFile(tmp_out, "w", zipfile.ZIP_DEFLATED) as z_out:
            mime_p = tmp_dir / "mimetype"
            if mime_p.exists():
                z_out.write(mime_p, "mimetype", compress_type=zipfile.ZIP_STORED)
            for root_d, _, files in os.walk(tmp_dir):
                for fn in files:
                    fp = Path(root_d) / fn
                    rel_z = fp.relative_to(tmp_dir)
                    if str(rel_z) == "mimetype": continue
                    z_out.write(fp, str(rel_z))
                    
        shutil.move(str(tmp_out), str(out_epub))
        shutil.rmtree(tmp_dir, ignore_errors=True)
        
        return {
            "ok": True,
            "target": target_name,
            "is_pure": is_pure_new,
            "pairs": transformed_pairs
        }
    except Exception as e:
        return {
            "ok": False,
            "target": target_name,
            "error": str(e)
        }

def main():
    print("==================================================================")
    print("🚀 DERIVING & REPLACING ALL [e-s] EDITIONS FROM AUTHENTIC [study]")
    print("==================================================================")
    
    all_study_epubs = sorted(study_dir.glob("**/*.epub"))
    print(f"Total Study EPUBs to derive [e-s] from: {len(all_study_epubs):,}")
    
    tasks = [str(p) for p in all_study_epubs]
    
    pure_es_count = 0
    dash_es_count = 0
    total_pairs = 0
    
    with ProcessPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(derive_es_from_study, t) for t in tasks]
        for fut in as_completed(futures):
            res = fut.result()
            if res.get("ok"):
                total_pairs += res.get("pairs", 0)
                if res.get("is_pure"):
                    pure_es_count += 1
                else:
                    dash_es_count += 1
            else:
                print(f"  ❌ Error building {res.get('target')}: {res.get('error')}")

    print(f"\nDerived [e-s] Summary:")
    print(f"  • Pure '[e-s]'  (New Version AI Study Notes)    : {pure_es_count:,} books")
    print(f"  • Dash '[e-s-]' (Old Version Static Study Notes) : {dash_es_count:,} books")
    print(f"  • Total Transformed English Paragraphs           : {total_pairs:,} pairs")

    # Clean orphaned old [e-s] that don't match current study relative paths
    study_rel_set = {re.sub(r'^\[study(-\])?', '', p.name).strip() for p in all_study_epubs}
    cleaned_orphans = 0
    for es_f in list(es_dir.glob("**/*.epub")):
        clean_es = re.sub(r'^\[e-s(-\])?', '', es_f.name).strip()
        if clean_es not in study_rel_set:
            try:
                es_f.unlink()
                cleaned_orphans += 1
            except: pass

    # Synchronize 100% to Google Drive #Books/[e-s]
    print("\nSynchronizing clean 1:1 state to Google Drive #Books/[e-s]...")
    for gd_f in gdrive_es.glob("**/*.epub"):
        try: gd_f.unlink()
        except: pass
        
    local_es_all = list(es_dir.glob("**/*.epub"))
    for lp in local_es_all:
        rel = lp.relative_to(es_dir)
        gd_dest = gdrive_es / rel
        gd_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(lp), str(gd_dest))

    print("\n==================================================================")
    print("🎉 FULL [e-s] DERIVATION & GDRIVE SYNCHRONIZATION COMPLETED!")
    print("==================================================================")
    print(f"• Local '[e-s]'   : {len([p for p in es_dir.glob('**/*.epub') if p.name.startswith('[e-s]')]):,}")
    print(f"• Local '[e-s-]'  : {len([p for p in es_dir.glob('**/*.epub') if p.name.startswith('[e-s-]')]):,}")
    print(f"• GDrive '[e-s]'  : {len([p for p in gdrive_es.glob('**/*.epub') if p.name.startswith('[e-s]')]):,}")
    print(f"• GDrive '[e-s-]' : {len([p for p in gdrive_es.glob('**/*.epub') if p.name.startswith('[e-s-]')]):,}")
    print("==================================================================")

if __name__ == "__main__":
    main()
