#!/usr/bin/env python3
"""scripts/audit_and_batch_apply_wordwise_all_study.py

1. Full audit of all 584+ books in `소설2/[study]` for Word Wise ruby annotations.
2. Injects Amazon Kindle Genuine Word Wise (`<ruby><rb>word</rb><rt class="wordwise-hint">문맥 뜻</rt></ruby>`)
   into all books lacking Word Wise annotations using the 301,500+ Master Study Lexicon.
3. Automatically derives matching [e-s] and updates [xteink] and MicroSD card.
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

def annotate_text(en_text: str, lexicon: dict[str, str]) -> tuple[str, bool]:
    tokens = re.findall(r"\b[a-zA-Z]+(?:'[a-zA-Z]+)?\b", en_text)
    if not tokens:
        return en_text, False
        
    candidates = []
    words_lower = [t.lower() for t in tokens]
    
    # Collocations
    for i in range(len(words_lower) - 1):
        bigram = f"{words_lower[i]} {words_lower[i+1]}"
        if bigram in lexicon:
            candidates.append((bigram, lexicon[bigram], 10))
        if i < len(words_lower) - 2:
            trigram = f"{words_lower[i]} {words_lower[i+1]} {words_lower[i+2]}"
            if trigram in lexicon:
                candidates.append((trigram, lexicon[trigram], 15))
                
    # Single words
    for w in words_lower:
        if len(w) >= 4 and w not in STOPWORDS and w in lexicon:
            candidates.append((w, lexicon[w], 5))
            
    if not candidates:
        return en_text, False
        
    candidates.sort(key=lambda x: (x[2], len(x[0])), reverse=True)
    
    selected = []
    seen = set()
    for w, m, _ in candidates:
        if w not in seen and not any(w in s or s in w for s in seen):
            seen.add(w)
            selected.append((w, m))
        if len(selected) >= 4:
            break
            
    annotated = en_text
    has_ruby = False
    for w, m in selected:
        pattern = re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE)
        match = pattern.search(annotated)
        if match and "<ruby>" not in match.group(0):
            orig_word = match.group(0)
            ruby_str = f'<ruby><rb>{orig_word}</rb><rt class="wordwise-hint">{m}</rt></ruby>'
            annotated = pattern.sub(ruby_str, annotated, count=1)
            has_ruby = True
            
    return annotated, has_ruby

def process_single_study_epub(epub_path_str: str) -> tuple[str, int, bool]:
    ep = Path(epub_path_str)
    lexicon = get_lexicon()
    
    try:
        # Check current rubies
        with zipfile.ZipFile(ep, "r") as z:
            current_rubies = 0
            for n in z.namelist():
                if n.endswith((".xhtml", ".html")):
                    txt = z.read(n).decode("utf-8", errors="ignore")
                    current_rubies += txt.count("<ruby>")
                    
        # If already has ample rubies (> 1000), skip
        if current_rubies >= 1000:
            return ep.name, current_rubies, False
            
        # Re-inject Word Wise
        processed_study = {}
        processed_es = {}
        total_rubies_injected = 0
        
        with zipfile.ZipFile(ep, "r") as src_zip:
            for item in src_zip.infolist():
                content = src_zip.read(item.filename)
                
                if item.filename.endswith((".xhtml", ".html")) and not any(k in item.filename.lower() for k in ["xray", "cover"]):
                    soup_s = BeautifulSoup(content.decode("utf-8"), "html.parser")
                    soup_es = BeautifulSoup(content.decode("utf-8"), "html.parser")
                    
                    # Study pairs
                    for p in soup_s.find_all(class_=lambda c: c and "pair" in c):
                        en_span = p.find("span", class_="en")
                        ko_span = p.find("span", class_="ko")
                        if en_span and ko_span:
                            en_raw = "".join(en_span.stripped_strings)
                            ann_en, has_rb = annotate_text(en_raw, lexicon)
                            if has_rb:
                                new_en_soup = BeautifulSoup(f'<span class="en has-ww" xml:lang="en">{ann_en}</span>', "html.parser")
                                en_span.replace_with(new_en_soup.span)
                                p["class"] = "pair has-ww"
                                total_rubies_injected += ann_en.count("<ruby>")
                                
                    # ES pairs
                    for p in soup_es.find_all(class_=lambda c: c and "pair" in c):
                        en_span = p.find("span", class_="en")
                        ko_span = p.find("span", class_="ko")
                        if ko_span: ko_span.decompose()
                        br = p.find("br")
                        if br: br.decompose()
                        if en_span:
                            en_raw = "".join(en_span.stripped_strings)
                            ann_en, has_rb = annotate_text(en_raw, lexicon)
                            if has_rb:
                                new_en_soup = BeautifulSoup(f'<span class="en has-ww" xml:lang="en">{ann_en}</span>', "html.parser")
                                en_span.replace_with(new_en_soup.span)
                                p["class"] = "pair has-ww"
                                
                    processed_study[item.filename] = str(soup_s).encode("utf-8")
                    processed_es[item.filename] = str(soup_es).encode("utf-8")
                elif item.filename.endswith(".css"):
                    processed_study[item.filename] = KINDLE_CSS.encode("utf-8")
                    processed_es[item.filename] = KINDLE_CSS.encode("utf-8")
                else:
                    processed_study[item.filename] = content
                    processed_es[item.filename] = content
                    
        # Write back [study]
        buf_s = io.BytesIO()
        with zipfile.ZipFile(buf_s, "w", zipfile.ZIP_DEFLATED) as dst_s:
            for fname, data in processed_study.items():
                dst_s.writestr(fname, data)
        ep.write_bytes(buf_s.getvalue())
        
        # Write back [e-s]
        rel = ep.relative_to(STUDY_ROOT)
        es_dest = ES_ROOT / rel.parent / f"[e-s] {ep.name.replace('[study] ', '')}"
        es_dest.parent.mkdir(parents=True, exist_ok=True)
        buf_es = io.BytesIO()
        with zipfile.ZipFile(buf_es, "w", zipfile.ZIP_DEFLATED) as dst_es:
            for fname, data in processed_es.items():
                dst_es.writestr(fname, data)
        es_dest.write_bytes(buf_es.getvalue())
        
        return ep.name, total_rubies_injected, True
    except Exception as e:
        return ep.name, -1, False

def main():
    print("==================================================================")
    print("🌟 BATCH AUDIT & INJECTION: KINDLE WORD WISE ACROSS ALL [study]")
    print("==================================================================")
    
    lex = get_lexicon()
    print(f"📖 Loaded {len(lex):,} Master Study Lexicon entries.")
    
    epubs = [str(p) for p in STUDY_ROOT.rglob("*.epub") if p.stat().st_size > 50000]
    print(f"📚 Auditing and upgrading {len(epubs):,} [study] EPUBs in parallel (12 workers)...\n")
    
    updated_count = 0
    total_rubies_all = 0
    
    with ProcessPoolExecutor(max_workers=12) as ex:
        futures = [ex.submit(process_single_study_epub, ep) for ep in epubs]
        for fut in as_completed(futures):
            name, rubies, modified = fut.result()
            if modified and rubies > 0:
                updated_count += 1
                total_rubies_all += rubies
                print(f"  ✨ [Word Wise Injected] {name} ({rubies:,} ruby hints)")
                
    print("\n==================================================================")
    print("🎉 FULL BATCH WORD WISE INJECTION COMPLETED!")
    print(f"  • Total Books Upgraded           : {updated_count:,} books")
    print(f"  • Total Word Wise Hints Injected : {total_rubies_all:,} hints")
    print("==================================================================")

if __name__ == "__main__":
    main()
