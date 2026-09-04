#!/usr/bin/env python3
"""High-Speed Batch Transformer: Kindle Genuine Word Wise across [study] & [e-s] Library.

Processes all 1,141 books in /Users/hyeokjunkong/Desktop/소설2/[study] and [e-s].
"""

from __future__ import annotations

import html
import os
import re
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

/* === AMAZON KINDLE GENUINE OVERHEAD WORD WISE STYLING === */
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

def fast_transform_html(html_str: str, edition_type: str) -> str:
    # Pattern to match <p class="pair">...</p> or <p>...</p>
    def repl_p(m):
        full_p = m.group(0)

        # Check for study note
        note_match = re.search(r'<span[^>]*class=["\']study-note["\'][^>]*>(.*?)</span>', full_p, flags=re.DOTALL)
        en_match = re.search(r'<span[^>]*class=["\']en["\'][^>]*>(.*?)</span>', full_p, flags=re.DOTALL)
        ko_match = re.search(r'<span[^>]*class=["\']ko["\'][^>]*>(.*?)</span>', full_p, flags=re.DOTALL)

        raw_note = note_match.group(1).strip() if note_match else ""
        raw_en = en_match.group(1).strip() if en_match else ""
        raw_ko = ko_match.group(1).strip() if ko_match else ""

        # Check embedded note in ko
        if "※" in raw_ko:
            parts = raw_ko.split("※", 1)
            raw_ko = parts[0].strip()
            emb = "※" + parts[1].strip()
            raw_note = (raw_note + " ; " + emb) if raw_note else emb

        # If [e-s] and no spans but has ※ in paragraph text
        if edition_type == "e-s" and not en_match and not ko_match and "※" in full_p:
            p_inner = re.sub(r"^<p[^>]*>|</p>$", "", full_p).strip()
            if "※" in p_inner:
                parts = p_inner.split("※", 1)
                raw_en = parts[0].strip()
                raw_note = "※" + parts[1].strip()

        if not raw_note and not ("<ruby>" in raw_en):
            return full_p

        pairs = parse_authentic_study_note(raw_note) if raw_note else []

        # Annotate raw_en with Word Wise
        annotated_en = raw_en
        for w, mean in pairs:
            # Avoid re-annotating if already ruby
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

            with zipfile.ZipFile(tmp_file, "w") as zout:
                zout.comment = zin.comment
                if "mimetype" in in_names:
                    zout.writestr(
                        zipfile.ZipInfo("mimetype"),
                        zin.read("mimetype"),
                        compress_type=zipfile.ZIP_STORED
                    )

                for name in in_names:
                    if name == "mimetype":
                        continue
                    data = zin.read(name)

                    if name.lower().endswith(".css"):
                        zout.writestr(name, kindle_css, compress_type=zipfile.ZIP_DEFLATED)
                    elif name.endswith((".xhtml", ".html", ".htm")):
                        html_str = data.decode("utf-8", errors="replace")
                        if "class=\"study-note\"" in html_str or "class='study-note'" in html_str or "※" in html_str:
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
    print("🌟 BATCH APPLYING KINDLE GENUINE WORD WISE ACROSS [study] & [e-s]", flush=True)
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
