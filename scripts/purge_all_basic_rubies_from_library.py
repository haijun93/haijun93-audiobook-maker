#!/usr/bin/env python3
"""scripts/purge_all_basic_rubies_from_library.py

Performs library-wide deep purification of Word Wise Ruby hints:
1. Strips all middle/high school basic words (e.g. 'fate', 'words', 'smile', 'dinner').
2. Strips all basic multi-word mechanical combinations (e.g. 'that one', 'three little words', 'in the car').
3. Unwraps invalid <ruby><rb>word</rb><rt>hint</rt></ruby> back to clean plain text 'word' without altering sentence structure.
4. Updates line-height class (removes 'has-ww' if no rubies remain in paragraph).
"""

from __future__ import annotations

import io
import re
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from bs4 import BeautifulSoup

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from audiobook_studio.study_filter import is_valid_toeic_700_plus_target

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

def clean_rubies_in_html(html_text: str) -> tuple[str, int]:
    soup = BeautifulSoup(html_text, "html.parser")
    stripped_count = 0

    for ruby in soup.find_all("ruby"):
        rb = ruby.find("rb")
        rt = ruby.find("rt")

        rb_text = rb.get_text().strip() if rb else ""
        if not rb_text:
            # Maybe text directly inside ruby
            rb_text = "".join(c for c in ruby.contents if getattr(c, "name", None) != "rt").strip()

        if not is_valid_toeic_700_plus_target(rb_text):
            # Strip ruby: replace ruby tag with just the original plain text
            ruby.replace_with(rb_text)
            stripped_count += 1

    # Clean up empty ruby or orphaned tags
    for p in soup.find_all("p"):
        if not p.find("ruby"):
            classes = p.get("class", [])
            if "has-ww" in classes:
                classes.remove("has-ww")
                if classes:
                    p["class"] = classes
                else:
                    del p["class"]

    for span in soup.find_all("span"):
        if not span.find("ruby"):
            classes = span.get("class", [])
            if "has-ww" in classes:
                classes.remove("has-ww")
                if classes:
                    span["class"] = classes
                else:
                    del span["class"]

    clean_html = str(soup)
    # Ensure XML well-formedness
    clean_html = re.sub(r"&(?!([a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);)", "&amp;", clean_html)
    clean_html = re.sub(r"<(?![a-zA-Z/!\?])", "&lt;", clean_html)
    return clean_html, stripped_count

def process_single_epub(args: tuple[str, str]) -> tuple[str, int, bool]:
    ep_path_str, ed_name = args
    ep = Path(ep_path_str)

    try:
        data = {}
        total_stripped = 0

        with zipfile.ZipFile(ep, "r") as z:
            for it in z.infolist():
                try:
                    data[it.filename] = z.read(it.filename)
                except Exception:
                    pass

        if not data:
            return ep.name, 0, False

        modified = False
        for fname in list(data.keys()):
            if fname.endswith((".xhtml", ".html")):
                txt = data[fname].decode("utf-8", "ignore")
                if "<ruby" in txt:
                    clean_txt, stripped = clean_rubies_in_html(txt)
                    if stripped > 0:
                        data[fname] = clean_txt.encode("utf-8")
                        total_stripped += stripped
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

        return ep.name, total_stripped, True
    except Exception as e:
        return ep.name, 0, False

def main():
    print("==================================================================")
    print("🧹 PURGING ALL BASIC VOCAB & TRIVIAL PHRASES ACROSS LIBRARY")
    print("   Standard: TOEIC 700+ to 990 Advanced Lexicon Only")
    print("==================================================================")

    editions = ["[study]", "[e-s]", "[k-e]", "[ks]", "[xteink]/[study]", "[xteink]/[e-s]"]
    target_tasks = []

    for ed in editions:
        ed_dir = LIB_ROOT / ed
        if ed_dir.exists():
            for p in ed_dir.rglob("*.epub"):
                if p.stat().st_size > 15000:
                    target_tasks.append((str(p), ed))

    print(f"📚 Scanning and purifying {len(target_tasks):,} books (16 workers)...\n")

    total_rubies_purged = 0
    books_purified = 0

    with ProcessPoolExecutor(max_workers=16) as ex:
        futures = [ex.submit(process_single_epub, t) for t in target_tasks]
        for fut in as_completed(futures):
            name, stripped, ok = fut.result()
            if ok and stripped > 0:
                books_purified += 1
                total_rubies_purged += stripped

    print("\n==================================================================")
    print("🎉 VOCABULARY PURIFICATION COMPLETE!")
    print(f"  • Total Books Processed      : {len(target_tasks):,} books")
    print(f"  • Books with Basic Rubies Fixed: {books_purified:,} books")
    print(f"  • Total Trivial Rubies Purged: {total_rubies_purged:,} rubies removed")
    print("==================================================================")

if __name__ == "__main__":
    main()
