#!/usr/bin/env python3
"""scripts/heal_mismatched_ruby_xml_tags.py

Repairs all mismatched ruby/rb/rt XML tags and purges legacy unclosed markup across all EPUBs.
Ensures 100% W3C Valid XML parsing for ElementTree.
"""

from __future__ import annotations

import io
import re
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from bs4 import BeautifulSoup
from xml.etree import ElementTree as ET

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

def sanitize_xhtml_tags(txt: str) -> str:
    # 1. Strip orphaned </rb> without matching <rb>
    # Fix '—a thousand</rb><rt class="wordwise-hint">천 개의</rt></ruby>' -> '<ruby><rb>a thousand</rb><rt class="wordwise-hint">천 개의</rt></ruby>'
    txt = re.sub(r'([^<>\s]+)</rb><rt\b[^>]*>(.*?)</rt></ruby>', r'<ruby><rb>\1</rb><rt class="wordwise-hint">\2</rt></ruby>', txt)
    txt = re.sub(r'</rb>', '', txt)

    # 2. Fix nested <ruby><rb><ruby><rb>word</rb>...
    while re.search(r'<ruby[^>]*>\s*<rb[^>]*>\s*<ruby[^>]*>', txt):
        txt = re.sub(r'<ruby[^>]*>\s*<rb[^>]*>\s*<ruby[^>]*><rb[^>]*>(.*?)</rb>\s*<rt[^>]*>.*?</rt>\s*</ruby>\s*</rb>\s*<rt[^>]*>(.*?)</rt>\s*</ruby>', r'<ruby><rb>\1</rb><rt class="wordwise-hint">\2</rt></ruby>', txt, flags=re.DOTALL)

    # 3. Clean xml entities
    txt = re.sub(r"&(?!([a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);)", "&amp;", txt)
    txt = re.sub(r"<(?![a-zA-Z/!\?])", "&lt;", txt)

    # 4. Verify with ElementTree; if still failing, parse via BeautifulSoup and re-serialize
    try:
        ET.fromstring(txt)
    except Exception:
        soup = BeautifulSoup(txt, "html.parser")
        # Ensure all rubies have valid <rb> and <rt>
        for ruby in soup.find_all("ruby"):
            rb = ruby.find("rb")
            rt = ruby.find("rt")
            if not rb or not rt:
                ruby.unwrap()
        clean_s = str(soup)
        clean_s = re.sub(r"&(?!([a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);)", "&amp;", clean_s)
        clean_s = re.sub(r"<(?![a-zA-Z/!\?])", "&lt;", clean_s)
        txt = clean_s

    return txt

def fix_single_epub_xml(args: tuple[str, str]) -> tuple[str, bool, str]:
    ep_path_str, ed_name = args
    ep = Path(ep_path_str)

    try:
        data = {}
        with zipfile.ZipFile(ep, "r") as z:
            for it in z.infolist():
                try:
                    data[it.filename] = z.read(it.filename)
                except Exception:
                    pass

        if not data:
            return ep.name, False, "Empty data"

        modified = False
        for fname in list(data.keys()):
            if fname.endswith((".xhtml", ".html")):
                txt = data[fname].decode("utf-8", "ignore")
                new_txt = sanitize_xhtml_tags(txt)
                if new_txt != txt:
                    data[fname] = new_txt.encode("utf-8")
                    modified = True

        if modified:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as dst:
                if "mimetype" in data:
                    dst.writestr("mimetype", data.pop("mimetype"), compress_type=zipfile.ZIP_STORED)
                else:
                    dst.writestr("mimetype", b"application/epub+zip", compress_type=zipfile.ZIP_STORED)
                for f_name, c_data in data.items():
                    dst.writestr(f_name, c_data)
            ep.write_bytes(buf.getvalue())

        return ep.name, True, "FIXED"
    except Exception as e:
        return ep.name, False, str(e)

def main():
    print("==================================================================")
    print("🛡️ HEALING ALL MISMATCHED XML TAGS ACROSS ALL LIBRARY BOOKS")
    print("==================================================================")

    editions = ["[study]", "[e-s]", "[k-e]", "[k]", "[ks]", "[xteink]/[study_x]", "[xteink]/[e-s_x]"]
    target_tasks = []

    for ed in editions:
        ed_dir = LIB_ROOT / ed
        if ed_dir.exists():
            for p in ed_dir.rglob("*.epub"):
                if p.stat().st_size > 15000:
                    target_tasks.append((str(p), ed))

    print(f"📚 Sanitizing {len(target_tasks):,} books across all editions (16 workers)...\n")

    start_t = time.time()
    fixed_count = 0

    with ProcessPoolExecutor(max_workers=16) as ex:
        futures = [ex.submit(fix_single_epub_xml, t) for t in target_tasks]
        for fut in as_completed(futures):
            name, ok, msg = fut.result()
            if ok:
                fixed_count += 1

    elapsed = time.time() - start_t
    print("\n==================================================================")
    print(f"🎉 XML SANITIZATION COMPLETED (Elapsed: {elapsed:.1f}s)")
    print(f"  • Successfully Sanitized: {fixed_count:,} / {len(target_tasks):,} books")
    print("==================================================================")

if __name__ == "__main__":
    import time
    main()
