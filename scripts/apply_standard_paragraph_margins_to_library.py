#!/usr/bin/env python3
"""Apply industry-standard golden paragraph margins across all EPUBs in the library.

Standards:
- [k] (Korean-only editions):
    p { margin: 0 0 0.5em; text-indent: 0; }
    p.pair { margin-bottom: 0.5em; }
- [k-e] (Bilingual editions):
    p { margin: 0 0 0.6em; text-indent: 0; }
    p.pair { margin-bottom: 0.6em; }
- [study] & [e-s] (Study editions):
    p { margin: 0 0 0.7em; text-indent: 0; }
    p.pair { margin-bottom: 0.7em; }
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

def get_target_margin_for_path(path: Path) -> str:
    path_str = str(path)
    if "/[k]/" in path_str or "/[k] " in path.name:
        return "0.5em"
    elif "/[k-e]/" in path_str or "/[k-e] " in path.name:
        return "0.6em"
    elif "/[study]/" in path_str or "/[e-s]/" in path_str or "/[study_]/" in path_str:
        return "0.7em"
    return "0.5em"

def update_css_content(css_text: str, margin_val: str) -> str:
    # 1. Update or add p rule
    if re.search(r"\bp\s*\{[^}]*\}", css_text):
        css_text = re.sub(
            r"(\bp\s*\{)([^}]*?)(\})",
            lambda m: f"p {{ margin: 0 0 {margin_val}; text-indent: 0; }}",
            css_text
        )
    else:
        css_text += f"\np {{ margin: 0 0 {margin_val}; text-indent: 0; }}\n"
        
    # 2. Update or add p.pair rule
    if re.search(r"\bp\.pair\s*\{[^}]*\}", css_text):
        css_text = re.sub(
            r"(\bp\.pair\s*\{)([^}]*?)(\})",
            lambda m: f"p.pair {{ margin-bottom: {margin_val}; }}",
            css_text
        )
    else:
        css_text += f"p.pair {{ margin-bottom: {margin_val}; }}\n"
        
    return css_text

def process_epub(epub_path: Path) -> bool:
    margin_val = get_target_margin_for_path(epub_path)
    tmp_file = None
    try:
        with zipfile.ZipFile(epub_path, "r") as zin:
            in_names = zin.namelist()
            css_names = [n for n in in_names if n.lower().endswith(".css")]
            if not css_names:
                # No CSS, create OEBPS/styles.css
                pass
                
            fd, tmp_path_str = tempfile.mkstemp(suffix=".epub", dir=epub_path.parent)
            os.close(fd)
            tmp_file = Path(tmp_path_str)
            
            with zipfile.ZipFile(tmp_file, "w") as zout:
                zout.comment = zin.comment
                # Preserve uncompressed mimetype at offset 0
                if "mimetype" in in_names:
                    zout.writestr(
                        zipfile.ZipInfo("mimetype"),
                        zin.read("mimetype"),
                        compress_type=zipfile.ZIP_STORED
                    )
                
                for name in in_names:
                    if name == "mimetype":
                        continue
                    data = zin.read(name)
                    if name.lower().endswith(".css"):
                        text = data.decode("utf-8", errors="replace")
                        new_text = update_css_content(text, margin_val)
                        data = new_text.encode("utf-8")
                    zout.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
                    
        # Replace atomically
        tmp_file.replace(epub_path)
        return True
    except Exception as e:
        print(f"❌ Error on {epub_path.name}: {e}", file=sys.stderr)
        if tmp_file and tmp_file.exists():
            tmp_file.unlink()
        return False

def main():
    print("==================================================================")
    print("🚀 APPLYING STANDARD PARAGRAPH MARGINS ACROSS ENTIRE LIBRARY")
    print("==================================================================")
    
    editions = ["[k]", "[k-e]", "[study]", "[e-s]"]
    total_processed = 0
    total_success = 0
    
    for ed in editions:
        ed_dir = LIB_ROOT / ed
        if not ed_dir.exists():
            continue
        epub_files = list(ed_dir.rglob("*.epub"))
        margin = "0.5em" if ed == "[k]" else ("0.6em" if ed == "[k-e]" else "0.7em")
        print(f"\n📚 Processing {ed} (Target margin: {margin}, {len(epub_files)} books)...")
        
        success_cnt = 0
        for ep in epub_files:
            if process_epub(ep):
                success_cnt += 1
        print(f"   -> Successfully updated {success_cnt}/{len(epub_files)} EPUBs in {ed}")
        total_processed += len(epub_files)
        total_success += success_cnt
        
    print("\n==================================================================")
    print(f"🎉 BATCH COMPLETE: Successfully applied standard margins to {total_success}/{total_processed} EPUBs!")
    print("==================================================================")

if __name__ == "__main__":
    main()
