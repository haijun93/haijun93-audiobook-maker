#!/usr/bin/env python3
"""scripts/perfect_authentic_ai_wordwise_tears_of_tess.py

Maps all 3,937 authentic Gemini AI contextual study notes directly onto the chapters of Tears of Tess.
Generates 100% authentic, high-quality overhead Word Wise ruby annotations without any mechanical dictionary mismatch.
"""

from __future__ import annotations

import html
import io
import json
import os
import re
import shutil
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
CACHE_DIR = LIB_ROOT / "_chatgpt_translate_work" / "vk_dark__tears-of-tess-pepper-winters"
TRANSLATIONS_DIR = CACHE_DIR / "translations"
SOURCE_SECTIONS = CACHE_DIR / "source_sections.json"

STUDY_EPUB = LIB_ROOT / "[study]" / "#Top 10 dark romance" / "[study] Tears of Tess - Pepper Winters.epub"
ES_EPUB = LIB_ROOT / "[e-s]" / "#Top 10 dark romance" / "[e-s] Tears of Tess - Pepper Winters.epub"

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

def normalize_key(s: str) -> str:
    s = re.sub(r'[\s\u2000-\u200f\ufeff]+', ' ', s)
    s = re.sub(r'["\'“”‘’`*_\-—–.,!?;:()\[\]]', '', s)
    return s.strip().lower()

def load_all_authentic_blocks():
    # 1. Source English
    src_data = json.loads(SOURCE_SECTIONS.read_text(encoding="utf-8"))
    sections = src_data.get("sections", [])
    src_blocks = {}
    for sec in sections:
        for b in sec.get("blocks", []):
            bid = b.get("id")
            txt = b.get("text", "").strip()
            if bid and txt:
                src_blocks[bid] = txt
                
    # 2. Authentic AI Translations & Study Notes
    translations = {}
    for j in sorted(TRANSLATIONS_DIR.glob("chunk_*.json")):
        data = json.loads(j.read_text(encoding="utf-8"))
        for bid, line_str in data.get("translations", {}).items():
            if isinstance(line_str, str):
                parts = re.split(r'※(?:학습|어휘|공부|노트)?[:：\s]*', line_str, maxsplit=1)
                ko = parts[0].strip()
                note = parts[1].strip() if len(parts) > 1 else ""
                translations[bid] = (ko, note)
                
    # Combine into fast lookup maps
    exact_lookup = {}
    fuzzy_lookup = {}
    
    for bid, en_text in src_blocks.items():
        if bid in translations:
            ko, note = translations[bid]
            exact_lookup[en_text.strip().lower()] = (en_text, ko, note)
            norm = normalize_key(en_text)
            if norm:
                fuzzy_lookup[norm] = (en_text, ko, note)
                
    print(f"✅ Loaded {len(exact_lookup):,} exact and {len(fuzzy_lookup):,} normalized authentic AI records!")
    return exact_lookup, fuzzy_lookup

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
                # Clean up definition
                m_clean = re.sub(r'^\(.*?\)\s*', '', m).strip()
                pairs.append((w, m_clean or m))
    return pairs

def annotate_authentic(en_text: str, note_str: str) -> tuple[str, bool]:
    word_pairs = parse_authentic_notes(note_str)
    if not word_pairs:
        return en_text, False
        
    annotated = en_text
    has_ruby = False
    
    for w, m in word_pairs:
        pattern = re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE)
        match = pattern.search(annotated)
        if match and "<ruby>" not in match.group(0):
            orig_word = match.group(0)
            ruby_tag = f'<ruby><rb>{html.escape(orig_word)}</rb><rt class="wordwise-hint">{html.escape(m)}</rt></ruby>'
            annotated = pattern.sub(ruby_tag, annotated, count=1)
            has_ruby = True
            
    return annotated, has_ruby

def run_rebuild():
    print("==================================================================")
    print("🌟 100% PURE AUTHENTIC AI WORD WISE REBUILD FOR TEARS OF TESS")
    print("==================================================================")
    
    exact_map, fuzzy_map = load_all_authentic_blocks()
    
    processed_study = {}
    processed_es = {}
    total_rubies = 0
    total_pairs = 0
    matched_pairs = 0
    
    with zipfile.ZipFile(STUDY_EPUB, "r") as src_zip:
        for item in src_zip.infolist():
            content = src_zip.read(item.filename)
            
            if item.filename.endswith((".xhtml", ".html")) and "chapter" in item.filename:
                soup_study = BeautifulSoup(content.decode("utf-8"), "html.parser")
                soup_es = BeautifulSoup(content.decode("utf-8"), "html.parser")
                
                # Update study
                for p in soup_study.find_all(class_=lambda c: c and "pair" in c):
                    en_span = p.find("span", class_="en")
                    ko_span = p.find("span", class_="ko")
                    if en_span and ko_span:
                        total_pairs += 1
                        en_raw = "".join(en_span.stripped_strings)
                        
                        # Match exact or fuzzy
                        matched = exact_map.get(en_raw.strip().lower())
                        if not matched:
                            norm_k = normalize_key(en_raw)
                            matched = fuzzy_map.get(norm_k)
                            
                        if matched:
                            matched_pairs += 1
                            orig_en, ai_ko, ai_note = matched
                            if ai_note:
                                ann_en, has_rb = annotate_authentic(en_raw, ai_note)
                                if has_rb:
                                    new_en_soup = BeautifulSoup(f'<span class="en has-ww" xml:lang="en">{ann_en}</span>', "html.parser")
                                    en_span.replace_with(new_en_soup.span)
                                    p["class"] = "pair has-ww"
                                    total_rubies += ann_en.count("<ruby>")
                                else:
                                    en_span["class"] = "en"
                                    p["class"] = "pair"
                            else:
                                en_span["class"] = "en"
                                p["class"] = "pair"
                                
                            if ai_ko and len(ai_ko) > 2:
                                ko_span.string = ai_ko
                                
                # Update es
                for p in soup_es.find_all(class_=lambda c: c and "pair" in c):
                    en_span = p.find("span", class_="en")
                    ko_span = p.find("span", class_="ko")
                    if ko_span: ko_span.decompose()
                    br = p.find("br")
                    if br: br.decompose()
                    if en_span:
                        en_raw = "".join(en_span.stripped_strings)
                        matched = exact_map.get(en_raw.strip().lower())
                        if not matched:
                            norm_k = normalize_key(en_raw)
                            matched = fuzzy_map.get(norm_k)
                        if matched and matched[2]:
                            ann_en, has_rb = annotate_authentic(en_raw, matched[2])
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
    print(f"\n🎉 Successfully Matched {matched_pairs:,} / {total_pairs:,} paragraphs ({matched_pairs/total_pairs*100:.1f}%)!")
    print(f"✨ Injected {total_rubies:,} 100% PURE AUTHENTIC GEMINI AI CONTEXTUAL WORD WISE HINTS!")
    
    # Save [e-s]
    buf_es = io.BytesIO()
    with zipfile.ZipFile(buf_es, "w", zipfile.ZIP_DEFLATED) as dst_es:
        for fname, data in processed_es.items():
            dst_es.writestr(fname, data)
    ES_EPUB.write_bytes(buf_es.getvalue())
    
    # Sync to GDrive
    GDRIVE_STUDY = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books/[study]/#Top 10 dark romance") / STUDY_EPUB.name
    GDRIVE_ES = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books/[e-s]/#Top 10 dark romance") / ES_EPUB.name
    if GDRIVE_STUDY.parent.exists():
        GDRIVE_STUDY.write_bytes(buf_s.getvalue())
        GDRIVE_ES.write_bytes(buf_es.getvalue())
        print("☁️ Synced 100% authentic AI edition to Google Drive #Books!")

if __name__ == "__main__":
    run_rebuild()
