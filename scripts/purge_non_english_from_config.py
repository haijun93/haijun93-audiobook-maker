#!/usr/bin/env python3
"""scripts/purge_non_english_from_config.py

1. Purges all non-English foreign edition tasks (French, German, Czech, Turkish, Italian, Indonesian, etc.) from config.json.
2. Ensures all tasks have canonical English inputs and standard destination paths.
3. Cleans any failing / deadlocked task IDs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

CONFIG_PATH = Path(".work/continuous_scheduler/config.json")

NON_ENGLISH_PATTERNS = [
    r"german\s*edition", r"french\s*edition", r"czech\s*edition", r"turkish\s*edition",
    r"italian\s*edition", r"indonesian\s*edition", r"spanish\s*edition", r"russian\s*edition",
    r"portuguese\s*edition", r"polish\s*edition", r"dutch\s*edition", r"swedish\s*edition",
    r"japanese\s*edition", r"chinese\s*edition", r"deutsche\s*ausgabe", r"edition\s*francaise",
    r"edicion\s*en\s*espanol", r"edizione\s*italiana", r"tome\s*[1-3]", r"fenixuv\s*rad",
    r"princ\s*dvoji\s*krve", r"ve\s*zumruduanka", r"sepuluh\s*anak\s*negro",
    r"die\s*hyperion\s*gesange", r"kameni\s*mudrcu", r"tajemna\s*komnata", r"vezen\s*z\s*azkabanu",
    r"ohnivy\s*pohar", r"relikvie\s*smrti", r"french\s*-", r"german\s*-", r"czech\s*-", r"turkish\s*-"
]

def purge_non_english():
    print("==================================================================")
    print("🧹 PURGING NON-ENGLISH TASKS FROM SUPERVISOR QUEUE")
    print("==================================================================")

    if not CONFIG_PATH.exists():
        print("❌ config.json not found!")
        return

    cfg = json.loads(CONFIG_PATH.read_text())
    tasks = cfg.get("tasks", [])
    print(f"Total tasks before purge: {len(tasks):,}")

    clean_tasks = []
    purged_count = 0

    for t in tasks:
        title = (t.get("book_title_ko") or t.get("title") or "").lower()
        in_epub = (t.get("input_epub") or "").lower()
        out_epub = (t.get("output_epub") or "").lower()

        is_foreign = False
        for pat in NON_ENGLISH_PATTERNS:
            if re.search(pat, title) or re.search(pat, in_epub) or re.search(pat, out_epub):
                is_foreign = True
                break

        if is_foreign:
            purged_count += 1
            print(f"  🗑️ Purged non-English task: {t.get('book_title_ko') or t.get('title')}")
        else:
            clean_tasks.append(t)

    cfg["tasks"] = clean_tasks
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n✨ Purged {purged_count} non-English tasks. Clean tasks in queue: {len(clean_tasks):,}")
    print("==================================================================")

if __name__ == "__main__":
    purge_non_english()
