#!/usr/bin/env python3
"""Lightning-Fast Zero-Remnant Builder for Dedicated [xteink] Editions ([study] & [e-s]).

Completely eliminates all <ruby> / Word Wise tags, nested ruby annotations,
dangling rt remnants, and empty note spans, creating pristine 3-line ([study])
and 2-line ([e-s]) editions dedicated for the Xteink X4 e-reader.

Directories:
- /Users/hyeokjunkong/Desktop/소설2/[xteink]/[study]/
- /Users/hyeokjunkong/Desktop/소설2/[xteink]/[e-s]/
"""

from __future__ import annotations

import html
import os
import re
import sys
import tempfile
import time
import zipfile
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
XTEINK_ROOT = LIB_ROOT / "[xteink]"

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
    for _ in range(10):
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
            break
    return pairs

def transform_html_for_xteink(html_str: str, edition_type: str = "study") -> str:
    def repl_p(m):
        full_p = m.group(0)
        
        # 1. Extract all vocabulary pairs from <ruby> tags
        ruby_pairs = extract_ruby_pairs_regex(full_p)
        
        # 2. Strip ALL <rt>...</rt> tags and <ruby>/<rb> tags completely (Zero Remnants)
        clean_p = re.sub(r"<rt\b[^>]*>.*?</rt>", "", full_p, flags=re.DOTALL)
        clean_p = re.sub(r"</?(ruby|rb)\b[^>]*>", "", clean_p)
        clean_p = re.sub(r"\bhas-ww\b", "", clean_p)
        
        # 3. Locate English, Korean, and legacy Study Note spans
        en_match = re.search(r'<span[^>]*class=["\']en\s*["\'][^>]*>(.*?)</span>', clean_p, flags=re.DOTALL)
        ko_match = re.search(r'<span[^>]*class=["\']ko\s*["\'][^>]*>(.*?)</span>', clean_p, flags=re.DOTALL)
        note_match = re.search(r'<span[^>]*class=["\']study-note\s*["\'][^>]*>(.*?)</span>', clean_p, flags=re.DOTALL)
        
        plain_en = en_match.group(1).strip() if en_match else ""
        raw_ko = ko_match.group(1).strip() if ko_match else ""
        raw_note = note_match.group(1).strip() if note_match else ""
        
        # Extract notes embedded in Korean line
        if "※" in raw_ko:
            parts = raw_ko.split("※", 1)
            raw_ko = parts[0].strip()
            emb = "※" + parts[1].strip()
            raw_note = (raw_note + " ; " + emb) if raw_note else emb
            
        if edition_type == "e-s" and not en_match and not ko_match and "※" in full_p:
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
        
        # Clean plain_en of any trailing <br /> or empty study-notes
        plain_en = re.sub(r"<br\s*/?>\s*<span class=\"study-note\"[^>]*>.*?</span>", "", plain_en).strip()
        plain_en = re.sub(r"<[^>]+>", "", plain_en).strip()
        raw_ko = re.sub(r"<[^>]+>", "", raw_ko).strip()
        
        if edition_type == "study":
            if plain_en and raw_ko:
                return f'<p class="pair"><span class="en" xml:lang="en">{html.escape(plain_en)}</span><br /><span class="ko" xml:lang="ko">{html.escape(raw_ko)}</span>{note_html}</p>'
            elif plain_en:
                return f'<p class="pair"><span class="en" xml:lang="en">{html.escape(plain_en)}</span>{note_html}</p>'
            elif raw_ko:
                return f'<p class="pair"><span class="ko" xml:lang="ko">{html.escape(raw_ko)}</span></p>'
            return clean_p
        else: # e-s
            clean_en = plain_en or re.sub(r"<[^>]+>", "", clean_p).strip()
            return f'<p><span class="en" xml:lang="en">{html.escape(clean_en)}</span>{note_html}</p>'
            
    return re.sub(r"<p\b[^>]*>.*?</p>", repl_p, html_str, flags=re.DOTALL)

def build_single_xteink_epub(src_epub: Path, dst_epub: Path, edition_type: str) -> bool:
    dst_epub.parent.mkdir(parents=True, exist_ok=True)
    xteink_css = get_xteink_css()
    
    tmp_file = None
    try:
        with zipfile.ZipFile(src_epub, "r") as zin:
            in_names = zin.namelist()
            fd, tmp_path_str = tempfile.mkstemp(suffix=".epub", dir=dst_epub.parent)
            os.close(fd)
            tmp_file = Path(tmp_path_str)
            
            with zipfile.ZipFile(tmp_file, "w") as zout:
                zout.comment = zin.comment
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
                        zout.writestr(name, xteink_css, compress_type=zipfile.ZIP_DEFLATED)
                    elif name.endswith((".xhtml", ".html", ".htm")):
                        html_str = data.decode("utf-8", errors="replace")
                        if "000-xray" in name:
                            new_html = re.sub(r"<rt\b[^>]*>.*?</rt>", "", html_str, flags=re.DOTALL)
                            new_html = re.sub(r"</?(ruby|rb)\b[^>]*>", "", new_html)
                            zout.writestr(name, new_html.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
                        else:
                            new_html = transform_html_for_xteink(html_str, edition_type)
                            zout.writestr(name, new_html.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
                    else:
                        zout.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
                        
        tmp_file.replace(dst_epub)
        return True
    except Exception:
        if tmp_file and tmp_file.exists():
            tmp_file.unlink()
        return False

def sanitize_rel_parent(rel: Path) -> Path:
    parts = list(rel.parts)
    sanitized_parts = [p for p in parts if p not in {"[e]", "finished", "non-english", "Uncategorized"}]
    if not sanitized_parts:
        return Path("Literary_General_Fiction")
    return Path(*sanitized_parts)

def main():
    t0 = time.time()
    print("==================================================================", flush=True)
    print("🌟 REBUILDING ZERO-REMNANT DEDICATED [xteink] EDITIONS", flush=True)
    print("==================================================================", flush=True)
    
    src_study_files = sorted(list((LIB_ROOT / "[study]").rglob("*.epub")))
    src_es_files = sorted(list((LIB_ROOT / "[e-s]").rglob("*.epub")))
    
    print(f"📚 Source [study] Books: {len(src_study_files)}", flush=True)
    print(f"📚 Source [e-s] Books:   {len(src_es_files)}", flush=True)
    print(f"📁 Destination Folder:   {XTEINK_ROOT}\n", flush=True)
    
    # 1. Build [xteink]/[study]
    print("🚀 1/2: Building [xteink]/[study] edition...", flush=True)
    study_ok = 0
    for i, src_f in enumerate(src_study_files, 1):
        rel_parent = sanitize_rel_parent(src_f.parent.relative_to(LIB_ROOT / "[study]"))
        clean_stem = re.sub(r"^\[(k-e|k|e-s|e|ks|study_)\]\s*", "", src_f.name)
        if not clean_stem.startswith("[study] "):
            dst_name = f"[study] {clean_stem}"
        else:
            dst_name = clean_stem
        dst_f = XTEINK_ROOT / "[study]" / rel_parent / dst_name
        if build_single_xteink_epub(src_f, dst_f, "study"):
            study_ok += 1
        if i % 100 == 0 or i == len(src_study_files):
            print(f"   -> [xteink]/[study] Progress: {i}/{len(src_study_files)} ({study_ok} built)", flush=True)
            
    # 2. Build [xteink]/[e-s]
    print("\n🚀 2/2: Building [xteink]/[e-s] edition...", flush=True)
    es_ok = 0
    for i, src_f in enumerate(src_es_files, 1):
        rel_parent = sanitize_rel_parent(src_f.parent.relative_to(LIB_ROOT / "[e-s]"))
        clean_stem = re.sub(r"^\[(k-e|k|e-s|e|ks|study_)\]\s*", "", src_f.name)
        if not clean_stem.startswith("[e-s] "):
            dst_name = f"[e-s] {clean_stem}"
        else:
            dst_name = clean_stem
        dst_f = XTEINK_ROOT / "[e-s]" / rel_parent / dst_name
        if build_single_xteink_epub(src_f, dst_f, "e-s"):
            es_ok += 1
        if i % 100 == 0 or i == len(src_es_files):
            print(f"   -> [xteink]/[e-s] Progress: {i}/{len(src_es_files)} ({es_ok} built)", flush=True)
            
    elapsed = time.time() - t0
    print("\n==================================================================", flush=True)
    print(f"🎉 COMPLETED in {elapsed:.1f}s! Successfully created {study_ok + es_ok} Zero-Remnant Xteink X4 editions in {XTEINK_ROOT}!", flush=True)
    print("==================================================================", flush=True)

if __name__ == "__main__":
    main()
