#!/usr/bin/env python3
"""scripts/build_xteink_dedicated_editions.py

High-Performance Parallel Builder for Dedicated [xteink] Editions:
- /Users/hyeokjunkong/Desktop/소설2/[xteink]/[study_x]/ (3-Line Edition: EN + KO + Study Notes)
- /Users/hyeokjunkong/Desktop/소설2/[xteink]/[e-s_x]/   (2-Line Edition: EN + Study Notes, No KO)

Key Specifications:
1. Zero Ruby / Zero Word Wise: Completely removes all <ruby>, <rb>, <rt> tags.
2. Extracts authentic TOEIC 700+ vocabulary notes into standalone bottom <span class="study-note">※ 단어 - 문맥 뜻</span>.
3. 100% X-Ray Purged: Zero xray files or links.
4. Clean Typography optimized for Xteink e-ink e-readers.
"""

from __future__ import annotations

import html
import os
import re
import tempfile
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
XTEINK_ROOT = LIB_ROOT / "[xteink]"
STUDY_X_ROOT = XTEINK_ROOT / "[study_x]"
ES_X_ROOT = XTEINK_ROOT / "[e-s_x]"

def get_xteink_css() -> bytes:
    css = '''@charset "utf-8";
html, body {
  margin: 0;
  padding: 0;
  background: transparent;
  color: inherit;
}
body {
  font-family: "Bookerly_KR", "Amazon Ember", "Charis SIL", "Georgia", serif;
  line-height: 1.65;
  letter-spacing: -0.02em;
  word-break: keep-all;
  overflow-wrap: break-word;
  -webkit-hyphens: none;
  hyphens: none;
}
section { margin: 0; padding: 0; }
h1 {
  font-size: 1.45em;
  line-height: 1.3;
  margin: 1.3em 0 0.9em;
  text-align: center;
  page-break-before: always;
  font-weight: bold;
}
h2 {
  font-size: 1.15em;
  line-height: 1.35;
  margin: 1.2em 0 0.8em;
  text-align: left;
}
p { margin: 0 0 0.5em; text-indent: 0; line-height: 1.65; }
p.pair { margin-bottom: 0.6em; }

span.en {
  color: inherit;
  font-size: 0.98em;
  line-height: 1.65;
}

span.ko {
  color: #334155;
  font-size: 0.96em;
  line-height: 1.65;
}

span.study-note {
  display: block;
  margin-top: 0.22em;
  color: #0284c7;
  font-size: 0.86em;
  line-height: 1.45;
  font-family: "Bookerly_KR", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

blockquote {
  margin: 1.2em 0 1.2em 1.2em;
  padding-left: 0.8em;
  border-left: 3px solid rgba(148, 163, 184, 0.4);
  font-style: italic;
  opacity: 0.92;
}
.scene-break {
  text-align: center;
  margin: 1.8em 0;
  color: #94a3b8;
  letter-spacing: 0.6em;
  font-size: 0.9em;
}
nav#toc { margin: 0 2%; }
nav#toc h1 { page-break-before: auto; }
nav#toc ol { padding-left: 1.4em; }
nav#toc li { margin: 0.3em 0; }
a { color: inherit; text-decoration: none; }
'''
    return css.encode("utf-8")

def extract_ruby_pairs_regex(text: str) -> list[tuple[str, str]]:
    pairs = []
    if "<rt" not in text:
        return pairs
    cur = text
    for _ in range(20):
        if "<rt" not in cur:
            break
        found = False
        for m in re.finditer(r"<ruby[^>]*>\s*<rb[^>]*>((?:(?!<ruby).)*?)</rb>\s*<rt[^>]*>(.*?)</rt>\s*</ruby>", cur, flags=re.DOTALL):
            found = True
            w = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            mean = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            if w and mean:
                pairs.append((w, mean))
            cur = cur[:m.start()] + w + cur[m.end():]
            break
        if not found:
            # Check for ruby without rb
            for m in re.finditer(r"<ruby[^>]*>((?:(?!<ruby).)*?)<rt[^>]*>(.*?)</rt>\s*</ruby>", cur, flags=re.DOTALL):
                found = True
                w = re.sub(r"<[^>]+>", "", m.group(1)).strip()
                mean = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                if w and mean:
                    pairs.append((w, mean))
                cur = cur[:m.start()] + w + cur[m.end():]
                break
        if not found:
            break
    return pairs

def transform_html_for_xteink(html_str: str, edition_type: str = "study_x") -> str:
    def repl_p(m):
        full_p = m.group(0)

        # 1. Extract vocabulary pairs from ruby tags
        ruby_pairs = extract_ruby_pairs_regex(full_p)

        # 2. Strip all ruby tags and classes
        clean_p = re.sub(r"<rt\b[^>]*>.*?</rt>", "", full_p, flags=re.DOTALL)
        clean_p = re.sub(r"</?(ruby|rb)\b[^>]*>", "", clean_p)
        clean_p = re.sub(r"\bhas-ww\b", "", clean_p)

        # 3. Locate English, Korean, and Study Note spans
        en_match = re.search(r'<span[^>]*class=["\']en[^"\']*["\'][^>]*>(.*?)</span>', clean_p, flags=re.DOTALL)
        ko_match = re.search(r'<span[^>]*class=["\']ko[^"\']*["\'][^>]*>(.*?)</span>', clean_p, flags=re.DOTALL)
        note_match = re.search(r'<span[^>]*class=["\']study-note[^"\']*["\'][^>]*>(.*?)</span>', clean_p, flags=re.DOTALL)

        plain_en = en_match.group(1).strip() if en_match else ""
        raw_ko = ko_match.group(1).strip() if ko_match else ""
        raw_note = note_match.group(1).strip() if note_match else ""

        # Extract notes embedded in Korean line
        if "※" in raw_ko:
            parts = raw_ko.split("※", 1)
            raw_ko = parts[0].strip()
            emb = "※" + parts[1].strip()
            raw_note = (raw_note + " ; " + emb) if raw_note else emb

        if edition_type == "e-s_x" and not en_match and not ko_match and "※" in full_p:
            p_inner = re.sub(r"^<p[^>]*>|</p>$", "", clean_p).strip()
            if "※" in p_inner:
                parts = p_inner.split("※", 1)
                plain_en = parts[0].strip()
                raw_note = "※" + parts[1].strip()

        all_pairs = list(ruby_pairs)
        if raw_note:
            n_txt = re.sub(r"※\s*(학림|학습|어휘)?[:\s]*", "", raw_note).strip()
            for item in n_txt.split(";"):
                if "-" in item or ":" in item:
                    s = item.split("-" if "-" in item else ":", 1)
                    w_s = s[0].strip()
                    m_s = s[1].strip()
                    if w_s and m_s:
                        all_pairs.append((w_s, m_s))

        seen = set()
        dedup = []
        for w, mean in all_pairs:
            w_c = re.sub(r"<[^>]+>", "", w).replace("&lt;", "").replace("<", "").strip()
            m_c = re.sub(r"<[^>]+>", "", mean).replace("&lt;", "").replace("<", "").strip()
            if w_c.lower() not in seen and w_c and m_c:
                seen.add(w_c.lower())
                dedup.append((w_c, m_c))

        note_str = " ; ".join(f"{w} - {m}" for w, m in dedup)
        note_html = f'<br /><span class="study-note" xml:lang="ko">※ {html.escape(note_str)}</span>' if note_str else ""

        plain_en = re.sub(r"<br\s*/?>\s*<span class=\"study-note\"[^>]*>.*?</span>", "", plain_en).strip()
        plain_en = re.sub(r"<[^>]+>", "", plain_en).strip()
        raw_ko = re.sub(r"<[^>]+>", "", raw_ko).strip()

        if edition_type == "study_x":
            # 3-Line layout: English -> Korean -> Study Note
            if plain_en and raw_ko:
                return f'<p class="pair"><span class="en" xml:lang="en">{html.escape(plain_en)}</span><br /><span class="ko" xml:lang="ko">{html.escape(raw_ko)}</span>{note_html}</p>'
            elif plain_en:
                return f'<p class="pair"><span class="en" xml:lang="en">{html.escape(plain_en)}</span>{note_html}</p>'
            elif raw_ko:
                return f'<p class="pair"><span class="ko" xml:lang="ko">{html.escape(raw_ko)}</span></p>'
            return clean_p
        else:
            # 2-Line layout (e-s_x): English -> Study Note (No Korean translation)
            clean_en = plain_en or re.sub(r"<[^>]+>", "", clean_p).strip()
            return f'<p><span class="en" xml:lang="en">{html.escape(clean_en)}</span>{note_html}</p>'

    # Process all <p> tags
    return re.sub(r"<p\b[^>]*>.*?</p>", repl_p, html_str, flags=re.DOTALL)

def build_single_xteink_epub_worker(args: tuple[str, str, str]) -> tuple[str, bool, str]:
    src_str, dst_str, edition_type = args
    src_epub = Path(src_str)
    dst_epub = Path(dst_str)

    dst_epub.parent.mkdir(parents=True, exist_ok=True)
    xteink_css = get_xteink_css()

    tmp_file = None
    try:
        data = {}
        with zipfile.ZipFile(src_epub, "r") as zin:
            for it in zin.infolist():
                try:
                    data[it.filename] = zin.read(it.filename)
                except Exception:
                    pass

        if not data:
            return src_epub.name, False, "Empty EPUB"

        # 1. Purge all X-Ray files
        for k in list(data.keys()):
            if "xray" in k.lower() and k.endswith((".xhtml", ".html", ".htm")):
                del data[k]

        # 2. Clean content.opf (manifest and spine)
        for opf_key in [k for k in data.keys() if k.endswith(".opf")]:
            opf_txt = data[opf_key].decode("utf-8", "ignore")
            opf_txt = re.sub(r'<item[^>]*href="[^"]*xray[^"]*"[^>]*/>\s*', '', opf_txt, flags=re.IGNORECASE)
            opf_txt = re.sub(r'<item[^>]*id="[^"]*xray[^"]*"[^>]*/>\s*', '', opf_txt, flags=re.IGNORECASE)
            opf_txt = re.sub(r'<itemref[^>]*idref="[^"]*xray[^"]*"[^>]*/>\s*', '', opf_txt, flags=re.IGNORECASE)
            data[opf_key] = opf_txt.encode("utf-8")

        # 3. Clean nav.xhtml & toc.ncx
        for nav_key in [k for k in data.keys() if "nav" in k.lower() and k.endswith((".xhtml", ".html"))]:
            nav_txt = data[nav_key].decode("utf-8", "ignore")
            nav_txt = re.sub(r'<li\b[^>]*>\s*<a\b[^>]*href="[^"]*xray[^"]*"[^>]*>.*?</a>\s*</li>\s*', '', nav_txt, flags=re.IGNORECASE | re.DOTALL)
            nav_txt = re.sub(r'<li\b[^>]*>\s*<a\b[^>]*>.*?X-Ray.*?</a>\s*</li>\s*', '', nav_txt, flags=re.IGNORECASE | re.DOTALL)
            data[nav_key] = nav_txt.encode("utf-8")

        for ncx_key in [k for k in data.keys() if k.endswith(".ncx")]:
            ncx_txt = data[ncx_key].decode("utf-8", "ignore")
            ncx_txt = re.sub(r'<navPoint\b[^>]*id="[^"]*xray[^"]*"[^>]*>.*?</navPoint>\s*', '', ncx_txt, flags=re.IGNORECASE | re.DOTALL)
            ncx_txt = re.sub(r'<navPoint\b[^>]*>\s*<navLabel>\s*<text>.*?X-Ray.*?</text>\s*</navLabel>\s*<content\b[^>]*src="[^"]*xray[^"]*"[^>]*/>\s*</navPoint>\s*', '', ncx_txt, flags=re.IGNORECASE | re.DOTALL)
            data[ncx_key] = ncx_txt.encode("utf-8")

        # 4. Transform CSS and XHTML for Xteink
        for k in list(data.keys()):
            if k.lower().endswith(".css"):
                data[k] = xteink_css
            elif k.endswith((".xhtml", ".html", ".htm")):
                html_str = data[k].decode("utf-8", errors="replace")
                new_html = transform_html_for_xteink(html_str, edition_type)
                data[k] = new_html.encode("utf-8")

        # 5. Pack EPUB
        fd, tmp_path_str = tempfile.mkstemp(suffix=".epub", dir=dst_epub.parent)
        os.close(fd)
        tmp_file = Path(tmp_path_str)

        with zipfile.ZipFile(tmp_file, "w", zipfile.ZIP_DEFLATED) as zout:
            if "mimetype" in data:
                zout.writestr("mimetype", data.pop("mimetype"), compress_type=zipfile.ZIP_STORED)
            else:
                zout.writestr("mimetype", b"application/epub+zip", compress_type=zipfile.ZIP_STORED)
            for f_name, c_data in data.items():
                zout.writestr(f_name, c_data)

        tmp_file.replace(dst_epub)
        return src_epub.name, True, "BUILT"
    except Exception as e:
        if tmp_file and tmp_file.exists():
            tmp_file.unlink()
        return src_epub.name, False, str(e)

def sanitize_rel_parent(rel: Path) -> Path:
    parts = list(rel.parts)
    sanitized_parts = [p for p in parts if p not in {"[e]", "finished", "non-english", "Uncategorized"}]
    if not sanitized_parts:
        return Path("Literary_General_Fiction")
    return Path(*sanitized_parts)


def xteink_destination(source_epub: Path, source_edition: str, xteink_root: Path) -> Path:
    """Return the canonical dedicated-Xteink destination for one source EPUB.

    The directory names ``[study_x]`` and ``[e-s_x]`` are intentional: they
    distinguish the e-ink layouts from the Kindle-oriented ``[study]`` and
    ``[e-s]`` editions.  Keeping this mapping in one place prevents callers
    from accidentally writing to the obsolete ``[xteink]/[study]`` folders.
    """
    source_root = LIB_ROOT / source_edition
    relative_parent = sanitize_rel_parent(source_epub.parent.relative_to(source_root))
    if source_edition == "[study]":
        clean_stem = re.sub(r"^\[(?:k-e|k|e-s|e|ks|study_|study)\]\s*", "", source_epub.name)
        return xteink_root / "[study_x]" / relative_parent / f"[study] {clean_stem}"
    if source_edition == "[e-s]":
        clean_stem = re.sub(r"^\[(?:k-e|k|e-s|e|ks|study_|study)\]\s*", "", source_epub.name)
        return xteink_root / "[e-s_x]" / relative_parent / f"[e-s] {clean_stem}"
    raise ValueError(f"Unsupported Xteink source edition: {source_edition}")


def build_xteink_book_pair(
    study_epub: Path,
    english_study_epub: Path,
    *,
    xteink_root: Path = XTEINK_ROOT,
) -> tuple[Path, Path]:
    """Build both dedicated Xteink layouts for one completed translation.

    This is the incremental API used by the live translation workflow.  The
    old implementation only exposed the whole-library ``main()`` batch, so a
    newly updated book could leave stale Xteink copies behind indefinitely.
    """
    if not study_epub.is_file():
        raise FileNotFoundError(f"[study] source does not exist: {study_epub}")
    if not english_study_epub.is_file():
        raise FileNotFoundError(f"[e-s] source does not exist: {english_study_epub}")

    destinations = (
        xteink_destination(study_epub, "[study]", xteink_root),
        xteink_destination(english_study_epub, "[e-s]", xteink_root),
    )
    results = []
    for source, destination, edition_type in (
        (study_epub, destinations[0], "study_x"),
        (english_study_epub, destinations[1], "e-s_x"),
    ):
        _name, ok, message = build_single_xteink_epub_worker(
            (str(source), str(destination), edition_type)
        )
        if not ok:
            raise RuntimeError(f"Xteink {edition_type} build failed for {source.name}: {message}")
        results.append(destination)
    return results[0], results[1]

def main():
    t0 = time.time()
    print("==================================================================", flush=True)
    print("🌟 16-WORKER PARALLEL BUILDER FOR DEDICATED [xteink] EDITIONS", flush=True)
    print("   • [study_x]: 3-Line Edition (EN + KO + Study Notes, No Ruby)", flush=True)
    print("   • [e-s_x]  : 2-Line Edition (EN + Study Notes, No KO, No Ruby)", flush=True)
    print("==================================================================", flush=True)

    STUDY_X_ROOT.mkdir(parents=True, exist_ok=True)
    ES_X_ROOT.mkdir(parents=True, exist_ok=True)

    src_study_files = sorted(list((LIB_ROOT / "[study]").rglob("*.epub")))
    src_es_files = sorted(list((LIB_ROOT / "[e-s]").rglob("*.epub")))

    print(f"📚 Source [study] Books: {len(src_study_files):,}", flush=True)
    print(f"📚 Source [e-s] Books  : {len(src_es_files):,}", flush=True)
    print(f"📁 Destination Folder  : {XTEINK_ROOT}\n", flush=True)

    tasks = []

    # 1. Prepare [study_x] tasks
    for src_f in src_study_files:
        if src_f.stat().st_size < 10000:
            continue
        dst_f = xteink_destination(src_f, "[study]", XTEINK_ROOT)
        tasks.append((str(src_f), str(dst_f), "study_x"))

    # 2. Prepare [e-s_x] tasks
    for src_f in src_es_files:
        if src_f.stat().st_size < 10000:
            continue
        dst_f = xteink_destination(src_f, "[e-s]", XTEINK_ROOT)
        tasks.append((str(src_f), str(dst_f), "e-s_x"))

    print(f"🚀 Dispatching {len(tasks):,} Xteink conversion tasks across 16 parallel workers...", flush=True)

    built_study = 0
    built_es = 0
    failed = 0

    with ProcessPoolExecutor(max_workers=16) as ex:
        futures = [ex.submit(build_single_xteink_epub_worker, t) for t in tasks]
        for fut in as_completed(futures):
            name, ok, ed_type = fut.result()
            if ok:
                if "study" in ed_type or "[study]" in name:
                    built_study += 1
                else:
                    built_es += 1
            else:
                failed += 1

    elapsed = time.time() - t0
    print("\n==================================================================", flush=True)
    print(f"🎉 COMPLETED in {elapsed:.1f}s! Successfully built {built_study + built_es:,} Xteink dedicated editions!", flush=True)
    print(f"  • [study_x] 3-Line Editions Built : {built_study:,} books")
    print(f"  • [e-s_x] 2-Line Editions Built   : {built_es:,} books")
    print(f"  • Build Failures                  : {failed} books")
    print("  • Zero Ruby & Zero X-Ray Verified : 100.0% PURE")
    print("==================================================================", flush=True)

if __name__ == "__main__":
    main()
