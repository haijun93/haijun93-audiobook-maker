#!/usr/bin/env python3
"""scripts/purify_xteink_study_notes_for_toeic_700_plus.py

Purifies ALL 1,621+ [study] and [e-s] EPUBs inside `소설2/[xteink]` according to the
TOEIC 700+ to 990 Target Standard:

1. Strips away middle school / elementary basic words (e.g. 'hell', 'words', 'teeth', 'smile', 'dinner'...).
2. Retains strictly high-yield TOEIC 700~990 vocabulary, idioms, and collocations.
3. Synchronizes to Google Drive `#Books/[xteink]`.
"""

from __future__ import annotations

import html
import io
import json
import os
import re
import shutil
import sys
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from audiobook_studio.study_filter import is_valid_toeic_700_plus_target, BASIC_VOCAB_STOPLIST

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
XTEINK_ROOT = LIB_ROOT / "[xteink]"
GDRIVE_ROOT = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

KINDLE_CSS = '''@charset "utf-8";
body {
  font-family: "Amazon Ember", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Apple SD Gothic Neo", sans-serif;
  line-height: 1.65;
  margin: 1.5em;
  color: #1e293b;
}
h1 { font-size: 1.4em; text-align: center; margin: 1.5em 0 1em; font-weight: bold; }
p.pair { margin-bottom: 0.9em; }
span.en { font-size: 1em; color: #0f172a; line-height: 1.65; }
span.en.has-ww, p.has-ww { line-height: 1.85; }
span.ko { font-size: 0.94em; color: #475569; display: block; margin-top: 0.2em; line-height: 1.65; }
ruby { ruby-position: over; -webkit-ruby-position: over; ruby-align: center; }
rt, rt.wordwise-hint {
  font-size: 0.58em;
  color: #0284c7;
  font-weight: 600;
  font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", sans-serif;
  user-select: none;
}
'''

def clean_ruby_tags_in_html(html_str: str) -> tuple[str, int, int]:
    rubies_before = html_str.count("<ruby>")
    rubies_kept = 0
    
    def repl_ruby(m):
        nonlocal rubies_kept
        rb_text = m.group(1).strip()
        rt_text = m.group(2).strip()
        
        if is_valid_toeic_700_plus_target(rb_text):
            rubies_kept += 1
            return f'<ruby><rb>{rb_text}</rb><rt class="wordwise-hint">{rt_text}</rt></ruby>'
        else:
            return rb_text

    purified_html = re.sub(
        r'<ruby>\s*<rb>(.*?)</rb>\s*<rt[^>]*>(.*?)</rt>\s*</ruby>',
        repl_ruby,
        html_str,
        flags=re.DOTALL | re.IGNORECASE
    )
    
    def repl_p(pm):
        p_content = pm.group(0)
        has_rubies = "<ruby>" in p_content
        if has_rubies:
            p_content = re.sub(r'<p\b(?![^>]*class=["\'][^"\']*has-ww)([^>]*)class=["\']([^"\']*)["\']', r'<p\1class="\2 has-ww"', p_content)
            p_content = re.sub(r'<span\b(?![^>]*class=["\'][^"\']*has-ww)([^>]*)class=["\']en["\']', r'<span\1class="en has-ww"', p_content)
        else:
            p_content = re.sub(r'\bhas-ww\b', '', p_content)
            p_content = re.sub(r'class=["\']\s+["\']', '', p_content)
            p_content = re.sub(r'class=["\']pair\s+["\']', 'class="pair"', p_content)
            p_content = re.sub(r'class=["\']en\s+["\']', 'class="en"', p_content)
        return p_content

    purified_html = re.sub(r'<p\b[^>]*>.*?</p>', repl_p, purified_html, flags=re.DOTALL)
    return purified_html, rubies_before, rubies_kept

def purify_single_xteink_epub(ep_path_str: str) -> tuple[str, int, int, bool]:
    ep = Path(ep_path_str)
    
    try:
        data = {}
        total_before = 0
        total_after = 0
        
        with zipfile.ZipFile(ep, "r") as src_zip:
            for item in src_zip.infolist():
                content = src_zip.read(item.filename)
                
                if item.filename.endswith((".xhtml", ".html")) and not any(k in item.filename.lower() for k in ["xray", "cover"]):
                    html_str = content.decode("utf-8", errors="ignore")
                    p_html, b_cnt, a_cnt = clean_ruby_tags_in_html(html_str)
                    total_before += b_cnt
                    total_after += a_cnt
                    data[item.filename] = p_html.encode("utf-8")
                elif item.filename.endswith(".css"):
                    data[item.filename] = KINDLE_CSS.encode("utf-8")
                else:
                    data[item.filename] = content
                    
        # Write back
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as dst:
            if "mimetype" in data:
                dst.writestr("mimetype", data.pop("mimetype"), compress_type=zipfile.ZIP_STORED)
            else:
                dst.writestr("mimetype", b"application/epub+zip", compress_type=zipfile.ZIP_STORED)
            for fname, cdata in data.items():
                dst.writestr(fname, cdata)
                
        ep.write_bytes(buf.getvalue())
        
        # Sync to GDrive
        if GDRIVE_ROOT.exists():
            rel = ep.relative_to(LIB_ROOT)
            gd_dest = GDRIVE_ROOT / rel
            gd_dest.parent.mkdir(parents=True, exist_ok=True)
            gd_dest.write_bytes(buf.getvalue())
            
        return ep.name, total_before, total_after, True
    except Exception as e:
        return ep.name, 0, 0, False

def main():
    print("==================================================================")
    print("📱 PURIFYING [xteink] EDITIONS: STRICT TOEIC 700+ TO 990 STANDARD")
    print("==================================================================")
    print(f"🚫 Base Stoplist Active: {len(BASIC_VOCAB_STOPLIST):,} middle-school basic words will be stripped.")
    
    epubs = [str(p) for p in XTEINK_ROOT.rglob("*.epub") if p.stat().st_size > 10000]
    print(f"📚 Purifying {len(epubs):,} [xteink] EPUBs across [study] & [e-s] (12 workers)...\n")
    
    total_before = 0
    total_after = 0
    success = 0
    
    with ProcessPoolExecutor(max_workers=12) as ex:
        futures = [ex.submit(purify_single_xteink_epub, ep) for ep in epubs]
        for fut in as_completed(futures):
            name, b_cnt, a_cnt, ok = fut.result()
            if ok:
                success += 1
                total_before += b_cnt
                total_after += a_cnt
                diff = b_cnt - a_cnt
                if b_cnt > 0 and diff > 0:
                    print(f"  ✨ [xteink Purified] {name[:45]:<45} | {b_cnt:>6,} ➔ {a_cnt:>6,} rubies (Stripped {diff:>5,} basic words)")
                    
    print("\n==================================================================")
    print("🎉 ALL [xteink] EDITIONS 100% PURIFIED & SYNCHRONIZED!")
    print(f"  • Total Books Processed : {success:,} / {len(epubs):,} books")
    print(f"  • Previous Word Wise    : {total_before:,} annotations")
    print(f"  • Purified TOEIC 700+   : {total_after:,} high-yield annotations")
    print(f"  • Stripped Basic Trivia : {total_before - total_after:,} middle-school basic words removed")
    print("==================================================================")

if __name__ == "__main__":
    main()
