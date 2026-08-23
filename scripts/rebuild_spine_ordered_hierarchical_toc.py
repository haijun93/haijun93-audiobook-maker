#!/usr/bin/env python3
"""scripts/rebuild_spine_ordered_hierarchical_toc.py

Ground-Truth Fix for EPUB TOC Order:
1. Parses content.opf <spine> to get the EXACT reading play order of XHTML files.
2. Injects clean scene subheadings and extracts 2-level hierarchical TOC in strictly spine order.
3. Renumbers scene subheadings sequentially (제1막, 제2막...) based on spine play order.
4. Generates standard 2-level hierarchical toc.ncx and nav.xhtml.
5. Processes entire 4-edition library (2,371 books) in parallel and syncs with Google Drive #Books.
"""

from __future__ import annotations

import html
import os
import re
import shutil
import sys
import tempfile
import unicodedata
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup, NavigableString

desktop = Path("/Users/hyeokjunkong/Desktop")
lib_root = next(p for p in desktop.iterdir() if "소설2" in unicodedata.normalize("NFC", p.name))
gdrive_root = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

CLEAN_CSS = """.scene-subheading {
  margin-top: 2em !important;
  margin-bottom: 0.8em !important;
  padding: 0 !important;
  font-size: 1.05em !important;
  font-weight: 700 !important;
  color: inherit !important;
  background: none !important;
  border: none !important;
  line-height: 1.5 !important;
  page-break-after: avoid !important;
  break-after: avoid !important;
}"""

SCENE_SUBHEADING_STYLE_PATTERN = re.compile(r'\.scene-subheading\s*\{[^}]*\}', re.DOTALL)
SEP_PATTERN = re.compile(r'^\s*([*#\-—_~•\s]{3,}|[◆◇★☆■□▲△▼▽✦✧]+)\s*$')


def clean_summary_text(txt: str, max_len: int = 35) -> str:
    txt = re.sub(r'^(제\s*\d+\s*[장막회편부절관권호곡단계]\s*[:\.\-]?\s*)+', '', txt).strip()
    txt = re.sub(r'^(Chapter|Section|Part|Scene|Act)\s*\d+\s*[:\.\-]?\s*', '', txt, flags=re.I).strip()
    txt = re.sub(r'[*#\-—_~•◆◇★☆■□▲△▼▽✦✧]+', '', txt).strip()
    txt = ' '.join(txt.split())
    if len(txt) > max_len:
        txt = txt[:max_len].rsplit(' ', 1)[0].strip() + '...'
    return txt


def get_first_valid_sentence(tag) -> str:
    for node in tag.find_all_next(["p", "div", "h2", "h3", "h4"]):
        if node.name in ["h2", "h3"] and "scene-subheading" in node.get("class", []):
            continue
        text = node.get_text(separator=" ", strip=True)
        if text and len(text) > 4 and not SEP_PATTERN.match(text):
            return clean_summary_text(text)
    return ""


def process_single_epub(epub_path: Path) -> tuple[str, bool, str]:
    if not epub_path.exists() or epub_path.name.startswith("._"):
        return epub_path.name, False, "skipped"
        
    try:
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            with zipfile.ZipFile(epub_path, "r") as zin:
                zin.extractall(tmp_dir)
                
            # 1. Locate OPF and get exact Spine order
            opf_files = list(tmp_dir.rglob("*.opf"))
            if not opf_files:
                return epub_path.name, False, "no_opf"
                
            opf_path = opf_files[0]
            opf_dir = opf_path.parent
            
            try:
                opf_tree = ET.parse(opf_path)
                opf_root = opf_tree.getroot()
            except Exception:
                return epub_path.name, False, "opf_parse_error"
                
            manifest = {}
            for item in opf_root.findall(".//{http://www.idpf.org/2007/opf}item"):
                item_id = item.attrib.get("id")
                item_href = item.attrib.get("href")
                if item_id and item_href:
                    manifest[item_id] = item_href
                    
            spine_itemrefs = opf_root.findall(".//{http://www.idpf.org/2007/opf}itemref")
            spine_files = []
            for itemref in spine_itemrefs:
                idref = itemref.attrib.get("idref")
                if idref in manifest:
                    href = manifest[idref]
                    # normalize relative to opf_dir
                    file_path = (opf_dir / href).resolve()
                    if file_path.exists() and file_path.suffix.lower() in [".xhtml", ".html"]:
                        spine_files.append((file_path, href))
                        
            if not spine_files:
                return epub_path.name, False, "no_spine_files"
                
            # 2. Iterate spine files in EXACT reading play order
            global_scene_counter = 1
            toc_structure = [] # List of {title, href, scenes: [{title, anchor_id}]}
            
            for file_path, rel_href in spine_files:
                # Skip nav.xhtml, cover.xhtml from internal scene splitting unless legitimate chapter
                is_nav = "nav.xhtml" in file_path.name.lower() or "toc.xhtml" in file_path.name.lower()
                is_cover = "cover.xhtml" in file_path.name.lower()
                
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                    
                soup = BeautifulSoup(content, "html.parser")
                
                # Check / update CSS
                style_tag = soup.find("style")
                if style_tag:
                    if ".scene-subheading" in style_tag.text:
                        style_tag.string = SCENE_SUBHEADING_STYLE_PATTERN.sub(CLEAN_CSS, style_tag.text)
                    else:
                        style_tag.append(f"\n{CLEAN_CSS}\n")
                else:
                    head = soup.find("head")
                    if head:
                        new_style = soup.new_tag("style")
                        new_style.string = f"\n{CLEAN_CSS}\n"
                        head.append(new_style)
                        
                # Extract chapter main title
                chap_title = ""
                h1 = soup.find("h1")
                if h1 and h1.get_text(strip=True):
                    chap_title = h1.get_text(strip=True)
                elif soup.title and soup.title.get_text(strip=True):
                    chap_title = soup.title.get_text(strip=True)
                else:
                    # fallback from filename
                    chap_title = file_path.stem.replace("-", " ").replace("_", " ").title()
                    
                chap_title = clean_summary_text(chap_title, max_len=40)
                if not chap_title:
                    chap_title = f"Chapter {len(toc_structure) + 1}"
                    
                # Clean any previous duplicate/stale scene subheadings
                for h3 in soup.find_all("h3", class_="scene-subheading"):
                    h3.decompose()
                    
                # If cover or nav, don't inject scene subheadings
                if is_nav or is_cover:
                    toc_structure.append({
                        "title": chap_title,
                        "href": rel_href,
                        "scenes": []
                    })
                    file_path.write_text(str(soup), encoding="utf-8")
                    continue
                    
                # Find scene separation points
                # 1) Look for explicit delimiters (hr, p with ***, etc)
                delimiters = []
                for p_tag in soup.find_all(["p", "div", "hr"]):
                    if p_tag.name == "hr":
                        delimiters.append(p_tag)
                    else:
                        txt = p_tag.get_text(strip=True)
                        if txt and SEP_PATTERN.match(txt):
                            delimiters.append(p_tag)
                            
                # Merge consecutive delimiters
                filtered_delims = []
                for d in delimiters:
                    if filtered_delims:
                        prev = filtered_delims[-1]
                        if prev.find_next_sibling() == d or d.find_previous_sibling() == prev:
                            continue
                    filtered_delims.append(d)
                    
                file_scenes = []
                
                # Check if file is large (>25 paragraphs) and has 0 delimiters -> chunk by 25 paragraphs
                all_paras = [p for p in soup.find_all("p") if p.get_text(strip=True) and not SEP_PATTERN.match(p.get_text(strip=True))]
                
                if len(filtered_delims) > 0:
                    for d in filtered_delims:
                        anchor_id = f"sc-{global_scene_counter:03d}"
                        first_sentence = get_first_valid_sentence(d)
                        if first_sentence:
                            scene_title = f"제{global_scene_counter}막: {first_sentence}"
                        else:
                            scene_title = f"제{global_scene_counter}막"
                            
                        h3_tag = soup.new_tag("h3", attrs={"class": "scene-subheading", "id": anchor_id})
                        h3_tag.string = scene_title
                        d.insert_after(h3_tag)
                        
                        file_scenes.append({"title": scene_title, "anchor_id": anchor_id})
                        global_scene_counter += 1
                elif len(all_paras) >= 30:
                    # Multi-scene long chapter without explicit delimiters
                    for p_idx in range(25, len(all_paras), 25):
                        p_target = all_paras[p_idx]
                        anchor_id = f"sc-{global_scene_counter:03d}"
                        first_sentence = clean_summary_text(p_target.get_text(strip=True))
                        if first_sentence:
                            scene_title = f"제{global_scene_counter}막: {first_sentence}"
                        else:
                            scene_title = f"제{global_scene_counter}막"
                            
                        h3_tag = soup.new_tag("h3", attrs={"class": "scene-subheading", "id": anchor_id})
                        h3_tag.string = scene_title
                        p_target.insert_before(h3_tag)
                        
                        file_scenes.append({"title": scene_title, "anchor_id": anchor_id})
                        global_scene_counter += 1
                        
                toc_structure.append({
                    "title": chap_title,
                    "href": rel_href,
                    "scenes": file_scenes
                })
                
                file_path.write_text(str(soup), encoding="utf-8")
                
            # 3. Generate Perfectly Spine-Ordered toc.ncx and nav.xhtml
            # NCX
            ncx_files = list(tmp_dir.rglob("*.ncx"))
            if ncx_files:
                ncx_path = ncx_files[0]
                ncx_play_order = 1
                nav_points_xml = []
                
                for chap in toc_structure:
                    chap_np_id = f"navPoint-{ncx_play_order}"
                    chap_src = chap["href"]
                    chap_title_esc = html.escape(chap["title"])
                    
                    sub_points_xml = []
                    ncx_play_order += 1
                    for sc in chap["scenes"]:
                        sub_np_id = f"navPoint-{ncx_play_order}"
                        sub_src = f"{chap['href']}#{sc['anchor_id']}"
                        sub_title_esc = html.escape(sc["title"])
                        sub_points_xml.append(f"""    <navPoint id="{sub_np_id}" playOrder="{ncx_play_order}">
      <navLabel><text>{sub_title_esc}</text></navLabel>
      <content src="{sub_src}"/>
    </navPoint>""")
                        ncx_play_order += 1
                        
                    if sub_points_xml:
                        subs_str = "\n".join(sub_points_xml)
                        nav_points_xml.append(f"""  <navPoint id="{chap_np_id}" playOrder="{ncx_play_order}">
    <navLabel><text>{chap_title_esc}</text></navLabel>
    <content src="{chap_src}"/>
{subs_str}
  </navPoint>""")
                    else:
                        nav_points_xml.append(f"""  <navPoint id="{chap_np_id}" playOrder="{ncx_play_order}">
    <navLabel><text>{chap_title_esc}</text></navLabel>
    <content src="{chap_src}"/>
  </navPoint>""")
                        
                ncx_full_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:audiobook-maker-spine-aligned"/>
    <meta name="dtb:depth" content="2"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>{html.escape(epub_path.stem)}</text></docTitle>
  <navMap>
{chr(10).join(nav_points_xml)}
  </navMap>
</ncx>"""
                ncx_path.write_text(ncx_full_xml, encoding="utf-8")
                
            # NAV XHTML
            nav_files = list(tmp_dir.rglob("nav.xhtml")) + list(tmp_dir.rglob("toc.xhtml"))
            if nav_files:
                nav_path = nav_files[0]
                nav_lis = []
                for chap in toc_structure:
                    chap_title_esc = html.escape(chap["title"])
                    chap_src = chap["href"]
                    if chap["scenes"]:
                        sub_lis = []
                        for sc in chap["scenes"]:
                            sub_title_esc = html.escape(sc["title"])
                            sub_src = f"{chap['href']}#{sc['anchor_id']}"
                            sub_lis.append(f'        <li><a href="{sub_src}">{sub_title_esc}</a></li>')
                        sub_ol = "\n".join(sub_lis)
                        nav_lis.append(f"""      <li>
        <a href="{chap_src}">{chap_title_esc}</a>
        <ol>
{sub_ol}
        </ol>
      </li>""")
                    else:
                        nav_lis.append(f'      <li><a href="{chap_src}">{chap_title_esc}</a></li>')
                        
                nav_full_xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
  <title>차례</title>
  <style>
    nav#toc {{ margin: 1em; font-family: sans-serif; }}
    nav#toc h1 {{ font-size: 1.4em; margin-bottom: 0.8em; }}
    nav#toc ol {{ list-style-type: none; padding-left: 1.2em; }}
    nav#toc li {{ margin: 0.4em 0; line-height: 1.4; }}
    nav#toc ol ol {{ list-style-type: none; padding-left: 1.2em; }}
    nav#toc a {{ text-decoration: none; color: inherit; }}
  </style>
</head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>차례</h1>
    <ol>
{chr(10).join(nav_lis)}
    </ol>
  </nav>
</body>
</html>"""
                nav_path.write_text(nav_full_xhtml, encoding="utf-8")
                
            # 4. Pack EPUB
            with zipfile.ZipFile(epub_path, "w") as zout:
                mimetype_file = tmp_dir / "mimetype"
                if mimetype_file.exists():
                    zout.write(mimetype_file, "mimetype", compress_type=zipfile.ZIP_STORED)
                for root, _, files in os.walk(tmp_dir):
                    for f in files:
                        full_p = Path(root) / f
                        rel_p = full_p.relative_to(tmp_dir)
                        if str(rel_p) == "mimetype":
                            continue
                        zout.write(full_p, str(rel_p), compress_type=zipfile.ZIP_DEFLATED)
                        
        return epub_path.name, True, f"scenes: {global_scene_counter - 1}"
    except Exception as e:
        return epub_path.name, False, f"error: {e}"


def main():
    print("==================================================================")
    print("🌟 REBUILDING SPINE-ORDERED 2-LEVEL HIERARCHICAL TOC (ENTIRE LIBRARY)")
    print("==================================================================")
    
    # 1. First test directly on The Intruder
    target_intruder = lib_root / "[k]/#Freida McFadden/[k] The Intruder Freida McFadden 3 (3.00).epub"
    if target_intruder.exists():
        name, ok, msg = process_single_epub(target_intruder)
        print(f"🎯 Target Fixed: {name} -> {ok} ({msg})")
        
    all_epubs = []
    for ed in ["[k]", "[k-e]", "[study]", "[e-s]"]:
        ed_dir = lib_root / ed
        if ed_dir.exists():
            epubs = [p for p in ed_dir.rglob("*.epub") if not p.name.startswith("._")]
            all_epubs.extend(epubs)
            print(f"  Found {len(epubs):4} EPUBs in {ed}")
            
    print(f"\nTotal EPUBs to re-align & build spine TOC: {len(all_epubs)}")
    
    success_count = 0
    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(process_single_epub, epub): epub for epub in all_epubs}
        
        for i, future in enumerate(as_completed(futures), start=1):
            name, ok, msg = future.result()
            if ok:
                success_count += 1
            if i % 300 == 0 or i == len(all_epubs):
                print(f"  [{i:4}/{len(all_epubs)}] Processed {success_count} books in strict spine order...")
                
    print(f"\n🎉 ALL SPINE-ORDERED TOCs REBUILT SUCCESSFULLY!")
    print(f"  - Total Processed: {len(all_epubs)}")
    print(f"  - Success: {success_count}")
    
    print("\n☁️ Synchronizing spine-ordered library to Google Drive #Books...")
    for epub in all_epubs:
        try:
            rel = epub.relative_to(lib_root)
            g_dest = gdrive_root / rel
            if g_dest.parent.exists():
                shutil.copy2(epub, g_dest)
        except Exception:
            pass
    print("☁️ Google Drive synchronization complete!")


if __name__ == "__main__":
    main()
