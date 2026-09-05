#!/usr/bin/env python3
"""
'finished' 폴더(이미 번역이 끝난 원서 EPUB 모음)에 있는 작품명/작가명 목록을 만들고,
지정한 소스 폴더의 EPUB들을 대조하여 이미 완료된 작품은 finished 폴더로 이동한다.

배치 번역 파이프라인(webui/workflow_runner.py)은 매 항목을 처리하기 직전에
동일한 로직으로 자동 검사하므로, 이 스크립트는 수동 점검/사전 정리용이다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from webui.book_organizer import (  # noqa: E402
    archive_duplicate_source,
    build_finished_registry,
    extract_metadata_from_epub,
    find_finished_match,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--finished-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source_dir = args.source_dir.resolve()
    finished_dir = args.finished_dir.resolve()
    finished_dir.mkdir(parents=True, exist_ok=True)

    registry = build_finished_registry(finished_dir)
    print(f"finished 폴더 등록 작품 수: {len(registry)}")

    source_files = sorted(
        p for p in source_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".epub"
    )
    print(f"대조 대상 EPUB 수: {len(source_files)}\n")

    moved = []
    kept = []
    for source_path in source_files:
        meta = extract_metadata_from_epub(source_path)
        match = find_finished_match(meta["title"], meta["author"], registry)
        if match:
            moved.append((source_path, meta, match))
        else:
            kept.append((source_path, meta))

    print(f"=== 이미 완료된 작품으로 판단되어 finished로 이동: {len(moved)}건 ===")
    for source_path, meta, match in moved:
        print(f"  - {source_path.name}")
        print(f"      제목/작가: {meta['title']!r} / {meta['author']!r}")
        print(f"      매칭됨:    {match['title']!r} / {match['author']!r}  ({match['path'].name})")
        if not args.dry_run:
            archived_path = archive_duplicate_source(source_path, finished_dir)
            print(f"      -> 이동됨: {archived_path}")

    print(f"\n=== 번역 대기열에 남는 작품: {len(kept)}건 ===")
    for source_path, meta in kept[:20]:
        print(f"  - {source_path.name}  ({meta['title']!r} / {meta['author']!r})")
    if len(kept) > 20:
        print(f"  ... 외 {len(kept) - 20}건")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
