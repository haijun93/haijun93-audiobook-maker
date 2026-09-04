#!/usr/bin/env python3
"""scripts/sync_library_to_gdrive.py

Robust native Python differential synchronizer for macOS Google Drive FileProvider.
Avoids rsync mmap timeouts by using chunked file copy and differential synchronization.
"""

import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

LOCAL_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
GDRIVE_ROOT = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

FOLDERS_TO_SYNC = [
    "[study]",
    "[k-e]",
    "[k]",
    "[e-s]",
    "[e]",
    "MD collection"
]

def sync_file(args):
    src_file, dst_file = args
    for attempt in range(3):
        try:
            if not dst_file.exists() or (src_file.stat().st_size != dst_file.stat().st_size) or (src_file.stat().st_mtime - dst_file.stat().st_mtime > 2.0):
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                with open(src_file, "rb") as f_in, open(dst_file, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out, length=512 * 1024)
                shutil.copystat(src_file, dst_file)
                return ("copied", dst_file.name)
            return ("identical", dst_file.name)
        except Exception as e:
            if attempt < 2:
                time.sleep(1.0)
                continue
            return ("error", f"{src_file.name}: {e}")

def sync_folder(folder_name: str):
    src_dir = LOCAL_ROOT / folder_name
    dst_dir = GDRIVE_ROOT / folder_name

    if not src_dir.exists():
        print(f"⏩ Skipping missing local folder: {folder_name}")
        return 0, 0, 0

    print(f"\n🔄 Syncing: {folder_name} ...", flush=True)
    dst_dir.mkdir(parents=True, exist_ok=True)

    # 1. Build list of files to copy
    tasks = []
    src_files = set()
    for root, _, files in os.walk(src_dir):
        for f in files:
            if f.startswith(".") or f.endswith(".pyc"):
                continue
            src_p = Path(root) / f
            rel = src_p.relative_to(src_dir)
            src_files.add(rel)
            dst_p = dst_dir / rel
            tasks.append((src_p, dst_p))

    # 2. Parallel copy with ThreadPoolExecutor
    copied = 0
    identical = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=4) as executor:
        for status, msg in executor.map(sync_file, tasks):
            if status == "copied":
                copied += 1
            elif status == "identical":
                identical += 1
            elif status == "error":
                errors += 1
                print(f"    ⚠️ Error: {msg}")

    # 3. Clean up deleted/orphaned files in GDrive
    deleted = 0
    for root, _, files in os.walk(dst_dir):
        for f in files:
            if f.startswith("."):
                continue
            dst_p = Path(root) / f
            rel = dst_p.relative_to(dst_dir)
            if rel not in src_files:
                try:
                    dst_p.unlink()
                    deleted += 1
                except Exception:
                    pass

    # Clean empty dirs in dst
    for root, dirs, _ in os.walk(dst_dir, topdown=False):
        for d in dirs:
            dp = Path(root) / d
            try:
                if not any(dp.iterdir()):
                    dp.rmdir()
            except Exception:
                pass

    print(f"  ✅ {folder_name}: {copied} copied, {identical} identical, {deleted} deleted orphans, {errors} errors (Total: {len(tasks)} files)")
    return copied, identical, errors

def main():
    print("==================================================================")
    print("☁️ SYNCHRONIZING LOCAL LIBRARY TO GOOGLE DRIVE #Books")
    print(f"📁 Local Source : {LOCAL_ROOT}")
    print(f"☁️ GDrive Target: {GDRIVE_ROOT}")
    print("==================================================================")

    if not LOCAL_ROOT.exists():
        print(f"❌ Error: Local source root not found: {LOCAL_ROOT}")
        return
    if not GDRIVE_ROOT.exists():
        print(f"❌ Error: Google Drive root not found: {GDRIVE_ROOT}")
        return

    start_time = time.time()
    total_copied = 0
    total_identical = 0
    total_errors = 0

    for folder in FOLDERS_TO_SYNC:
        c, i, err = sync_folder(folder)
        total_copied += c
        total_identical += i
        total_errors += err

    elapsed = time.time() - start_time
    print("\n==================================================================")
    print(f"🎉 Google Drive Synchronization Completed in {elapsed:.2f}s!")
    print(f"📊 Summary: {total_copied:,} files copied, {total_identical:,} verified identical, {total_errors} errors")
    print("==================================================================")

if __name__ == "__main__":
    main()
