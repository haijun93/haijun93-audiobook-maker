#!/usr/bin/env python3
"""Queue 10 VK Dark Romance Masterpieces exclusively for Gemini Account 1 (main)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".work" / "continuous_scheduler" / "config.json"
STATUS_PATH = ROOT / ".work" / "continuous_scheduler" / "status.json"
SOURCE_DIR = Path("/Users/hyeokjunkong/Desktop/소설2/new books from vk")

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
    existing_ids = {t["id"] for t in existing_tasks}

    status_data = {}
    if STATUS_PATH.exists():
        try:
            status_data = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        except Exception:
            status_data = {}

    status_tasks = status_data.get("tasks", [])
    status_task_ids = {t["id"] for t in status_tasks if isinstance(t, dict)}

    new_task_specs = []
    base_priority = -200 # Highest priority, strictly before any other pending task

    for idx, (author, title, stem, rank) in enumerate(VK_DARK_BOOKS, 1):
        task_id = f"vk-dark-{idx:02d}-{slugify(title)}"
        work_dir = Path(f"/Users/hyeokjunkong/Desktop/소설2/_chatgpt_translate_work/vk_dark__{slugify(stem)}")
        
        # Completion paths in 4 editions
        completion_paths = [
            f"/Users/hyeokjunkong/Desktop/소설2/[k-e]/[k-e] {stem}.epub",
            f"/Users/hyeokjunkong/Desktop/소설2/[k]/[k] {stem}.epub",
            f"/Users/hyeokjunkong/Desktop/소설2/[study]/[study] {stem}.epub",
            f"/Users/hyeokjunkong/Desktop/소설2/[e-s]/[e-s] {stem}.epub",
        ]

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
            "completion_paths": completion_paths,
        }

        # Check if already in config
        if task_id in existing_ids:
            # Update existing
            for i, t in enumerate(existing_tasks):
                if t["id"] == task_id:
                    existing_tasks[i] = task_spec
                    break
        else:
            new_task_specs.append(task_spec)

        # Status tracking
        if task_id not in status_task_ids:
            status_tasks.append({
                "id": task_id,
                "title": task_spec["title"],
                "providers": ["gemini"],
                "preferred_accounts": ["main"],
                "work_dir": str(work_dir),
                "status": "pending",
                "attempts": 0,
                "stall_restarts": 0,
                "priority": task_spec["priority"],
                "order": len(status_tasks) + 1,
                "primary_complete": False,
                "account_id": None,
                "pid": None,
                "started_at": None,
                "last_seen_at": None,
                "next_attempt_at": None,
                "error": None,
                "terminating_stale": False,
            })

    config["tasks"] = new_task_specs + existing_tasks
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    if status_data:
        status_data["tasks"] = status_tasks
        STATUS_PATH.write_text(json.dumps(status_data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Successfully queued 10 VK Dark Romance books exclusively for Gemini Account 1 (main)!")
    for idx, (author, title, stem, rank) in enumerate(VK_DARK_BOOKS, 1):
        print(f"  {rank} [Priority {base_priority + idx}] {title} by {author} -> Gemini Account 1")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
