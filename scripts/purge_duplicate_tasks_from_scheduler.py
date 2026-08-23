#!/usr/bin/env python3
"""scripts/purge_duplicate_tasks_from_scheduler.py

Compares the current library holding with scheduled queue tasks:
1. Identifies tasks whose completed target EPUB already exists in the library.
2. Removes duplicated completed tasks from config.json (or marks them completed).
3. Synchronizes state.json to mark completed tasks.
4. Backs up original config.json before applying changes.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root
sys.path.insert(0, "/Users/hyeokjunkong/Desktop/myproject_python/haijun93-audiobook-maker")
from scripts.library_catalog_manager import normalize_fingerprint, scan_and_build_catalog

REPO_ROOT = Path("/Users/hyeokjunkong/Desktop/myproject_python/haijun93-audiobook-maker")
SCHED_DIR = REPO_ROOT / ".work/continuous_scheduler"
CONFIG_PATH = SCHED_DIR / "config.json"
STATE_PATH = SCHED_DIR / "state.json"


def main():
    print("==================================================================")
    print("🧹 PURGING DUPLICATE / COMPLETED TASKS FROM SCHEDULER QUEUE")
    print("==================================================================")
    
    if not CONFIG_PATH.exists():
        print(f"❌ Config not found at {CONFIG_PATH}")
        return

    # 1. Refresh Master Library Catalog
    print("📚 Scanning master library catalog...")
    cat = scan_and_build_catalog()
    fps = cat.get("fingerprints", {})
    print(f"  • Unique books in library catalog: {len(fps)}")

    # 2. Load scheduler config
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    tasks = cfg.get("tasks", [])
    print(f"  • Initial tasks in scheduler config: {len(tasks)}")

    # 3. Load scheduler state
    state = {}
    if STATE_PATH.exists():
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    state_tasks = state.setdefault("tasks", {})

    purged_tasks = []
    retained_tasks = []

    for t in tasks:
        t_id = t.get("id")
        t_title = t.get("title") or t.get("book_title_ko") or ""
        t_input = t.get("input_epub", "")
        t_out = t.get("output_epub", "")
        
        is_completed = False
        reason = ""

        # Check direct output file
        out_p = Path(t_out) if t_out else None
        if out_p and out_p.exists() and out_p.stat().st_size > 15000:
            is_completed = True
            reason = f"Target output exists ({out_p.stat().st_size / 1024:.1f} KB)"
            
        # Check by normalized fingerprint against library
        if not is_completed:
            fp = normalize_fingerprint(t_title) or normalize_fingerprint(Path(t_input).stem if t_input else "")
            if fp and fp in fps:
                entry = fps[fp]
                editions = entry.get("editions", {})
                if "k-e" in editions or "study" in editions or "k" in editions:
                    exist_p = editions.get("k-e") or editions.get("study") or editions.get("k")
                    is_completed = True
                    reason = f"Library catalog match ({Path(exist_p).name})"

        if is_completed:
            purged_tasks.append((t, reason))
            # Update state to completed
            if t_id:
                state_tasks[t_id] = {
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "reason": reason,
                    "title": t_title
                }
        else:
            retained_tasks.append(t)

    print(f"\n📊 COMPARISON RESULTS:")
    print(f"  • Already completed in Library : {len(purged_tasks)} tasks (to be purged)")
    print(f"  • Truly pending tasks remaining: {len(retained_tasks)} tasks")

    # 4. Backup config & state
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_config = SCHED_DIR / f"config.json.backup_{now_str}"
    shutil.copy2(CONFIG_PATH, backup_config)
    print(f"\n💾 Backup created: {backup_config.name}")

    # 5. Write sanitized config & state
    cfg["tasks"] = retained_tasks
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    
    if STATE_PATH.exists():
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    print("🎉 SCHEDULER QUEUE SUCCESSFULLY PURGED & SANITIZED!")
    print(f"  - Config updated: {len(retained_tasks)} pending tasks remaining.")
    print("==================================================================")


if __name__ == "__main__":
    main()
