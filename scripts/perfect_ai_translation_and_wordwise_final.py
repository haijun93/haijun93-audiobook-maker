#!/usr/bin/env python3
"""scripts/perfect_ai_translation_and_wordwise_final.py

Combines:
1. 100% High-quality Korean literature translation for prologue and chapter 1.
2. 100% Authentic Gemini AI contextual study notes filtered strictly for TOEIC 700+ to 990 learners.
   (Excludes middle school basic words like 'hell', 'words', 'teeth', 'smile'...)
   (Preserves high-yield expressions: Starling: 찌르레기, plummet: 곤두박질치다, musty: 퀴퀴한, threshold: 문턱, unfixable: 돌이킬 수 없는...)
3. Full rebuild across all 4 editions ([study], [e-s], [k-e], [k]).
"""

from __future__ import annotations

import html
import io
import json
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from audiobook_studio.study_filter import is_valid_toeic_700_plus_target

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
CACHE_DIR = LIB_ROOT / "_chatgpt_translate_work" / "vk_dark__tears-of-tess-pepper-winters"
TRANSLATIONS_DIR = CACHE_DIR / "translations"
SOURCE_SECTIONS = CACHE_DIR / "source_sections.json"

STUDY_EPUB = LIB_ROOT / "[study]" / "#Top 10 dark romance" / "[study] Tears of Tess - Pepper Winters.epub"
ES_EPUB = LIB_ROOT / "[e-s]" / "#Top 10 dark romance" / "[e-s] Tears of Tess - Pepper Winters.epub"
KE_EPUB = LIB_ROOT / "[k-e]" / "#Top 10 dark romance" / "[k-e] Tears of Tess - Pepper Winters.epub"
K_EPUB = LIB_ROOT / "[k]" / "#Top 10 dark romance" / "[k] Tears of Tess - Pepper Winters.epub"

FRONTMATTER_KO = {
    "T hree little words.": "단 세 마디 말.",
    "Three little words.": "단 세 마디 말.",
    "If anyone asked what I was most afraid of, what terrified me, stole my breath, and made my life flicker before my eyes, I would say three little words.":
    "내가 무엇을 가장 두려워하는지, 무엇이 나를 공포에 떨게 하고 숨을 멎게 하며 내 인생을 주마등처럼 스쳐 지나가게 만드는지 묻는다면, 나는 단 세 마디 말이라고 답할 것이다.",
    "How could my perfect life plummet so far into hell?":
    "어떻게 나의 완벽했던 삶이 이토록 지옥 밑바닥으로 곤두박질칠 수 있었을까?",
    "How could my love for Brax twist so far into unfixable?":
    "어떻게 브랙스를 향한 나의 사랑이 돌이킬 수 없을 정도로 뒤틀려버릴 수 있었을까?",
    "The black musty hood over my head suffocated my thoughts, and I sat with hands bound behind my back. Twine rubbed my wrists with hungry stringed teeth, ready to bleed me dry in this new existence.":
    "머리에 뒤집어쓴 퀴퀴한 검은 두건이 내 숨을 턱턱 막히게 했고, 나는 등 뒤로 두 손이 묶인 채 웅크리고 앉아 있었다. 거친 노끈이 굶주린 톱니처럼 내 손목을 파고들며, 이 새로운 지옥에서 내 피를 말려버릴 기세였다.",
    "*Starling*": "찌르레기 (Starling)",
    "“ W here are you taking me, Brax?” I giggled as my boyfriend of two years beamed his slightly crooked smile and plucked my suitcase from my hands.":
    "“어디로 날 데려가는 거야, 브랙스?” 2년 동안 사귄 남자친구가 특유의 비뚤어진 미소를 지으며 내 손에서 여행 가방을 낚아채자 나는 쿡쿡 웃음을 터뜨렸다.",
    "We crossed the threshold of the airport and nerves of excitement fluttered in my stomach.":
    "우리는 공항 문턱을 넘어섰고, 내 뱃속에서는 흥분된 설렘이 나비처럼 팔딱거렸다.",
    "A week ago, Brax surprised me with a romantic dinner and an envelope. I grabbed him and squeezed him half to death when I pulled free two airplane tickets with the destinations blacked out by a marker.":
    "일주일 전, 브랙스는 로맨틱한 저녁 식사와 편지 봉투로 나를 놀라게 했다. 매직으로 목적지가 가려진 비행기 표 두 장을 꺼냈을 때, 나는 그를 끌어안고 숨이 막힐 정도로 세게 껴안았었다.",
    "My perfect, sweet boyfriend, Brax Cliffingstone was taking me somewhere exotic. And that meant connection, sex, fun. Things I sorely needed.":
    "나의 완벽하고 다정한 남자친구 브랙스 클리핑스톤이 나를 이국적인 곳으로 데려가고 있었다. 그것은 교감, 사랑, 그리고 즐거움을 의미했다. 내게 절실히 필요했던 것들이었다."
}

CHAPTER_NAMES = {
    0: "판권 및 도서 정보 (Title Page & Copyright)",
    1: "헌사 (Dedication)",
    2: "프롤로그: 세 마디 말 (Prologue: Three Little Words)",
    3: "제1장: 찌르레기 (Chapter 1: Starling)",
    4: "제2장: 푸른어치 (Chapter 2: Blue Jay)",
    5: "제3장: 로빈 (Chapter 3: Robin)",
    6: "제4장: 비둘기 (Chapter 4: Dove)",
    7: "제5장: 부채꼬리새 (Chapter 5: Fantail)",
    8: "제6장: 올빼미 (Chapter 6: Owl)",
    9: "제7장: 나이팅게일 (Chapter 7: Nightingale)",
    10: "제8장: 참새 (Chapter 8: Sparrow)",
    11: "제9장: 흑지빠귀 (Chapter 9: Blackbird)",
    12: "제10장: 제비 (Chapter 10: Swallow)",
    13: "제11장: 종달새 (Chapter 11: Skylark)",
    14: "제12장: 굴뚝새 (Chapter 12: Wren)",
    15: "제13장: 핀치 (Chapter 13: Finch)",
    16: "제14장: 벌새 (Chapter 14: Hummingbird)",
    17: "제15장: 왜가리 (Chapter 15: Heron)",
    18: "제16장: 집비둘기 (Chapter 16: Pigeon)",
    19: "제17장: 메추라기 (Chapter 17: Quail)",
    20: "제18장: 백조 (Chapter 18: Swan)",
    21: "제19장: 방울새 (Chapter 19: Goldfinch)",
    22: "제20장: 제비갈매기 (Chapter 20: Tern)",
    23: "제21장: 꿩 (Chapter 21: Pheasant)",
    24: "제22장: 종새 (Chapter 22: Bell Bird)",
    25: "제23장: 딱따구리 (Chapter 23: Woodpecker)",
    26: "제24장: 물총새 (Chapter 24: Kingfisher)",
    27: "제25장: 큐 머서 (Chapter 25: Q Mercer)",
    28: "에필로그 (Epilogue)",
    29: "다음 권 미리보기 (Sneak Peek: Quintessentially Q)",
    30: "작가 소개 (About Pepper Winters)",
    31: "감사의 글 (Acknowledgments)",
    32: "영감을 준 플레이리스트 (Inspired Playlist)"
}

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

def parse_authentic_notes(note_str: str) -> list[tuple[str, str]]:
    if not note_str: return []
    clean = re.sub(r'^[※\s*•\-]+', '', note_str).strip()
    items = re.split(r'[;\n\r]+', clean)
    pairs = []
    for item in items:
        item = item.strip()
        if not item: continue
        parts = re.split(r'\s*[-–—:]\s*', item, maxsplit=1)
        if len(parts) == 2:
            w, m = parts[0].strip(), parts[1].strip()
            if w and m and not re.search(r'[가-힣]', w):
                # Filter strictly for TOEIC 700+ to 990
                if is_valid_toeic_700_plus_target(w):
                    m_clean = re.sub(r'^\(.*?\)\s*', '', m).strip()
                    pairs.append((w, m_clean or m))
    return pairs

def annotate_authentic(en_text: str, note_str: str) -> tuple[str, bool]:
    word_pairs = parse_authentic_notes(note_str)
    if not word_pairs:
        return en_text, False
        
    annotated = en_text
    has_ruby = False
    
    # Cap at 2 high-yield terms per paragraph to prevent visual clutter
    for w, m in word_pairs[:2]:
        pattern = re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE)
        match = pattern.search(annotated)
        if match and "<ruby>" not in match.group(0):
            orig_word = match.group(0)
            ruby_tag = f'<ruby><rb>{html.escape(orig_word)}</rb><rt class="wordwise-hint">{html.escape(m)}</rt></ruby>'
            annotated = pattern.sub(ruby_tag, annotated, count=1)
            has_ruby = True
            
    return annotated, has_ruby

def run_master_build():
    print("==================================================================")
    print("💎 TOEIC 700~990 TARGETED AUTHENTIC BUILD: TEARS OF TESS")
    print("==================================================================")
    
    src_data = json.loads(SOURCE_SECTIONS.read_text(encoding="utf-8"))
    sections = src_data.get("sections", [])
    
    translations = {}
    for j in sorted(TRANSLATIONS_DIR.glob("chunk_*.json")):
        data = json.loads(j.read_text(encoding="utf-8"))
        for bid, line_str in data.get("translations", {}).items():
            if isinstance(line_str, str):
                parts = re.split(r'※(?:학습|어휘|공부|노트)?[:：\s]*', line_str, maxsplit=1)
                ko = parts[0].strip()
                note = parts[1].strip() if len(parts) > 1 else ""
                translations[bid] = (ko, note)
                
    base_files = {}
    with zipfile.ZipFile(KE_EPUB, "r") as z:
        for n in z.namelist():
            base_files[n] = z.read(n)
    xray_data = base_files.get("OEBPS/000-xray-dramatis-personae.xhtml", b"")
    
    study_chapters = {}
    es_chapters = {}
    ke_chapters = {}
    k_chapters = {}
    total_rubies = 0
    
    for idx, sec in enumerate(sections):
        ch_title = CHAPTER_NAMES.get(idx, f"제{idx+1}장")
        fname = f"OEBPS/chapter_{idx:03d}.xhtml"
        
        study_pairs = []
        es_pairs = []
        ke_pairs = []
        k_pairs = []
        
        for b in sec.get("blocks", []):
            bid = b.get("id")
            en_txt = b.get("text", "").strip()
            if not en_txt: continue
            
            ai_ko, ai_note = translations.get(bid, ("", ""))
            
            if not ai_ko or not re.search(r'[가-힣]', ai_ko):
                for k_src, v_ko in FRONTMATTER_KO.items():
                    if k_src in en_txt or en_txt.startswith(k_src[:30]):
                        ai_ko = v_ko
                        break
                        
            ann_en, has_rb = annotate_authentic(en_txt, ai_note)
            if has_rb:
                total_rubies += ann_en.count("<ruby>")
                
            en_cls = "en has-ww" if has_rb else "en"
            p_cls = "pair has-ww" if has_rb else "pair"
            
            # Study pair
            if ai_ko:
                study_pairs.append(f'<p class="{p_cls}"><span class="{en_cls}" xml:lang="en">{ann_en}</span><br/><span class="ko" xml:lang="ko">{html.escape(ai_ko)}</span></p>')
            else:
                study_pairs.append(f'<p class="{p_cls}"><span class="{en_cls}" xml:lang="en">{ann_en}</span></p>')
                
            # ES pair
            es_pairs.append(f'<p class="{p_cls}"><span class="{en_cls}" xml:lang="en">{ann_en}</span></p>')
            
            # KE pair
            if ai_ko:
                ke_pairs.append(f'<p class="pair"><span class="en" xml:lang="en">{html.escape(en_txt)}</span><br/><span class="ko" xml:lang="ko">{html.escape(ai_ko)}</span></p>')
            else:
                ke_pairs.append(f'<p class="pair"><span class="en" xml:lang="en">{html.escape(en_txt)}</span></p>')
                
            # K pair
            if ai_ko:
                k_pairs.append(f'<p class="pair"><span class="ko" xml:lang="ko">{html.escape(ai_ko)}</span></p>')
            else:
                k_pairs.append(f'<p class="pair"><span class="ko" xml:lang="ko">{html.escape(en_txt)}</span></p>')
                
        def make_doc(title_str, p_list):
            return f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="ko" xml:lang="ko">
<head>
  <title>{html.escape(title_str)}</title>
  <link rel="stylesheet" type="text/css" href="styles.css" />
</head>
<body>
  <section epub:type="chapter">
    <h1>{html.escape(title_str)}</h1>
{chr(10).join(p_list)}
  </section>
</body>
</html>'''

        study_chapters[fname] = make_doc(ch_title, study_pairs).encode("utf-8")
        es_chapters[fname] = make_doc(ch_title, es_pairs).encode("utf-8")
        ke_chapters[fname] = make_doc(ch_title, ke_pairs).encode("utf-8")
        k_chapters[fname] = make_doc(ch_title, k_pairs).encode("utf-8")

    # Build TOC & Nav
    nav_items = ['        <li><a href="000-xray-dramatis-personae.xhtml">⚡ X-Ray: 등장인물 및 용어 도감 (Dramatis Personae)</a></li>']
    ncx_items = ['''    <navPoint id="navPoint-1" playOrder="1">
      <navLabel><text>⚡ X-Ray: 등장인물 및 용어 도감 (Dramatis Personae)</text></navLabel>
      <content src="000-xray-dramatis-personae.xhtml"/>
    </navPoint>''']
    
    order = 2
    for idx in range(len(sections)):
        t = CHAPTER_NAMES.get(idx, f"제{idx+1}장")
        href = f"chapter_{idx:03d}.xhtml"
        nav_items.append(f'        <li><a href="{href}">{t}</a></li>')
        ncx_items.append(f'''    <navPoint id="navPoint-{order}" playOrder="{order}">
      <navLabel><text>{t}</text></navLabel>
      <content src="{href}"/>
    </navPoint>''')
        order += 1
        
    nav_html = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
  <title>목차 (Table of Contents)</title>
  <link rel="stylesheet" type="text/css" href="styles.css" />
</head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>목차 (Table of Contents)</h1>
    <ol>
{chr(10).join(nav_items)}
    </ol>
  </nav>
</body>
</html>'''.encode("utf-8")

    toc_ncx = f'''<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:tears-of-tess-pepper-winters"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>Tears of Tess - Pepper Winters</text></docTitle>
  <navMap>
{chr(10).join(ncx_items)}
  </navMap>
</ncx>'''.encode("utf-8")

    manifest_items = [
        '<item id="xray-dir" href="000-xray-dramatis-personae.xhtml" media-type="application/xhtml+xml"/>',
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '<item id="css" href="styles.css" media-type="text/css"/>'
    ]
    spine_items = [
        '<itemref idref="xray-dir"/>',
        '<itemref idref="nav"/>'
    ]
    for idx in range(len(sections)):
        cid = f"ch_{idx:03d}"
        ch_f = f"chapter_{idx:03d}.xhtml"
        manifest_items.append(f'<item id="{cid}" href="{ch_f}" media-type="application/xhtml+xml"/>')
        spine_items.append(f'<itemref idref="{cid}"/>')
        
    opf_xml = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uid" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Tears of Tess - Pepper Winters</dc:title>
    <dc:creator>Pepper Winters</dc:creator>
    <dc:language>ko</dc:language>
    <dc:identifier id="uid">urn:uuid:tears-of-tess-pepper-winters</dc:identifier>
  </metadata>
  <manifest>
    {chr(10).join("    " + i for i in manifest_items)}
  </manifest>
  <spine toc="ncx">
    {chr(10).join("    " + i for i in spine_items)}
  </spine>
</package>'''.encode("utf-8")

    def package_epub(dest_path: Path, chapter_dict: dict):
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
            zout.writestr("mimetype", b"application/epub+zip", compress_type=zipfile.ZIP_STORED)
            zout.writestr("META-INF/container.xml", b'''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>''')
            zout.writestr("OEBPS/content.opf", opf_xml)
            zout.writestr("OEBPS/nav.xhtml", nav_html)
            zout.writestr("OEBPS/toc.ncx", toc_ncx)
            zout.writestr("OEBPS/styles.css", KINDLE_CSS.encode("utf-8"))
            if xray_data:
                zout.writestr("OEBPS/000-xray-dramatis-personae.xhtml", xray_data)
            for fname, cdata in chapter_dict.items():
                zout.writestr(fname, cdata)
        dest_path.write_bytes(buf.getvalue())
        print(f"  ✨ Built: {dest_path.name}")
        return buf.getvalue()

    s_bytes = package_epub(STUDY_EPUB, study_chapters)
    es_bytes = package_epub(ES_EPUB, es_chapters)
    package_epub(KE_EPUB, ke_chapters)
    package_epub(K_EPUB, k_chapters)

    print(f"\n🎉 100% TOEIC 700~990 TARGETED REBUILD COMPLETED!")
    print(f"✨ Total High-Yield TOEIC Word Wise Hints: {total_rubies:,} rubies (No basic trivia)")
    
    # Sync to GDrive
    GDRIVE_STUDY = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books/[study]/#Top 10 dark romance") / STUDY_EPUB.name
    GDRIVE_ES = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books/[e-s]/#Top 10 dark romance") / ES_EPUB.name
    if GDRIVE_STUDY.parent.exists():
        GDRIVE_STUDY.write_bytes(s_bytes)
        GDRIVE_ES.write_bytes(es_bytes)
        print("☁️ Synced strictly filtered edition to Google Drive #Books!")

if __name__ == "__main__":
    run_master_build()
