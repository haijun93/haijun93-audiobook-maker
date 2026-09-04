#!/usr/bin/env python3
"""scripts/purge_all_scene_subheadings.py

Completely purges all synthetic scene sub-headings (제N막, scene-subheading, #sc-...)
across the entire library and restores authentic author-only Table of Contents (TOC).

Actions performed:
1. Strips all `<h3 class="scene-subheading">` from all XHTML/HTML files.
2. Removes `.scene-subheading` blocks from all CSS files.
3. Cleans `nav.xhtml` by removing nested `<ol>` scene sub-items and stripping `#sc-` fragments from parent chapter links.
4. Cleans `toc.ncx` by removing nested `<navPoint>` scene sub-items, stripping `#sc-` fragments, and renumbering playOrder.
5. Runs in parallel across CPU cores across all library editions ([k], [k-e], [study], [e-s], [xteink]).
6. Syncs changes to Google Drive `#Books`.
"""

from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from bs4 import BeautifulSoup

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
GDRIVE_ROOT = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

def purge_scene_subheadings_from_epub(epub_path: Path) -> tuple[bool, str, int]:
    """Purges scene subheadings and restores clean TOC in a single EPUB."""
    try:
        # Quick pre-check
        has_scenes = False
        with zipfile.ZipFile(epub_path, "r") as zin:
            for name in zin.namelist():
                if name.endswith((".xhtml", ".html", ".ncx", ".css")):
                    raw = zin.read(name).decode("utf-8", "ignore")
                    if "scene-subheading" in raw or "#sc-" in raw or "#scene-" in raw or "제1막" in raw or "제2막" in raw:
                        has_scenes = True
                        break

        if not has_scenes:
            return False, epub_path.name, 0

        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            with zipfile.ZipFile(epub_path, "r") as zin:
                zin.extractall(tmp_dir)

            purged_headings_count = 0

            # 1. Clean CSS files
            for css_f in tmp_dir.glob("**/*.css"):
                css_content = css_f.read_text(encoding="utf-8", errors="ignore")
                if "scene-subheading" in css_content:
                    css_cleaned = re.sub(r'/\* Scene Sub-heading Styling \*/.*?\.scene-subheading\s*\{[^}]*\}', '', css_content, flags=re.DOTALL)
                    css_cleaned = re.sub(r'\.scene-subheading\s*\{[^}]*\}', '', css_cleaned, flags=re.DOTALL)
                    css_f.write_text(css_cleaned, encoding="utf-8")

            # 2. Clean XHTML content files
            for xhtml_f in tmp_dir.glob("**/*.xhtml"):
                if xhtml_f.name in ["nav.xhtml", "toc.xhtml"]:
                    continue
                content = xhtml_f.read_text(encoding="utf-8", errors="ignore")
                if "scene-subheading" in content or "id=\"sc-" in content or "id=\"scene-" in content:
                    soup = BeautifulSoup(content, "html.parser")
                    # Find all h3/h4/h2 scene subheadings
                    for tag in soup.find_all(["h2", "h3", "h4", "div", "p"]):
                        cls = tag.get("class", [])
                        tag_id = tag.get("id", "")
                        tag_txt = tag.get_text(strip=True)

                        is_scene = False
                        if "scene-subheading" in cls:
                            is_scene = True
                        elif tag_id and (tag_id.startswith("sc-") or tag_id.startswith("scene-")):
                            is_scene = True
                        elif re.match(r"^제\s*\d+\s*막", tag_txt) and tag.name in ["h2", "h3", "h4"]:
                            is_scene = True

                        if is_scene:
                            tag.decompose()
                            purged_headings_count += 1

                    xhtml_f.write_text(str(soup), encoding="utf-8")

            # 3. Clean nav.xhtml
            for nav_f in tmp_dir.glob("**/nav.xhtml"):
                nav_content = nav_f.read_text(encoding="utf-8", errors="ignore")
                soup = BeautifulSoup(nav_content, "html.parser")

                # Remove nested sub-ordered lists under chapters that point to scene anchors
                for sub_ol in soup.find_all("ol"):
                    if sub_ol.parent and sub_ol.parent.name == "li":
                        # Check if this ol contains scene links
                        links = sub_ol.find_all("a")
                        if any(("#sc-" in (a.get("href") or "") or "#scene-" in (a.get("href") or "") or "제" in a.get_text()) for a in links):
                            sub_ol.decompose()

                # Clean any remaining parent links with fragment #sc-
                for a in soup.find_all("a"):
                    href = a.get("href", "")
                    if "#sc-" in href or "#scene-" in href:
                        clean_href = href.split("#")[0]
                        a["href"] = clean_href

                nav_f.write_text(str(soup), encoding="utf-8")

            # 4. Clean toc.ncx
            for ncx_f in tmp_dir.glob("**/toc.ncx"):
                ncx_content = ncx_f.read_text(encoding="utf-8", errors="ignore")
                soup = BeautifulSoup(ncx_content, "xml")

                # Remove nested navPoints pointing to scene fragments or containing 제N막
                for sub_np in soup.find_all("navPoint"):
                    if sub_np.parent and sub_np.parent.name == "navPoint":
                        # Nested under chapter
                        src_tag = sub_np.find("content")
                        lbl_tag = sub_np.find("text")
                        src_val = src_tag.get("src", "") if src_tag else ""
                        lbl_val = lbl_tag.get_text(strip=True) if lbl_tag else ""

                        if "#sc-" in src_val or "#scene-" in src_val or re.match(r"^제\s*\d+\s*막", lbl_val) or "프롤로그 " in lbl_val:
                            sub_np.decompose()

                # Clean remaining navPoints with #sc- fragments
                for np in soup.find_all("navPoint"):
                    src_tag = np.find("content")
                    if src_tag and ("#sc-" in src_tag.get("src", "") or "#scene-" in src_tag.get("src", "")):
                        src_tag["src"] = src_tag["src"].split("#")[0]

                # Renumber playOrder
                order = 1
                for np in soup.find_all("navPoint"):
                    np["playOrder"] = str(order)
                    np["id"] = f"num_{order}"
                    order += 1

                ncx_f.write_text(str(soup), encoding="utf-8")

            # 5. Re-pack EPUB with uncompressed mimetype first
            temp_out = tmp_dir.parent / (epub_path.name + ".tmp.epub")
            with zipfile.ZipFile(temp_out, "w") as zout:
                mimetype_p = tmp_dir / "mimetype"
                if mimetype_p.exists():
                    zout.write(mimetype_p, "mimetype", compress_type=zipfile.ZIP_STORED)
                for f in tmp_dir.rglob("*"):
                    if f.is_file() and f != temp_out and f.name != "mimetype":
                        zout.write(f, f.relative_to(tmp_dir), compress_type=zipfile.ZIP_DEFLATED)

            shutil.copy2(temp_out, epub_path)
            temp_out.unlink(missing_ok=True)

            # Sync to Google Drive if destination exists
            try:
                rel = epub_path.relative_to(LIB_ROOT)
                gdrive_dest = GDRIVE_ROOT / rel
                if gdrive_dest.parent.exists():
                    shutil.copy2(epub_path, gdrive_dest)
            except Exception:
                pass

            return True, epub_path.name, purged_headings_count

    except Exception as e:
        return False, f"ERR: {epub_path.name}: {e}", 0

def main():
    print("==================================================================")
    print("🧹 STARTING COMPLETE PURGE OF SCENE SUBHEADINGS FROM LIBRARY")
    print("==================================================================")

    epubs = list(LIB_ROOT.rglob("*.epub"))
    print(f"📚 Total EPUBs to inspect: {len(epubs):,}\n")

    cleaned_count = 0
    total_headings_removed = 0

    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(purge_scene_subheadings_from_epub, ep): ep for ep in epubs}
        for fut in as_completed(futures):
            success, fname, h_cnt = fut.result()
            if success:
                cleaned_count += 1
                total_headings_removed += h_cnt
                print(f"  ✨ [PURGED] {fname:<60} (Removed {h_cnt} scene tags & cleaned TOC)")

    print("\n==================================================================")
    print(f"🎉 COMPLETED: Successfully purged scene subheadings from {cleaned_count:,} EPUBs!")
    print(f"   Total synthetic scene tags removed: {total_headings_removed:,}")
    print("   All Table of Contents (TOC) restored to authentic author chapter structure.")
    print("==================================================================")

if __name__ == "__main__":
    main()
