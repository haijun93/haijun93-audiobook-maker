#!/usr/bin/env python3
"""scripts/update_master_study_lexicon.py

Continuously extracts, refines, and updates the 215,000+ entry Master Study Lexicon
from all [study] edition EPUBs in the local and Google Drive library repositories.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
LOCAL_LEXICON_PATH = DATA_DIR / "master_study_lexicon.json"


def find_library_roots() -> list[Path]:
    roots = []
    desktop = Path("/Users/hyeokjunkong/Desktop")
    if desktop.exists():
        for p in desktop.iterdir():
            if "소설2" in unicodedata.normalize("NFC", p.name):
                roots.append(p)
                break

    gdrive = Path(
        "/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books"
    )
    if gdrive.exists():
        roots.append(gdrive)

    return roots


def load_current_lexicon() -> dict[str, str]:
    if LOCAL_LEXICON_PATH.exists():
        try:
            return json.loads(LOCAL_LEXICON_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def extract_notes_from_epub(epub_path: Path) -> dict[str, str]:
    extracted = {}
    try:
        with zipfile.ZipFile(epub_path, "r") as z:
            for name in z.namelist():
                if name.endswith(".xhtml") or name.endswith(".html"):
                    content = z.read(name).decode("utf-8", errors="ignore")
                    # 1. Standard novel study notes: <span class="study-note">※ ...</span>
                    notes = re.findall(
                        r'<span class="study-note"[^>]*>※\s*([^<]+)</span>', content
                    )
                    for n in notes:
                        parts = n.split(";")
                        for part in parts:
                            if " - " in part:
                                k, v = part.split(" - ", 1)
                                k_clean = k.strip().lower()
                                v_clean = v.strip()
                                if len(k_clean) >= 2 and len(v_clean) >= 1:
                                    if (
                                        k_clean not in extracted
                                        or len(v_clean) > len(extracted[k_clean])
                                    ):
                                        extracted[k_clean] = v_clean
                                        
                    # 2. Native Daily English playlist entry format: <div class="entry"><p class="phrase">...</p><p class="meaning">...</p></div>
                    if 'class="entry"' in content or 'class="phrase"' in content:
                        from bs4 import BeautifulSoup
                        import html as html_mod
                        soup = BeautifulSoup(content, "html.parser")
                        for entry in soup.find_all("div", class_="entry"):
                            p_tag = entry.find("p", class_="phrase")
                            m_tag = entry.find("p", class_="meaning")
                            if p_tag and m_tag:
                                p_txt = html_mod.unescape(p_tag.get_text(strip=True))
                                m_txt = html_mod.unescape(m_tag.get_text(strip=True))
                                if p_txt and m_txt:
                                    k_clean = re.sub(r"[\?\.\!\,]+$", "", p_txt.strip().lower()).strip()
                                    v_clean = m_txt.strip()
                                    if len(k_clean) >= 2 and len(v_clean) >= 1:
                                        extracted[k_clean] = v_clean
    except Exception:
        pass
    return extracted


def update_master_lexicon(verbose: bool = True) -> dict[str, str]:
    DATA_DIR.mkdir(exist_ok=True)
    lexicon = load_current_lexicon()
    initial_count = len(lexicon)

    lib_roots = find_library_roots()
    if not lib_roots:
        if verbose:
            print("No library root found.")
        return lexicon

    scanned_epubs = set()
    new_entries_count = 0
    updated_entries_count = 0

    for root in lib_roots:
        # Scan both [study] and [s] (expression playlists)
        for sub_dir_name in ["[study]", "[s]"]:
            target_dir = root / sub_dir_name
            if not target_dir.exists():
                continue

            for ep in target_dir.glob("**/*.epub"):
                if ep.name in scanned_epubs:
                    continue
                scanned_epubs.add(ep.name)

                book_notes = extract_notes_from_epub(ep)
                for k, v in book_notes.items():
                    if k not in lexicon:
                        lexicon[k] = v
                        new_entries_count += 1
                    elif len(v) > len(lexicon[k]):
                        lexicon[k] = v
                        updated_entries_count += 1

    # Save to project local data directory
    LOCAL_LEXICON_PATH.write_text(
        json.dumps(lexicon, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Synchronize to MD collection in both Local and Google Drive
    for root in lib_roots:
        md_dir = root / "MD collection"
        md_dir.mkdir(parents=True, exist_ok=True)
        dest_file = md_dir / "master_study_lexicon.json"
        dest_file.write_text(
            json.dumps(lexicon, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    if verbose:
        print(f"=== Master Study Lexicon Update Summary ===")
        print(f"  • Total Books Scanned   : {len(scanned_epubs):,} [study] EPUBs")
        print(f"  • Previous Lexicon Size : {initial_count:,} entries")
        print(f"  • New Vocab Added       : +{new_entries_count:,} entries")
        print(f"  • Descriptions Enhanced : +{updated_entries_count:,} entries")
        print(f"  • Current Lexicon Size  : {len(lexicon):,} entries")
        print(f"  • Synced to MD Collections across Local & Google Drive")

    return lexicon


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Update Master Study Lexicon from [study] EPUBs"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress verbose output"
    )
    args = parser.parse_args()
    update_master_lexicon(verbose=not args.quiet)
