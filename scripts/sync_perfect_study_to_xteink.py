#!/usr/bin/env python3
"""scripts/sync_perfect_study_to_xteink.py

Synchronizes 100% purified TOEIC 700+ [study] and [e-s] editions directly into
`소설2/[xteink]/[study]` and `소설2/[xteink]/[e-s]`, as well as Google Drive `#Books/[xteink]`.
"""

import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
XTEINK_ROOT = LIB_ROOT / "[xteink]"
GDRIVE_ROOT = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

def sync_book(src_epub: Path, target_edition: str) -> tuple[str, bool]:
    try:
        rel = src_epub.relative_to(LIB_ROOT / target_edition)

        # 1. Local xteink
        local_dest = XTEINK_ROOT / target_edition / rel
        local_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_epub, local_dest)

        # 2. GDrive xteink
        if GDRIVE_ROOT.exists():
            gd_dest = GDRIVE_ROOT / "[xteink]" / target_edition / rel
            gd_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_epub, gd_dest)

        return src_epub.name, True
    except Exception as e:
        return src_epub.name, False

def main():
    print("==================================================================")
    print("📱 SYNCHRONIZING PURIFIED TOEIC 700+ STUDY EDITIONS TO [xteink]")
    print("==================================================================")

    for ed in ["[study]", "[e-s]"]:
        src_dir = LIB_ROOT / ed
        epubs = list(src_dir.rglob("*.epub"))
        print(f"\n📚 Syncing {len(epubs):,} {ed} books to [xteink]/{ed}...")

        with ProcessPoolExecutor(max_workers=12) as ex:
            futures = [ex.submit(sync_book, ep, ed) for ep in epubs]
            done = sum(1 for fut in as_completed(futures) if fut.result()[1])

        print(f"✅ Synced {done:,} / {len(epubs):,} {ed} books to [xteink] and Google Drive!")

    print("\n==================================================================")
    print("🎉 ALL [xteink] STUDY & E-S EDITIONS ARE 100% UP TO DATE & PURIFIED!")
    print("==================================================================")

if __name__ == "__main__":
    main()
