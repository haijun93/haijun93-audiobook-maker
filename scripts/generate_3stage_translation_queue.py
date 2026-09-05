#!/usr/bin/env python3
"""scripts/generate_3stage_translation_queue.py

Generates the prioritized 3-stage translation queue according to exact user policy:
  Stage 1 (Priority 100): '/Volumes/2T hard/best 100' master collection
  Stage 2 (Priority 80) : Library books in '소설2' missing [study] editions
  Stage 3 (Priority 50) : '/Volumes/2T hard/English Books Collection' massive catalogue
"""

import json
import os
import re
import time
import unicodedata
from pathlib import Path

def clean_key(text: str) -> str:
    c = re.sub(r'^\[.*?\]\s*', '', text)
    c = re.sub(r'\(.*?\)', '', c)
    return re.sub(r'[^a-zA-Z0-9가-힣]', '', c.lower())

def is_valid_epub(p: Path) -> bool:
    return p.is_file() and p.stat().st_size > 25000 and p.name.endswith(".epub")

def main():
    desktop = Path("/Users/hyeokjunkong/Desktop")
    lib_root = next(p for p in desktop.iterdir() if "소설2" in unicodedata.normalize("NFC", p.name))
    hard_drive = Path("/Volumes/2T hard")
    config_file = Path("/Users/hyeokjunkong/Desktop/myproject_python/haijun93-audiobook-maker/.work/continuous_scheduler/config.json")

    print("==================================================================")
    print("🚀 Generating Strict 3-Stage Translation Queue Configuration")
    print("   • Stage 1 (Priority 100): '/Volumes/2T hard/best 100'")
    print("   • Stage 2 (Priority 80) : Library Books Missing [study] Editions")
    print("   • Stage 3 (Priority 50) : '/Volumes/2T hard/English Books Collection'")
    print("==================================================================")

    # 1. Gather all existing [study] completed books
    study_epubs = list((lib_root / "[study]").glob("**/*.epub"))
    completed_study_keys = set()
    for p in study_epubs:
        clean = re.sub(r'^\[study\]\s*', '', p.stem)
        clean = re.sub(r'\(.*?\)', '', clean)
        key = re.sub(r'[^a-zA-Z0-9가-힣]', '', clean.lower())
        if key:
            completed_study_keys.add(key)

    print(f"Total Completed [study] Books in Library: {len(study_epubs)} (Keys: {len(completed_study_keys)})")

    tasks = []
    seen_keys = set(completed_study_keys)

    # ==============================================================================
    # STAGE 1: '/Volumes/2T hard/best 100' (Priority 100)
    # ==============================================================================
    stage1_dirs = [hard_drive / "best 100", hard_drive / "best 100 - account2"]
    stage1_count = 0
    for sdir in stage1_dirs:
        if not sdir.exists(): continue
        for dirpath, _, filenames in os.walk(str(sdir)):
            for f in filenames:
                if not f.endswith(".epub") or f.startswith(("[k]", "[k-e]", "[study]")): continue
                fp = Path(dirpath) / f
                if not is_valid_epub(fp): continue
                k = clean_key(fp.stem)
                if k and k not in seen_keys:
                    seen_keys.add(k)
                    stage1_count += 1
                    task_id = f"stage1_best100_{stage1_count:04d}_{k[:20]}"
                    rel_dir = fp.relative_to(sdir).parent
                    out_name = f"[k-e] {fp.stem}.epub"
                    study_name = f"[study] {fp.stem}.epub"
                    tasks.append({
                        "id": task_id,
                        "title": fp.name,
                        "book_title_ko": fp.stem,
                        "input_epub": str(fp),
                        "output_epub": str(lib_root / "[k-e]" / rel_dir / out_name),
                        "study_output_epub": str(lib_root / "[study]" / rel_dir / study_name),
                        "work_dir": str(lib_root / "_chatgpt_translate_work" / f"stage1_{k[:25]}"),
                        "stage": 1,
                        "stage_name": "Stage 1: Best 100 Master Collection",
                        "priority": 100,
                        "status": "pending"
                    })

    print(f"  ✅ Stage 1 (Best 100) Added: {stage1_count} books")

    # ==============================================================================
    # STAGE 2: Library books missing [study] versions (Priority 80)
    # ==============================================================================
    stage2_count = 0
    e_epubs = list((lib_root / "[e]").glob("**/*.epub"))
    for ep in e_epubs:
        if not is_valid_epub(ep): continue
        k = clean_key(ep.stem)
        if k and k not in seen_keys:
            seen_keys.add(k)
            stage2_count += 1
            task_id = f"stage2_library_study_{stage2_count:04d}_{k[:20]}"
            rel_parent = ep.relative_to(lib_root / "[e]").parent
            out_name = f"[k-e] {ep.stem.replace('[e] ', '')}.epub"
            study_name = f"[study] {ep.stem.replace('[e] ', '')}.epub"
            tasks.append({
                "id": task_id,
                "title": ep.name,
                "book_title_ko": ep.stem.replace('[e] ', ''),
                "input_epub": str(ep),
                "output_epub": str(lib_root / "[k-e]" / rel_parent / out_name),
                "study_output_epub": str(lib_root / "[study]" / rel_parent / study_name),
                "work_dir": str(lib_root / "_chatgpt_translate_work" / f"stage2_{k[:25]}"),
                "stage": 2,
                "stage_name": "Stage 2: Library Missing Study Editions",
                "priority": 80,
                "status": "pending"
            })

    print(f"  ✅ Stage 2 (Library Missing Study) Added: {stage2_count} books")

    # ==============================================================================
    # STAGE 3: '/Volumes/2T hard/English Books Collection' (Priority 50)
    # ==============================================================================
    stage3_dir = hard_drive / "English Books Collection"
    stage3_count = 0
    if stage3_dir.exists():
        for dirpath, _, filenames in os.walk(str(stage3_dir)):
            for f in filenames:
                if not f.endswith(".epub") or f.startswith(("[k]", "[k-e]", "[study]")): continue
                fp = Path(dirpath) / f
                if not is_valid_epub(fp): continue
                k = clean_key(fp.stem)
                if k and k not in seen_keys:
                    seen_keys.add(k)
                    stage3_count += 1
                    task_id = f"stage3_eng_coll_{stage3_count:05d}_{k[:20]}"
                    rel_parent = fp.relative_to(stage3_dir).parent
                    out_name = f"[k-e] {fp.stem}.epub"
                    study_name = f"[study] {fp.stem}.epub"
                    tasks.append({
                        "id": task_id,
                        "title": fp.name,
                        "book_title_ko": fp.stem,
                        "input_epub": str(fp),
                        "output_epub": str(lib_root / "[k-e]" / rel_parent / out_name),
                        "study_output_epub": str(lib_root / "[study]" / rel_parent / study_name),
                        "work_dir": str(lib_root / "_chatgpt_translate_work" / f"stage3_{k[:25]}"),
                        "stage": 3,
                        "stage_name": "Stage 3: English Books Collection",
                        "priority": 50,
                        "status": "pending"
                    })

    print(f"  ✅ Stage 3 (English Books Collection) Added: {stage3_count} books")

    # Save new config
    config_data = {
        "version": 3,
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stage_summary": {
            "Stage 1 (Best 100)": stage1_count,
            "Stage 2 (Library Missing Study)": stage2_count,
            "Stage 3 (English Books Collection)": stage3_count,
            "Total Pipeline Tasks": len(tasks)
        },
        "tasks": tasks
    }

    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps(config_data, indent=2, ensure_ascii=False))

    print("\n==================================================================")
    print(f"🎉 Successfully re-indexed {len(tasks):,} tasks to {config_file}!")
    print("==================================================================")

if __name__ == "__main__":
    main()
