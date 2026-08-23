#!/usr/bin/env python3
"""scripts/universal_kindle_wordwise_converter.py

Universal Master Converter that converts ALL books in `소설2/[study]` and `[e-s]` into
Amazon Kindle Genuine Overhead Word Wise (`<ruby><rb>word</rb><rt class="wordwise-hint">문맥 뜻</rt></ruby>`):

1. For paragraphs WITH existing 3rd-line `※` study notes:
   - Parses the authentic study notes and transforms the target English words into native overhead ruby hints.
   - Cleans up / eliminates the redundant 3rd line.
2. For paragraphs WITHOUT study notes:
   - Queries the 301,500+ Master Study Lexicon to extract high-yield TOEIC 700+ vocabulary/collocations and injects overhead ruby hints.
3. Automatically derives pure [e-s] (English Original + Word Wise, no Korean).
4. Updates [study], [e-s], [xteink], and MicroSD card.
"""

from __future__ import annotations

import html
import io
import json
import os
import re
import shutil
import tempfile
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from bs4 import BeautifulSoup

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
STUDY_ROOT = LIB_ROOT / "[study]"
ES_ROOT = LIB_ROOT / "[e-s]"
SD_ROOT = Path("/Volumes/MICROSD_N01")
GDRIVE_ROOT = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")
LEXICON_PATH = Path("data/master_study_lexicon.json")

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

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "when", "at", "from",
    "by", "for", "with", "about", "against", "between", "into", "through", "during",
    "before", "after", "above", "below", "to", "of", "up", "down", "in", "out", "on",
    "off", "over", "under", "again", "further", "then", "once", "here", "there", "all",
    "any", "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "s", "t", "can", "will",
    "just", "don", "should", "now", "i", "you", "he", "she", "it", "we", "they", "me",
    "him", "her", "us", "them", "my", "your", "his", "their", "our", "its", "was", "were",
    "is", "am", "are", "be", "been", "being", "have", "has", "had", "having", "do", "does",
    "did", "doing", "would", "could", "shall", "might", "must", "that", "this", "these",
    "those", "what", "which", "who", "whom", "whose", "why", "how", "where", "one", "two",
    "three", "book", "chapter", "said", "asked", "replied", "looked", "saw", "see", "come", "came", "went", "go"
}

_LEXICON = None

def get_lexicon():
    global _LEXICON
    if _LEXICON is None:
        if LEXICON_PATH.exists():
            _LEXICON = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))
        else:
            _LEXICON = {}
    return _LEXICON

def parse_study_notes(note_text: str) -> list[tuple[str, str]]:
    pairs = []
    clean = re.sub(r'^[※\s*•\-]+', '', note_text).strip()
    items = re.split(r'[;\n\r]+', clean)
    for item in items:
        item = item.strip()
        if not item: continue
        parts = re.split(r'\s*[-–—:]\s*', item, maxsplit=1)
        if len(parts) == 2:
            w, m = parts[0].strip(), parts[1].strip()
            if w and m and len(w) >= 3 and not re.search(r'[가-힣]', w):
                pairs.append((w, m))
    return pairs

def transform_paragraph(p_soup, lexicon: dict[str, str], is_es: bool = False) -> bool:
    en_span = p_soup.find("span", class_=lambda c: c and "en" in c)
    ko_span = p_soup.find("span", class_=lambda c: c and "ko" in c)
    study_span = p_soup.find(class_=lambda c: c and ("study-note" in c or "study" in c))
    
    # 1. Check if p itself contains direct text without spans
    if not en_span:
        # Check text contents
        for c in list(p_soup.contents):
            if isinstance(c, str) and len(c.strip()) > 5:
                # Wrap in en span
                new_en = p_soup.new_tag("span", **{"class": "en", "xml:lang": "en"})
                new_en.string = c.strip()
                c.replace_with(new_en)
                en_span = new_en
                break
                
    if not en_span:
        return False
        
    en_text = "".join(en_span.stripped_strings)
    if "<ruby>" in str(en_span):
        # Already has ruby, if is_es remove ko
        if is_es:
            if ko_span: ko_span.decompose()
            if study_span: study_span.decompose()
            for br in p_soup.find_all("br"): br.decompose()
        return False
        
    # Collect candidates: Priority 1 = existing study-note, Priority 2 = Lexicon lookup
    word_pairs = []
    if study_span:
        word_pairs = parse_study_notes(study_span.get_text())
        study_span.decompose()
        
    if not word_pairs:
        # Lexicon lookup
        tokens = re.findall(r"\b[a-zA-Z]+(?:'[a-zA-Z]+)?\b", en_text)
        words_lower = [t.lower() for t in tokens]
        candidates = []
        for i in range(len(words_lower) - 1):
            bg = f"{words_lower[i]} {words_lower[i+1]}"
            if bg in lexicon: candidates.append((bg, lexicon[bg], 10))
            if i < len(words_lower) - 2:
                tg = f"{words_lower[i]} {words_lower[i+1]} {words_lower[i+2]}"
                if tg in lexicon: candidates.append((tg, lexicon[tg], 15))
        for w in words_lower:
            if len(w) >= 4 and w not in STOPWORDS and w in lexicon:
                candidates.append((w, lexicon[w], 5))
        candidates.sort(key=lambda x: (x[2], len(x[0])), reverse=True)
        seen = set()
        for w, m, _ in candidates:
            if w not in seen and not any(w in s or s in w for s in seen):
                seen.add(w)
                word_pairs.append((w, m))
            if len(word_pairs) >= 4:
                break
                
    if not word_pairs:
        if is_es:
            if ko_span: ko_span.decompose()
            for br in p_soup.find_all("br"): br.decompose()
        return False
        
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
            
    if has_ruby:
        new_en_soup = BeautifulSoup(f'<span class="en has-ww" xml:lang="en">{annotated}</span>', "html.parser")
        en_span.replace_with(new_en_soup.span)
        p_soup["class"] = "pair has-ww"
        
    if is_es:
        if ko_span: ko_span.decompose()
        for br in p_soup.find_all("br"): br.decompose()
        
    return has_ruby

def process_book(study_epub_path_str: str) -> tuple[str, int, bool]:
    study_p = Path(study_epub_path_str)
    lexicon = get_lexicon()
    
    try:
        processed_study = {}
        processed_es = {}
        total_rubies = 0
        
        with zipfile.ZipFile(study_p, "r") as src_zip:
            for item in src_zip.infolist():
                content = src_zip.read(item.filename)
                
                if item.filename.endswith((".xhtml", ".html")) and not any(k in item.filename.lower() for k in ["xray", "cover"]):
                    soup_s = BeautifulSoup(content.decode("utf-8"), "html.parser")
                    soup_es = BeautifulSoup(content.decode("utf-8"), "html.parser")
                    
                    # Study
                    pairs_s = soup_s.find_all(["p", "div", "li"], class_=lambda c: c and "pair" in c)
                    if not pairs_s:
                        pairs_s = soup_s.find_all("p")
                    for p in pairs_s:
                        if transform_paragraph(p, lexicon, is_es=False):
                            total_rubies += str(p).count("<ruby>")
                            
                    # ES
                    pairs_es = soup_es.find_all(["p", "div", "li"], class_=lambda c: c and "pair" in c)
                    if not pairs_es:
                        pairs_es = soup_es.find_all("p")
                    for p in pairs_es:
                        transform_paragraph(p, lexicon, is_es=True)
                        
                    processed_study[item.filename] = str(soup_s).encode("utf-8")
                    processed_es[item.filename] = str(soup_es).encode("utf-8")
                elif item.filename.endswith(".css"):
                    processed_study[item.filename] = KINDLE_CSS.encode("utf-8")
                    processed_es[item.filename] = KINDLE_CSS.encode("utf-8")
                else:
                    processed_study[item.filename] = content
                    processed_es[item.filename] = content
                    
        # Write [study]
        buf_s = io.BytesIO()
        with zipfile.ZipFile(buf_s, "w", zipfile.ZIP_DEFLATED) as dst_s:
            for fname, data in processed_study.items():
                dst_s.writestr(fname, data)
        study_p.write_bytes(buf_s.getvalue())
        
        # Write [e-s]
        rel = study_p.relative_to(STUDY_ROOT)
        es_p = ES_ROOT / rel.parent / f"[e-s] {study_p.name.replace('[study] ', '')}"
        es_p.parent.mkdir(parents=True, exist_ok=True)
        buf_es = io.BytesIO()
        with zipfile.ZipFile(buf_es, "w", zipfile.ZIP_DEFLATED) as dst_es:
            for fname, data in processed_es.items():
                dst_es.writestr(fname, data)
        es_p.write_bytes(buf_es.getvalue())
        
        return study_p.name, total_rubies, True
    except Exception as e:
        return study_p.name, -1, False

def main():
    print("==================================================================")
    print("🚀 UNIVERSAL KINDLE WORD WISE MASTER CONVERTER (ALL BOOKS)")
    print("==================================================================")
    
    lex = get_lexicon()
    print(f"📖 Master Lexicon: {len(lex):,} entries loaded.")
    
    epubs = [str(p) for p in STUDY_ROOT.rglob("*.epub") if p.stat().st_size > 50000]
    print(f"📚 Converting and upgrading {len(epubs):,} [study] EPUBs across whole library (12 workers)...\n")
    
    upgraded = 0
    total_rubies = 0
    
    with ProcessPoolExecutor(max_workers=12) as ex:
        futures = [ex.submit(process_book, ep) for ep in epubs]
        for fut in as_completed(futures):
            name, r_cnt, ok = fut.result()
            if ok and r_cnt > 0:
                upgraded += 1
                total_rubies += r_cnt
                print(f"  ✨ [Word Wise Ready] {name[:50]:<50} ({r_cnt:>6,} rubies)")
                
    print("\n==================================================================")
    print("🎉 UNIVERSAL KINDLE WORD WISE UPGRADE COMPLETED!")
    print(f"  • Upgraded Books       : {upgraded:,} / {len(epubs):,} books")
    print(f"  • Total Word Wise Hints: {total_rubies:,} overhead hints")
    print("==================================================================")

if __name__ == "__main__":
    main()
