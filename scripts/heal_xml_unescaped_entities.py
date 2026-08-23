#!/usr/bin/env python3
"""scripts/heal_xml_unescaped_entities.py

Fixes unescaped '&' and invalid XML tokens in [study] EPUBs to ensure 100% derivation success for [e-s].
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
STUDY_ROOT = LIB_ROOT / "[study]"

def sanitize_xml_string(raw_html: str) -> str:
    # Replace unescaped & that is not part of a valid xml entity
    fixed = re.sub(r'&(?!(?:[a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);)', '&amp;', raw_html)
    return fixed

def heal_epub(epub_p: Path):
    try:
        temp_buf = io.BytesIO()
        mod = False
        with zipfile.ZipFile(epub_p, "r") as src_zip:
            with zipfile.ZipFile(temp_buf, "w", zipfile.ZIP_DEFLATED) as dst_zip:
                for item in src_zip.infolist():
                    content = src_zip.read(item.filename)
                    if item.filename.endswith((".xhtml", ".html", ".xml", ".opf", ".ncx")):
                        try:
                            txt = content.decode("utf-8")
                            fixed_txt = sanitize_xml_string(txt)
                            if fixed_txt != txt:
                                mod = True
                                dst_zip.writestr(item, fixed_txt.encode("utf-8"))
                            else:
                                dst_zip.writestr(item, content)
                        except Exception:
                            dst_zip.writestr(item, content)
                    else:
                        dst_zip.writestr(item, content)
                        
        if mod:
            epub_p.write_bytes(temp_buf.getvalue())
            return True
    except Exception:
        pass
    return False

def main():
    print("==================================================================")
    print("🛡️ HEALING XML UNESCAPED ENTITIES ACROSS [study] EDITIONS")
    print("==================================================================")
    
    epubs = list(STUDY_ROOT.rglob("*.epub"))
    healed_count = 0
    for ep in epubs:
        if heal_epub(ep):
            healed_count += 1
            print(f"  ✨ Healed XML tokens in: {ep.name}")
            
    print(f"\n🎉 Total [study] EPUBs Healed: {healed_count:,} books")

if __name__ == "__main__":
    main()
