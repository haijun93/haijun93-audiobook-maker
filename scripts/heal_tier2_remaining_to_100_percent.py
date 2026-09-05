#!/usr/bin/env python3
"""scripts/heal_tier2_remaining_to_100_percent.py

Final Master Healer that eliminates all remaining Tier-2 Sentinel rejections:
1. Fixes broken TOC link mappings by syncing nav.xhtml & toc.ncx with actual chapter files.
2. Purges middle-school basic rubies and expands TOEIC 700+ vocabulary.
3. Auto-translates raw English headers in span.ko (Chapter, Part, Prologue, Epilogue, etc.).
4. Escapes all raw `<` and `&` in XHTML documents for 100% W3C XML validity.
"""

from __future__ import annotations

import html
import io
import re
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from bs4 import BeautifulSoup
from audiobook_studio.epub_xray_policy import purge_xray_from_epub

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from audiobook_studio.study_filter import is_valid_toeic_700_plus_target, BASIC_VOCAB_STOPLIST

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

HEADER_MAP = {
    r'^prologue\b': '프롤로그',
    r'^epilogue\b': '에필로그',
    r'^chapter\s+(\d+)': r'제\1장',
    r'^part\s+(\d+)': r'제\1부',
    r'^book\s+(\d+)': r'제\1권',
    r'^act\s+([ivxlcdm]+|\d+)': r'제\1막',
    r'^scene\s+(\d+)': r'제\1장',
    r'^interlude\b': '막간',
    r'^dedication\b': '헌사',
    r'^acknowledgments?\b': '감사의 글',
    r'^author\s*note\b': '작가의 말',
    r'^about\s+the\s+author\b': '작가 소개',
    r'^title\s+page\b': '표제지',
    r'^copyright\b': '판권',
}

def translate_hdr(text: str) -> str:
    c = text.strip()
    for pat, rep in HEADER_MAP.items():
        if re.search(pat, c, re.IGNORECASE):
            return re.sub(pat, rep, c, flags=re.IGNORECASE)
    return ""

def deep_heal_epub(args: tuple[str, str]) -> tuple[str, bool, str]:
    ep_path_str, ed_name = args
    ep = Path(ep_path_str)
    try:
        data = {}
        try:
            with zipfile.ZipFile(ep, "r") as z:
                for it in z.infolist():
                    try:
                        data[it.filename] = z.read(it.filename)
                    except Exception:
                        pass
        except Exception:
            return ep.name, False, "Corrupted ZIP"

        if not data:
            return ep.name, False, "Empty data"

        chapters = []
        for fname in sorted(data.keys()):
            if fname.endswith((".xhtml", ".html")) and not any(k in fname.lower() for k in ["cover", "xray", "nav"]):
                c_bytes = data[fname]
                txt = c_bytes.decode("utf-8", "ignore")

                soup = BeautifulSoup(txt, "html.parser")
                h1 = soup.find(["h1", "h2", "title"])
                ch_t = h1.get_text().strip() if h1 else Path(fname).stem
                rel_href = fname[6:] if fname.startswith("OEBPS/") else fname
                chapters.append((rel_href, ch_t))

                mod = False
                for p in soup.find_all("p"):
                    # 1. Clean basic rubies
                    for rb in p.find_all("ruby"):
                        rb_t = rb.find("rb").get_text().strip() if rb.find("rb") else ""
                        if rb_t.lower() in BASIC_VOCAB_STOPLIST and not is_valid_toeic_700_plus_target(rb_t):
                            rb.replace_with(rb_t)
                            mod = True

                    # 2. Clean untranslated raw English in span.ko
                    ko_span = p.find("span", class_="ko")
                    en_span = p.find("span", class_=lambda c: c and "en" in c)
                    if ko_span:
                        ko_t = ko_span.get_text().strip()
                        en_t = en_span.get_text().strip() if en_span else ""
                        if ko_t and not re.search(r'[가-힣]', ko_t) and len(ko_t) > 2:
                            t_ko = translate_hdr(ko_t) or translate_hdr(en_t)
                            if t_ko:
                                ko_span.string = t_ko
                                mod = True
                            elif ko_t.lower() == en_t.lower() or not re.search(r'[a-zA-Z]', ko_t):
                                ko_span.decompose()
                                mod = True

                    # 3. Clean rt tags
                    for rt in p.find_all("rt"):
                        t_rt = rt.get_text().strip()
                        if t_rt.endswith("...") or t_rt.endswith("…"):
                            rt.string = t_rt.rstrip(".").rstrip("…").strip()
                            mod = True

                clean_xml = str(soup)
                clean_xml = re.sub(r"<(?![a-zA-Z/!\?])", "&lt;", clean_xml)
                clean_xml = re.sub(r"&(?!([a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);)", "&amp;", clean_xml)
                data[fname] = clean_xml.encode("utf-8")

        # Re-generate clean TOC if broken links or missing
        if chapters:
            nav_items, ncx_items = [], []
            order = 1

            for rel_href, ch_t in chapters:
                c_t = html.escape(translate_hdr(ch_t) or ch_t)
                nav_items.append(f"      <li><a href=\"{rel_href}\">{c_t}</a></li>")
                ncx_items.append(f"""    <navPoint id="nav_{order}" playOrder="{order}">
      <navLabel><text>{c_t}</text></navLabel>
      <content src="{rel_href}"/>
    </navPoint>""")
                order += 1

            nav_html = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="ko" xml:lang="ko">
<head>
  <title>목차 (Table of Contents)</title>
  <meta charset="utf-8" />
  <link rel="stylesheet" type="text/css" href="styles.css" />
</head>
<body>
  <nav epub:type="toc" id="toc" role="doc-toc">
    <h1>목차 (Table of Contents)</h1>
    <ol>
{chr(10).join(nav_items)}
    </ol>
  </nav>
</body>
</html>""".encode("utf-8")

            toc_ncx = f"""<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="ko">
  <head>
    <meta name="dtb:uid" content="urn:uuid:{ep.stem}"/>
    <meta name="dtb:depth" content="2"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>{html.escape(ep.stem)}</text></docTitle>
  <navMap>
{chr(10).join(ncx_items)}
  </navMap>
</ncx>""".encode("utf-8")

            data["OEBPS/nav.xhtml"] = nav_html
            data["OEBPS/toc.ncx"] = toc_ncx

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as dst:
            if "mimetype" in data:
                dst.writestr("mimetype", data.pop("mimetype"), compress_type=zipfile.ZIP_STORED)
            else:
                dst.writestr("mimetype", b"application/epub+zip", compress_type=zipfile.ZIP_STORED)
            for f_name, c_data in data.items():
                dst.writestr(f_name, c_data)

        ep.write_bytes(buf.getvalue())
        purge_xray_from_epub(ep)
        return ep.name, True, "HEALED"
    except Exception as e:
        return ep.name, False, str(e)

def main():
    print("==================================================================")
    print("🚀 HEALING ALL REMAINING TIER-2 VIOLATIONS ACROSS FULL LIBRARY")
    print("==================================================================")

    target_tasks = []
    editions = ["[study]", "[e-s]", "[k-e]", "[k]", "[xteink]/[study]", "[xteink]/[e-s]"]

    for ed in editions:
        ed_dir = LIB_ROOT / ed
        if ed_dir.exists():
            for p in ed_dir.rglob("*.epub"):
                if p.stat().st_size > 15000:
                    target_tasks.append((str(p), ed))

    print(f"📚 Deep-healing {len(target_tasks):,} books across all editions (16 workers)...\n")

    start_t = time.time()
    healed = 0
    failed = 0

    with ProcessPoolExecutor(max_workers=16) as ex:
        futures = [ex.submit(deep_heal_epub, t) for t in target_tasks]
        for fut in as_completed(futures):
            name, ok, msg = fut.result()
            if ok:
                healed += 1
            else:
                failed += 1

    elapsed = time.time() - start_t
    print("\n==================================================================")
    print(f"🎉 TIER-2 DEEP-HEALING COMPLETED (Elapsed: {elapsed:.1f}s)")
    print(f"  • Successfully Deep-Healed  : {healed:,} / {len(target_tasks):,} books ({(healed/len(target_tasks))*100:.1f}%)")
    print(f"  • Failed / Corrupted        : {failed:,} books")
    print("==================================================================")

if __name__ == "__main__":
    import time
    main()
