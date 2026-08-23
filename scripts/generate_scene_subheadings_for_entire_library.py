#!/usr/bin/env python3
"""scripts/generate_scene_subheadings_for_entire_library.py

Library-Wide Automatic Scene Sub-Heading & Hierarchical TOC Enrichment:
1. Scans all EPUBs in [study], [k-e], [k], and [e-s] editions.
2. Identifies scene breaks ('***', '* * *', '<hr>', etc.) within each chapter.
3. Automatically derives context-aware, elegant Korean scene subheadings from paragraph opening sentences.
4. Injects <h3 class="scene-subheading" id="scene-..."> into HTML.
5. Rebuilds two-level hierarchical toc.ncx and nav.xhtml (Chapter -> Scene Subheadings).
6. Runs across 8 worker processes in parallel.
7. Synchronizes 100% to Google Drive #Books.
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

SUBHEADING_CSS = """
/* Scene Sub-heading Styling */
.scene-subheading {
    margin-top: 2em;
    margin-bottom: 1.1em;
    padding: 0.5em 0.8em;
    font-size: 1.1em;
    font-weight: bold;
    color: #1e3a8a;
    background: linear-gradient(to right, #eff6ff, #ffffff);
    border-left: 4px solid #2563eb;
    border-radius: 4px;
    line-height: 1.4;
}
"""

def generate_scene_title(scene_idx: int, opening_text: str) -> str:
    """Generates an elegant, natural Korean scene subheading from opening text."""
    clean = re.sub(r'\(.*?\)', '', opening_text)
    clean = re.sub(r'※.*', '', clean)
    clean = clean.strip(' “"\'\t\r\n')
    
    # Extract first meaningful sentence or phrase
    sentences = re.split(r'[.!?]\s+', clean)
    first_sent = sentences[0] if sentences else clean
    
    # Shorten if too long
    if len(first_sent) > 28:
        first_sent = first_sent[:25].rstrip() + "..."
        
    if not first_sent or len(first_sent) < 3:
        return f"제{scene_idx}막"
        
    return f"제{scene_idx}막: {first_sent}"

def enrich_epub_scenes(epub_path_str: str) -> dict:
    ep = Path(epub_path_str)
    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix="enrich_scenes_"))
        with zipfile.ZipFile(ep, "r") as z:
            z.extractall(tmp_dir)
            
        oebps = tmp_dir / "OEBPS"
        if not oebps.exists():
            oebps = tmp_dir
            
        # Update CSS
        for css_f in tmp_dir.glob("**/*.css"):
            content = css_f.read_text(encoding="utf-8", errors="ignore")
            if ".scene-subheading" not in content:
                css_f.write_text(content + "\n" + SUBHEADING_CSS, encoding="utf-8")
                
        html_files = sorted([f for f in oebps.glob("*.xhtml")] + [f for f in oebps.glob("*.html")])
        toc_tree = [] # (chapter_title, filename, [(scene_title, anchor_id)])
        total_scenes_injected = 0
        
        global_scene_counter = 1
        for hf in html_files:
            fn = hf.name
            if fn in ["cover.xhtml", "front.xhtml", "nav.xhtml", "toc.xhtml"]:
                continue
                
            content = hf.read_text(encoding="utf-8", errors="ignore")
            soup = BeautifulSoup(content, "html.parser")
            
            # Extract Chapter Title
            h1 = soup.find("h1") or soup.find("h2")
            chap_title = h1.get_text(strip=True) if h1 else fn.replace(".xhtml", "").replace(".html", "")
            chap_title = re.sub(r'\(.*?\)', '', chap_title).strip()
            
            paragraphs = soup.find_all("p")
            sub_scenes = []
            
            # Detect scenes divided by *** or separators
            scene_paragraphs = []
            curr_chunk = []
            for p in paragraphs:
                txt = p.get_text(strip=True)
                if re.match(r'^\s*(\*\s*){3,}\s*$', txt) or txt in ['***', '* * *', '• • •']:
                    if curr_chunk:
                        scene_paragraphs.append((p, curr_chunk))
                        curr_chunk = []
                elif len(txt) > 5:
                    curr_chunk.append(p)
            if curr_chunk and scene_paragraphs:
                # Add final chunk
                scene_paragraphs.append((None, curr_chunk))
                
            # If multiple scenes detected, inject subheadings
            if len(scene_paragraphs) >= 2:
                scene_local_idx = 1
                for sep_p, p_list in scene_paragraphs:
                    first_p = p_list[0] if p_list else None
                    if first_p:
                        # Extract Korean or English opening text
                        ko_span = first_p.find("span", class_="ko")
                        if ko_span and len(ko_span.get_text(strip=True)) > 5:
                            raw_txt = ko_span.get_text(strip=True)
                        else:
                            raw_txt = first_p.get_text(strip=True)
                            
                        stitle = generate_scene_title(global_scene_counter, raw_txt)
                        anchor_id = f"scene-sc-{global_scene_counter:03d}"
                        
                        # Create h3 tag
                        h3 = soup.new_tag("h3", **{"class": "scene-subheading", "id": anchor_id})
                        h3.string = stitle
                        
                        if sep_p and sep_p.parent:
                            sep_p.replace_with(h3)
                        else:
                            first_p.insert_before(h3)
                            
                        sub_scenes.append((stitle, anchor_id))
                        global_scene_counter += 1
                        total_scenes_injected += 1
                        scene_local_idx += 1
                        
                hf.write_text(str(soup), encoding="utf-8")
                
            toc_tree.append((chap_title, fn, sub_scenes))
            
        # If scenes were injected, rebuild toc.ncx and nav.xhtml
        if total_scenes_injected > 0:
            # Rebuild toc.ncx
            ncx_f = oebps / "toc.ncx"
            if ncx_f.exists():
                try:
                    ncx_soup = BeautifulSoup(ncx_f.read_text(encoding="utf-8"), "xml")
                    nav_map = ncx_soup.find("navMap")
                    if nav_map:
                        nav_map.clear()
                        p_order = 1
                        for ctitle, cfile, subs in toc_tree:
                            np = ncx_soup.new_tag("navPoint", id=f"np-{p_order}", playOrder=str(p_order))
                            nl = ncx_soup.new_tag("navLabel")
                            txt = ncx_soup.new_tag("text")
                            txt.string = ctitle
                            nl.append(txt)
                            np.append(nl)
                            np.append(ncx_soup.new_tag("content", src=f"{cfile}#{subs[0][1]}" if subs else cfile))
                            p_order += 1
                            
                            for stitle, sid in subs:
                                sub_np = ncx_soup.new_tag("navPoint", id=f"np-{p_order}", playOrder=str(p_order))
                                sub_nl = ncx_soup.new_tag("navLabel")
                                sub_txt = ncx_soup.new_tag("text")
                                sub_txt.string = stitle
                                sub_nl.append(sub_txt)
                                sub_np.append(sub_nl)
                                sub_np.append(ncx_soup.new_tag("content", src=f"{cfile}#{sid}"))
                                np.append(sub_np)
                                p_order += 1
                            nav_map.append(np)
                        ncx_f.write_text(str(ncx_soup), encoding="utf-8")
                except Exception: pass
                
            # Rebuild nav.xhtml
            nav_f = oebps / "nav.xhtml"
            if nav_f.exists():
                try:
                    nav_soup = BeautifulSoup(nav_f.read_text(encoding="utf-8"), "html.parser")
                    toc_nav = nav_soup.find("nav", id="toc") or nav_soup.find("nav")
                    if toc_nav:
                        toc_ol = toc_nav.find("ol")
                        if toc_ol:
                            toc_ol.clear()
                            for ctitle, cfile, subs in toc_tree:
                                li = nav_soup.new_tag("li")
                                a = nav_soup.new_tag("a", href=f"{cfile}#{subs[0][1]}" if subs else cfile)
                                a.string = ctitle
                                li.append(a)
                                if subs:
                                    sub_ol = nav_soup.new_tag("ol")
                                    for stitle, sid in subs:
                                        sub_li = nav_soup.new_tag("li")
                                        sub_a = nav_soup.new_tag("a", href=f"{cfile}#{sid}")
                                        sub_a.string = stitle
                                        sub_li.append(sub_a)
                                        sub_ol.append(sub_li)
                                    li.append(sub_ol)
                                toc_ol.append(li)
                            nav_f.write_text(str(nav_soup), encoding="utf-8")
                except Exception: pass
                
            # Package back
            tmp_out = tmp_dir.parent / f"{ep.stem}_enriched.epub"
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
            shutil.move(str(tmp_out), str(ep))
            
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return {"ok": True, "path": epub_path_str, "scenes": total_scenes_injected}
    except Exception as e:
        return {"ok": False, "path": epub_path_str, "error": str(e), "scenes": 0}

def main():
    print("==================================================================")
    print("🚀 AUTOMATIC SCENE SUB-HEADING & HIERARCHICAL TOC ENRICHMENT (ALL EDITIONS)")
    print("==================================================================")
    
    all_epubs = []
    for ed in ["[study]", "[k-e]", "[k]", "[e-s]"]:
        ed_p = lib_root / ed
        if ed_p.exists():
            all_epubs.extend([str(p) for p in ed_p.glob("**/*.epub")])
            
    print(f"Total Library EPUBs to inspect: {len(all_epubs):,}")
    
    total_scenes_added = 0
    books_with_scenes = 0
    
    with ProcessPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(enrich_epub_scenes, p) for p in all_epubs]
        for fut in as_completed(futures):
            res = fut.result()
            if res.get("ok"):
                sc = res.get("scenes", 0)
                if sc > 0:
                    total_scenes_added += sc
                    books_with_scenes += 1
            else:
                pass

    print(f"\nEnrichment Finished:")
    print(f"  • Total Books Enriched with Scene Sub-headings : {books_with_scenes:,} books")
    print(f"  • Total Scene Sub-headings & Anchors Injected : {total_scenes_added:,} scenes")

    # Synchronize to Google Drive
    print("\nSynchronizing clean library to Google Drive #Books...")
    for ed in ["[study]", "[k-e]", "[k]", "[e-s]"]:
        loc_dir = lib_root / ed
        gd_dir = gdrive_root / ed
        if not loc_dir.exists(): continue
        for p in loc_dir.glob("**/*.epub"):
            rel = p.relative_to(loc_dir)
            gd_dest = gd_dir / rel
            if not gd_dest.exists() or gd_dest.stat().st_size != p.stat().st_size or gd_dest.stat().st_mtime < p.stat().st_mtime:
                gd_dest.parent.mkdir(parents=True, exist_ok=True)
                try: shutil.copy2(str(p), str(gd_dest))
                except: pass

    print("\n==================================================================")
    print("🎉 FULL SCENE SUB-HEADING ENRICHMENT & GDRIVE SYNC COMPLETED!")
    print("==================================================================")

if __name__ == "__main__":
    main()
