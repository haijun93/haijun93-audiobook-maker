#!/usr/bin/env python3
"""scripts/safe_heal_library.py

Safely and atomically heals any control characters or invalid mimetype in all EPUBs.
Each process uses a unique tempfile in the target directory to avoid any race conditions.
"""

from __future__ import annotations

import os
import re
import tempfile
import zipfile
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
GDRIVE_ROOT = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

def safe_heal_single_epub(epub_path: Path) -> tuple[bool, str]:
    if not epub_path.is_file() or epub_path.stat().st_size == 0:
        return False, f"Empty or missing file: {epub_path.name}"

    try:
        # Validate ZIP
        with zipfile.ZipFile(epub_path, "r") as zin:
            # Test CRC of all files
            bad_crc = zin.testzip()
            if bad_crc:
                return False, f"Bad CRC in {epub_path.name}: {bad_crc}"
            in_names = zin.namelist()

            # Check if modification needed
            needs_heal = False
            if "mimetype" in in_names and zin.getinfo("mimetype").compress_type != zipfile.ZIP_STORED:
                needs_heal = True

            xhtml_names = [n for n in in_names if n.endswith((".xhtml", ".html", ".htm", ".ncx", ".opf"))]
            for xn in xhtml_names:
                raw_bytes = zin.read(xn)
                if re.search(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]", raw_bytes) or b"scene-subheading" in raw_bytes:
                    needs_heal = True
                    break

            if not needs_heal:
                return True, "Already Pristine"

            # Create unique temp file in same directory
            fd, tmp_path_str = tempfile.mkstemp(suffix=".epub", dir=epub_path.parent)
            os.close(fd)
            tmp_path = Path(tmp_path_str)

            with zipfile.ZipFile(tmp_path, "w") as zout:
                if "mimetype" in in_names:
                    zout.writestr(
                        zipfile.ZipInfo("mimetype"),
                        zin.read("mimetype"),
                        compress_type=zipfile.ZIP_STORED
                    )
                for name in in_names:
                    if name == "mimetype":
                        continue
                    data = zin.read(name)
                    if name.endswith((".xhtml", ".html", ".htm", ".ncx", ".opf")):
                        # clean control chars
                        data = re.sub(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]", b"", data)
                        if b"scene-subheading" in data:
                            txt = data.decode("utf-8", "ignore")
                            txt = re.sub(r'<p[^>]*class=["\']scene-subheading["\'][^>]*>.*?</p>', "", txt, flags=re.DOTALL)
                            data = txt.encode("utf-8")
                    zout.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)

            # Atomic replace
            tmp_path.replace(epub_path)
            return True, f"Healed {epub_path.name}"

    except Exception as e:
        return False, f"Error healing {epub_path.name}: {e}"

def main():
    print("==================================================================")
    print("🛡️ SAFE ATOMIC HEALING FOR ALL LIBRARY EDITIONS")
    print("==================================================================")

    editions = ["[k]", "[k-e]", "[study]", "[e-s]", "[e]"]
    all_epubs = []
    for ed in editions:
        d = LIB_ROOT / ed
        if d.exists():
            all_epubs.extend(list(d.rglob("*.epub")))

    print(f"📚 Total EPUBs to inspect & heal: {len(all_epubs):,}\n")

    healed = 0
    errors = 0
    with ProcessPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(safe_heal_single_epub, p) for p in all_epubs]
        for f in as_completed(futs):
            ok, msg = f.result()
            if ok:
                if msg.startswith("Healed"):
                    healed += 1
            else:
                errors += 1
                print(f"  ❌ {msg}")

    print(f"\n✨ Completed: {healed} healed, {errors} errors.")

    # Rebuild Xteink
    from build_xteink_dedicated_editions import main as build_xteink
    build_xteink()

if __name__ == "__main__":
    main()
