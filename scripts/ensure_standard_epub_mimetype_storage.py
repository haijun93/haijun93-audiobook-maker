#!/usr/bin/env python3
"""scripts/ensure_standard_epub_mimetype_storage.py

Ensures all EPUBs have a compliant `mimetype` entry stored as uncompressed ZIP_STORED.
"""

import io
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

def fix_mimetype_in_epub(ep_path_str: str) -> bool:
    ep = Path(ep_path_str)
    try:
        data = {}
        with zipfile.ZipFile(ep, "r") as z:
            for item in z.infolist():
                data[item.filename] = z.read(item.filename)
                
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
            if "mimetype" in data:
                zout.writestr("mimetype", data.pop("mimetype"), compress_type=zipfile.ZIP_STORED)
            else:
                zout.writestr("mimetype", b"application/epub+zip", compress_type=zipfile.ZIP_STORED)
            for fname, cdata in data.items():
                zout.writestr(fname, cdata)
        ep.write_bytes(buf.getvalue())
        return True
    except Exception:
        return False

def main():
    print("Fixing EPUB mimetype compliance across library...")
    epubs = [str(p) for p in LIB_ROOT.rglob("*.epub")]
    with ProcessPoolExecutor(max_workers=12) as ex:
        futures = [ex.submit(fix_mimetype_in_epub, p) for p in epubs]
        done = sum(1 for fut in as_completed(futures) if fut.result())
    print(f"✅ Fixed mimetype compliance for {done:,} / {len(epubs):,} EPUBs!")

if __name__ == "__main__":
    main()
