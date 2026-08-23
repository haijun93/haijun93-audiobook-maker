#!/usr/bin/env python3
"""scripts/apply_master_lexicon_wordwise_to_book.py

Extracts TOEIC 700+ vocabulary, idioms, and collocations from `data/master_study_lexicon.json` (215,000+ entries)
and injects Kindle Genuine Overhead Word Wise (`<ruby><rb>word</rb><rt class="wordwise-hint">문맥 뜻</rt></ruby>`)
directly into `[study]` and `[e-s]` editions of Tears of Tess.
"""

from __future__ import annotations

import html
import io
import json
import re
import shutil
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
LEXICON_PATH = Path("data/master_study_lexicon.json")

STUDY_EPUB = LIB_ROOT / "[study]" / "#Top 10 dark romance" / "[study] Tears of Tess - Pepper Winters.epub"
ES_EPUB = LIB_ROOT / "[e-s]" / "#Top 10 dark romance" / "[e-s] Tears of Tess - Pepper Winters.epub"
XTEINK_STUDY = LIB_ROOT / "[xteink]/[study]" / "#Top 10 dark romance" / "[study] Tears of Tess - Pepper Winters.epub"
XTEINK_ES = LIB_ROOT / "[xteink]/[e-s]" / "#Top 10 dark romance" / "[e-s] Tears of Tess - Pepper Winters.epub"

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

def load_lexicon() -> dict[str, str]:
    if LEXICON_PATH.exists():
        print(f"📖 Loading Master Lexicon from {LEXICON_PATH}...")
        return json.loads(LEXICON_PATH.read_text(encoding="utf-8"))
    return {}

def annotate_en_sentence(en_text: str, lexicon: dict[str, str]) -> tuple[str, bool]:
    # Extract candidate multi-words and single words
    tokens = re.findall(r"\b[a-zA-Z]+(?:'[a-zA-Z]+)?\b", en_text)
    if not tokens:
        return en_text, False
        
    candidates = []
    
    # 1. 2-word & 3-word collocations
    words_lower = [t.lower() for t in tokens]
    for i in range(len(words_lower) - 1):
        bigram = f"{words_lower[i]} {words_lower[i+1]}"
        if bigram in lexicon:
            candidates.append((bigram, lexicon[bigram], 10))
        if i < len(words_lower) - 2:
            trigram = f"{words_lower[i]} {words_lower[i+1]} {words_lower[i+2]}"
            if trigram in lexicon:
                candidates.append((trigram, lexicon[trigram], 15))
                
    # 2. Single words
    for w in words_lower:
        if len(w) >= 4 and w not in STOPWORDS and w in lexicon:
            candidates.append((w, lexicon[w], 5))
            
    if not candidates:
        return en_text, False
        
    # Sort candidates by priority and length
    candidates.sort(key=lambda x: (x[2], len(x[0])), reverse=True)
    
    selected = []
    seen = set()
    for w, m, _ in candidates:
        if w not in seen and not any(w in s or s in w for s in seen):
            seen.add(w)
            selected.append((w, m))
        if len(selected) >= 4:  # Max 4 Word Wise hints per sentence for clean layout
            break
            
    annotated = en_text
    has_ruby = False
    for w, m in selected:
        # Match word in text preserving original case
        pattern = re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE)
        match = pattern.search(annotated)
        if match and "<ruby>" not in match.group(0):
            orig_word = match.group(0)
            ruby_str = f'<ruby><rb>{orig_word}</rb><rt class="wordwise-hint">{m}</rt></ruby>'
            annotated = pattern.sub(ruby_str, annotated, count=1)
            has_ruby = True
            
    return annotated, has_ruby

def process_study_and_es_epubs():
    print("==================================================================")
    print("⚡ INJECTING KINDLE GENUINE WORD WISE INTO TEARS OF TESS")
    print("==================================================================")
    
    lexicon = load_lexicon()
    print(f"Loaded {len(lexicon):,} Master Study Lexicon entries.\n")
    
    if not STUDY_EPUB.exists():
        print(f"❌ Target [study] EPUB not found: {STUDY_EPUB}")
        return
        
    processed_study_files = {}
    processed_es_files = {}
    total_rubies = 0
    
    with zipfile.ZipFile(STUDY_EPUB, "r") as src_zip:
        for item in src_zip.infolist():
            content = src_zip.read(item.filename)
            
            if item.filename.endswith((".xhtml", ".html")) and "chapter" in item.filename:
                soup_study = BeautifulSoup(content.decode("utf-8"), "html.parser")
                soup_es = BeautifulSoup(content.decode("utf-8"), "html.parser")
                
                # Update pairs in study
                for p in soup_study.find_all(class_=lambda c: c and "pair" in c):
                    en_span = p.find("span", class_="en")
                    ko_span = p.find("span", class_="ko")
                    if en_span and ko_span:
                        en_raw = "".join(en_span.stripped_strings)
                        annotated_en, has_ruby = annotate_en_sentence(en_raw, lexicon)
                        if has_ruby:
                            # Parse back ruby markup safely
                            new_en_soup = BeautifulSoup(f'<span class="en has-ww" xml:lang="en">{annotated_en}</span>', "html.parser")
                            en_span.replace_with(new_en_soup.span)
                            p["class"] = "pair has-ww"
                            total_rubies += annotated_en.count("<ruby>")
                            
                # Update pairs in es (strip korean)
                for p in soup_es.find_all(class_=lambda c: c and "pair" in c):
                    en_span = p.find("span", class_="en")
                    ko_span = p.find("span", class_="ko")
                    if ko_span:
                        ko_span.decompose()
                    br = p.find("br")
                    if br:
                        br.decompose()
                    if en_span:
                        en_raw = "".join(en_span.stripped_strings)
                        annotated_en, has_ruby = annotate_en_sentence(en_raw, lexicon)
                        if has_ruby:
                            new_en_soup = BeautifulSoup(f'<span class="en has-ww" xml:lang="en">{annotated_en}</span>', "html.parser")
                            en_span.replace_with(new_en_soup.span)
                            p["class"] = "pair has-ww"
                            
                processed_study_files[item.filename] = str(soup_study).encode("utf-8")
                processed_es_files[item.filename] = str(soup_es).encode("utf-8")
                
            elif item.filename.endswith(".css"):
                processed_study_files[item.filename] = KINDLE_CSS.encode("utf-8")
                processed_es_files[item.filename] = KINDLE_CSS.encode("utf-8")
            else:
                processed_study_files[item.filename] = content
                processed_es_files[item.filename] = content
                
    # 1. Save [study]
    buf_study = io.BytesIO()
    with zipfile.ZipFile(buf_study, "w", zipfile.ZIP_DEFLATED) as dst_study:
        for fname, data in processed_study_files.items():
            dst_study.writestr(fname, data)
    STUDY_EPUB.write_bytes(buf_study.getvalue())
    print(f"✅ Saved [study] edition with {total_rubies:,} overhead Word Wise hints: {STUDY_EPUB.name}")
    
    # 2. Save [e-s]
    buf_es = io.BytesIO()
    with zipfile.ZipFile(buf_es, "w", zipfile.ZIP_DEFLATED) as dst_es:
        for fname, data in processed_es_files.items():
            dst_es.writestr(fname, data)
    ES_EPUB.write_bytes(buf_es.getvalue())
    print(f"✅ Saved [e-s] edition with pure English + Word Wise hints: {ES_EPUB.name}")
    
    # 3. Sync to [xteink]
    if XTEINK_STUDY.parent.exists():
        XTEINK_STUDY.write_bytes(buf_study.getvalue())
        print(f"📱 Updated Xteink [study]: {XTEINK_STUDY.name}")
    if XTEINK_ES.parent.exists():
        XTEINK_ES.write_bytes(buf_es.getvalue())
        print(f"📱 Updated Xteink [e-s]: {XTEINK_ES.name}")
        
    print("\n==================================================================")
    print("🎉 KINDLE GENUINE WORD WISE FULLY IMPLEMENTED FOR TEARS OF TESS!")
    print("==================================================================")

if __name__ == "__main__":
    process_study_and_es_epubs()
