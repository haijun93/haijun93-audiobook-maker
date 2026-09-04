#!/usr/bin/env python3
"""scripts/purify_all_library_study_notes_for_toeic_700_plus.py

Purifies ALL 594+ [study] and [e-s] EPUBs in the entire library according to the
TOEIC 700+ to 990 Target Standard:

1. Strips away all middle school / elementary basic words (e.g. 'hell', 'words', 'teeth', 'smile', 'dinner', 'hand'...).
2. Retains strictly high-yield TOEIC 700~990 vocabulary, advanced idioms/phrasal verbs, and context-specific collocations.
3. Automatically fixes dynamic line-height:
   - Paragraphs WITH remaining TOEIC 700+ rubies: span.en.has-ww, p.has-ww (line-height: 1.85)
   - Paragraphs WITHOUT rubies: span.en, p.pair (line-height: 1.65 standard)
4. Synchronizes across [study], [e-s], and Google Drive `#Books`.
"""

from __future__ import annotations

import io
import re
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from audiobook_studio.study_filter import is_valid_toeic_700_plus_target, BASIC_VOCAB_STOPLIST

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
STUDY_ROOT = LIB_ROOT / "[study]"
ES_ROOT = LIB_ROOT / "[e-s]"
GDRIVE_ROOT = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

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

def clean_ruby_tags(html_str: str, is_es: bool = False) -> tuple[str, int]:
    rubies_kept = 0

    def repl_ruby(m):
        nonlocal rubies_kept
        rb_text = m.group(1).strip()
        rt_text = m.group(2).strip()

        # Check if the word is a valid TOEIC 700+ target
        if is_valid_toeic_700_plus_target(rb_text):
            rubies_kept += 1
            return f'<ruby><rb>{rb_text}</rb><rt class="wordwise-hint">{rt_text}</rt></ruby>'
        else:
            # Strip ruby, keep clean original word
            return rb_text

    # 1. Purify ruby tags
    purified_html = re.sub(
        r'<ruby>\s*<rb>(.*?)</rb>\s*<rt[^>]*>(.*?)</rt>\s*</ruby>',
        repl_ruby,
        html_str,
        flags=re.DOTALL | re.IGNORECASE
    )

    # 2. Update paragraph / span classes dynamically
    def repl_p(pm):
        p_content = pm.group(0)
        has_rubies = "<ruby>" in p_content

        if is_es:
            # For [e-s], remove Korean translations if present
            p_content = re.sub(r'<span[^>]*class=["\']ko["\'][^>]*>.*?</span>', '', p_content, flags=re.DOTALL)
            p_content = re.sub(r'<br\s*/?>', '', p_content)

        if has_rubies:
            p_content = re.sub(r'<p\b(?![^>]*class=["\'][^"\']*has-ww)([^>]*)class=["\']([^"\']*)["\']', r'<p\1class="\2 has-ww"', p_content)
            p_content = re.sub(r'<span\b(?![^>]*class=["\'][^"\']*has-ww)([^>]*)class=["\']en["\']', r'<span\1class="en has-ww"', p_content)
        else:
            p_content = re.sub(r'\bhas-ww\b', '', p_content)
            p_content = re.sub(r'class=["\']\s+["\']', '', p_content)
            p_content = re.sub(r'class=["\']pair\s+["\']', 'class="pair"', p_content)
            p_content = re.sub(r'class=["\']en\s+["\']', 'class="en"', p_content)

        return p_content

    purified_html = re.sub(r'<p\b[^>]*>.*?</p>', repl_p, purified_html, flags=re.DOTALL)
    return purified_html, rubies_kept

def process_study_epub(epub_path_str: str) -> tuple[str, int, int, bool]:
    study_p = Path(epub_path_str)

    try:
        processed_study = {}
        processed_es = {}
        original_rubies = 0
        retained_rubies = 0

        with zipfile.ZipFile(study_p, "r") as src_zip:
            for item in src_zip.infolist():
                content = src_zip.read(item.filename)

                if item.filename.endswith((".xhtml", ".html")) and not any(k in item.filename.lower() for k in ["xray", "cover"]):
                    html_str = content.decode("utf-8", errors="ignore")
                    original_rubies += html_str.count("<ruby>")

                    # Purify for [study]
                    s_html, s_cnt = clean_ruby_tags(html_str, is_es=False)
                    # Purify for [e-s]
                    es_html, _ = clean_ruby_tags(html_str, is_es=True)

                    retained_rubies += s_cnt
                    processed_study[item.filename] = s_html.encode("utf-8")
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

        # Sync to Google Drive #Books
        if GDRIVE_ROOT.exists():
            gd_study = GDRIVE_ROOT / "[study]" / rel
            gd_es = GDRIVE_ROOT / "[e-s]" / rel.parent / f"[e-s] {study_p.name.replace('[study] ', '')}"
            gd_study.parent.mkdir(parents=True, exist_ok=True)
            gd_es.parent.mkdir(parents=True, exist_ok=True)
            gd_study.write_bytes(buf_s.getvalue())
            gd_es.write_bytes(buf_es.getvalue())

        return study_p.name, original_rubies, retained_rubies, True
    except Exception as e:
        return study_p.name, 0, 0, False

def main():
    print("==================================================================")
    print("🧹 PURIFYING ALL LIBRARY STUDY NOTES: STRICT TOEIC 700+ TO 990 TARGET")
    print("==================================================================")
    print(f"🚫 Base Stoplist Active: {len(BASIC_VOCAB_STOPLIST):,} middle-school words will be stripped.")

    epubs = [str(p) for p in STUDY_ROOT.rglob("*.epub") if p.stat().st_size > 30000]
    print(f"📚 Purifying and optimizing {len(epubs):,} [study] & [e-s] EPUBs across whole library (12 workers)...\n")

    total_before = 0
    total_after = 0
    success_count = 0

    with ProcessPoolExecutor(max_workers=12) as ex:
        futures = [ex.submit(process_study_epub, ep) for ep in epubs]
        for fut in as_completed(futures):
            name, orig_r, kept_r, ok = fut.result()
            if ok:
                success_count += 1
                total_before += orig_r
                total_after += kept_r
                diff = orig_r - kept_r
                if orig_r > 0:
                    print(f"  ✨ [Purified] {name[:45]:<45} | {orig_r:>6,} ➔ {kept_r:>6,} rubies (Stripped {diff:>5,} basic words)")

    print("\n==================================================================")
    print("🎉 FULL LIBRARY STUDY NOTE PURIFICATION 100% COMPLETED!")
    print(f"  • Total Books Processed : {success_count:,} / {len(epubs):,} books")
    print(f"  • Previous Word Wise    : {total_before:,} annotations (included basic clutter)")
    print(f"  • Purified TOEIC 700+   : {total_after:,} high-yield annotations")
    print(f"  • Stripped Basic Trivia : {total_before - total_after:,} middle-school basic words removed")
    print("==================================================================")

if __name__ == "__main__":
    main()
