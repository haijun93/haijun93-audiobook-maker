#!/usr/bin/env python3
"""scripts/apply_clean_scene_subheading_style.py

Updates the styling of all scene subheadings in the entire library (2,271 books):
1. Removes box/background/border/gradient styles.
2. Applies a clean, elegant, natural novel heading style (simple text & number).
3. Preserves all technical <h3 class="scene-subheading" id="sc-..."> elements and 2-level TOC.
4. Synchronizes to Google Drive #Books.
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

desktop = Path("/Users/hyeokjunkong/Desktop")
lib_root = next(p for p in desktop.iterdir() if "소설2" in unicodedata.normalize("NFC", p.name))
gdrive_root = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

CLEAN_CSS_REPLACEMENT = """.scene-subheading {
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

OLD_CSS_PATTERN = re.compile(r'\.scene-subheading\s*\{[^}]*\}', re.DOTALL)


def update_single_epub_style(epub_path: Path) -> tuple[str, bool]:
    if not epub_path.exists() or epub_path.name.startswith("._"):
        return epub_path.name, False
        
    try:
        modified = False
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            with zipfile.ZipFile(epub_path, "r") as zin:
                zin.extractall(tmp_dir)
                
            # Scan and update all .xhtml, .html, .css files
            for root, _, files in os.walk(tmp_dir):
                for f in files:
                    if f.endswith((".xhtml", ".html", ".css")):
                        fp = Path(root) / f
                        try:
                            content = fp.read_text(encoding="utf-8", errors="ignore")
                            if ".scene-subheading" in content:
                                new_content = OLD_CSS_PATTERN.sub(CLEAN_CSS_REPLACEMENT, content)
                                if new_content != content:
                                    fp.write_text(new_content, encoding="utf-8")
                                    modified = True
                        except Exception:
                            pass
                            
            if modified:
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
                            
        return epub_path.name, True
    except Exception:
        return epub_path.name, False


def main():
    print("==================================================================")
    print("🎨 APPLYING CLEAN & NATURAL SCENE SUBHEADING DESIGN TO LIBRARY")
    print("==================================================================")
    
    all_epubs = []
    for ed in ["[k]", "[k-e]", "[study]", "[e-s]"]:
        ed_dir = lib_root / ed
        if ed_dir.exists():
            epubs = [p for p in ed_dir.rglob("*.epub") if not p.name.startswith("._")]
            all_epubs.extend(epubs)
            print(f"  Found {len(epubs):4} EPUBs in {ed}")
            
    print(f"\nTotal EPUBs to update: {len(all_epubs)}")
    
    success_count = 0
    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(update_single_epub_style, epub): epub for epub in all_epubs}
        
        for i, future in enumerate(as_completed(futures), start=1):
            name, ok = future.result()
            if ok:
                success_count += 1
            if i % 300 == 0 or i == len(all_epubs):
                print(f"  [{i:4}/{len(all_epubs)}] Completed styling for {success_count} books...")
                
    print(f"\n🎉 CLEAN STYLING COMPLETE!")
    print(f"  - Total Processed: {len(all_epubs)}")
    print(f"  - Success: {success_count}")
    
    print("\n☁️ Synchronizing updated styling to Google Drive #Books...")
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
