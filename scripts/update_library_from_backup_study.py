#!/usr/bin/env python3
"""scripts/update_library_from_backup_study.py

Updates all 4 editions ([study], [k-e], [k], [e-s]) in the library
using authentic new-version study EPUBs from '/Users/hyeokjunkong/Desktop/소설2/[backup_data] 20260807/[study]'.
"""

from __future__ import annotations

import html as html_mod
import os
import re
import shutil
import tempfile
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from bs4 import BeautifulSoup

BACKUP_STUDY_DIR = Path("/Users/hyeokjunkong/Desktop/소설2/[backup_data] 20260807/[study]")
LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

STUDY_ROOT = LIB_ROOT / "[study]"
KE_ROOT = LIB_ROOT / "[k-e]"
K_ROOT = LIB_ROOT / "[k]"
ES_ROOT = LIB_ROOT / "[e-s]"


def get_clean_stem(p: Path) -> str:
    name = p.stem
    name = re.sub(r"^\[(study|k-e|k|e-s|e|s)\]\s*", "", name, flags=re.IGNORECASE)
    return name.strip()


def build_ke_and_k_and_es_from_study(
    source_study_epub: Path,
    target_study_epub: Path,
    target_ke_epub: Path,
    target_k_epub: Path,
    target_es_epub: Path,
) -> tuple[bool, str]:
    try:
        # 1. Copy source [study] to target [study]
        target_study_epub.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_study_epub, target_study_epub)

        target_ke_epub.parent.mkdir(parents=True, exist_ok=True)
        target_k_epub.parent.mkdir(parents=True, exist_ok=True)
        target_es_epub.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="epub_update_") as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            with zipfile.ZipFile(source_study_epub, "r") as z:
                z.extractall(tmp_dir)

            html_files = [
                p for p in tmp_dir.rglob("*")
                if p.is_file() and p.suffix.lower() in (".xhtml", ".html", ".htm")
            ]

            # Storage for transformed HTML contents
            ke_contents = {}
            k_contents = {}
            es_contents = {}

            for h in html_files:
                rel_h = h.relative_to(tmp_dir)
                orig_text = h.read_text(encoding="utf-8", errors="ignore")

                # Parse BeautifulSoup
                soup_ke = BeautifulSoup(orig_text, "html.parser")
                soup_k = BeautifulSoup(orig_text, "html.parser")
                soup_es = BeautifulSoup(orig_text, "html.parser")

                # --- 1) KE edition: remove study notes ---
                for s in soup_ke.find_all(class_=lambda c: c and "study-note" in c):
                    prev = s.find_previous_sibling()
                    if prev and prev.name == "br":
                        prev.decompose()
                    s.decompose()
                ke_contents[rel_h] = str(soup_ke).encode("utf-8")

                # --- 2) K edition: keep only Korean text ---
                # Remove English spans in .pair and .study-note
                for p in soup_k.find_all(class_=lambda c: c and "pair" in c):
                    en_span = p.find(class_=lambda c: c and "en" in c)
                    if en_span:
                        en_span.decompose()
                    study_span = p.find(class_=lambda c: c and "study-note" in c)
                    if study_span:
                        study_span.decompose()
                    for br in p.find_all("br"):
                        br.decompose()
                # For h2 with (EN) KO
                for h2 in soup_k.find_all("h2"):
                    en_span = h2.find(class_=lambda c: c and "en" in c)
                    if en_span:
                        en_span.decompose()
                k_contents[rel_h] = str(soup_k).encode("utf-8")

                # --- 3) ES edition: keep English text + study notes, remove Korean ---
                for p in soup_es.find_all(class_=lambda c: c and "pair" in c):
                    ko_span = p.find(class_=lambda c: c and "ko" in c)
                    if ko_span:
                        ko_span.decompose()
                    # Keep study note with br if exists
                for h2 in soup_es.find_all("h2"):
                    ko_span = h2.find(class_=lambda c: c and "ko" in c)
                    if ko_span:
                        ko_span.decompose()
                es_contents[rel_h] = str(soup_es).encode("utf-8")

            # Write target [k-e]
            with zipfile.ZipFile(target_ke_epub, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                for item in tmp_dir.rglob("*"):
                    if item.is_file():
                        rel = item.relative_to(tmp_dir)
                        if rel in ke_contents:
                            zout.writestr(str(rel), ke_contents[rel])
                        else:
                            zout.write(item, str(rel))

            # Write target [k]
            with zipfile.ZipFile(target_k_epub, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                for item in tmp_dir.rglob("*"):
                    if item.is_file():
                        rel = item.relative_to(tmp_dir)
                        if rel in k_contents:
                            zout.writestr(str(rel), k_contents[rel])
                        else:
                            zout.write(item, str(rel))

            # Write target [e-s]
            with zipfile.ZipFile(target_es_epub, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                for item in tmp_dir.rglob("*"):
                    if item.is_file():
                        rel = item.relative_to(tmp_dir)
                        if rel in es_contents:
                            zout.writestr(str(rel), es_contents[rel])
                        else:
                            zout.write(item, str(rel))

        return True, target_study_epub.name
    except Exception as e:
        return False, f"{source_study_epub.name}: {e}"


def main():
    print("==================================================================")
    print("📚 UPDATING 4-EDITION LIBRARY FROM 2026-08-07 [STUDY] BACKUP")
    print("==================================================================")

    backup_epubs = sorted([
        p for p in BACKUP_STUDY_DIR.rglob("*.epub")
        if not any(x.startswith(".") for x in p.parts)
    ])
    print(f"Total backup [study] EPUBs to process: {len(backup_epubs)}")

    # Build map of existing library folders
    existing_map = {}
    for edition_root in [STUDY_ROOT, KE_ROOT, K_ROOT, ES_ROOT]:
        if edition_root.exists():
            for p in edition_root.rglob("*.epub"):
                if not any(x.startswith(".") for x in p.parts) and "[backup_data]" not in str(p):
                    c_stem = get_clean_stem(p).lower()
                    rel_parent = p.parent.relative_to(edition_root)
                    existing_map[c_stem] = rel_parent

    tasks = []
    for b_epub in backup_epubs:
        clean_stem = get_clean_stem(b_epub)
        c_lower = clean_stem.lower()

        if c_lower in existing_map:
            rel_dir = existing_map[c_lower]
        else:
            rel_dir = b_epub.parent.relative_to(BACKUP_STUDY_DIR)

        t_study = STUDY_ROOT / rel_dir / f"[study] {clean_stem}.epub"
        t_ke = KE_ROOT / rel_dir / f"[k-e] {clean_stem}.epub"
        t_k = K_ROOT / rel_dir / f"[k] {clean_stem}.epub"
        t_es = ES_ROOT / rel_dir / f"[e-s] {clean_stem}.epub"

        tasks.append((b_epub, t_study, t_ke, t_k, t_es))

    print(f"Prepared {len(tasks)} books across 4 editions ([study], [k-e], [k], [e-s]).")
    print(f"Running multi-process build on {min(8, os.cpu_count() or 4)} CPU cores...")

    start_time = time.time()
    success_cnt = 0
    fail_cnt = 0

    with ProcessPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as executor:
        futures = {
            executor.submit(
                build_ke_and_k_and_es_from_study,
                b_epub,
                t_study,
                t_ke,
                t_k,
                t_es,
            ): b_epub.name
            for b_epub, t_study, t_ke, t_k, t_es in tasks
        }

        for idx, future in enumerate(as_completed(futures), 1):
            ok, msg = future.result()
            if ok:
                success_cnt += 1
                if idx % 20 == 0 or idx == len(tasks):
                    print(f"[{idx:3d}/{len(tasks):3d}] ✅ {msg}")
            else:
                fail_cnt += 1
                print(f"[{idx:3d}/{len(tasks):3d}] ❌ {msg}")

    elapsed = time.time() - start_time
    print("==================================================================")
    print(f"🎉 4-Edition Library Update Completed in {elapsed:.2f}s!")
    print(f"   • Successfully Updated : {success_cnt} books (x4 = {success_cnt * 4} EPUBs)")
    print(f"   • Failed               : {fail_cnt} books")
    print("==================================================================")


if __name__ == "__main__":
    main()
