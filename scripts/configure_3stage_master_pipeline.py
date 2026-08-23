#!/usr/bin/env python3
"""
3-Stage Master Pipeline Configurator
Configures tasks in strict order:
  Stage 1: /Volumes/2T hard/best 100 (Priority: 100)
  Stage 2: Library books missing [study] / [e-s] (Priority: 80)
  Stage 3: /Volumes/2T hard/English Books Collection (Priority: 60)
"""

import json, re
from pathlib import Path

BEST100_DIR = Path("/Volumes/2T hard/best 100")
LIBRARY_DIR = Path("/Users/hyeokjunkong/Desktop/소설2")
ENG_COLLECTION_DIR = Path("/Volumes/2T hard/English Books Collection")
CONFIG_PATH = Path(".work/continuous_scheduler/config.json")

def sanitize_id(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_]+", "-", s)[:80]

def clean_author_from_path(p: Path) -> str:
    parent_name = p.parent.name
    if parent_name.startswith("#"):
        return parent_name[1:].strip()
    # Check if format is 'Title - Author'
    stem = p.stem
    if " - " in stem:
        parts = stem.split(" - ")
        return parts[-1].strip()
    return "Unknown"

def main():
    print("Building 3-Stage Master Pipeline Task List...")
    tasks = []
    
    # ── 1. Stage 1: Best 100 (Priority 100) ──────────────────────────────────
    if BEST100_DIR.exists():
        best100_files = sorted(BEST100_DIR.rglob("*.epub"))
        print(f"Stage 1: Found {len(best100_files)} files in 'best 100'")
        for p in best100_files:
            author = clean_author_from_path(p)
            author_folder = f"#{author}"
            stem = p.stem
            
            # Check if already complete in library [study]
            out_study = LIBRARY_DIR / "[study]" / author_folder / f"[study] {stem}.epub"
            out_ke = LIBRARY_DIR / "[k-e]" / author_folder / f"[k-e] {stem}.epub"
            if out_study.exists() and out_ke.exists():
                continue
                
            task_id = f"best100-{sanitize_id(stem)}"
            work_slug = sanitize_id(f"best100_{stem}")
            tasks.append({
                "id": task_id,
                "title": f"Best 100 · {stem}",
                "input_epub": str(p),
                "output_epub": str(out_ke),
                "study_output_epub": str(out_study),
                "work_dir": str(LIBRARY_DIR / "_chatgpt_translate_work" / work_slug),
                "book_title_ko": stem,
                "stage": 1,
                "priority": 100,
                "account_id": None, # Dynamic allocation
                "status": "pending",
                "max_chars_per_chunk": 6000,
                "request_timeout_sec": 1200,
                "web_max_attempts": 3,
                "chunks_per_conversation": 10,
                "inter_request_delay_sec": 8.0,
            })
            
    # ── 2. Stage 2: Missing Study / E-S Editions (Priority 80) ────────────────
    ke_root = LIBRARY_DIR / "[k-e]"
    study_root = LIBRARY_DIR / "[study]"
    if ke_root.exists():
        ke_files = sorted(ke_root.rglob("*.epub"))
        missing_count = 0
        for ke_p in ke_files:
            rel = ke_p.relative_to(ke_root)
            study_p = study_root / rel.parent / f"[study] {ke_p.name.replace('[k-e] ', '')}"
            if not study_p.exists():
                missing_count += 1
                stem = ke_p.stem.replace("[k-e] ", "")
                task_id = f"study-derive-{sanitize_id(stem)}"
                work_slug = sanitize_id(f"study_derive_{stem}")
                tasks.append({
                    "id": task_id,
                    "title": f"Study 생성 · {stem}",
                    "input_epub": str(ke_p),
                    "output_epub": str(ke_p),
                    "study_output_epub": str(study_p),
                    "work_dir": str(LIBRARY_DIR / "_chatgpt_translate_work" / work_slug),
                    "book_title_ko": stem,
                    "stage": 2,
                    "priority": 80,
                    "account_id": None,
                    "status": "pending",
                    "max_chars_per_chunk": 6000,
                    "request_timeout_sec": 1200,
                    "web_max_attempts": 3,
                    "chunks_per_conversation": 10,
                    "inter_request_delay_sec": 8.0,
                })
        print(f"Stage 2: Found {missing_count} books missing study editions")

    # ── 3. Stage 3: English Books Collection (Priority 60) ───────────────────
    if ENG_COLLECTION_DIR.exists():
        eng_files = sorted(ENG_COLLECTION_DIR.rglob("*.epub"))
        print(f"Stage 3: Found {len(eng_files)} files in 'English Books Collection'")
        # Add first batch of non-translated books
        added_eng = 0
        for p in eng_files:
            author = clean_author_from_path(p)
            author_folder = f"#{author}"
            stem = p.stem
            out_ke = LIBRARY_DIR / "[k-e]" / author_folder / f"[k-e] {stem}.epub"
            out_study = LIBRARY_DIR / "[study]" / author_folder / f"[study] {stem}.epub"
            if out_ke.exists() and out_study.exists():
                continue
                
            task_id = f"eng-col-{sanitize_id(stem)}"
            work_slug = sanitize_id(f"eng_col_{stem}")
            tasks.append({
                "id": task_id,
                "title": f"English Collection · {stem}",
                "input_epub": str(p),
                "output_epub": str(out_ke),
                "study_output_epub": str(out_study),
                "work_dir": str(LIBRARY_DIR / "_chatgpt_translate_work" / work_slug),
                "book_title_ko": stem,
                "stage": 3,
                "priority": 60,
                "account_id": None,
                "status": "pending",
                "max_chars_per_chunk": 6000,
                "request_timeout_sec": 1200,
                "web_max_attempts": 3,
                "chunks_per_conversation": 10,
                "inter_request_delay_sec": 8.0,
            })
            added_eng += 1
            if added_eng >= 300:  # Register top 300 queue items for scheduler performance
                break

    # Save to config.json
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing_cfg = {}
    if CONFIG_PATH.exists():
        try:
            existing_cfg = json.loads(CONFIG_PATH.read_text())
        except:
            pass
            
    accounts = existing_cfg.get("accounts", [
        {"id": "main", "provider": "gemini"},
        {"id": "account2", "provider": "gemini"},
        {"id": "account3", "provider": "gemini"},
        {"id": "chatgpt", "provider": "chatgpt"},
    ])
    
    cfg = {
        "accounts": accounts,
        "tasks": tasks,
    }
    
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    print(f"🎉 Successfully built 3-Stage Master Pipeline Config with {len(tasks)} total queued tasks!")
    print(f"   - Stage 1 (Best 100): Priority 100")
    print(f"   - Stage 2 (Missing Study/E-S): Priority 80")
    print(f"   - Stage 3 (English Books Collection): Priority 60")

if __name__ == "__main__":
    main()
