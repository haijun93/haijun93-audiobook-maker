#!/usr/bin/env python3
"""Apply complete publishing industry master stylesheet across entire library.

Includes:
1. Korean Typography: word-break: keep-all; letter-spacing: -0.03em; line-height: 1.65;
2. Adaptive Themes (Dark/Sepia/Light): background: transparent; color: inherit;
3. Kindle X-Ray Style Study Notes: green capsule styling with border & background
4. Blockquote & Scene Break Separator Styling
5. Golden Standard Paragraph Margins (0.5em for [k], 0.6em for [k-e], 0.7em for [study]/[e-s])
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

def build_master_css(edition_type: str) -> str:
    margin_val = "0.5em"  # Unified 0.5em golden standard across all editions
    
    return f'''@charset "utf-8";
html, body {{
  margin: 0;
  padding: 0;
  background: transparent;
  color: inherit;
}}
body {{
  font-family: serif;
  line-height: 1.65;
  letter-spacing: -0.03em;
  word-break: keep-all;
  overflow-wrap: break-word;
  -webkit-hyphens: none;
  hyphens: none;
}}
section {{ margin: 0; padding: 0; }}
h1 {{
  font-size: 1.45em;
  line-height: 1.25;
  margin: 1.35em 0 1em;
  text-align: center;
  page-break-before: always;
}}
h2 {{
  font-size: 1.05em;
  line-height: 1.35;
  margin: 1.15em 0 0.75em;
  text-align: left;
}}
p {{ margin: 0 0 {margin_val}; text-indent: 0; }}
p.pair {{ margin-bottom: {margin_val}; }}
span.en {{
  color: #555555;
  font-size: 0.92em;
  letter-spacing: normal;
}}
span.study-note {{
  display: inline-block;
  color: #15803d;
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.2);
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 0.85em;
  font-style: normal;
  margin: 0.15em 0;
  line-height: 1.4;
}}
blockquote {{
  margin: 1.2em 0 1.2em 1.2em;
  padding-left: 0.8em;
  border-left: 3px solid rgba(148, 163, 184, 0.4);
  font-style: italic;
  opacity: 0.92;
}}
.scene-break {{
  text-align: center;
  margin: 1.8em 0;
  color: #94a3b8;
  letter-spacing: 0.6em;
  font-size: 0.9em;
}}
.scene-subheading {{
  margin-top: 2em;
  margin-bottom: 0.8em;
  padding: 0;
  font-size: 1.05em;
  font-weight: 700;
  color: inherit;
  background: none;
  border: none;
  line-height: 1.5;
  page-break-after: avoid;
  break-after: avoid;
}}
nav#toc {{ margin: 0 2%; }}
nav#toc h1 {{ page-break-before: auto; }}
nav#toc ol {{ padding-left: 1.4em; }}
nav#toc li {{ margin: 0.3em 0; }}
.cover-page {{
  margin: 0;
  padding: 0;
  text-align: center;
  page-break-after: always;
}}
.cover-page img {{
  display: block;
  margin: 0 auto;
  max-width: 100%;
  max-height: 100%;
}}
a {{ color: inherit; text-decoration: none; }}
'''

def get_edition_type(path: Path) -> str:
    path_str = str(path)
    if "/[k]/" in path_str or "/[k] " in path.name:
        return "k"
    elif "/[k-e]/" in path_str or "/[k-e] " in path.name:
        return "k-e"
    elif "/[study]/" in path_str or "/[e-s]/" in path_str or "/[study_]/" in path_str:
        return "study"
    return "k"

def process_epub(epub_path: Path) -> bool:
    ed_type = get_edition_type(epub_path)
    master_css_bytes = build_master_css(ed_type).encode("utf-8")
    
    tmp_file = None
    try:
        with zipfile.ZipFile(epub_path, "r") as zin:
            in_names = zin.namelist()
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
                    if name.lower().endswith(".css"):
                        # Replace with full master CSS
                        zout.writestr(name, master_css_bytes, compress_type=zipfile.ZIP_DEFLATED)
                    else:
                        data = zin.read(name)
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
    print("🌟 APPLYING PUBLISHING MASTER STYLESHEET ACROSS ENTIRE LIBRARY")
    print("==================================================================")
    
    editions = ["[k]", "[k-e]", "[study]", "[e-s]"]
    total_processed = 0
    total_success = 0
    
    for ed in editions:
        ed_dir = LIB_ROOT / ed
        if not ed_dir.exists():
            continue
        epub_files = list(ed_dir.rglob("*.epub"))
        print(f"\n🎨 Enhancing {ed} ({len(epub_files)} books)...")
        
        success_cnt = 0
        for ep in epub_files:
            if process_epub(ep):
                success_cnt += 1
        print(f"   -> Successfully updated {success_cnt}/{len(epub_files)} EPUBs in {ed}")
        total_processed += len(epub_files)
        total_success += success_cnt
        
    print("\n==================================================================")
    print(f"🎉 MASTER STYLES APPLIED: Successfully enhanced {total_success}/{total_processed} EPUBs!")
    print("==================================================================")

if __name__ == "__main__":
    main()
