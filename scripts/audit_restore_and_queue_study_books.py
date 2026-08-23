#!/usr/bin/env python3
"""scripts/audit_restore_and_queue_study_books.py

Scans `/Users/hyeokjunkong/Desktop/소설2/[study]/` for EPUBs missing study notes.
Searches the entire system (.webui/, backups, etc.) for authentic original study EPUBs:
- If an authentic study file is found -> RESTORES it to [study], and regenerates [e-s], [k], [k-e].
- If NOT found -> RENAMES file in [study] from `[study] ...` to `[study_] ...` and ENQUEUES it for new translation.
"""

import json
import os
import re
import shutil
import zipfile
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
STUDY_ROOT = LIB_ROOT / "[study]"
KE_ROOT = LIB_ROOT / "[k-e]"
K_ROOT = LIB_ROOT / "[k]"
ES_ROOT = LIB_ROOT / "[e-s]"
E_ROOT = LIB_ROOT / "[e]"
CONFIG_PATH = Path(".work/continuous_scheduler/config.json")

SEARCH_DIRS = [
    Path(".webui"),
    Path(".work"),
    LIB_ROOT / "_chatgpt_translate_work",
    LIB_ROOT / "_backups",
    LIB_ROOT / "_manual_backups",
    LIB_ROOT / "[backup_data] 20260807",
    LIB_ROOT / "new books from vk",
    Path.home() / "Desktop" / "myproject_python" / "haijun93-audiobook-maker" / ".webui"
]


def clean_title_key(name: str) -> str:
    clean = re.sub(r"^\[.*?\]\s*", "", name)
    clean = re.sub(r"\.epub$", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r"\(\d+\.\d+\)", "", clean).strip()
    clean = re.sub(r"[^a-zA-Z0-9가-힣]", "", clean).lower()
    return clean


def count_study_notes(epub_path: Path) -> int:
    if not epub_path.exists() or epub_path.stat().st_size < 1000:
        return 0
    total_notes = 0
    try:
        with zipfile.ZipFile(epub_path, "r") as z:
            for name in z.namelist():
                if name.endswith((".xhtml", ".html", ".htm")) and not name.startswith("cover"):
                    try:
                        content = z.read(name).decode("utf-8", errors="ignore")
                    except:
                        continue
                    notes = len(re.findall(r"※\s*[^<\n]+", content))
                    if "study-note" in content or "study_notes" in content:
                        notes += len(re.findall(r"class=[\"\']study-note", content))
                    if "【어휘" in content or "[어휘" in content:
                        notes += len(re.findall(r"【어휘|\[어휘", content))
                    total_notes += notes
    except Exception as e:
        return 0
    return total_notes


def find_candidate_authentic_study_file(book_key: str, original_filename: str) -> Path | None:
    best_candidate = None
    best_notes = 0

    clean_raw = re.sub(r"^\[.*?\]\s*", "", original_filename).replace(".epub", "").strip()
    words = [w for w in re.split(r"[\s\-_]+", clean_raw) if len(w) > 3][:3]

    for s_dir in SEARCH_DIRS:
        if not s_dir.exists():
            continue
        for root, _, files in os.walk(s_dir):
            for f in files:
                if not f.endswith(".epub") or f.startswith("."):
                    continue
                f_p = Path(root) / f
                if f_p.parent == STUDY_ROOT or "[study_]" in f:
                    continue

                # Match by key or title words
                f_key = clean_title_key(f)
                if (book_key and book_key == f_key) or (words and all(w.lower() in f.lower() for w in words)):
                    notes = count_study_notes(f_p)
                    if notes > 50 and notes > best_notes:
                        best_notes = notes
                        best_candidate = f_p

    return best_candidate


def main():
    print("==================================================================")
    print("🔍 AUDITING, RESTORING, AND QUEUING [study] EPUBs")
    print(f"📁 Target Library: {STUDY_ROOT}")
    print("==================================================================")

    all_study_epubs = list(STUDY_ROOT.rglob("*.epub"))
    print(f"Discovered {len(all_study_epubs)} EPUB files in [study].")

    healthy_count = 0
    restored_list = []
    renamed_and_queued_list = []

    for epub_p in sorted(all_study_epubs):
        if any(part.startswith(".") for part in epub_p.parts) or "[backup_data]" in str(epub_p):
            continue

        notes_count = count_study_notes(epub_p)
        if notes_count >= 30:
            healthy_count += 1
            continue

        # Missing study notes
        print(f"\n⚠️ Missing Study Notes ({notes_count} notes): {epub_p.relative_to(STUDY_ROOT)}")
        book_key = clean_title_key(epub_p.name)

        # Search for authentic candidate
        candidate = find_candidate_authentic_study_file(book_key, epub_p.name)

        if candidate:
            c_notes = count_study_notes(candidate)
            print(f"  🎉 FOUND AUTHENTIC BACKUP: {candidate} ({c_notes:,} notes)")
            shutil.copy2(candidate, epub_p)
            restored_list.append({
                "path": str(epub_p.relative_to(STUDY_ROOT)),
                "notes": c_notes,
                "source": str(candidate)
            })
        else:
            # Not found -> rename to [study_]
            new_name = epub_p.name.replace("[study]", "[study_]") if epub_p.name.startswith("[study]") else f"[study_] {epub_p.name}"
            new_path = epub_p.parent / new_name
            if epub_p != new_path:
                shutil.move(str(epub_p), str(new_path))
                print(f"  🏷️ RENAMED: {epub_p.name} -> {new_name}")
            else:
                new_path = epub_p

            # Find matching [e] original for translation queue
            rel_dir = new_path.parent.relative_to(STUDY_ROOT)
            e_matching = None
            e_dir = E_ROOT / rel_dir
            if e_dir.exists():
                for ef in e_dir.glob("*.epub"):
                    if clean_title_key(ef.name) == book_key:
                        e_matching = ef
                        break

            renamed_and_queued_list.append({
                "title": new_name,
                "rel_path": str(new_path.relative_to(STUDY_ROOT)),
                "input_epub": str(e_matching) if e_matching else None,
                "study_path": str(new_path)
            })

    # Update Queue in config.json
    if CONFIG_PATH.exists() and renamed_and_queued_list:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        existing_tasks = cfg.get("tasks", [])
        existing_ids = {t["id"] for t in existing_tasks}

        new_tasks = []
        for item in renamed_and_queued_list:
            if not item["input_epub"]:
                continue
            slug = re.sub(r"[^a-zA-Z0-9]", "_", item["title"].lower()).strip("_")
            t_id = f"stage0_study_regen_{slug}"
            if t_id not in existing_ids:
                task_obj = {
                    "id": t_id,
                    "title": Path(item["input_epub"]).name,
                    "book_title_ko": item["title"],
                    "input_epub": item["input_epub"],
                    "output_epub": str(KE_ROOT / Path(item["rel_path"]).parent / item["title"].replace("[study_]", "[k-e]")),
                    "study_output_epub": str(STUDY_ROOT / item["rel_path"].replace("[study_]", "[study]")),
                    "work_dir": str(LIB_ROOT / "_chatgpt_translate_work" / f"study_regen_{slug}"),
                    "stage": 0,
                    "stage_name": "Stage 0: Study Notes Generation (Pending [study_])",
                    "priority": 940,
                    "force_retranslate": True,
                    "status": "pending"
                }
                new_tasks.append(task_obj)
                existing_ids.add(t_id)

        all_tasks = new_tasks + existing_tasks
        all_tasks.sort(key=lambda x: x.get("priority", 0), reverse=True)
        cfg["tasks"] = all_tasks
        cfg["stage_summary"]["Stage 0 (Study Notes Regeneration [study_])"] = len(new_tasks)

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Injected {len(new_tasks)} [study_] books into translation queue with Priority 940!")

    print("\n==================================================================")
    print("📊 FINAL AUDIT & RESTORATION SUMMARY")
    print("==================================================================")
    print(f"✅ Healthy Study Books (>30 notes): {healthy_count} 권")
    print(f"🎉 Restored from Authentic Backups: {len(restored_list)} 권")
    print(f"🏷️ Renamed to [study_] & Enqueued: {len(renamed_and_queued_list)} 권")
    print("==================================================================")


if __name__ == "__main__":
    main()
