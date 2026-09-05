#!/usr/bin/env python3
"""Build Amazon Kindle Genuine Word Wise [ks] (Kindle Study) Edition.

Rules Enforced:
1. ONLY use authentic AI-generated study notes (※ 단어 - 문맥 뜻) from the new version translation.
2. 100% Amazon Kindle Genuine Word Wise Layout:
   - Word Wise hint sits directly ABOVE (overhead) the English word.
   - Expanded line-height (2.2) on English text to provide elegant vertical breathing room.
   - Distinct, clean typography with slate/sky-blue (#0284c7) 0.58em hint font.
3. Streamlined 2-Line Layout:
   - Line 1: English original with overhead Word Wise hints.
   - Line 2: Korean contextual translation.
   - Line 3 (separate ※ notes): Completely removed & integrated directly into words.
4. Kindle X-Ray Directory (000-xray-dramatis-personae.xhtml) & Master Styling.
"""

from __future__ import annotations

import html
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from audiobook_studio.epub_xray_policy import purge_xray_from_epub

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

def kindle_study_styles_css() -> str:
    return '''@charset "utf-8";
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
p { margin: 0 0 0.6em; text-indent: 0; }
p.pair { margin-bottom: 0.65em; }

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

def generate_xray_xhtml(book_title: str, author: str) -> str:
    return '''<?xml version="1.0" encoding="utf-8"?>
<html lang="en" xml:lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
<title>X-Ray: Characters &amp; Key Terms</title>
<meta charset="utf-8"/>
<link href="styles.css" rel="stylesheet" type="text/css"/>
</head>
<body>
<section epub:type="frontmatter">
<h1>⚡ Kindle X-Ray Directory</h1>
<div class="xray-container">
  <div class="xray-title">👥 Major Characters (등장인물 사전)</div>
  
  <div class="xray-entity-card">
    <div><span class="xray-entity-name">Ivory (Emeri Connors)</span> <span class="xray-entity-role">Protagonist</span></div>
    <div class="xray-entity-desc">17세 피아노 영재 소녀. 어두운 과거와 가정 폭력의 학대 속에서도 뉴욕 음악원에 입학하여 피아노에 모든 열정을 바치는 비운의 천재 피아니스트.</div>
  </div>

  <div class="xray-entity-card">
    <div><span class="xray-entity-name">Lorenzo Gandara</span> <span class="xray-entity-role">Maestro / Mentor</span></div>
    <div class="xray-entity-desc">뉴욕 음악원의 엄격하고 압도적인 천재 거장 음악 교수이자 지휘자. 아이보리의 천부적인 재능을 발견하고 그녀를 보호하며 어둡고 강렬한 집착과 사랑에 빠지게 된다.</div>
  </div>

  <div class="xray-entity-card">
    <div><span class="xray-entity-name">Santiago</span> <span class="xray-entity-role">Supporting</span></div>
    <div class="xray-entity-desc">음악원과 교향악단 주변 인물. 갈등과 조력을 동시에 제공하는 핵심 인물.</div>
  </div>
</div>

<div class="xray-container">
  <div class="xray-title">🏛️ Locations &amp; Key Terms (주요 장소 및 용어)</div>
  
  <div class="xray-entity-card">
    <div><span class="xray-entity-name">Manhattan Symphony &amp; Conservatory</span> <span class="xray-entity-role">Setting</span></div>
    <div class="xray-entity-desc">작품의 주요 무대가 되는 뉴욕 최고의 클래식 음악원 및 교향악단 공연장.</div>
  </div>

  <div class="xray-entity-card">
    <div><span class="xray-entity-name">Chopin Etudes &amp; Dark Nocturnes</span> <span class="xray-entity-role">Theme</span></div>
    <div class="xray-entity-desc">아이보리와 로렌조의 감정과 고통, 집착이 건반을 통해 폭발하는 핵심 클래식 악곡 테마.</div>
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

        # Clean word
        w_clean = re.sub(r"^\([^)]*\)\s*", "", w).strip()
        w_clean = re.sub(r"\s*\([^)]*\)$", "", w_clean).strip()

        # Clean meaning: preserve complete natural phrases without hard length slicing
        m_clean = re.sub(r"^\([^)]*\)\s*", "", m).strip()
        m_clean = re.sub(r"\s*\([^)]*\)$", "", m_clean).strip()
        if "/" in m_clean:
            m_clean = m_clean.split("/")[0].strip()
        elif "," in m_clean:
            m_clean = m_clean.split(",")[0].strip()

        if w_clean and m_clean and not "장" in w_clean and not "Chapter" in w_clean and not "생략" in m_clean:
            pairs.append((w_clean, m_clean))
    return pairs

def convert_study_to_ks_chapter(html_content: str) -> tuple[str, int]:
    soup = BeautifulSoup(html_content, "html.parser")
    total_hints = 0

    for p in soup.find_all("p"):
        en_span = p.find("span", class_="en")
        ko_span = p.find("span", class_="ko")
        note_span = p.find("span", class_="study-note")

        if not en_span and not ko_span:
            continue

        en_text = en_span.get_text().strip() if en_span else ""
        ko_text = ko_span.get_text().strip() if ko_span else ""
        note_text = note_span.get_text().strip() if note_span else ""

        # Also extract any study notes embedded inside ko_text (e.g. ※학림:, ※...)
        if "※" in ko_text:
            parts = ko_text.split("※", 1)
            ko_text = parts[0].strip()
            embedded_note = "※" + parts[1].strip()
            note_text = (note_text + " ; " + embedded_note) if note_text else embedded_note

        pairs = parse_authentic_study_note(note_text) if note_text else []

        # Annotate English text with authentic AI Word Wise ruby tags
        annotated_en = html.escape(en_text)
        for w, m in pairs:
            pattern = rf"\b{re.escape(w)}\b"
            ruby_tag = f'<ruby><rb>{html.escape(w)}</rb><rt class="wordwise-hint">{html.escape(m)}</rt></ruby>'
            new_text = re.sub(pattern, ruby_tag, annotated_en, count=1, flags=re.IGNORECASE)
            if new_text != annotated_en:
                annotated_en = new_text
                total_hints += 1

        # Construct clean [ks] paragraph: English (with Word Wise) + Korean (No separate study note)
        has_ruby = "<ruby>" in annotated_en
        en_cls = "en has-ww" if has_ruby else "en"
        p_html = '<p class="pair">'
        if en_text and ko_text:
            p_html += f'<span class="{en_cls}" xml:lang="en">{annotated_en}</span><br /><span class="ko" xml:lang="ko">{html.escape(ko_text)}</span>'
        elif en_text:
            p_html += f'<span class="{en_cls}" xml:lang="en">{annotated_en}</span>'
        elif ko_text:
            p_html += f'<span class="ko" xml:lang="ko">{html.escape(ko_text)}</span>'
        p_html += '</p>'

        new_p = BeautifulSoup(p_html, "html.parser").p
        p.replace_with(new_p)

    return str(soup), total_hints

def build_ks_edition(study_epub: Path, output_epub: Path) -> dict:
    print(f"📖 Building Amazon Kindle Genuine Word Wise [ks] Edition from: {study_epub.name}")
    print(f"   -> Destination: {output_epub.name}")

    total_hints_injected = 0
    tmp_file = None

    try:
        with zipfile.ZipFile(study_epub, "r") as zin:
            in_names = zin.namelist()
            fd, tmp_path_str = tempfile.mkstemp(suffix=".epub", dir=output_epub.parent)
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

                # 1. Add X-Ray Directory
                xray_xhtml = generate_xray_xhtml("Dark Notes", "Pam Godwin")
                zout.writestr("OEBPS/000-xray-dramatis-personae.xhtml", xray_xhtml.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)

                # 2. Add Kindle Study Styles CSS (Overhead Word Wise)
                zout.writestr("OEBPS/styles.css", kindle_study_styles_css().encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)

                # 3. Process Chapter XHTMLs and OPF
                for name in in_names:
                    if name in ["mimetype", "OEBPS/styles.css"]:
                        continue
                    data = zin.read(name)

                    if name.endswith("nav.xhtml"):
                        nav_str = data.decode("utf-8", errors="replace")
                        if "000-xray-dramatis-personae.xhtml" not in nav_str:
                            xray_li = '<li><a href="000-xray-dramatis-personae.xhtml">⚡ X-Ray: 등장인물 및 용어 도감</a></li>\n      '
                            nav_str = re.sub(r"(<ol[^>]*>)", rf"\1\n      {xray_li}", nav_str, count=1)
                        data = nav_str.encode("utf-8")

                    elif name.endswith("toc.ncx"):
                        ncx_str = data.decode("utf-8", errors="replace")
                        if "000-xray-dramatis-personae.xhtml" not in ncx_str:
                            xray_navpoint = '<navPoint id="navpoint-xray" playOrder="1">\n    <navLabel><text>⚡ X-Ray: 등장인물 및 용어 도감</text></navLabel>\n    <content src="000-xray-dramatis-personae.xhtml"/>\n  </navPoint>\n  '
                            ncx_str = re.sub(r"(<navMap[^>]*>)", rf"\1\n  {xray_navpoint}", ncx_str, count=1)
                        data = ncx_str.encode("utf-8")

                    elif name.endswith((".xhtml", ".html", ".htm")):
                        html_str = data.decode("utf-8", errors="replace")
                        if "class=\"study-note\"" in html_str or "class='study-note'" in html_str or "class=\"en\"" in html_str:
                            new_html, hints_cnt = convert_study_to_ks_chapter(html_str)
                            total_hints_injected += hints_cnt
                            data = new_html.encode("utf-8")

                    elif name.endswith(".opf"):
                        opf_str = data.decode("utf-8", errors="replace")
                        opf_str = re.sub(r"<dc:title>\[study\]", "<dc:title>[ks]", opf_str)
                        opf_str = re.sub(r"<dc:title>", "<dc:title>[ks] ", opf_str) if "[ks]" not in opf_str else opf_str

                        if "000-xray-dramatis-personae.xhtml" not in opf_str:
                            item_tag = '<item id="xray-dir" href="000-xray-dramatis-personae.xhtml" media-type="application/xhtml+xml"/>\n'
                            itemref_tag = '<itemref idref="xray-dir"/>\n'
                            opf_str = re.sub(r"(<manifest[^>]*>)", rf"\1\n    {item_tag}", opf_str, count=1)
                            opf_str = re.sub(r"(<spine[^>]*>)", rf"\1\n    {itemref_tag}", opf_str, count=1)
                        data = opf_str.encode("utf-8")

                    zout.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)

        tmp_file.replace(output_epub)
        purge_xray_from_epub(output_epub)
        print(f"🎉 Genuine Word Wise [ks] Edition Created: {output_epub.name}")
        print(f"   • File Size: {output_epub.stat().st_size:,} bytes")
        print(f"   • Authentic AI Word Wise Hints: {total_hints_injected:,} hints")
        print("   • Overhead Layout: Amazon Kindle Genuine Layout Enforced ✅")
        print("   • Separate Study Notes: Completely removed & streamlined ✅")
        return {
            "success": True,
            "output_path": str(output_epub),
            "hints": total_hints_injected
        }
    except Exception as e:
        print(f"❌ Error creating [ks] edition: {e}", file=sys.stderr)
        if tmp_file and tmp_file.exists():
            tmp_file.unlink()
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    study_p = LIB_ROOT / "new books from vk - account2" / "[study] Dark Notes Pam Godwin (3.92).epub"
    out_p = LIB_ROOT / "new books from vk - account2" / "[ks] Dark Notes Pam Godwin (3.92).epub"
    build_ks_edition(study_p, out_p)
