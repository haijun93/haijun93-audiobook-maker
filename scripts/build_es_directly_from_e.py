#!/usr/bin/env python3
"""scripts/build_es_directly_from_e.py

Generates [e-s] (English Original + TOEIC 700+ Study Notes) directly from
all [e] original English EPUBs in the library using master_study_lexicon.json.
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


def process_single_e_to_es(task: tuple[str, str]) -> tuple[bool, str, str]:
    e_path_str, es_path_str = task
    e_path = Path(e_path_str)
    es_path = Path(es_path_str)
    lexicon = get_lexicon()

    if es_path.exists() and es_path.stat().st_size > 1000:
        return (True, es_path.name, "Already exists")

    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix="es_gen_"))
        with zipfile.ZipFile(e_path, "r") as z:
            z.extractall(tmp_dir)

        injected = 0
        html_files = list(tmp_dir.glob("**/*.xhtml")) + list(tmp_dir.glob("**/*.html")) + list(tmp_dir.glob("**/*.htm"))
        for xhtml in html_files:
            content = xhtml.read_text(encoding="utf-8", errors="ignore")
            soup = BeautifulSoup(content, "html.parser")
            modified = False

            for p in soup.find_all(["p", "div", "li"]):
                # check if already has note
                if p.find(class_="study-note"):
                    continue

                txt = p.get_text(strip=True)
                if len(txt) < 15:
                    continue

                words = re.findall(r"\b[a-zA-Z]{3,}\b", txt.lower())
                if not words:
                    continue

                found = []
                for i in range(len(words) - 1):
                    bg = f"{words[i]} {words[i+1]}"
                    if bg in lexicon:
                        found.append((bg, lexicon[bg], 10))
                for w in words:
                    if w not in STOPWORDS and w in lexicon:
                        found.append((w, lexicon[w], 5))

                if found:
                    found.sort(key=lambda x: (x[2], len(x[0])), reverse=True)
                    sel = []
                    seen = set()
                    for w, m, _ in found:
                        if w not in seen and not any(w in s or s in w for s in seen):
                            seen.add(w)
                            sel.append(f"{w} - {m}")
                        if len(sel) >= 3:
                            break
                    if sel:
                        note = "※ " + "; ".join(sel)
                        br = soup.new_tag("br")
                        span = soup.new_tag(
                            "span", **{"class": "study-note", "xml:lang": "ko"}
                        )
                        span.string = note
                        p.append(br)
                        p.append(span)
                        modified = True
                        injected += 1

            if modified:
                xhtml.write_text(str(soup), encoding="utf-8")

        es_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_epub = tmp_dir.parent / (es_path.name + ".tmp")
        with zipfile.ZipFile(tmp_epub, "w", zipfile.ZIP_DEFLATED) as z_out:
            mp = tmp_dir / "mimetype"
            if mp.exists():
                z_out.write(mp, "mimetype", compress_type=zipfile.ZIP_STORED)
            for root, dirs, files in os.walk(tmp_dir):
                for f in files:
                    if f == "mimetype":
                        continue
                    fp = Path(root) / f
                    z_out.write(fp, str(fp.relative_to(tmp_dir)))
        shutil.move(str(tmp_epub), str(es_path))
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return (True, es_path.name, f"+{injected} notes")
    except Exception as e:
        return (False, e_path.name, str(e))


def main():
    desktop = Path("/Users/hyeokjunkong/Desktop")
    lib_root = None
    for p in desktop.iterdir():
        if "소설2" in unicodedata.normalize("NFC", p.name):
            lib_root = p
            break

    if not lib_root:
        print("소설2 not found.")
        return

    e_root = lib_root / "[e]"
    es_root = lib_root / "[e-s]"

    tasks = []
    for ep in e_root.glob("**/*.epub"):
        rel = ep.relative_to(e_root)
        dest_es = es_root / rel.parent / rel.name.replace("[e] ", "[e-s] ")
        if not dest_es.exists() or dest_es.stat().st_size < 1000:
            tasks.append((str(ep), str(dest_es)))

    print(f"🚀 Generating [e-s] Study Editions directly from [e] originals for {len(tasks)} books...")
    success = 0
    with ProcessPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(process_single_e_to_es, t): t for t in tasks}
        for fut in as_completed(futures):
            ok, name, msg = fut.result()
            if ok:
                success += 1
                print(f"[{success:3d}/{len(tasks)}] ✅ {name[:55]:55s} ({msg})")
            else:
                print(f"❌ Failed {name}: {msg}")

    print(f"🎉 Successfully built {success}/{len(tasks)} [e-s] books!")


if __name__ == "__main__":
    main()
