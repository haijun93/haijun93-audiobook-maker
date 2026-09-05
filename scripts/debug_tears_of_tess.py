#!/usr/bin/env python3
"""scripts/debug_tears_of_tess.py
Debugs TOC, structure, and missing translations in Tears of Tess.
"""

from __future__ import annotations

import zipfile
from bs4 import BeautifulSoup
from pathlib import Path

epub_k = Path("/Users/hyeokjunkong/Desktop/소설2/[k]/#Top 10 dark romance/[k] Tears of Tess - Pepper Winters.epub")
epub_e = Path("/Users/hyeokjunkong/Desktop/소설2/[e]/#Top 10 dark romance/[e] Tears of Tess - Pepper Winters.epub")
epub_ke = Path("/Users/hyeokjunkong/Desktop/소설2/[k-e]/#Top 10 dark romance/[k-e] Tears of Tess - Pepper Winters.epub")

print("=== 1. ENGLISH ORIGINAL FILES & TOC ===")
with zipfile.ZipFile(epub_e, "r") as z:
    for n in z.namelist():
        if n.endswith((".ncx", ".xhtml", ".html", ".htm")):
            if "toc" in n.lower() or "nav" in n.lower():
                soup = BeautifulSoup(z.read(n), "html.parser")
                print(f"\nTOC File: {n}")
                for a in soup.find_all("a"):
                    print(f"  • [HTML a] {a.get_text().strip()} -> {a.get('href')}")
                for nav in soup.find_all("navpoint"):
                    lbl = nav.find("text")
                    src = nav.find("content")
                    if lbl and src:
                        print(f"  • [NCX nav] {lbl.get_text().strip()} -> {src.get('src')}")

print("\n=== 2. ENGLISH ORIGINAL FIRST 5 HTML CONTENTS ===")
with zipfile.ZipFile(epub_e, "r") as z:
    htmls = [n for n in z.namelist() if n.endswith((".xhtml", ".html", ".htm")) and not "toc" in n.lower() and not "nav" in n.lower()]
    for h in htmls[:6]:
        soup = BeautifulSoup(z.read(h), "html.parser")
        txt = soup.get_text().strip()[:200].replace("\n", " ")
        print(f"  📄 {h}: {txt}...")

print("\n=== 3. CURRENT [k] FIRST 5 HTML CONTENTS ===")
with zipfile.ZipFile(epub_k, "r") as z:
    htmls = [n for n in z.namelist() if n.endswith((".xhtml", ".html", ".htm")) and not "toc" in n.lower() and not "nav" in n.lower()]
    for h in htmls[:6]:
        soup = BeautifulSoup(z.read(h), "html.parser")
        txt = soup.get_text().strip()[:200].replace("\n", " ")
        print(f"  📄 {h}: {txt}...")

print("\n=== 4. CURRENT [k-e] FIRST 5 HTML CONTENTS ===")
with zipfile.ZipFile(epub_ke, "r") as z:
    htmls = [n for n in z.namelist() if n.endswith((".xhtml", ".html", ".htm")) and not "toc" in n.lower() and not "nav" in n.lower()]
    for h in htmls[:6]:
        soup = BeautifulSoup(z.read(h), "html.parser")
        txt = soup.get_text().strip()[:200].replace("\n", " ")
        print(f"  📄 {h}: {txt}...")
