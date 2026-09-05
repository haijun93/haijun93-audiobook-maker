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
LIBRARY_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
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

    # Ultra high priority so Gemini Account 1 takes it immediately
    base_priority = -1000

    task_specs = {}
    for idx, (author, title, stem, rank) in enumerate(VK_DARK_BOOKS, 1):
        task_id = f"vk-dark-{idx:02d}-{slugify(title)}"
        work_dir = LIBRARY_ROOT / "_chatgpt_translate_work" / f"vk_dark__{slugify(stem)}"
        input_epub = SOURCE_DIR / f"{stem}.epub"

        # If not exact match, search in SOURCE_DIR
        if not input_epub.exists():
            matches = list(SOURCE_DIR.glob(f"*{title}*.epub"))
            if matches:
                input_epub = matches[0]

        bilingual_output = LIBRARY_ROOT / "[k-e]" / DEST_CATEGORY / f"[k-e] {stem}.epub"
        study_output = LIBRARY_ROOT / "[study]" / DEST_CATEGORY / f"[study] {stem}.epub"
        korean_output = LIBRARY_ROOT / "[k]" / DEST_CATEGORY / f"[k] {stem}.epub"
        english_study_output = LIBRARY_ROOT / "[e-s]" / DEST_CATEGORY / f"[e-s] {stem}.epub"

        completion_paths = [
            str(bilingual_output),
            str(korean_output),
            str(study_output),
            str(english_study_output),
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
                "scripts/translate_epub_with_chatgpt_web_to_study_epub.py",
                "--input-epub",
                str(input_epub),
                "--output-epub",
                str(bilingual_output),
                "--study-output-epub",
                str(study_output),
                "--work-dir",
                str(work_dir),
                "--book-title-ko",
                stem,
                "--max-chars-per-chunk",
                "6000",
                "--request-timeout-sec",
                "1200",
                "--web-max-attempts",
                "3",
                "--chunks-per-conversation",
                "10",
                "--inter-request-delay-sec",
                "15",
                "--heartbeat-file",
                str(work_dir / "heartbeat.json"),
                "--web-provider",
                "{provider}",
            ],
            "post_commands": [
                [
                    "{python}",
                    "scripts/make_korean_only_epubs.py",
                    str(LIBRARY_ROOT / "[k-e]" / DEST_CATEGORY),
                    "--overwrite",
                ],
                [
                    "{python}",
                    "scripts/make_english_study_epubs.py",
                    str(LIBRARY_ROOT / "[study]" / DEST_CATEGORY),
                    "--overwrite",
                ],
            ],
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

    # Update status.json (clean slate: reset retry_wait / error so scheduler runs immediately)
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
                "status": "pending",
                "attempts": 0,
                "stall_restarts": 0,
                "priority": spec["priority"],
                "order": idx,
                "primary_complete": False,
                "account_id": None,
                "pid": None,
                "started_at": None,
                "last_seen_at": None,
                "next_attempt_at": "2026-08-16T00:00:00+00:00",
                "error": None,
                "failure_kind": None,
                "last_exit_code": None,
                "terminating_stale": False,
            })
            updated_status_tasks.append(st)
            status_seen.add(task_id)

        for t in status_tasks:
            if isinstance(t, dict) and t.get("id") not in status_seen:
                updated_status_tasks.append(t)
                status_seen.add(t.get("id"))

        status_data["tasks"] = updated_status_tasks
        STATUS_PATH.write_text(json.dumps(status_data, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Successfully configured 10 VK Dark Romance books with PRIORITY -1000!")
    for idx, (author, title, stem, rank) in enumerate(VK_DARK_BOOKS, 1):
        print(f"  {rank} {title} -> {DEST_CATEGORY}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
