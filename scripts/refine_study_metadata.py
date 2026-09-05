#!/usr/bin/env python3
"""scripts/refine_study_metadata.py"""

import os
import re
import shutil
import tempfile
import unicodedata
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from bs4 import BeautifulSoup

def is_korean(text: str) -> bool:
    if not text: return False
    ko = len(re.findall(r'[가-힣]', text))
    en = len(re.findall(r'[a-zA-Z]', text))
    return ko > 0 and (ko >= en * 0.3 or ko >= 5)

def is_english(text: str) -> bool:
    if not text: return False
    en = len(re.findall(r'[a-zA-Z]', text))
    ko = len(re.findall(r'[가-힣]', text))
    return en > 5 and ko == 0

def clean_remaining_meta(epub_path_str: str, study_dir_str: str, gdrive_study_str: str):
    ep = Path(epub_path_str)
    study_dir = Path(study_dir_str)
    gdrive_study = Path(gdrive_study_str)
    modified = False

    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix="clean_meta_"))
        with zipfile.ZipFile(ep, "r") as z:
            z.extractall(tmp_dir)

        htmls = list(tmp_dir.glob("**/*.xhtml")) + list(tmp_dir.glob("**/*.html")) + list(tmp_dir.glob("**/*.htm"))
        for h in htmls:
            c = h.read_text(encoding="utf-8", errors="ignore")
            if "class=\"pair\"" not in c and "<p class=\"pair\"" not in c:
                continue
            soup = BeautifulSoup(c, "html.parser")
            pairs = soup.find_all(class_=lambda cls: cls and "pair" in cls)
            h_mod = False
            for p in pairs:
                ko_s = p.find("span", class_="ko")
                if ko_s:
                    kt = ko_s.get_text(strip=True)
                    if is_english(kt):
                        kt_l = kt.lower()
                        if any(k in kt_l for k in ["isbn", "eisbn", "issn", "catalog"]):
                            ko_s.string = "도서 등록 정보 (ISBN 및 출판 분류)"
                            h_mod = True
                        elif any(k in kt_l for k in ["photo ©", "illustration ©", "cover design", "cover art", "jacket design"]):
                            ko_s.string = "표지 디자인 및 사진 저작권 안내"
                            h_mod = True
                        elif any(k in kt_l for k in ["publishing group", "publisher", "published by", "press", "random house", "penguin", "harpercollins"]):
                            ko_s.string = "출판사 및 발행처 안내"
                            h_mod = True
                        elif "@" in kt or "www." in kt_l or "http" in kt_l or ".com" in kt_l or ".co.uk" in kt_l:
                            ko_s.string = "공식 웹사이트 및 연락처 안내 링크"
                            h_mod = True
                        elif any(k in kt_l for k in ["all rights reserved", "trademark", "printed in", "first edition"]):
                            ko_s.string = "판권 및 무단 복제 금지 안내"
                            h_mod = True
            if h_mod:
                h.write_text(str(soup), encoding="utf-8")
                modified = True

        if modified:
            epub_tmp = tmp_dir.parent / f"{ep.stem}_cleaned.epub"
            with zipfile.ZipFile(epub_tmp, "w", zipfile.ZIP_DEFLATED) as z_out:
                mime_p = tmp_dir / "mimetype"
                if mime_p.exists():
                    z_out.write(mime_p, "mimetype", compress_type=zipfile.ZIP_STORED)
                for root_d, _, files in os.walk(tmp_dir):
                    for fn in files:
                        fp = Path(root_d) / fn
                        rel_z = fp.relative_to(tmp_dir)
                        if str(rel_z) == "mimetype": continue
                        z_out.write(fp, str(rel_z))
            shutil.move(str(epub_tmp), str(ep))

            # Sync to Google Drive
            rel_ep = ep.relative_to(study_dir)
            g_dest = gdrive_study / rel_ep
            if g_dest.parent.exists():
                shutil.copy2(str(ep), str(g_dest))

        shutil.rmtree(tmp_dir, ignore_errors=True)
        return (True, ep.name, modified)
    except Exception as e:
        return (False, ep.name, False)

def main():
    desktop = Path("/Users/hyeokjunkong/Desktop")
    lib_root = next(p for p in desktop.iterdir() if "소설2" in unicodedata.normalize("NFC", p.name))
    study_dir = lib_root / "[study]"
    gdrive_root = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")
    gdrive_study = gdrive_root / "[study]"

    epubs = sorted(study_dir.glob("**/*.epub"))
    tasks = [(str(ep), str(study_dir), str(gdrive_study)) for ep in epubs]
    print(f"Refining metadata spans across {len(epubs)} [study] EPUBs...")

    modified_count = 0
    with ProcessPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(clean_remaining_meta, t[0], t[1], t[2]) for t in tasks]
        for fut in as_completed(futures):
            ok, name, mod = fut.result()
            if mod:
                modified_count += 1

    print(f"🎉 Successfully refined {modified_count} books with clean Korean metadata!")

if __name__ == "__main__":
    main()
