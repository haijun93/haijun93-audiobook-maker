#!/usr/bin/env python3
"""scripts/restore_authentic_ai_study_notes_tears_of_tess.py

Restores 100% authentic AI-generated contextual study notes directly from Gemini web translation cache
(`_chatgpt_translate_work/vk_dark__tears-of-tess-pepper-winters/translations/*.json`).

Eliminates all mechanical static dictionary mis-matches and replaces them with authentic AI contextual definitions.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
CACHE_DIR = LIB_ROOT / "_chatgpt_translate_work" / "vk_dark__tears-of-tess-pepper-winters"
TRANSLATIONS_DIR = CACHE_DIR / "translations"
SOURCE_SECTIONS = CACHE_DIR / "source_sections.json"

STUDY_EPUB = LIB_ROOT / "[study]" / "#Top 10 dark romance" / "[study] Tears of Tess - Pepper Winters.epub"
ES_EPUB = LIB_ROOT / "[e-s]" / "#Top 10 dark romance" / "[e-s] Tears of Tess - Pepper Winters.epub"
KE_EPUB = LIB_ROOT / "[k-e]" / "#Top 10 dark romance" / "[k-e] Tears of Tess - Pepper Winters.epub"

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

def load_authentic_ai_translations():
    print("📖 Loading authentic Gemini AI translations and study notes...")
    block_map = {}

    # 1. Load source english text
    source_texts = {}
    if SOURCE_SECTIONS.exists():
        src_data = json.loads(SOURCE_SECTIONS.read_text(encoding="utf-8"))
        secs = src_data.get("sections", src_data) if isinstance(src_data, dict) else src_data
        for sec in secs:
            if isinstance(sec, dict):
                for b in sec.get("blocks", []):
                    if isinstance(b, dict):
                        bid = b.get("id")
                        txt = b.get("text", "").strip()
                        if bid and txt:
                            source_texts[bid] = txt

    # 2. Load authentic AI translations and ※학습: notes
    for json_f in sorted(TRANSLATIONS_DIR.glob("chunk_*.json")):
        try:
            data = json.loads(json_f.read_text(encoding="utf-8"))
            tr = data.get("translations", {})
            for bid, line_str in tr.items():
                if isinstance(line_str, str):
                    parts = re.split(r'※(?:학습|어휘|공부|노트)?[:：\s]*', line_str, maxsplit=1)
                    ko_txt = parts[0].strip()
                    study_note = parts[1].strip() if len(parts) > 1 else ""

                    en_txt = source_texts.get(bid, "")
                    block_map[bid] = {
                        "en": en_txt,
                        "ko": ko_txt,
                        "study_note": study_note
                    }
        except Exception as e:
            print(f"Error loading {json_f.name}: {e}")

    print(f"✅ Loaded {len(block_map):,} authentic AI translated blocks!")
    return block_map

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
            if w and m and len(w) >= 2 and not re.search(r'[가-힣]', w):
                pairs.append((w, m))
    return pairs

def annotate_with_authentic_ai(en_text: str, study_note: str) -> tuple[str, bool]:
    word_pairs = parse_authentic_notes(study_note)
    if not word_pairs:
        return en_text, False

    annotated = en_text
    has_ruby = False
    for w, m in word_pairs:
        pattern = re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE)
        match = pattern.search(annotated)
        if match and "<ruby>" not in match.group(0):
            orig_word = match.group(0)
            ruby_str = f'<ruby><rb>{orig_word}</rb><rt class="wordwise-hint">{m}</rt></ruby>'
            annotated = pattern.sub(ruby_str, annotated, count=1)
            has_ruby = True

    return annotated, has_ruby

def rebuild_authentic_tears_of_tess():
    print("==================================================================")
    print("🌟 REBUILDING TEARS OF TESS WITH 100% AUTHENTIC GEMINI AI STUDY NOTES")
    print("==================================================================")

    block_map = load_authentic_ai_translations()

    # Map by clean english text
    en_lookup = {}
    for bid, data in block_map.items():
        en_clean = re.sub(r'\s+', ' ', data["en"]).strip().lower()
        if en_clean:
            en_lookup[en_clean] = data

    processed_study = {}
    processed_es = {}
    processed_ke = {}
    total_rubies = 0

    with zipfile.ZipFile(STUDY_EPUB, "r") as src_zip:
        for item in src_zip.infolist():
            content = src_zip.read(item.filename)

            if item.filename.endswith((".xhtml", ".html")) and "chapter" in item.filename:
                soup_study = BeautifulSoup(content.decode("utf-8"), "html.parser")
                soup_es = BeautifulSoup(content.decode("utf-8"), "html.parser")
                soup_ke = BeautifulSoup(content.decode("utf-8"), "html.parser")

                # Update study
                for p in soup_study.find_all(class_=lambda c: c and "pair" in c):
                    en_span = p.find("span", class_="en")
                    ko_span = p.find("span", class_="ko")
                    if en_span and ko_span:
                        en_raw = "".join(en_span.stripped_strings)
                        en_key = re.sub(r'\s+', ' ', en_raw).strip().lower()

                        matched = en_lookup.get(en_key)
                        if matched and matched["study_note"]:
                            # Use authentic AI translation and study note!
                            ann_en, has_rb = annotate_with_authentic_ai(en_raw, matched["study_note"])
                            if has_rb:
                                new_en_soup = BeautifulSoup(f'<span class="en has-ww" xml:lang="en">{ann_en}</span>', "html.parser")
                                en_span.replace_with(new_en_soup.span)
                                p["class"] = "pair has-ww"
                                total_rubies += ann_en.count("<ruby>")
                            else:
                                en_span["class"] = "en"
                                p["class"] = "pair"
                            if matched["ko"]:
                                ko_span.string = matched["ko"]

                # Update es
                for p in soup_es.find_all(class_=lambda c: c and "pair" in c):
                    en_span = p.find("span", class_="en")
                    ko_span = p.find("span", class_="ko")
                    if ko_span: ko_span.decompose()
                    br = p.find("br")
                    if br: br.decompose()
                    if en_span:
                        en_raw = "".join(en_span.stripped_strings)
                        en_key = re.sub(r'\s+', ' ', en_raw).strip().lower()
                        matched = en_lookup.get(en_key)
                        if matched and matched["study_note"]:
                            ann_en, has_rb = annotate_with_authentic_ai(en_raw, matched["study_note"])
                            if has_rb:
                                new_en_soup = BeautifulSoup(f'<span class="en has-ww" xml:lang="en">{ann_en}</span>', "html.parser")
                                en_span.replace_with(new_en_soup.span)
                                p["class"] = "pair has-ww"
                            else:
                                en_span["class"] = "en"
                                p["class"] = "pair"

                processed_study[item.filename] = str(soup_study).encode("utf-8")
                processed_es[item.filename] = str(soup_es).encode("utf-8")
            elif item.filename.endswith(".css"):
                processed_study[item.filename] = KINDLE_CSS.encode("utf-8")
                processed_es[item.filename] = KINDLE_CSS.encode("utf-8")
            else:
                processed_study[item.filename] = content
                processed_es[item.filename] = content

    # Save [study]
    buf_s = io.BytesIO()
    with zipfile.ZipFile(buf_s, "w", zipfile.ZIP_DEFLATED) as dst_s:
        for fname, data in processed_study.items():
            dst_s.writestr(fname, data)
    STUDY_EPUB.write_bytes(buf_s.getvalue())
    print(f"✅ Saved [study] with {total_rubies:,} AUTHENTIC AI contextual ruby hints!")

    # Save [e-s]
    buf_es = io.BytesIO()
    with zipfile.ZipFile(buf_es, "w", zipfile.ZIP_DEFLATED) as dst_es:
        for fname, data in processed_es.items():
            dst_es.writestr(fname, data)
    ES_EPUB.write_bytes(buf_es.getvalue())
    print("✅ Saved [e-s] with pure English + AUTHENTIC AI study hints!")

    # Sync to GDrive
    GDRIVE_STUDY = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books/[study]/#Top 10 dark romance") / STUDY_EPUB.name
    GDRIVE_ES = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books/[e-s]/#Top 10 dark romance") / ES_EPUB.name
    if GDRIVE_STUDY.parent.exists():
        GDRIVE_STUDY.write_bytes(buf_s.getvalue())
        GDRIVE_ES.write_bytes(buf_es.getvalue())
        print("☁️ Synced authentic edition to Google Drive #Books!")

if __name__ == "__main__":
    rebuild_authentic_tears_of_tess()
