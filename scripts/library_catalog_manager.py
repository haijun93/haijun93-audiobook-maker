#!/usr/bin/env python3
"""scripts/library_catalog_manager.py

Master Library Catalog & Deduplication Guard:
1. Indexes all books across the 4 editions ([k], [k-e], [study], [e-s]).
2. Generates fuzzy-resilient normalized fingerprints (ignoring edition prefixes, ratings, punctuation).
3. Persists master library index at data/master_library_catalog.json.
4. Provides `check_duplicate()` guard API for all translation engines & schedulers.
"""

from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path

# Paths
REPO_ROOT = Path("/Users/hyeokjunkong/Desktop/myproject_python/haijun93-audiobook-maker")
CATALOG_PATH = REPO_ROOT / "data/master_library_catalog.json"
DESKTOP = Path("/Users/hyeokjunkong/Desktop")
LIB_ROOT = next((p for p in DESKTOP.iterdir() if "소설2" in unicodedata.normalize("NFC", p.name)), None)

PREFIX_RE = re.compile(r"^(\s*\[\s*(k|k-e|study|e-s|e)\s*[-\s]*\]\s*)+", re.I)
RATING_RE = re.compile(r"\s*\(\s*\d+\.\d+\s*\)\s*")
CLEAN_PUNCT_RE = re.compile(r"[^a-zA-Z0-9가-힣\s]")


def normalize_fingerprint(title_or_filename: str) -> str:
    """Extracts clean, punctuation-free normalized fingerprint for duplicate checking."""
    name = str(title_or_filename)
    if name.lower().endswith(".epub"):
        name = name[:-5]
        
    # Strip prefixes
    while True:
        m = PREFIX_RE.match(name)
        if m:
            name = name[m.end():].strip()
        else:
            break
            
    # Strip rating, e.g. (4.15)
    name = RATING_RE.sub(" ", name)
    
    # Strip noise words & author markers
    name = re.sub(r"#", "", name)
    name = re.sub(r"oceanofpdf|readrobe|dailybooks", "", name, flags=re.I)
    
    # Normalize unicode
    name = unicodedata.normalize("NFKD", name)
    
    # Normalize punctuation to spaces
    name = CLEAN_PUNCT_RE.sub(" ", name)
    
    # Collapse multiple spaces and lowercase
    tokens = [t.lower() for t in name.split() if len(t) > 0]
    return " ".join(tokens)


def scan_and_build_catalog() -> dict:
    """Scans the entire library and builds data/master_library_catalog.json."""
    if not LIB_ROOT or not LIB_ROOT.exists():
        return {}
        
    catalog = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_books_unique": 0,
        "editions": {"k": 0, "k-e": 0, "study": 0, "e-s": 0},
        "fingerprints": {}, # fp -> {title, editions: {k: path, k-e: path, ...}, size_bytes}
    }
    
    ed_map = {
        "[k]": "k",
        "[k-e]": "k-e",
        "[study]": "study",
        "[e-s]": "e-s"
    }
    
    for ed_dir_name, ed_code in ed_map.items():
        ed_dir = LIB_ROOT / ed_dir_name
        if not ed_dir.exists():
            continue
            
        epubs = [p for p in ed_dir.rglob("*.epub") if not p.name.startswith("._")]
        catalog["editions"][ed_code] = len(epubs)
        
        for epub in epubs:
            try:
                stat = epub.stat()
                if stat.st_size < 5000: # Ignore corrupted empty files (<5KB)
                    continue
            except Exception:
                continue
                
            fp = normalize_fingerprint(epub.name)
            if not fp:
                continue
                
            if fp not in catalog["fingerprints"]:
                catalog["fingerprints"][fp] = {
                    "base_title": epub.stem,
                    "editions": {},
                    "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                }
                
            catalog["fingerprints"][fp]["editions"][ed_code] = str(epub.resolve())
            
    catalog["total_books_unique"] = len(catalog["fingerprints"])
    
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    return catalog


def is_book_already_completed(
    input_path_or_title: str | Path,
    target_edition: str = "k-e",
    min_size_bytes: int = 15000
) -> tuple[bool, str, Path | None]:
    """Guard API: Checks if a given book is already completed in the library.
    
    Returns:
        (is_duplicate, reason_message, existing_file_path_or_None)
    """
    fp = normalize_fingerprint(str(input_path_or_title))
    if not fp:
        return False, "empty_fingerprint", None
        
    # Load catalog if exists
    catalog_data = None
    if CATALOG_PATH.exists():
        try:
            catalog_data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
            
    if not catalog_data:
        catalog_data = scan_and_build_catalog()
        
    fps = catalog_data.get("fingerprints", {})
    
    # 1. Exact fingerprint match
    if fp in fps:
        entry = fps[fp]
        editions = entry.get("editions", {})
        if target_edition in editions:
            p = Path(editions[target_edition])
            if p.exists() and p.stat().st_size >= min_size_bytes:
                return True, f"이미 서재 {target_edition} 에디션에 완성본이 존재함: {p.name}", p
        elif "k-e" in editions and target_edition == "k":
            # [k-e] exists, can be derived
            p = Path(editions["k-e"])
            if p.exists() and p.stat().st_size >= min_size_bytes:
                return True, f"기본 대역본([k-e])이 이미 완성되어 있음: {p.name}", p
                
    # 2. Token subset match (resilient against slight title variations)
    fp_tokens = set(fp.split())
    if len(fp_tokens) >= 3:
        for exist_fp, entry in fps.items():
            exist_tokens = set(exist_fp.split())
            overlap = len(fp_tokens & exist_tokens)
            if overlap >= len(fp_tokens) * 0.85 and overlap >= len(exist_tokens) * 0.85:
                editions = entry.get("editions", {})
                if target_edition in editions:
                    p = Path(editions[target_edition])
                    if p.exists() and p.stat().st_size >= min_size_bytes:
                        return True, f"유사 일치 도서가 이미 서재에 존재함 ({exist_fp}): {p.name}", p

    return False, "new_book", None


if __name__ == "__main__":
    print("==================================================================")
    print("📚 BUILDING MASTER LIBRARY CATALOG & DEDUPLICATION INDEX")
    print("==================================================================")
    cat = scan_and_build_catalog()
    print(f"✅ Master Catalog Updated: {CATALOG_PATH}")
    print(f"  - Unique Book Titles Indexed: {cat.get('total_books_unique', 0)}")
    print(f"  - [k]     Korean-Only       : {cat.get('editions', {}).get('k', 0)} books")
    print(f"  - [k-e]   Bilingual         : {cat.get('editions', {}).get('k-e', 0)} books")
    print(f"  - [study] Korean Study      : {cat.get('editions', {}).get('study', 0)} books")
    print(f"  - [e-s]   English Study     : {cat.get('editions', {}).get('e-s', 0)} books")
    print("==================================================================")
