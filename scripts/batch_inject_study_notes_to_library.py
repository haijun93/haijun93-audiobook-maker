#!/usr/bin/env python3
"""scripts/batch_inject_study_notes_to_library.py

Batch upgrades all legacy and missing [study] edition EPUBs across the entire library
by injecting high-yield TOEIC 700+ vocabulary notes using the 215,000+ Master Study Lexicon.
"""

from __future__ import annotations

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
    "off", "over", "under", "again", "further", "once", "here", "there", "all",
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
    if not selected:
        return ""
    res = "※ " + "; ".join(selected)
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", res)


def process_single_epub(args_tuple: tuple[str, str]) -> tuple[bool, str, int | str]:
    src_path_str, target_path_str = args_tuple
    src_epub_path = Path(src_path_str)
    target_study_path = Path(target_path_str)
    lexicon = get_lexicon()

    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix="study_batch_"))
        with zipfile.ZipFile(src_epub_path, "r") as z:
            z.extractall(tmp_dir)

        injected_count = 0
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

        # Create target dir
        target_study_path.parent.mkdir(parents=True, exist_ok=True)
        output_tmp = tmp_dir.parent / (target_study_path.name + ".tmp")

        with zipfile.ZipFile(output_tmp, "w", zipfile.ZIP_DEFLATED) as z_out:
            mimetype_path = tmp_dir / "mimetype"
            if mimetype_path.exists():
                z_out.write(
                    mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED
                )
            for root, dirs, files in os.walk(tmp_dir):
                for file in files:
                    if file == "mimetype":
                        continue
                    full_p = Path(root) / file
                    rel_p = full_p.relative_to(tmp_dir)
                    z_out.write(full_p, str(rel_p))

        shutil.move(str(output_tmp), str(target_study_path))
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return (True, target_study_path.name, injected_count)
    except Exception as e:
        return (False, target_study_path.name, str(e))


def main():
    t0 = time.time()
    desktop = Path("/Users/hyeokjunkong/Desktop")
    lib_root = None
    for p in desktop.iterdir():
        if "소설2" in unicodedata.normalize("NFC", p.name):
            lib_root = p
            break

    if not lib_root:
        print("Error: Library root 소설2 not found.")
        return

    study_dir = lib_root / "[study]"
    ke_dir = lib_root / "[k-e]"

    tasks = []
    # 1. Existing [study] books that need notes
    for ep in study_dir.glob("**/*.epub"):
        tasks.append((str(ep), str(ep)))

    # 2. [k-e] books without [study] counterpart
    for ep in ke_dir.glob("**/*.epub"):
        rel = ep.relative_to(ke_dir)
        target_study = study_dir / rel.parent / rel.name.replace("[k-e] ", "[study] ")
        if not target_study.exists():
            tasks.append((str(ep), str(target_study)))

    print("===============================================================")
    print("🚀 Launching Batch Library Study Notes Injection Engine")
    print(f"   • Total Books to Process : {len(tasks):,} books")
    print(f"   • Master Lexicon Entries : {len(get_lexicon()):,} entries")
    print("===============================================================")

    success = 0
    total_notes = 0

    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(process_single_epub, t): t for t in tasks}
        for fut in as_completed(futures):
            ok, name, count = fut.result()
            if ok:
                success += 1
                if isinstance(count, int):
                    total_notes += count
                print(f"[{success:3d}/{len(tasks)}] ✅ {name[:60]:60s} (+{count:,} notes)")
            else:
                print(f"❌ Failed: {name} ({count})")

    print("\n===============================================================")
    print("🎉 Batch Study Generation Completed Successfully!")
    print(f"   • Total Books Processed : {success:,} / {len(tasks):,}")
    print(f"   • Total TOEIC Notes     : {total_notes:,} notes injected")
    print(f"   • Elapsed Time          : {time.time() - t0:.2f} seconds")
    print("===============================================================")


if __name__ == "__main__":
    main()
