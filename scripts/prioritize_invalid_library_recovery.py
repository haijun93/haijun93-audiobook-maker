#!/usr/bin/env python3
"""Put recoverable library defects ahead of all new translation tasks."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

LIB = Path("/Users/hyeokjunkong/Desktop/소설2")
QUEUE = Path(__file__).resolve().parents[1] / ".work/continuous_scheduler/config.json"
ENGLISH_COLLECTION = Path("/Volumes/2T hard/English Books Collection")


def key(name: str) -> str:
    name = re.sub(r"^\[[^]]+\]\s*", "", name)
    name = re.sub(r"\.epub$", "", name, flags=re.I)
    name = unicodedata.normalize("NFKC", name).casefold()
    return re.sub(r"[^a-z0-9가-힣]", "", name)


def valid(path: Path) -> bool:
    import zipfile

    try:
        with zipfile.ZipFile(path) as archive:
            return archive.testzip() is None
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library-root", type=Path, default=LIB)
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = args.library_root.expanduser().resolve()

    english = {}
    for base in (root / "[e]", ENGLISH_COLLECTION):
        if base.is_dir():
            for path in base.rglob("*.epub"):
                # Full CRC validation is intentionally deferred to the
                # translation quality gate; indexing only needs a readable
                # ZIP directory and avoids rescanning gigabytes here.
                try:
                    import zipfile
                    with zipfile.ZipFile(path) as archive:
                        archive.namelist()
                    english.setdefault(key(path.name), path)
                except Exception:
                    continue

    damaged = []
    # Reuse the completed archive scan when available.  Re-testing every
    # multi-megabyte EPUB here made queue maintenance unnecessarily slow.
    prior_report = Path(__file__).resolve().parents[1] / "data/library_invalid_epub_recovery.json"
    prior_targets = []
    if prior_report.exists():
        try:
            prior_targets = [item for item in json.loads(prior_report.read_text(encoding="utf-8")).get("failed", [])]
        except (OSError, ValueError):
            prior_targets = []
    if prior_targets:
        for item in prior_targets:
            target = Path(item.get("target", ""))
            parts = target.parts
            try:
                if "[xteink]" in parts and "[study_x]" in parts:
                    idx = parts.index("[study_x]")
                    edition = "[study]"
                    target = root / "[study]" / Path(*parts[idx + 1 :])
                elif "[xteink]" in parts and "[e-s_x]" in parts:
                    idx = parts.index("[e-s_x]")
                    edition = "[e-s]"
                    target = root / "[e-s]" / Path(*parts[idx + 1 :])
                elif "[k-e]" in parts and "[xteink]" not in parts:
                    edition_index = parts.index("[k-e]")
                    edition = "[k-e]"
                elif "[study]" in parts and "[xteink]" not in parts:
                    edition_index = parts.index("[study]")
                    edition = "[study]"
                elif "[k]" in parts and "[xteink]" not in parts:
                    edition_index = parts.index("[k]")
                    edition = "[k-e]"
                    target = root / "[k-e]" / Path(*parts[edition_index + 1 :])
                elif "[e-s]" in parts and "[xteink]" not in parts:
                    edition_index = parts.index("[e-s]")
                    edition = "[study]"
                    target = root / "[study]" / Path(*parts[edition_index + 1 :])
                else:
                    continue
            except ValueError:
                continue
            if edition in {"[k-e]", "[study]", "[e-s]"} and target.is_file() and not valid(target):
                damaged.append((edition, target, Path(item.get("source", ""))))
    else:
        for edition in ("[k-e]", "[study]"):
            base = root / edition
            if not base.is_dir():
                continue
            for path in base.rglob("*.epub"):
                if not valid(path):
                    damaged.append((edition, path, english.get(key(path.name))))

    config = json.loads(args.queue.read_text(encoding="utf-8")) if args.queue.exists() else {"tasks": []}
    tasks = config.setdefault("tasks", [])
    existing = {str(t.get("repair_target")) for t in tasks if isinstance(t, dict)}
    added = []
    for edition, target, source in damaged:
        if source is None or not source.is_file() or str(source).startswith(str(root)):
            source = english.get(key(target.name))
        if source is None or str(target) in existing:
            continue
        clean = re.sub(r"^\[[^]]+\]\s*", "", target.name)
        rel_parent = target.parent.relative_to(root / edition)
        output = root / "[k-e]" / rel_parent / f"[k-e] {clean}"
        study_output = root / "[study]" / rel_parent / f"[study] {clean}"
        task_id = f"repair_invalid_{edition.strip('[]')}_{key(target.name)[:48]}"
        task = {
            "id": task_id,
            "title": clean,
            "book_title_ko": clean,
            "input_epub": str(source),
            "output_epub": str(output),
            "study_output_epub": str(study_output),
            "work_dir": str(root / "_chatgpt_translate_work" / task_id),
            "stage": 0,
            "stage_name": "Recovery: invalid library EPUB retranslation",
            "priority": 10000,
            "force_retranslate": True,
            "repair_target": str(target),
            "status": "pending",
        }
        tasks.append(task)
        existing.add(str(target))
        added.append(task)

    tasks.sort(key=lambda task: task.get("priority", 0), reverse=True)
    if args.apply:
        config["last_updated"] = __import__("time").strftime("%Y-%m-%d %H:%M:%S")
        config["recovery_priority"] = {"priority": 10000, "count": len(added)}
        args.queue.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"damaged_sources": len(damaged), "queued": len(added), "apply": args.apply}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
