#!/usr/bin/env python3
"""Queue 19 Freida McFadden books for study & e-s note backfill exclusively for Gemini Account 2 (account2)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".work" / "continuous_scheduler" / "config.json"
STATUS_PATH = ROOT / ".work" / "continuous_scheduler" / "status.json"
LIBRARY_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

AUTHOR = "Freida McFadden"
AUTHOR_FOLDER = f"#{AUTHOR}"

FREIDA_BOOKS = [
    "Housemaid 01 The Housemaid Freida McFadden (4.26)",
    "Housemaid 02 The Housemaids Secret Freida McFadden 2 (4.15)",
    "Housemaid 03 The Housemaid Is Watching Freida McFadden 2 (3.85)",
    "Never Lie Freida McFadden (4.08)",
    "The Teacher Freida McFadden (3.89)",
    "The Inmate Freida McFadden (4.00)",
    "The Tenant Freida McFadden (4.00)",
    "Boyfriend Freida McFadden (4.03)",
    "The Divorce Freida McFadden (3.89)",
    "Baby City Freida McFadden (3.73)",
    "The Devil Wears Scrubs Freida McFadden (3.43)",
    "The Gift Freida McFadden McFadden Freida (3.18)",
    "The Intruder Freida McFadden 3 (3.00)",
    "Brain Damage Freida McFadden",
    "Do You Remember Freida McFadden",
    "Suicide Med Freida McFadden",
    "The Crash Freida McFadden (0.00)",
    "The Psyching A Short Thriller Freida McFadden",
    "Want to Know a Secret Freida McFadden",
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

    # High priority for account2 right after current Beartown job
    base_priority = -800

    task_specs = {}
    for idx, stem in enumerate(FREIDA_BOOKS, 1):
        task_id = f"freida-study-{idx:02d}-{slugify(stem)}"
        work_dir = LIBRARY_ROOT / "_chatgpt_translate_work" / f"freida_study__{slugify(stem)}"
        input_epub = LIBRARY_ROOT / "[e]" / AUTHOR_FOLDER / f"[e] {stem}.epub"
        live_ke_epub = LIBRARY_ROOT / "[k-e]" / AUTHOR_FOLDER / f"[k-e] {stem}.epub"
        bilingual_output = live_ke_epub
        study_output = LIBRARY_ROOT / "[study]" / AUTHOR_FOLDER / f"[study] {stem}.epub"
        korean_output = LIBRARY_ROOT / "[k]" / AUTHOR_FOLDER / f"[k] {stem}.epub"
        english_study_output = LIBRARY_ROOT / "[e-s]" / AUTHOR_FOLDER / f"[e-s] {stem}.epub"

        # Fallback search if exact input_epub path not found
        if not input_epub.exists():
            matches = list((LIBRARY_ROOT / "[e]").rglob(f"*{stem}*.epub"))
            if matches:
                input_epub = matches[0]

        completion_paths = [
            str(study_output),
            str(english_study_output),
        ]

        task_spec = {
            "id": task_id,
            "title": f"Freida McFadden {idx:02d} · {stem} [study/e-s]",
            "providers": ["gemini"],
            "preferred_accounts": ["account2"],
            "priority": base_priority + idx,
            "max_attempts": 20,
            "max_stall_restarts": 1,
            "work_dir": str(work_dir),
            "command": [
                "{python}",
                "scripts/backfill_study_notes.py",
                "--input-epub",
                str(input_epub),
                "--live-k-e-epub",
                str(live_ke_epub),
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
                "--web-max-attempts",
                "3",
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
                    "scripts/make_english_study_epubs.py",
                    str(LIBRARY_ROOT / "[study]" / AUTHOR_FOLDER),
                    "--overwrite",
                ],
            ],
            "completion_paths": completion_paths,
        }
        task_specs[task_id] = task_spec

    # Reassemble tasks list: keep VK tasks first (priority -1000 for main), then Freida tasks (-800 for account2)
    new_tasks = []
    seen_ids = set()

    # Preserve existing vk tasks
    for t in existing_tasks:
        if "vk-dark" in t.get("id", ""):
            new_tasks.append(t)
            seen_ids.add(t["id"])

    # Add Freida McFadden tasks
    for task_id in sorted(task_specs.keys()):
        new_tasks.append(task_specs[task_id])
        seen_ids.add(task_id)

    # Add remaining best100 / other tasks
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

        for t in status_tasks:
            if isinstance(t, dict) and "vk-dark" in t.get("id", ""):
                updated_status_tasks.append(t)
                status_seen.add(t.get("id"))

        for idx, task_id in enumerate(sorted(task_specs.keys()), 1):
            spec = task_specs[task_id]
            st = status_tasks_by_id.get(task_id, {})
            st.update({
                "id": task_id,
                "title": spec["title"],
                "providers": ["gemini"],
                "preferred_accounts": ["account2"],
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

    print("Successfully configured 19 Freida McFadden books for study/e-s generation with Account 2 (priority -800)!")
    for idx, stem in enumerate(FREIDA_BOOKS, 1):
        print(f"  {idx:02d}. {stem}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
