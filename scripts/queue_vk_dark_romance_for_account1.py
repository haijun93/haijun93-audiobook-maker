#!/usr/bin/env python3
"""Queue 10 VK Dark Romance Masterpieces exclusively for Gemini Account 1 (main) with destination `#Top 10 dark romance`."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".work" / "continuous_scheduler" / "config.json"
STATUS_PATH = ROOT / ".work" / "continuous_scheduler" / "status.json"
SOURCE_DIR = Path("/Users/hyeokjunkong/Desktop/소설2/new books from vk")
DEST_CATEGORY = "#Top 10 dark romance"

VK_DARK_BOOKS = [
    ("Pepper Winters", "Tears of Tess", "Tears of Tess - Pepper Winters", "🥇"),
    ("Rina Kent", "God of Malice", "God of Malice - Rina Kent", "🥈"),
    ("Keri Lake", "Nocticadia", "Nocticadia - Keri Lake", "🥉"),
    ("H.D. Carlton", "Haunting Adeline", "Haunting Adeline - H.D. Carlton", "4"),
    ("Penelope Douglas", "Corrupt", "Corrupt - Penelope Douglas", "5"),
    ("C.J. Roberts", "Captive in the Dark", "Captive in the Dark - C.J. Roberts", "6"),
    ("Danielle Lori", "The Maddest Obsession", "The Maddest Obsession - Danielle Lori", "7"),
    ("Cora Reilly", "Bound by Honor", "Bound by Honor - Cora Reilly", "8"),
    ("Neva Altaj", "Painted Scars", "Painted Scars - Neva Altaj", "9"),
    ("L.J. Shen", "Vicious", "Vicious - L.J. Shen", "10"),
]


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", cleaned)


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    existing_tasks = config.get("tasks", [])

    status_data = {}
    if STATUS_PATH.exists():
        try:
            status_data = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        except Exception:
            status_data = {}

    status_tasks = status_data.get("tasks", [])
    status_tasks_by_id = {t["id"]: t for t in status_tasks if isinstance(t, dict)}

    base_priority = -200

    # Build updated task dictionary
    task_specs = {}
    for idx, (author, title, stem, rank) in enumerate(VK_DARK_BOOKS, 1):
        task_id = f"vk-dark-{idx:02d}-{slugify(title)}"
        work_dir = Path(f"/Users/hyeokjunkong/Desktop/소설2/_chatgpt_translate_work/vk_dark__{slugify(stem)}")
        
        # Sources in root output dirs
        src_ke = f"/Users/hyeokjunkong/Desktop/소설2/[k-e]/[k-e] {stem}.epub"
        src_k = f"/Users/hyeokjunkong/Desktop/소설2/[k]/[k] {stem}.epub"
        
        # Target destinations in #Top 10 dark romance
        dest_ke = f"/Users/hyeokjunkong/Desktop/소설2/[k-e]/{DEST_CATEGORY}/[k-e] {stem}.epub"
        dest_k = f"/Users/hyeokjunkong/Desktop/소설2/[k]/{DEST_CATEGORY}/[k] {stem}.epub"
        
        deployments = [
            {"source": src_ke, "destination": dest_ke},
            {"source": src_k, "destination": dest_k},
        ]
        completion_paths = [dest_ke, dest_k]

        task_spec = {
            "id": task_id,
            "title": f"VK 다크 {rank} · {title} - {author}",
            "providers": ["gemini"],
            "preferred_accounts": ["main"],
            "priority": base_priority + idx,
            "max_attempts": 20,
            "max_stall_restarts": 1,
            "work_dir": str(work_dir),
            "command": [
                "{python}",
                "scripts/run_soseol2_chatgpt_k_e_batch.py",
                "--source-dir",
                str(SOURCE_DIR),
                "--only",
                stem,
                "--watch-new-seconds",
                "0",
                "--web-provider",
                "{provider}",
                "--web-max-attempts",
                "3",
                "--inter-request-delay-sec",
                "8"
            ],
            "deploy": deployments,
            "completion_paths": completion_paths,
        }
        task_specs[task_id] = task_spec

    # Reassemble tasks list: our 10 tasks at the very front
    new_tasks = []
    seen_ids = set()
    for task_id in sorted(task_specs.keys()):
        new_tasks.append(task_specs[task_id])
        seen_ids.add(task_id)

    for t in existing_tasks:
        if t["id"] not in seen_ids:
            new_tasks.append(t)
            seen_ids.add(t["id"])

    config["tasks"] = new_tasks
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    # Update status.json
    if status_data:
        updated_status_tasks = []
        status_seen = set()
        for idx, task_id in enumerate(sorted(task_specs.keys()), 1):
            spec = task_specs[task_id]
            st = status_tasks_by_id.get(task_id, {})
            st.update({
                "id": task_id,
                "title": spec["title"],
                "providers": ["gemini"],
                "preferred_accounts": ["main"],
                "work_dir": spec["work_dir"],
                "status": st.get("status") if st.get("status") in {"running", "completed"} else "pending",
                "attempts": st.get("attempts", 0),
                "stall_restarts": st.get("stall_restarts", 0),
                "priority": spec["priority"],
                "order": idx,
                "primary_complete": st.get("primary_complete", False),
                "account_id": st.get("account_id"),
                "pid": st.get("pid"),
                "started_at": st.get("started_at"),
                "last_seen_at": st.get("last_seen_at"),
                "next_attempt_at": st.get("next_attempt_at"),
                "error": st.get("error"),
                "terminating_stale": st.get("terminating_stale", False),
            })
            updated_status_tasks.append(st)
            status_seen.add(task_id)

        for t in status_tasks:
            if isinstance(t, dict) and t.get("id") not in status_seen:
                updated_status_tasks.append(t)
                status_seen.add(t.get("id"))

        status_data["tasks"] = updated_status_tasks
        STATUS_PATH.write_text(json.dumps(status_data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Successfully configured 10 VK Dark Romance books to auto-deploy into '{DEST_CATEGORY}'!")
    for idx, (author, title, stem, rank) in enumerate(VK_DARK_BOOKS, 1):
        print(f"  {rank} {title} -> {DEST_CATEGORY}/[k-e], [k]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
