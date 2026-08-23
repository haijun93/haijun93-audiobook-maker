#!/usr/bin/env python3
"""scripts/inject_pam_godwin_queue.py

Injects the 20 Pam Godwin books missing study notes into the continuous translation queue
with Priority 950, placing them immediately after Freida McFadden (Priority 1000).
"""

import json
import re
from pathlib import Path

CONFIG_PATH = Path(".work/continuous_scheduler/config.json")
LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

MISSING_PAM_GODWIN_BOOKS = [
    "Booted Pam goodwin (4.28)",
    "Buckled Pam Godwin (4.18)",
    "Complicate Pam Godwin (4.24)",
    "Dawn of Eve Pam Godwin (4.22)",
    "Deliver Pam Godwin (3.93)",
    "Deliver Us Books 1 3 Pam Godwin",
    "Devastate Pam Godwin (0.00)",
    "Dirty Ties Pam Godwin (3.91)",
    "Disclaim Pam Godwin (4.13)",
    "From Evil Pam Godwin (4.57)",
    "Heart of Eve Pam Godwin (3.87)",
    "Hills of Shivers and Shadows Pam Godwin",
    "Incentive Pam Godwin",
    "Into Temptation Pam Godwin (4.60)",
    "King of Libertines Pam Godwin (3.83)",
    "Manipulate Pam Godwin (4.18)",
    "Rise of Ink and Smoke Pam Godwin",
    "Take Pam Godwin (4.25)",
    "Three is a War Pam Godwin (4.06)",
    "Two is a Lie Pam Godwin (4.05)"
]

def make_slug(text: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]", "_", text.lower())
    return re.sub(r"_+", "_", clean).strip("_")

def inject_queue():
    if not CONFIG_PATH.exists():
        print(f"❌ Error: Config file not found: {CONFIG_PATH}")
        return

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    tasks = data.get("tasks", [])
    existing_ids = {t["id"] for t in tasks}

    e_pam_dir = LIB_ROOT / "[e]" / "#Pam Godwin"
    e_files = list(e_pam_dir.glob("*.epub"))

    injected = []
    for title in MISSING_PAM_GODWIN_BOOKS:
        clean_t = re.sub(r"\(.*?\)", "", title).replace("Pam Godwin", "").replace("Pam goodwin", "").strip().lower()
        matched = None
        for ef in e_files:
            if clean_t in ef.name.lower():
                matched = ef
                break

        if not matched:
            print(f"⚠️ Warning: Could not find [e] file for {title}")
            continue

        task_id = f"stage0_pam_{make_slug(matched.stem)}"
        
        # Remove existing if already present
        tasks = [t for t in tasks if t["id"] != task_id]

        task_obj = {
            "id": task_id,
            "title": matched.name,
            "book_title_ko": title,
            "input_epub": str(matched),
            "output_epub": str(LIB_ROOT / "[k-e]" / "#Pam Godwin" / f"[k-e] {matched.name.replace('[e] ', '')}"),
            "study_output_epub": str(LIB_ROOT / "[study]" / "#Pam Godwin" / f"[study] {matched.name.replace('[e] ', '')}"),
            "work_dir": str(LIB_ROOT / "_chatgpt_translate_work" / f"pam_{make_slug(matched.stem)}"),
            "stage": 0,
            "stage_name": "Stage 0: Pam Godwin Master Study Re-translation",
            "priority": 950,
            "force_retranslate": True,
            "status": "pending"
        }
        injected.append(task_obj)

    # Prepend new tasks and sort by priority descending
    all_tasks = injected + tasks
    all_tasks.sort(key=lambda x: x.get("priority", 0), reverse=True)

    data["tasks"] = all_tasks
    data["stage_summary"]["Stage 0 (Pam Godwin Re-translation)"] = len(injected)

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ Successfully injected {len(injected)} Pam Godwin books into translation queue with Priority 950!")
    print("\n=== TOP QUEUE PREVIEW (First 15 Tasks) ===")
    for idx, t in enumerate(all_tasks[:15], 1):
        print(f"  {idx:2d}. [P{t.get('priority', 0):4d}] {t['stage_name']} -> {t['title']}")

if __name__ == "__main__":
    inject_queue()
