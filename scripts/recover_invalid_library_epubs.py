#!/usr/bin/env python3
"""Recover invalid derived EPUBs without overwriting active translation output.

Only deterministic derivations are attempted:
  [k]      <- [k-e]
  [e-s]    <- [study]
  [study_x] <- [study]
  [e-s_x]  <- [e-s]

Invalid source editions are reported for retranslation/source recovery instead
of being guessed or replaced with mechanical content.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
WORKSPACE = Path(__file__).resolve().parents[1]

if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from build_xteink_dedicated_editions import (  # noqa: E402
    build_single_xteink_epub_worker,
)
from make_english_study_epubs import convert_epub as make_es  # noqa: E402
from make_korean_only_epubs import convert_epub as make_k  # noqa: E402


PREFIX = re.compile(r"^\[(?:e|k|k-e|study|e-s|study_x|e-s_x)\]\s*", re.I)


def valid_epub(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.testzip() is None
    except (OSError, zipfile.BadZipFile, Exception):
        return False


def strip_prefix(name: str) -> str:
    return PREFIX.sub("", name)


def index(root: Path) -> dict[tuple[str, str], Path]:
    result = {}
    if not root.is_dir():
        return result
    for path in root.rglob("*.epub"):
        if path.is_file():
            result.setdefault((str(path.parent.relative_to(root)).casefold(), strip_prefix(path.name).casefold()), path)
    return result


def is_recent(path: Path, minutes: int) -> bool:
    return time.time() - path.stat().st_mtime < minutes * 60


def source_for(target: Path, target_root: Path, source_root: Path, prefix: str) -> Path:
    rel = target.relative_to(target_root)
    clean_name = re.sub(r"^\[[^]]+\]\s*", "", rel.name)
    return source_root / rel.parent / f"{prefix} {clean_name}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-root", type=Path, default=ROOT)
    parser.add_argument("--active-window-minutes", type=int, default=15)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = args.library_root.expanduser().resolve()

    roots = {
        "[e]": root / "[e]",
        "[k-e]": root / "[k-e]",
        "[study]": root / "[study]",
        "[e-s]": root / "[e-s]",
        "[k]": root / "[k]",
    }
    indexes = {name: index(path) for name, path in roots.items()}
    xroot = root / "[xteink]"
    targets: list[tuple[str, Path, Path]] = []
    prior_report = WORKSPACE / "data/library_invalid_epub_recovery.json"
    prior_items = []
    if prior_report.exists():
        try:
            prior_items = json.loads(prior_report.read_text(encoding="utf-8")).get("failed", [])
        except (OSError, ValueError):
            prior_items = []

    # Prefer the previous archive scan.  Re-running CRC validation over every
    # EPUB before each repair made urgent recovery unnecessarily slow.
    if prior_items:
        for item in prior_items:
            target = Path(item.get("target", ""))
            parts = target.parts
            if "[k]" in parts:
                idx = parts.index("[k]")
                target = root / "[k]" / Path(*parts[idx + 1 :])
                source = source_for(target, root / "[k]", root / "[k-e]", "[k-e]")
                targets.append(("[k]<-[k-e]", target, source))
            elif "[e-s]" in parts:
                idx = parts.index("[e-s]")
                target = root / "[e-s]" / Path(*parts[idx + 1 :])
                source = source_for(target, root / "[e-s]", root / "[study]", "[study]")
                targets.append(("[e-s]<-[study]", target, source))
            elif "[study_x]" in parts:
                idx = parts.index("[study_x]")
                target = xroot / "[study_x]" / Path(*parts[idx + 1 :])
                source = root / "[study]" / Path(*parts[idx + 1 :])
                targets.append(("[study_x]<-[study]", target, source))
            elif "[e-s_x]" in parts:
                idx = parts.index("[e-s_x]")
                target = xroot / "[e-s_x]" / Path(*parts[idx + 1 :])
                source = root / "[e-s]" / Path(*parts[idx + 1 :])
                targets.append(("[e-s_x]<-[e-s]", target, source))
        targets = list({(relation, target, source) for relation, target, source in targets if target.is_file()})

    if targets:
        indexes = {}
    else:
        # First-run fallback: discover invalid derived files normally.
        indexes = {name: index(path) for name, path in roots.items()}
    for edition, source_edition in (("[k]", "[k-e]"), ("[e-s]", "[study]")) if not targets else ():
        for key, target in indexes[edition].items():
            if valid_epub(target):
                continue
            source = indexes[source_edition].get(key)
            targets.append((f"{edition}<-{source_edition}", target, source) if source else (f"{edition}<-{source_edition}", target, Path()))

    for path in (xroot / "[study_x]", xroot / "[e-s_x]") if not targets else ():
        edition = "[study_x]" if path.name == "[study_x]" else "[e-s_x]"
        source_root = roots["[study]"] if edition == "[study_x]" else roots["[e-s]"]
        source_index = indexes["[study]"] if edition == "[study_x]" else indexes["[e-s]"]
        for target in path.rglob("*.epub") if path.is_dir() else ():
            if valid_epub(target):
                continue
            rel = target.relative_to(path)
            source = source_index.get((str(rel.parent).casefold(), strip_prefix(target.name).casefold()))
            if source is None:
                source = source_root / rel.parent / strip_prefix(target.name)
            targets.append((f"{edition}<-{source_root.name}", target, source))

    result = {"apply": args.apply, "attempted": 0, "recovered": 0, "skipped_recent": 0, "no_source": 0, "failed": []}
    for relation, target, source in targets:
        result["attempted"] += 1
        if is_recent(target, args.active_window_minutes):
            result["skipped_recent"] += 1
            continue
        if not source or not source.is_file() or not valid_epub(source):
            result["no_source"] += 1
            result["failed"].append({"target": str(target), "reason": "invalid_or_missing_source", "source": str(source)})
            continue
        if not args.apply:
            result["recovered"] += 1
            continue
        try:
            if relation.startswith("[k]<-"):
                make_k(source, target, overwrite=True)
            elif relation.startswith("[e-s]<-"):
                make_es(source, target, overwrite=True)
            else:
                edition_type = "study_x" if relation.startswith("[study_x]") else "e-s_x"
                build_single_xteink_epub_worker((str(source), str(target), edition_type))
            if not valid_epub(target):
                raise RuntimeError("output failed ZIP validation")
            result["recovered"] += 1
        except Exception as exc:  # one book must not stop the batch
            result["failed"].append({"target": str(target), "source": str(source), "reason": str(exc)})

    report = root.parent / "myproject_python/haijun93-audiobook-maker/data/library_invalid_epub_recovery.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "failed"}, ensure_ascii=False))
    print(f"report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
