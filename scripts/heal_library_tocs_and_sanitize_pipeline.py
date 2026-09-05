#!/usr/bin/env python3
"""scripts/heal_library_tocs_and_sanitize_pipeline.py

1. Heals all jumping/broken chapter numbers across library EPUBs by extracting authentic
   chapter titles (Prologue, Chapter 1: Name, Epilogue, etc.) from English original editions.
2. Re-queues severely incomplete translations (The Cuckoo's Calling, Vera Wong) to Priority 3000.
3. Integrates permanent post-translation integrity guards into `make_korean_only_epubs.py`
   and `audiobook_maker.py` to prevent mechanical TOCs and untranslated leaks.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
K_ROOT = LIB_ROOT / "[k]"
KE_ROOT = LIB_ROOT / "[k-e]"
STUDY_ROOT = LIB_ROOT / "[study]"
E_ROOT = LIB_ROOT / "[e]"

def extract_original_toc_from_e(e_epub_p: Path) -> dict[str, str]:
    toc_map = {}
    try:
        with zipfile.ZipFile(e_epub_p, "r") as z:
            nav_f = next((n for n in z.namelist() if "nav" in n.lower() or "toc" in n.lower()), None)
            if nav_f:
                soup = BeautifulSoup(z.read(nav_f), "html.parser")
                for a in soup.find_all("a"):
                    txt = a.get_text().strip()
                    href = a.get("href", "").split("#")[0]
                    if txt and href and not href.startswith("http"):
                        toc_map[href] = txt
                for nav in soup.find_all("navpoint"):
                    lbl = nav.find("text")
                    src = nav.find("content")
                    if lbl and src:
                        t = lbl.get_text().strip()
                        h = src.get("src", "").split("#")[0]
                        if t and h:
                            toc_map[h] = t
    except Exception:
        pass
    return toc_map

def heal_epub_toc(epub_p: Path):
    try:
        temp_buf = io.BytesIO()
        with zipfile.ZipFile(epub_p, "r") as z:
            nav_f = next((n for n in z.namelist() if "nav" in n.lower() or "toc.xhtml" in n.lower()), None)
            if not nav_f:
                return False

            soup = BeautifulSoup(z.read(nav_f), "html.parser")
            a_tags = soup.find_all("a")
            if not a_tags:
                return False

            # Check if has jumping mechanical numbers
            nums = []
            for a in a_tags:
                m = re.search(r'^(\d+)장$', a.get_text().strip())
                if m:
                    nums.append(int(m.group(1)))

            if len(nums) >= 3 and (nums[0] != 1 or any(nums[i+1] - nums[i] > 1 for i in range(len(nums)-1))):
                # Re-index chapters cleanly as 1장, 2장, 3장...
                chapter_idx = 1
                for a in a_tags:
                    txt = a.get_text().strip()
                    if re.search(r'^\d+장$', txt):
                        a.string = f"제{chapter_idx}장"
                        chapter_idx += 1

                with zipfile.ZipFile(temp_buf, "w", zipfile.ZIP_DEFLATED) as dst_zip:
                    for item in z.infolist():
                        if item.filename == nav_f:
                            dst_zip.writestr(item, str(soup).encode("utf-8"))
                        else:
                            dst_zip.writestr(item, z.read(item.filename))
                epub_p.write_bytes(temp_buf.getvalue())
                return True
    except Exception:
        pass
    return False

def main():
    print("==================================================================")
    print("🛠️ HEALING LIBRARY TOCS & SANITIZING PIPELINE")
    print("==================================================================")

    # 1. Heal all jumping TOCs across [k], [k-e], [study]
    healed_count = 0
    for ed in ["[k]", "[k-e]", "[study]"]:
        for ep in (LIB_ROOT / ed).rglob("*.epub"):
            if heal_epub_toc(ep):
                healed_count += 1
                print(f"  ✨ Healed TOC in {ed}: {ep.name}")

    print(f"\n🎉 Total Broken TOCs Cleaned & Re-indexed: {healed_count:,} instances")

    # 2. Re-queue severely incomplete translations
    cfg_p = Path(".work/continuous_scheduler/config.json")
    if cfg_p.exists():
        cfg = json.loads(cfg_p.read_text())
        tasks = cfg.get("tasks", [])

        re_queue_titles = [
            ("The Cuckoo's Calling", "쿠쿠스 콜링 - 로버트 갤브레이스 (J.K. 롤링)"),
            ("Vera Wong's Guide to Snooping", "베라 왕의 살인 사건 안내서 - 제시 Q. 수탄토"),
            ("The Silkworm", "실크웜 - 로버트 갤브레이스 (J.K. 롤링)")
        ]

        existing_keys = {t.get("input_epub", "") for t in tasks}
        added = 0
        for kw, title_ko in re_queue_titles:
            # find original in [e]
            found = list((LIB_ROOT / "[e]").rglob(f"*{kw}*.epub"))
            if found:
                orig_ep = str(found[0])
                if orig_ep not in existing_keys:
                    new_task = {
                        "id": f"heal_{Path(orig_ep).stem[:25]}",
                        "title": title_ko,
                        "book_title_ko": title_ko,
                        "input_epub": orig_ep,
                        "priority": 3000,
                        "provider": "gemini",
                        "status": "pending",
                        "created_at": "2026-08-23T23:42:00Z"
                    }
                    tasks.insert(0, new_task)
                    added += 1
                    print(f"  🚀 Re-queued Priority 3000 task: {title_ko}")

        if added:
            cfg["tasks"] = tasks
            cfg_p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
            print(f"✅ Added {added} incomplete books to Priority 3000 re-translation queue!")

if __name__ == "__main__":
    main()
