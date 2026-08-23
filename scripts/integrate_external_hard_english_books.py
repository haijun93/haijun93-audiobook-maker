#!/usr/bin/env python3
"""scripts/integrate_external_hard_english_books.py

Copies found English editions from 2T hard to `소설2/[e]/` and queues them for translation.
"""

import json
import re
import shutil
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
E_ROOT = LIB_ROOT / "[e]"
CONFIG_PATH = Path(".work/continuous_scheduler/config.json")
HARD_ROOT = Path("/Volumes/2T hard/English Books Collection")

FOUND_BOOKS = [
    {
        "src": HARD_ROOT / "Young_Adult_Children/#J.K. Rowling/Harry Potter and the Order of the Phoenix - J.K. Rowling (4.64).epub",
        "genre": "Fantasy_Science_Fiction",
        "author": "#J.K. Rowling",
        "title_e": "[e] Harry Potter and the Order of the Phoenix - J.K. Rowling (4.64).epub",
        "title_ko": "해리 포터와 불사조 기사단 - J.K. 롤링 (4.64)",
    },
    {
        "src": HARD_ROOT / "Mystery_Thriller_Crime/#Emily Henry/People We Meet on Vacation - Emily Henry.epub",
        "genre": "Romance_Contemporary",
        "author": "#Emily Henry",
        "title_e": "[e] People We Meet on Vacation - Emily Henry (4.15).epub",
        "title_ko": "우리가 휴가 중에 만난 사람들 - 에밀리 헨리 (4.15)",
    }
]

def main():
    cfg = json.loads(CONFIG_PATH.read_text())
    tasks = cfg.get("tasks", [])
    
    for item in FOUND_BOOKS:
        src = item["src"]
        if src.exists():
            dest_dir = E_ROOT / item["genre"] / item["author"]
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_f = dest_dir / item["title_e"]
            shutil.copy2(src, dest_f)
            print(f"✅ Copied English Edition to library: {dest_f.relative_to(LIB_ROOT)}")
            
            clean_stem = dest_f.name.replace("[e] ", "").replace(".epub", "")
            tid = f"stage1_replace_non_en_{re.sub(r'[^a-zA-Z0-9]', '', item['title_e'].lower())}"
            
            # Check duplicate
            if any(t.get("id") == tid for t in tasks):
                continue
                
            new_task = {
                "id": tid,
                "input_epub": str(dest_f),
                "output_epub": str(LIB_ROOT / "[k-e]" / item["genre"] / item["author"] / f"[k-e] {clean_stem}.epub"),
                "study_output_epub": str(LIB_ROOT / "[study]" / item["genre"] / item["author"] / f"[study] {clean_stem}.epub"),
                "work_dir": str(LIB_ROOT / f"_translation_work_{tid}"),
                "book_title_ko": item["title_ko"],
                "stage": 1,
                "priority": 3000,
                "max_chars_per_chunk": 6000,
                "request_timeout_sec": 1200,
                "web_max_attempts": 3,
                "chunks_per_conversation": 10,
                "inter_request_delay_sec": 8.0,
                "force_retranslate": True
            }
            tasks.insert(0, new_task)
            print(f"🚀 Queued: {item['title_ko']} (Priority 3000)")
            
    cfg["tasks"] = tasks
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
