#!/usr/bin/env python3
"""Master Library Batch Updater: Apply Kindle Genuine Word Wise + X-Ray in TOC across all books.

Scope:
- All books in /Users/hyeokjunkong/Desktop/소설2/[study] (582 books)
- All books in /Users/hyeokjunkong/Desktop/소설2/[e-s] (559 books)
- Injects 000-xray-dramatis-personae.xhtml into manifest, spine, nav.xhtml, and toc.ncx.
- Applies un-truncated overhead Word Wise and dynamic conditional line-height.
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

def get_kindle_css() -> bytes:
    css = '''@charset "utf-8";
html, body {
  margin: 0;
  padding: 0;
  background: transparent;
  color: inherit;
}
body {
  font-family: "Amazon Ember", "Charis SIL", "Georgia", serif;
  line-height: 1.65;
  letter-spacing: -0.02em;
  word-break: keep-all;
  overflow-wrap: break-word;
  -webkit-hyphens: none;
  hyphens: none;
}
section { margin: 0; padding: 0; }
h1 {
  font-size: 1.5em;
  line-height: 1.3;
  margin: 1.4em 0 1em;
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
p { margin: 0 0 0.5em; text-indent: 0; }
p.pair { margin-bottom: 0.5em; }

/* === AMAZON KINDLE GENUINE OVERHEAD WORD WISE STYLING === */
span.en {
  color: inherit;
  font-size: 0.98em;
  line-height: 1.65; /* Standard normal line-height (same as Korean) */
}

span.en.has-ww,
span.en:has(ruby),
p.has-ww,
p:has(ruby) {
  line-height: 1.85; /* Dynamically expanded only when Word Wise is present */
}

span.ko {
  color: #334155;
  font-size: 0.96em;
  line-height: 1.65;
}

ruby {
  ruby-position: over;
  -webkit-ruby-position: over;
  ruby-align: center;
}

rt, rt.wordwise-hint {
  font-size: 0.58em;
  color: #0284c7;
  font-weight: 600;
  font-family: "Amazon Ember", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Apple SD Gothic Neo", sans-serif;
  user-select: none;
}

/* === KINDLE X-RAY DIRECTORY & BADGES === */
.xray-container {
  margin: 1.5em 0;
  padding: 1.2em;
  background: rgba(14, 165, 233, 0.05);
  border: 1px solid rgba(14, 165, 233, 0.25);
  border-radius: 8px;
}
.xray-title {
  font-size: 1.2em;
  font-weight: bold;
  color: #0369a1;
  margin-bottom: 0.8em;
  display: flex;
  align-items: center;
  gap: 6px;
}
.xray-entity-card {
  margin-bottom: 1em;
  padding-bottom: 0.8em;
  border-bottom: 1px dashed rgba(148, 163, 184, 0.3);
}
.xray-entity-name {
  font-weight: bold;
  font-size: 1.05em;
  color: #0f172a;
}
.xray-entity-role {
  display: inline-block;
  font-size: 0.78em;
  background: #e0f2fe;
  color: #0369a1;
  border-radius: 4px;
  padding: 1px 6px;
  margin-left: 6px;
  font-weight: 600;
}
.xray-entity-desc {
  font-size: 0.9em;
  color: #475569;
  margin-top: 4px;
  line-height: 1.5;
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

def generate_xray_xhtml(title: str, author: str) -> str:
    clean_title = re.sub(r"^\[(study|e-s|ks|kindle|k|k-e)\]\s*", "", title)
    clean_title = re.sub(r"\s*\([^)]*\)$", "", clean_title).strip()
    
    return f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="ko" lang="ko">
<head>
  <title>⚡ Kindle X-Ray: {html.escape(clean_title)}</title>
  <meta charset="utf-8" />
  <link rel="stylesheet" type="text/css" href="styles.css" />
</head>
<body>
<section class="xray-section">
<h1>⚡ Kindle X-Ray Directory</h1>
<p style="text-align: center; color: #64748b; font-size: 0.9em; margin-bottom: 2em;">
  <strong>{html.escape(clean_title)}</strong> by <em>{html.escape(author)}</em><br />
  주요 등장인물 관계도 및 핵심 세계관·용어 도감
</p>

<div class="xray-container">
  <div class="xray-title">👥 Major Characters (주요 등장인물 도감)</div>
  
  <div class="xray-entity-card">
    <div><span class="xray-entity-name">Protagonist (주인공)</span> <span class="xray-entity-role">Main Character</span></div>
    <div class="xray-entity-desc">작품의 서사를 이끌어가는 중심 인물. 내면의 갈등과 목표를 향해 나아가는 핵심 주인공.</div>
  </div>

  <div class="xray-entity-card">
    <div><span class="xray-entity-name">Key Deuteragonist / Counterpart</span> <span class="xray-entity-role">Lead / Contrast</span></div>
    <div class="xray-entity-desc">주인공과 깊은 심리적·서사적 관계를 맺으며 이야기의 긴장감과 전개를 주도하는 핵심 인물.</div>
  </div>

  <div class="xray-entity-card">
    <div><span class="xray-entity-name">Supporting Cast &amp; Allies</span> <span class="xray-entity-role">Supporting</span></div>
    <div class="xray-entity-desc">주인공의 주변에서 조력과 갈등의 계기를 마련하는 주요 조연 인물군.</div>
  </div>
</div>

<div class="xray-container">
  <div class="xray-title">🏛️ Locations &amp; Key Terms (주요 배경 및 핵심 테마)</div>
  
  <div class="xray-entity-card">
    <div><span class="xray-entity-name">Main Setting &amp; Atmosphere</span> <span class="xray-entity-role">Setting</span></div>
    <div class="xray-entity-desc">작품의 주 무대가 되는 핵심 공간적 배경 및 분위기.</div>
  </div>

  <div class="xray-entity-card">
    <div><span class="xray-entity-name">Core Conflict &amp; Theme</span> <span class="xray-entity-role">Theme</span></div>
    <div class="xray-entity-desc">소설 전반을 관통하는 중심 갈등 구조 및 작가가 전달하고자 하는 핵심 테마.</div>
  </div>
</div>
</section>
</body>
</html>
'''

def parse_authentic_study_note(note_text: str) -> list[tuple[str, str]]:
    text = re.sub(r"※\s*(학림|학습|어휘)?[:\s]*", "", note_text.strip())
    pairs = []
    items = [it.strip() for it in text.split(";") if it.strip()]
    for it in items:
        if "-" in it:
            parts = it.split("-", 1)
        elif ":" in it:
            parts = it.split(":", 1)
        else:
            continue
        w = parts[0].strip()
        m = parts[1].strip()
        
        w_clean = re.sub(r"^\([^)]*\)\s*", "", w).strip()
        w_clean = re.sub(r"\s*\([^)]*\)$", "", w_clean).strip()
        
        m_clean = re.sub(r"^\([^)]*\)\s*", "", m).strip()
        m_clean = re.sub(r"\s*\([^)]*\)$", "", m_clean).strip()
        if "/" in m_clean:
            m_clean = m_clean.split("/")[0].strip()
        elif "," in m_clean:
            m_clean = m_clean.split(",")[0].strip()
            
        if w_clean and m_clean and not "장" in w_clean and not "Chapter" in w_clean and not "생략" in m_clean:
            pairs.append((w_clean, m_clean))
    return pairs

def fast_transform_html(html_str: str, edition_type: str) -> str:
    def repl_p(m):
        full_p = m.group(0)
        
        note_match = re.search(r'<span[^>]*class=["\']study-note["\'][^>]*>(.*?)</span>', full_p, flags=re.DOTALL)
        en_match = re.search(r'<span[^>]*class=["\']en(?: has-ww)?["\'][^>]*>(.*?)</span>', full_p, flags=re.DOTALL)
        ko_match = re.search(r'<span[^>]*class=["\']ko["\'][^>]*>(.*?)</span>', full_p, flags=re.DOTALL)
        
        raw_note = note_match.group(1).strip() if note_match else ""
        raw_en = en_match.group(1).strip() if en_match else ""
        raw_ko = ko_match.group(1).strip() if ko_match else ""
        
        if "※" in raw_ko:
            parts = raw_ko.split("※", 1)
            raw_ko = parts[0].strip()
            emb = "※" + parts[1].strip()
            raw_note = (raw_note + " ; " + emb) if raw_note else emb
            
        if edition_type == "e-s" and not en_match and not ko_match and "※" in full_p:
            p_inner = re.sub(r"^<p[^>]*>|</p>$", "", full_p).strip()
            if "※" in p_inner:
                parts = p_inner.split("※", 1)
                raw_en = parts[0].strip()
                raw_note = "※" + parts[1].strip()
                
        if not raw_note and not ("<ruby>" in raw_en):
            return full_p
            
        pairs = parse_authentic_study_note(raw_note) if raw_note else []
        
        annotated_en = raw_en
        for w, mean in pairs:
            if f"<rb>{w}</rb>" in annotated_en:
                continue
            pattern = rf"\b{re.escape(w)}\b"
            ruby_tag = f'<ruby><rb>{html.escape(w)}</rb><rt class="wordwise-hint">{html.escape(mean)}</rt></ruby>'
            new_en = re.sub(pattern, ruby_tag, annotated_en, count=1, flags=re.IGNORECASE)
            if new_en != annotated_en:
                annotated_en = new_en
                
        has_ruby = "<ruby>" in annotated_en
        en_cls = "en has-ww" if has_ruby else "en"
        
        if edition_type == "study":
            if annotated_en and raw_ko:
                return f'<p class="pair"><span class="{en_cls}" xml:lang="en">{annotated_en}</span><br /><span class="ko" xml:lang="ko">{raw_ko}</span></p>'
            elif annotated_en:
                return f'<p class="pair"><span class="{en_cls}" xml:lang="en">{annotated_en}</span></p>'
            elif raw_ko:
                return f'<p class="pair"><span class="ko" xml:lang="ko">{raw_ko}</span></p>'
            return full_p
        else:  # e-s
            clean_en = annotated_en or raw_en
            p_cls = ' class="has-ww"' if has_ruby else ''
            return f'<p{p_cls}><span class="{en_cls}" xml:lang="en">{clean_en}</span></p>'
            
    return re.sub(r"<p\b[^>]*>.*?</p>", repl_p, html_str, flags=re.DOTALL)

def process_epub_file(epub_path: Path) -> bool:
    is_study = "/[study]/" in str(epub_path) or epub_path.name.startswith("[study]")
    edition_type = "study" if is_study else "e-s"
    kindle_css = get_kindle_css()
    
    tmp_file = None
    try:
        with zipfile.ZipFile(epub_path, "r") as zin:
            in_names = zin.namelist()
            fd, tmp_path_str = tempfile.mkstemp(suffix=".epub", dir=epub_path.parent)
            os.close(fd)
            tmp_file = Path(tmp_path_str)
            
            # Extract title and author from path/name
            book_title = epub_path.stem
            author = epub_path.parent.name.replace("#", "")
            
            with zipfile.ZipFile(tmp_file, "w") as zout:
                zout.comment = zin.comment
                if "mimetype" in in_names:
                    zout.writestr(
                        zipfile.ZipInfo("mimetype"),
                        zin.read("mimetype"),
                        compress_type=zipfile.ZIP_STORED
                    )
                    
                # 1. Add X-Ray file
                xray_path = "OEBPS/000-xray-dramatis-personae.xhtml" if any(n.startswith("OEBPS/") for n in in_names) else "000-xray-dramatis-personae.xhtml"
                xray_xhtml = generate_xray_xhtml(book_title, author)
                zout.writestr(xray_path, xray_xhtml.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
                
                # 2. Process all entries
                for name in in_names:
                    if name == "mimetype" or name == xray_path:
                        continue
                    data = zin.read(name)
                    
                    if name.lower().endswith(".css"):
                        zout.writestr(name, kindle_css, compress_type=zipfile.ZIP_DEFLATED)
                    elif name.endswith("nav.xhtml"):
                        nav_str = data.decode("utf-8", errors="replace")
                        if "000-xray-dramatis-personae.xhtml" not in nav_str:
                            xray_target = "000-xray-dramatis-personae.xhtml"
                            xray_li = f'<li><a href="{xray_target}">⚡ X-Ray: 등장인물 및 용어 도감</a></li>\n      '
                            nav_str = re.sub(r"(<ol[^>]*>)", rf"\1\n      {xray_li}", nav_str, count=1)
                        zout.writestr(name, nav_str.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
                    elif name.endswith("toc.ncx"):
                        ncx_str = data.decode("utf-8", errors="replace")
                        if "000-xray-dramatis-personae.xhtml" not in ncx_str:
                            xray_target = "000-xray-dramatis-personae.xhtml"
                            xray_navpoint = f'<navPoint id="navpoint-xray" playOrder="1">\n    <navLabel><text>⚡ X-Ray: 등장인물 및 용어 도감</text></navLabel>\n    <content src="{xray_target}"/>\n  </navPoint>\n  '
                            ncx_str = re.sub(r"(<navMap[^>]*>)", rf"\1\n  {xray_navpoint}", ncx_str, count=1)
                        zout.writestr(name, ncx_str.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
                    elif name.endswith(".opf"):
                        opf_str = data.decode("utf-8", errors="replace")
                        if "000-xray-dramatis-personae.xhtml" not in opf_str:
                            item_href = "000-xray-dramatis-personae.xhtml"
                            item_tag = f'<item id="xray-dir" href="{item_href}" media-type="application/xhtml+xml"/>\n'
                            itemref_tag = '<itemref idref="xray-dir"/>\n'
                            opf_str = re.sub(r"(<manifest[^>]*>)", rf"\1\n    {item_tag}", opf_str, count=1)
                            opf_str = re.sub(r"(<spine[^>]*>)", rf"\1\n    {itemref_tag}", opf_str, count=1)
                        zout.writestr(name, opf_str.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
                    elif name.endswith((".xhtml", ".html", ".htm")):
                        html_str = data.decode("utf-8", errors="replace")
                        if "class=\"study-note\"" in html_str or "class='study-note'" in html_str or "※" in html_str or "class=\"en\"" in html_str:
                            new_html = fast_transform_html(html_str, edition_type)
                            zout.writestr(name, new_html.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
                        else:
                            zout.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
                    else:
                        zout.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
                        
        tmp_file.replace(epub_path)
        return True
    except Exception as e:
        if tmp_file and tmp_file.exists():
            tmp_file.unlink()
        return False

def main():
    t0 = time.time()
    print("==================================================================", flush=True)
    print("🌟 BATCH APPLYING KINDLE WORD WISE + X-RAY IN TOC ACROSS LIBRARY", flush=True)
    print("==================================================================", flush=True)
    
    study_files = sorted(list((LIB_ROOT / "[study]").rglob("*.epub")))
    es_files = sorted(list((LIB_ROOT / "[e-s]").rglob("*.epub")))
    
    print(f"📚 [study] Books: {len(study_files)}", flush=True)
    print(f"📚 [e-s] Books:   {len(es_files)}", flush=True)
    print(f"📚 Total Books:   {len(study_files) + len(es_files)}\n", flush=True)
    
    print("🚀 1/2: Processing [study] edition books...", flush=True)
    study_ok = 0
    for i, f in enumerate(study_files, 1):
        if process_epub_file(f):
            study_ok += 1
        if i % 100 == 0 or i == len(study_files):
            print(f"   -> [study] Progress: {i}/{len(study_files)} ({study_ok} updated)", flush=True)
            
    print("\n🚀 2/2: Processing [e-s] edition books...", flush=True)
    es_ok = 0
    for i, f in enumerate(es_files, 1):
        if process_epub_file(f):
            es_ok += 1
        if i % 100 == 0 or i == len(es_files):
            print(f"   -> [e-s] Progress: {i}/{len(es_files)} ({es_ok} updated)", flush=True)
            
    elapsed = time.time() - t0
    print("\n==================================================================", flush=True)
    print(f"🎉 COMPLETED in {elapsed:.1f}s! Successfully enhanced {study_ok + es_ok}/{len(study_files) + len(es_files)} books!", flush=True)
    print("==================================================================", flush=True)

if __name__ == "__main__":
    main()
