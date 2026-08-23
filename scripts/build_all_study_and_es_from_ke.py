#!/usr/bin/env python3
"""scripts/build_all_study_and_es_from_ke.py

Rebuilds and synchronizes all [study] and [e-s] edition EPUBs directly from
the 609 canonical [k-e] bilingual editions using the 216,400+ Master Study Lexicon.
"""

from __future__ import annotations

import html as html_mod
import json
import os
import re
import shutil
import tempfile
import time
import unicodedata
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
LEXICON_PATH = ROOT / "data" / "master_study_lexicon.json"

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
    "three", "book", "chapter"
}

_LEXICON_CACHE = None


def get_lexicon() -> dict[str, str]:
    global _LEXICON_CACHE
    if _LEXICON_CACHE is None:
        if LEXICON_PATH.exists():
            _LEXICON_CACHE = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))
        else:
            _LEXICON_CACHE = {}
    return _LEXICON_CACHE


def extract_notes_fast(en_text: str, ko_text: str, lexicon: dict[str, str]) -> str:
    en_words = re.findall(r"\b[a-zA-Z]{3,}\b", en_text.lower())
    if not en_words:
        return ""

    found = []
    # 1. 2-word collocations
    for i in range(len(en_words) - 1):
        bigram = f"{en_words[i]} {en_words[i+1]}"
        if bigram in lexicon:
            found.append((bigram, lexicon[bigram], 10))

    # 2. Single words
    for w in en_words:
        if w in STOPWORDS:
            continue
        if w in lexicon:
            found.append((w, lexicon[w], 5))

    if not found:
        return ""

    found.sort(key=lambda x: (x[2], len(x[0])), reverse=True)

    selected = []
    seen = set()
    for w, m, _ in found:
        if w not in seen and not any(w in s or s in w for s in seen):
            seen.add(w)
            selected.append(f"{w} - {m}")
        if len(selected) >= 3:
            break

    return "※ " + "; ".join(selected) if selected else ""


def build_study_and_es_from_ke(task_info: tuple[str, str, str]) -> tuple[bool, str, int]:
    src_ke_str, dest_study_str, dest_es_str = task_info
    src_ke = Path(src_ke_str)
    dest_study = Path(dest_study_str)
    dest_es = Path(dest_es_str)
    lexicon = get_lexicon()

    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix="build_study_"))
        with zipfile.ZipFile(src_ke, "r") as z:
            z.extractall(tmp_dir)

        injected_count = 0
        
        # 1. Inject study notes into all xhtml
        for html_file in tmp_dir.glob("**/*.xhtml"):
            content = html_file.read_text(encoding="utf-8")
            soup = BeautifulSoup(content, "html.parser")

            pairs = soup.find_all(
                ["p", "div", "li", "h1", "h2", "h3"],
                class_=lambda c: c and "pair" in c,
            )
            modified = False

            for p_tag in pairs:
                en_span = p_tag.find("span", class_="en")
                ko_span = p_tag.find("span", class_="ko")
                study_span = p_tag.find("span", class_="study-note")

                if en_span and ko_span and not study_span:
                    en_txt = en_span.get_text(strip=True)
                    ko_txt = ko_span.get_text(strip=True)
                    note = extract_notes_fast(en_txt, ko_txt, lexicon)
                    if note:
                        br_tag = soup.new_tag("br")
                        new_study_span = soup.new_tag(
                            "span", **{"class": "study-note", "xml:lang": "ko"}
                        )
                        new_study_span.string = note
                        p_tag.append(br_tag)
                        p_tag.append(new_study_span)
                        modified = True
                        injected_count += 1

            if modified:
                html_file.write_text(str(soup), encoding="utf-8")

        # 2. Package [study] EPUB
        dest_study.parent.mkdir(parents=True, exist_ok=True)
        tmp_study_epub = tmp_dir.parent / (dest_study.name + ".tmp")
        with zipfile.ZipFile(tmp_study_epub, "w", zipfile.ZIP_DEFLATED) as z_out:
            mimetype_path = tmp_dir / "mimetype"
            if mimetype_path.exists():
                z_out.write(mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED)
            for root, dirs, files in os.walk(tmp_dir):
                for file in files:
                    if file == "mimetype": continue
                    full_p = Path(root) / file
                    rel_p = full_p.relative_to(tmp_dir)
                    z_out.write(full_p, str(rel_p))
        shutil.move(str(tmp_study_epub), str(dest_study))

        # 3. Create [e-s] by removing <span class="ko"> and preceding <br/>
        dest_es.parent.mkdir(parents=True, exist_ok=True)
        for html_file in tmp_dir.glob("**/*.xhtml"):
            content = html_file.read_text(encoding="utf-8")
            soup = BeautifulSoup(content, "html.parser")
            modified_es = False
            for ko_span in soup.find_all("span", class_="ko"):
                # remove previous br if exists
                prev_sibling = ko_span.previous_sibling
                if prev_sibling and getattr(prev_sibling, "name", None) == "br":
                    prev_sibling.decompose()
                ko_span.decompose()
                modified_es = True
            if modified_es:
                html_file.write_text(str(soup), encoding="utf-8")

        tmp_es_epub = tmp_dir.parent / (dest_es.name + ".tmp")
        with zipfile.ZipFile(tmp_es_epub, "w", zipfile.ZIP_DEFLATED) as z_out:
            mimetype_path = tmp_dir / "mimetype"
            if mimetype_path.exists():
                z_out.write(mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED)
            for root, dirs, files in os.walk(tmp_dir):
                for file in files:
                    if file == "mimetype": continue
                    full_p = Path(root) / file
                    rel_p = full_p.relative_to(tmp_dir)
                    z_out.write(full_p, str(rel_p))
        shutil.move(str(tmp_es_epub), str(dest_es))

        shutil.rmtree(tmp_dir, ignore_errors=True)
        return (True, dest_study.name, injected_count)

    except Exception as e:
        return (False, dest_study.name, str(e))


def main():
    t0 = time.time()
    desktop = Path("/Users/hyeokjunkong/Desktop")
    lib_root = None
    for p in desktop.iterdir():
        if "소설2" in unicodedata.normalize("NFC", p.name):
            lib_root = p
            break

    if not lib_root:
        print("Library root 소설2 not found.")
        return

    ke_root = lib_root / "[k-e]"
    study_root = lib_root / "[study]"
    es_root = lib_root / "[e-s]"

    def sanitize_rel_parent(rel: Path) -> Path:
        parts = [p for p in rel.parts if p not in {"[e]", "finished", "non-english", "Uncategorized"}]
        return Path(*parts) if parts else Path("Literary_General_Fiction")

    tasks = []
    for ke_epub in ke_root.glob("**/*.epub"):
        rel = ke_epub.relative_to(ke_root)
        clean_parent = sanitize_rel_parent(rel.parent)
        dest_study_epub = study_root / clean_parent / rel.name.replace("[k-e] ", "[study] ")
        dest_es_epub = es_root / clean_parent / rel.name.replace("[k-e] ", "[e-s] ")
        tasks.append((str(ke_epub), str(dest_study_epub), str(dest_es_epub)))

    print("==================================================================")
    print(f"🚀 Launching Full [study] & [e-s] Master Rebuild Engine")
    print(f"   • Total Source [k-e] Books: {len(tasks):,}")
    print(f"   • Master Study Lexicon    : {len(get_lexicon()):,} entries")
    print("==================================================================")

    success = 0
    total_notes = 0

    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(build_study_and_es_from_ke, t): t for t in tasks}
        for fut in as_completed(futures):
            ok, name, count = fut.result()
            if ok:
                success += 1
                if isinstance(count, int):
                    total_notes += count
                print(f"[{success:3d}/{len(tasks)}] ✅ {name[:55]:55s} (+{count:,} notes)")
            else:
                print(f"❌ Failed {name}: {count}")

    print("\n==================================================================")
    print(f"🎉 Full Library [study] & [e-s] Rebuild Completed Successfully!")
    print(f"   • Total Books Built   : {success:,} / {len(tasks):,}")
    print(f"   • Total Study Notes   : {total_notes:,} TOEIC 700+ notes injected")
    print(f"   • Execution Time      : {time.time() - t0:.2f} seconds")
    print("==================================================================")


if __name__ == "__main__":
    main()
