#!/usr/bin/env python3
"""Queue Best 100 books from external drive into the continuous scheduler."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.atomic_io import atomic_write_json
from webui.continuous_scheduler import validate_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".work" / "continuous_scheduler" / "config.json"
BEST100_DIR = Path("/Volumes/2T hard/best 100")
LIBRARY_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
PYTHON_PATH = str(ROOT / ".venv311" / "bin" / "python")


def clean_slug(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9가-힣._-]+", "_", text).strip("_")
    return re.sub(r"_+", "_", slug)[:100] or "book"


def extract_rating(filename: str) -> float:
    match = re.search(r"\(([0-9]\.[0-9]+)\)", filename)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return 4.0


def extract_author(p: Path) -> str:
    parent_name = p.parent.name
    if parent_name.startswith("#"):
        return parent_name
    stem = p.stem.replace("[e] ", "").strip()
    if " - " in stem:
        author_part = stem.split(" - ")[-1]
        author_clean = re.sub(r"\([0-9]\.[0-9]+\)", "", author_part).strip()
        if author_clean:
            return f"#{author_clean}"
    return "#Best 100"


def discover_best100_books() -> list[Path]:
    epubs = []
    for p in BEST100_DIR.rglob("*.epub"):
        if any(x in p.parts for x in ("finished", "non-english", "[k]", "[k-e]", "[study]", "[e-s]", "[e]")):
            continue
        epubs.append(p)

    unique_books: dict[str, Path] = {}
    for p in epubs:
        clean_key = re.sub(r"[^a-zA-Z0-9]+", "", p.stem.lower())
        if clean_key not in unique_books:
            unique_books[clean_key] = p

    sorted_paths = sorted(unique_books.values(), key=lambda p: (extract_rating(p.name), p.name), reverse=True)
    return sorted_paths


def build_best100_tasks(existing_config: dict[str, object]) -> list[dict[str, object]]:
    best100_paths = discover_best100_books()
    existing_tasks = list(existing_config.get("tasks", []))
    existing_ids = {t["id"] for t in existing_tasks}

    accounts = ["main", "chatgpt", "account2", "account3"]

    new_tasks = []
    for idx, epub_path in enumerate(best100_paths):
        stem = epub_path.stem.replace("[e] ", "").strip()
        author_folder = extract_author(epub_path)
        t_id = f"best100-{clean_slug(stem).lower()}"
        if t_id in existing_ids:
            continue

        work_dir = LIBRARY_ROOT / "_chatgpt_translate_work" / f"best100__{clean_slug(stem)}"
        bilingual_output = LIBRARY_ROOT / "[k-e]" / author_folder / f"[k-e] {stem}.epub"
        study_output = LIBRARY_ROOT / "[study]" / author_folder / f"[study] {stem}.epub"
        korean_output = LIBRARY_ROOT / "[k]" / author_folder / f"[k] {stem}.epub"
        english_study_output = LIBRARY_ROOT / "[e-s]" / author_folder / f"[e-s] {stem}.epub"

        preferred_acc = accounts[idx % len(accounts)]

        task = {
            "id": t_id,
            "title": f"Best 100 · {stem}",
            "providers": ["gemini", "chatgpt"],
            "preferred_accounts": [preferred_acc],
            "priority": 100 + idx,
            "max_attempts": 20,
            "max_stall_restarts": 1,
            "work_dir": str(work_dir),
            "command": [
                "{python}",
                "scripts/translate_epub_with_chatgpt_web_to_study_epub.py",
                "--input-epub",
                str(epub_path),
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
                "8",
                "--heartbeat-file",
                str(work_dir / "heartbeat.json"),
                "--web-provider",
                "{provider}",
            ],
            "post_commands": [
                [
                    "{python}",
                    "scripts/make_korean_only_epubs.py",
                    str(LIBRARY_ROOT / "[k-e]" / author_folder),
                    "--overwrite",
                ],
                [
                    "{python}",
                    "scripts/make_english_study_epubs.py",
                    str(LIBRARY_ROOT / "[study]" / author_folder),
                    "--output-root",
                    str(LIBRARY_ROOT / "[e-s]" / author_folder),
                    "--overwrite",
                ],
            ],
            "completion_paths": [
                str(bilingual_output),
                str(korean_output),
                str(study_output),
                str(english_study_output),
            ],
        }
        new_tasks.append(task)

    return new_tasks


def main() -> int:
    if not CONFIG_PATH.exists():
        print(f"Error: Config path not found: {CONFIG_PATH}")
        return 1

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    new_tasks = build_best100_tasks(config)
    print(f"Found {len(new_tasks)} new Best 100 tasks to queue.")

    if not new_tasks:
        print("All Best 100 books are already queued.")
        return 0

    config["tasks"].extend(new_tasks)
    validate_config(config)
    atomic_write_json(CONFIG_PATH, config)
    print(f"Successfully added {len(new_tasks)} Best 100 tasks to {CONFIG_PATH}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
