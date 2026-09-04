#!/usr/bin/env python3
"""scripts/register_vk_new_books_to_queue.py

Registers the 8 new raw books from /Users/hyeokjunkong/Desktop/소설2/new books from vk/
1. Cleans OceanofPDF filenames and moves to standard genre paths in 소설2/[e]/
2. Enqueues them at top priority (Priority 100) in .work/continuous_scheduler/config.json
3. Lists the upcoming task queue across all workers.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
VK_DIR = LIB_ROOT / "new books from vk"
CONFIG_PATH = Path(".work/continuous_scheduler/config.json")

NEW_BOOK_MAP = [
    {
        "src_pattern": "Wool",
        "author": "Hugh Howey",
        "author_folder": "#Hugh Howey",
        "genre": "Fantasy_Science_Fiction",
        "standard_title": "Wool (Silo Book 1) - Hugh Howey",
        "title_ko": "울 (실로 1부) - 휴 하위",
        "provider": "any"
    },
    {
        "src_pattern": "Shift",
        "author": "Hugh Howey",
        "author_folder": "#Hugh Howey",
        "genre": "Fantasy_Science_Fiction",
        "standard_title": "Shift (Silo Book 2) - Hugh Howey",
        "title_ko": "시프트 (실로 2부) - 휴 하위",
        "provider": "any"
    },
    {
        "src_pattern": "Dust",
        "author": "Hugh Howey",
        "author_folder": "#Hugh Howey",
        "genre": "Fantasy_Science_Fiction",
        "standard_title": "Dust (Silo Book 3) - Hugh Howey",
        "title_ko": "더스트 (실로 3부) - 휴 하위",
        "provider": "any"
    },
    {
        "src_pattern": "Presumed_Innocent",
        "author": "Scott Turow",
        "author_folder": "#Scott Turow",
        "genre": "Mystery_Thriller_Crime",
        "standard_title": "Presumed Innocent - Scott Turow",
        "title_ko": "무죄추정 - 스콧 터로",
        "provider": "any"
    },
    {
        "src_pattern": "Black_Bir",
        "author": "James Keene",
        "author_folder": "#James Keene",
        "genre": "Mystery_Thriller_Crime",
        "standard_title": "Black Bird - James Keene",
        "title_ko": "블랙 버드 - 제임스 킨",
        "provider": "any"
    },
    {
        "src_pattern": "last_Thing",
        "author": "Laura Dave",
        "author_folder": "#Laura Dave",
        "genre": "Mystery_Thriller_Crime",
        "standard_title": "The Last Thing He Told Me - Laura Dave",
        "title_ko": "그가 나에게 말하지 않은 마지막 것 - 로라 데이브",
        "provider": "any"
    },
    {
        "src_pattern": "Shining_Girls",
        "author": "Lauren Beukes",
        "author_folder": "#Lauren Beukes",
        "genre": "Mystery_Thriller_Crime",
        "standard_title": "The Shining Girls - Lauren Beukes",
        "title_ko": "샤이닝 걸스 - 로런 뷰크스",
        "provider": "any"
    },
    {
        "src_pattern": "Dark_City",
        "author": "Frank Lauria",
        "author_folder": "#Frank Lauria",
        "genre": "Fantasy_Science_Fiction",
        "standard_title": "Dark City - Frank Lauria",
        "title_ko": "다크 시티 - 프랭크 로리아",
        "provider": "any"
    },
]

def register_and_queue():
    print("==================================================================")
    print("🚀 REGISTERING 8 NEW VK BOOKS & ENQUEUEING FOR TRANSLATION")
    print("==================================================================")

    # 1. Load supervisor config
    cfg = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {"tasks": []}
    existing_tasks = cfg.get("tasks", [])
    existing_ids = {t["id"] for t in existing_tasks}

    new_tasks = []

    for item in NEW_BOOK_MAP:
        pat = item["src_pattern"]
        matched = list(VK_DIR.glob(f"*{pat}*.epub"))
        if not matched:
            print(f"  ⚠️ File matching {pat} not found in {VK_DIR}")
            continue

        src_epub = matched[0]
        # Target path in 소설2/[e]/
        target_e = LIB_ROOT / "[e]" / item["genre"] / item["author_folder"] / f"[e] {item['standard_title']}.epub"
        target_e.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_epub, target_e)

        target_ke = LIB_ROOT / "[k-e]" / item["genre"] / item["author_folder"] / f"[k-e] {item['standard_title']}.epub"
        target_study = LIB_ROOT / "[study]" / item["genre"] / item["author_folder"] / f"[study] {item['standard_title']}.epub"

        task_id = "stage1_vk_" + re.sub(r"[^a-zA-Z0-9]", "", item["standard_title"].lower())[:30]

        task_entry = {
            "id": task_id,
            "title": f"[e] {item['standard_title']}.epub",
            "book_title_ko": item["title_ko"],
            "input_epub": str(target_e),
            "output_epub": str(target_ke),
            "study_output_epub": str(target_study),
            "priority": 100,  # Top priority
            "status": "pending",
            "provider": item["provider"]
        }

        # Add to list if not already there
        if task_id not in existing_ids:
            new_tasks.append(task_entry)
            print(f"  ✅ Registered: {item['title_ko']} ({item['standard_title']}) -> Priority 100")
        else:
            print(f"  ℹ️ Already in queue: {item['standard_title']}")

    # Prepend new tasks to front of queue
    all_tasks = new_tasks + existing_tasks
    # Sort by priority
    all_tasks = sorted(all_tasks, key=lambda t: t.get("priority", 0), reverse=True)
    cfg["tasks"] = all_tasks
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n📦 Updated {CONFIG_PATH} with {len(all_tasks):,} total queued tasks.\n")

if __name__ == "__main__":
    register_and_queue()
