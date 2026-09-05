#!/usr/bin/env python3
"""Find translated library books without an ``[e]`` source and acquire them.

Search order is implemented by :mod:`scripts.book_downloader_engine`:
OceanofPDF first, then Readrobe.  The default mode is a report only; use
``--apply`` to download.  A downloaded file is accepted only when it is a
valid EPUB, then it is placed under the matching standard ``[e]`` path and
registered as a pending translation task.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.book_downloader_engine import run_integrated_downloader  # noqa: E402
from webui.storage import atomic_write_json  # noqa: E402


EDITION_ROOTS = ("[k-e]", "[study]", "[k]", "[e-s]")
PREFIX_RE = re.compile(r"^\[(?:k-e|study|k|e-s|e)\]\s*", re.I)


def normalized_name(name: str) -> str:
    value = PREFIX_RE.sub("", Path(name).stem)
    value = re.sub(r"\s*\(\d+(?:\.\d+)?\)\s*$", "", value).strip()
    value = re.sub(r"\s+", " ", value).strip()
    return unicodedata.normalize("NFC", value).casefold()


def valid_epub(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 10_000:
        return False
    try:
        import zipfile

        with zipfile.ZipFile(path) as archive:
            return any(name.lower().endswith((".xhtml", ".html", ".htm")) for name in archive.namelist())
    except (OSError, zipfile.BadZipFile):
        return False


def discover_missing(library_root: Path) -> list[dict[str, str]]:
    """Return one candidate per book, preferring the most informative edition."""
    english = {normalized_name(path.name) for path in (library_root / "[e]").rglob("*.epub")}
    candidates: dict[str, dict[str, str]] = {}
    for edition in EDITION_ROOTS:
        root = library_root / edition
        if not root.is_dir():
            continue
        for path in root.rglob("*.epub"):
            # ZIP validation is deliberately deferred until after download;
            # opening every existing EPUB here makes discovery needlessly
            # expensive on a multi-thousand-book library.
            if path.name.startswith("._") or path.stat().st_size < 10_000:
                continue
            key = normalized_name(path.name)
            if not key or key in english or key in candidates:
                continue
            parent = path.relative_to(root).parent
            raw = PREFIX_RE.sub("", path.stem).strip()
            raw = re.sub(r"\s*\(\d+(?:\.\d+)?\)\s*$", "", raw).strip()
            # [k-e]/[study]/[e-s] normally preserve the English title.  For a
            # Korean-only title, the author folder still provides a useful
            # search discriminator and the downloader can report no match.
            author = parent.name.lstrip("#") if parent.name.startswith("#") else ""
            # Most library names are ``Title - Author (rating)``.  Remove the
            # filename's author suffix before adding the canonical folder
            # author, otherwise search engines receive the author twice.
            title_for_search = raw
            if author and " - " in raw and raw.casefold().endswith(f" - {author}".casefold()):
                title_for_search = raw[: -(len(author) + 3)].strip()
            query = f"{title_for_search} {author}".strip()
            candidates[key] = {
                "key": key,
                "query": query,
                "title": raw,
                "author": author or "Unknown",
                "relative_parent": str(parent),
            }
    return list(candidates.values())


def task_for_download(path: Path, library_root: Path, item: dict[str, str]) -> dict[str, object]:
    stem = path.stem.removeprefix("[e] ")
    safe_id = re.sub(r"[^A-Za-z0-9_]+", "", stem.casefold())[:80] or "book"
    parent = item["relative_parent"]
    return {
        "id": f"stage2_missing_english_{safe_id}",
        "title": path.name,
        "book_title_ko": stem,
        "input_epub": str(path),
        "output_epub": str(library_root / "[k-e]" / parent / f"[k-e] {stem}.epub"),
        "study_output_epub": str(library_root / "[study]" / parent / f"[study] {stem}.epub"),
        "work_dir": str(library_root / f"_translation_work_missing_{safe_id}"),
        "stage": 2,
        "stage_name": "Stage 2: Missing English Original",
        "priority": 90,
        "status": "pending",
        "force_retranslate": False,
    }


def register_tasks(config_path: Path, tasks_to_add: list[dict[str, object]]) -> int:
    if not tasks_to_add:
        return 0
    try:
        config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {"tasks": []}
    except (OSError, ValueError):
        config = {"tasks": []}
    tasks = config.get("tasks", [])
    existing = {str(task.get("id")) for task in tasks if isinstance(task, dict)}
    additions = [task for task in tasks_to_add if str(task["id"]) not in existing]
    if additions:
        config["tasks"] = additions + tasks
        atomic_write_json(config_path, config)
    return len(additions)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-root", type=Path, default=Path("/Users/hyeokjunkong/Desktop/소설2"))
    parser.add_argument("--config", type=Path, default=ROOT / ".work/continuous_scheduler/config.json")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N candidates (0 means all)")
    parser.add_argument("--apply", action="store_true", help="Search and download missing originals")
    parser.add_argument("--headless", action="store_true", help="Run browser headlessly")
    args = parser.parse_args()
    library_root = args.library_root.expanduser()
    missing = discover_missing(library_root)
    if args.limit > 0:
        missing = missing[: args.limit]
    print(f"Missing [e] originals: {len(missing):,}")
    for item in missing:
        print(f"- {item['query']} -> [e]/{item['relative_parent']}")
    if not args.apply or not missing:
        print("Dry-run only. Use --apply to download and queue verified results.")
        return 0

    added_tasks: list[dict[str, object]] = []
    for index, item in enumerate(missing, 1):
        destination = library_root / "[e]" / item["relative_parent"]
        before = {path.resolve() for path in destination.glob("*.epub")} if destination.is_dir() else set()
        print(f"[{index}/{len(missing)}] Searching: {item['query']}")
        run_integrated_downloader(
            author=item["author"],
            query=item["query"],
            dest_dir=destination,
            source_choice="all",
            max_pages=2,
            auto_queue=False,
            visible=not args.headless,
        )
        new_files = [path for path in destination.glob("*.epub") if path.resolve() not in before and valid_epub(path)]
        if new_files:
            chosen = max(new_files, key=lambda path: path.stat().st_mtime)
            added_tasks.append(task_for_download(chosen, library_root, item))
            print(f"  Verified English EPUB: {chosen}")
        else:
            print("  No verified download found; nothing queued.")
    added = register_tasks(args.config.expanduser(), added_tasks)
    print(f"Registered translation tasks: {added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
