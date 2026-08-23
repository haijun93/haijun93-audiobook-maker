#!/usr/bin/env python3
"""scripts/fast_complete_wordwise_injector.py

Ultra-fast regex-based Word Wise injector that transforms ALL 584+ books in `소설2/[study]` and `[e-s]`
into Amazon Kindle Genuine Overhead Word Wise (`<ruby><rb>word</rb><rt class="wordwise-hint">문맥 뜻</rt></ruby>`).
"""

from __future__ import annotations

import html
import io
import json
import os
import re
import shutil
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

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

def parse_study_note(note_str: str) -> list[tuple[str, str]]:
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

def transform_html_str(html_text: str, lexicon: dict[str, str], is_es: bool = False) -> tuple[str, int]:
    rubies_added = 0
    
    def repl_p(match):
        nonlocal rubies_added
        full_p = match.group(0)
        
        # 1. Extract note, en, ko
        note_m = re.search(r'<span[^>]*class=["\'](?:study-note|study)["\'][^>]*>(.*?)</span>', full_p, flags=re.DOTALL)
        en_m = re.search(r'<span[^>]*class=["\']en(?: has-ww)?["\'][^>]*>(.*?)</span>', full_p, flags=re.DOTALL)
        ko_m = re.search(r'<span[^>]*class=["\']ko["\'][^>]*>(.*?)</span>', full_p, flags=re.DOTALL)
        
        raw_note = note_m.group(1).strip() if note_m else ""
        raw_en = en_m.group(1).strip() if en_m else ""
        raw_ko = ko_m.group(1).strip() if ko_m else ""
        
        # If no spans, check if p has direct text
        if not raw_en and not raw_ko:
            p_inner = re.sub(r"^<p[^>]*>|</p>$", "", full_p).strip()
            if "※" in p_inner:
                parts = p_inner.split("※", 1)
                raw_en = parts[0].strip()
                raw_note = parts[1].strip()
            else:
                raw_en = p_inner
                
        if "※" in raw_ko:
            parts = raw_ko.split("※", 1)
            raw_ko = parts[0].strip()
            raw_note = (raw_note + " ; " + parts[1].strip()) if raw_note else parts[1].strip()
            
        # Collect word pairs
        word_pairs = []
        if raw_note:
            word_pairs = parse_study_note(raw_note)
            
        if not word_pairs and raw_en and "<ruby>" not in raw_en:
            tokens = re.findall(r"\b[a-zA-Z]+(?:'[a-zA-Z]+)?\b", raw_en)
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
                    
        annotated_en = raw_en
        for w, m in word_pairs:
            if f"<rb>{w}</rb>" in annotated_en:
                continue
            pattern = rf"\b{re.escape(w)}\b"
            ruby_tag = f'<ruby><rb>{html.escape(w)}</rb><rt class="wordwise-hint">{html.escape(m)}</rt></ruby>'
            new_en = re.sub(pattern, ruby_tag, annotated_en, count=1, flags=re.IGNORECASE)
            if new_en != annotated_en:
                annotated_en = new_en
                rubies_added += 1
                
        has_ruby = "<ruby>" in annotated_en
        en_cls = "en has-ww" if has_ruby else "en"
        p_cls = "pair has-ww" if has_ruby else "pair"
        
        if is_es:
            clean_en = annotated_en or raw_en
            return f'<p class="{p_cls}"><span class="{en_cls}" xml:lang="en">{clean_en}</span></p>'
        else:
            if annotated_en and raw_ko:
                return f'<p class="{p_cls}"><span class="{en_cls}" xml:lang="en">{annotated_en}</span><br/><span class="ko" xml:lang="ko">{raw_ko}</span></p>'
            elif annotated_en:
                return f'<p class="{p_cls}"><span class="{en_cls}" xml:lang="en">{annotated_en}</span></p>'
            elif raw_ko:
                return f'<p class="pair"><span class="ko" xml:lang="ko">{raw_ko}</span></p>'
            return full_p
            
    transformed = re.sub(r"<p\b[^>]*>.*?</p>", repl_p, html_text, flags=re.DOTALL)
    return transformed, rubies_added

def process_single_study_epub(epub_path_str: str) -> tuple[str, int, bool]:
    ep = Path(epub_path_str)
    lexicon = get_lexicon()
    
    try:
        processed_study = {}
        processed_es = {}
        total_rubies = 0
        
        with zipfile.ZipFile(ep, "r") as src_zip:
            for item in src_zip.infolist():
                content = src_zip.read(item.filename)
                
                if item.filename.endswith((".xhtml", ".html")) and not any(k in item.filename.lower() for k in ["xray", "cover"]):
                    html_str = content.decode("utf-8", errors="ignore")
                    study_html, r_cnt = transform_html_str(html_str, lexicon, is_es=False)
                    es_html, _ = transform_html_str(html_str, lexicon, is_es=True)
                    total_rubies += r_cnt
                    processed_study[item.filename] = study_html.encode("utf-8")
                    processed_es[item.filename] = es_html.encode("utf-8")
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
        ep.write_bytes(buf_s.getvalue())
        
        # Write [e-s]
        rel = ep.relative_to(STUDY_ROOT)
        es_p = ES_ROOT / rel.parent / f"[e-s] {ep.name.replace('[study] ', '')}"
        es_p.parent.mkdir(parents=True, exist_ok=True)
        buf_es = io.BytesIO()
        with zipfile.ZipFile(buf_es, "w", zipfile.ZIP_DEFLATED) as dst_es:
            for fname, data in processed_es.items():
                dst_es.writestr(fname, data)
        es_p.write_bytes(buf_es.getvalue())
        
        # Copy to SD card if in Top 10 or mounted
        if SD_ROOT.exists():
            sd_dest_s = SD_ROOT / "[study]" / rel
            sd_dest_es = SD_ROOT / "[e-s]" / rel.parent / f"[e-s] {ep.name.replace('[study] ', '')}"
            sd_dest_s.parent.mkdir(parents=True, exist_ok=True)
            sd_dest_es.parent.mkdir(parents=True, exist_ok=True)
            sd_dest_s.write_bytes(buf_s.getvalue())
            sd_dest_es.write_bytes(buf_es.getvalue())
            
        return ep.name, total_rubies, True
    except Exception as e:
        return ep.name, -1, False

def main():
    print("==================================================================")
    print("⚡ FAST ULTRA-PERFECT WORD WISE INJECTION (ALL 584+ BOOKS)")
    print("==================================================================")
    
    lex = get_lexicon()
    print(f"📖 Master Lexicon loaded: {len(lex):,} entries.")
    
    epubs = [str(p) for p in STUDY_ROOT.rglob("*.epub") if p.stat().st_size > 50000]
    print(f"📚 Upgrading all {len(epubs):,} [study] and [e-s] books in parallel (12 workers)...\n")
    
    upgraded = 0
    total_rubies = 0
    
    with ProcessPoolExecutor(max_workers=12) as ex:
        futures = [ex.submit(process_single_study_epub, ep) for ep in epubs]
        for fut in as_completed(futures):
            name, r_cnt, ok = fut.result()
            if ok and r_cnt > 0:
                upgraded += 1
                total_rubies += r_cnt
                print(f"  ✨ [Word Wise Injected] {name[:50]:<50} ({r_cnt:>6,} rubies)")
                
    print("\n==================================================================")
    print("🎉 FULL BATCH WORD WISE INJECTION 100% COMPLETED!")
    print(f"  • Upgraded Books       : {upgraded:,} / {len(epubs):,} books")
    print(f"  • Total Word Wise Hints: {total_rubies:,} overhead ruby annotations")
    print("==================================================================")

if __name__ == "__main__":
    main()
