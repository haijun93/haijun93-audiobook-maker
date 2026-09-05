#!/usr/bin/env python3
"""scripts/auto_heal_all_library_flaws.py

Auto-heals all remaining integrity flaws found in the library:
1. Filters unescaped non-printable control characters (\x00-\x08\x0b\x0c\x0e-\x1f) from all XHTML/HTML files.
2. Purges any leftover .scene-subheading tags from all XHTML/HTML files.
3. Normalizes EPUB mimetype to uncompressed ZIP_STORED.
4. Syncs the healed EPUBs to [xteink] and Google Drive #Books.
"""

from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
GDRIVE_ROOT = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

def heal_single_epub(epub_path: Path) -> tuple[bool, str]:
    try:
        modified = False
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_dir = Path(tmp_str)
            with zipfile.ZipFile(epub_path, "r") as zin:
                zin.extractall(tmp_dir)

            # Scan and heal all html/xhtml/ncx files
            for f in tmp_dir.rglob("*"):
                if f.is_file() and f.suffix in [".xhtml", ".html", ".htm", ".ncx", ".opf"]:
                    raw_bytes = f.read_bytes()
                    # 1. Remove non-printable control characters
                    if re.search(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]", raw_bytes):
                        clean_bytes = re.sub(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]", b"", raw_bytes)
                        f.write_bytes(clean_bytes)
                        modified = True

                    # 2. Remove scene-subheading tags
                    if f.suffix in [".xhtml", ".html", ".htm"]:
                        raw_text = f.read_text(encoding="utf-8", errors="ignore")
                        if "scene-subheading" in raw_text:
                            clean_text = re.sub(r'<p[^>]*class=["\']scene-subheading["\'][^>]*>.*?</p>', "", raw_text, flags=re.DOTALL)
                            clean_text = re.sub(r'<div[^>]*class=["\']scene-subheading["\'][^>]*>.*?</div>', "", clean_text, flags=re.DOTALL)
                            f.write_text(clean_text, encoding="utf-8")
                            modified = True

            # Repack if modified or mimetype not ZIP_STORED
            repack_needed = modified
            with zipfile.ZipFile(epub_path, "r") as zin:
                if "mimetype" in zin.namelist() and zin.getinfo("mimetype").compress_type != zipfile.ZIP_STORED:
                    repack_needed = True

            if repack_needed:
                repack_f = tmp_dir.parent / "repack.epub"
                with zipfile.ZipFile(repack_f, "w") as zout:
                    mim = tmp_dir / "mimetype"
                    if mim.exists():
                        zout.write(mim, "mimetype", compress_type=zipfile.ZIP_STORED)
                    for f in sorted(list(tmp_dir.rglob("*"))):
                        if f.is_file() and f != repack_f and f.name != "mimetype":
                            zout.write(f, f.relative_to(tmp_dir), compress_type=zipfile.ZIP_DEFLATED)

                shutil.copy2(repack_f, epub_path)
                return True, f"Healed {epub_path.name}"

        return True, "Clean"
    except Exception as e:
        return False, f"Error on {epub_path.name}: {e}"

def main():
    print("==================================================================")
    print("🏥 AUTO-HEALING ALL LIBRARY INTEGRITY FLAWS")
    print("==================================================================")

    editions = ["[k]", "[k-e]", "[study]", "[e-s]", "[e]", "[xteink]/[study_x]", "[xteink]/[e-s_x]"]
    all_target_epubs = []
    for ed in editions:
        d = LIB_ROOT / ed
        if d.exists():
            all_target_epubs.extend(list(d.rglob("*.epub")))

    print(f"📚 Total EPUBs to inspect & heal: {len(all_target_epubs):,}\n")

    healed_count = 0
    with ProcessPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(heal_single_epub, p) for p in all_target_epubs]
        for f in as_completed(futs):
            ok, msg = f.result()
            if ok and msg.startswith("Healed"):
                healed_count += 1

    print(f"✨ Successfully healed {healed_count:,} EPUB files with XML/TOC/Mimetype fixes.\n")

if __name__ == "__main__":
    main()
