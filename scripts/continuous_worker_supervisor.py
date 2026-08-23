#!/usr/bin/env python3
"""
Continuous Worker Supervisor & Visual Health Auditor (24/7 Zero-Idle)
Features:
  1. 3-Stage Master Pipeline Auto-Dispatcher (Best 100 -> Missing Study -> English Collection)
  2. 24/7 Zero-Idle Account Dispatcher across 4 accounts
  3. Scheduled Visual Health Monitoring & Screen-Capture Engine (Every 3 minutes)
  4. Automatic Hot-Injection Session Self-Healing on Visual Anomalies
"""

import os, sys, time, json, psutil, subprocess, shutil, re
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / ".work" / "continuous_scheduler" / "config.json"
STATE_DIR = BASE_DIR / ".work" / "continuous_scheduler"
LOG_DIR = BASE_DIR / ".work" / "supervisor_logs"
VISUAL_AUDIT_DIR = BASE_DIR / ".work" / "visual_audits"
DESKTOP_LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

LOG_DIR.mkdir(parents=True, exist_ok=True)
VISUAL_AUDIT_DIR.mkdir(parents=True, exist_ok=True)

ACCOUNTS = [
    {
        "id": "main",
        "name": "Gemini 1 (Main)",
        "provider": "gemini",
        "profile_dir": "/Users/hyeokjunkong/Library/Application Support/AudiobookStudio/browser_profiles",
    },
    {
        "id": "account2",
        "name": "Gemini 2 (Account 2)",
        "provider": "gemini",
        "profile_dir": "/Users/hyeokjunkong/Library/Application Support/AudiobookStudio-account2/browser_profiles",
    },
    {
        "id": "account3",
        "name": "Gemini 3 (Account 3)",
        "provider": "gemini",
        "profile_dir": "/Users/hyeokjunkong/Library/Application Support/AudiobookStudio-account3/browser_profiles",
    },
    {
        "id": "chatgpt",
        "name": "ChatGPT 1 (ChatGPT)",
        "provider": "chatgpt",
        "profile_dir": "/Users/hyeokjunkong/Library/Application Support/AudiobookStudio-chatgpt/browser_profiles",
    },
]

def is_account_in_blackout_schedule(account_id: str) -> bool:
    """Checks if an account is restricted by time/day schedule or user disable flag.
    User override: Gemini 1 ('main') allowed during weekdays.
    """
    if account_id == "chatgpt":
        flag_p = Path("/Users/hyeokjunkong/Desktop/myproject_python/haijun93-audiobook-maker/.work/chatgpt_disabled.flag")
        if flag_p.exists():
            return True
    return False

def log(msg: str):
    t = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{t} {msg}"
    print(line, flush=True)
    with open(LOG_DIR / "supervisor.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")

def get_running_workers() -> dict:
    workers = {}
    for p in psutil.process_iter(['pid', 'cmdline', 'status', 'create_time', 'environ']):
        try:
            args = p.info.get('cmdline') or []
            cmd_str = " ".join(args)
            if "translate_epub_with_chatgpt_web_to_study_epub.py" in cmd_str:
                env_prof = (p.info.get('environ') or {}).get("AUDIOBOOK_WEB_PROFILE_DIR", "")
                acc = "main"
                if "account2" in env_prof or "AudiobookStudio-account2" in cmd_str:
                    acc = "account2"
                elif "account3" in env_prof or "AudiobookStudio-account3" in cmd_str:
                    acc = "account3"
                elif "chatgpt" in env_prof or "AudiobookStudio-chatgpt" in cmd_str:
                    acc = "chatgpt"
                
                book = "Unknown"
                work_dir = ""
                for i, a in enumerate(args):
                    if a == "--book-title-ko" and i + 1 < len(args):
                        book = args[i + 1]
                    elif a == "--work-dir" and i + 1 < len(args):
                        work_dir = args[i + 1]
                    elif a == "--input-epub" and i + 1 < len(args) and book == "Unknown":
                        book = Path(args[i + 1]).name
                        
                workers[acc] = {
                    "pid": p.info['pid'],
                    "book": book,
                    "work_dir": work_dir,
                    "status": p.info['status'],
                    "create_time": p.info['create_time']
                }
        except:
            pass
    return workers

_CONFIG_CACHE = None
_CONFIG_MTIME = 0.0
_COMPLETED_TASK_IDS = set()
_LIBRARY_KEYS_CACHE = set()
_LIBRARY_CACHE_TIME = 0.0

def get_library_completed_keys() -> set:
    global _LIBRARY_KEYS_CACHE, _LIBRARY_CACHE_TIME
    now = time.time()
    if not _LIBRARY_KEYS_CACHE or (now - _LIBRARY_CACHE_TIME > 60.0):
        keys = set()
        for edition in ["[study]", "[k-e]"]:
            ed_dir = DESKTOP_LIB_ROOT / edition
            if not ed_dir.exists():
                continue
            for f in ed_dir.glob("**/*.epub"):
                f_clean = re.sub(r'\[.*?\]', '', f.stem).strip().lower()
                f_key = re.sub(r'[^a-zA-Z0-9가-힣]', '', f_clean)
                if len(f_key) >= 3:
                    keys.add(f_key)
        _LIBRARY_KEYS_CACHE = keys
        _LIBRARY_CACHE_TIME = now
    return _LIBRARY_KEYS_CACHE

def is_book_already_completed_in_library(book_title: str, is_retranslate_task: bool = False) -> bool:
    """Fast in-memory check if a book already exists in [study] or [k-e].
    If is_retranslate_task is True, it allows re-translating existing low-quality study books.
    """
    if is_retranslate_task:
        return False
    clean = re.sub(r'\[.*?\]', '', book_title).strip().lower()
    clean_key = re.sub(r'[^a-zA-Z0-9가-힣]', '', clean)
    if len(clean_key) < 3:
        return False
        
    lib_keys = get_library_completed_keys()
    if clean_key in lib_keys:
        return True
    for lk in lib_keys:
        if (len(clean_key) >= 6 and clean_key in lk) or (len(lk) >= 6 and lk in clean_key):
            return True
    return False

KOREAN_ORIGINAL_EXCLUSIONS = {
    "pak kyongni", "pak_kyongni", "kyongni", "박경리", "토지", "shin young - bok", "shin_young_bok", "shin young-bok", "신영복", "강의", "lectures shin young"
}

DARK_ROMANCE_EXCLUSIONS = {
    "dark_romance", "dark romance", "leigh rivers", "pam godwin", "top 10 dark romance",
    "h.d. carlton", "h d carlton", "haunting adeline", "hunting adeline",
    "penelope douglas", "corrupt", "rina kent", "god of malice",
    "l.j. shen", "lj shen", "vicious", "neva altaj", "painted scars",
    "pepper winters", "tears of tess", "keri lake", "nocticadia",
    "danielle lori", "sweetest oblivion", "maddest obsession",
    "cora reilly", "bound by honor", "c.j. roberts", "captive in the dark",
    "harleigh beck", "chokehold", "satanic shadows", "psychotic obsession",
    "little stranger", "little liar", "voracious", "insatiable", "restitution"
}

ROBOT_SERIES_EXCLUSIONS = {
    "robot", "caves of steel", "naked sun", "positronic", "새벽의 로봇",
    "robots of dawn", "robots and empire", "i, robot", "i robot", "complete robot",
    "rest of the robots", "robot dreams", "robot visions"
}

NON_ENGLISH_KEYWORDS = {
    "german edition", "french edition", "czech edition", "turkish edition",
    "italian edition", "indonesian edition", "spanish edition", "russian edition",
    "portuguese edition", "polish edition", "dutch edition", "swedish edition",
    "japanese edition", "chinese edition", "deutsche ausgabe", "edition francaise",
    "edicion en espanol", "edizione italiana", "tome 1", "tome 2", "tome 3",
    "fenixuv rad", "princ dvoji krve", "ve zumruduanka", "sepuluh anak negro",
    "die hyperion gesange", "kameni mudrcu", "tajemna komnata", "vezen z azkabanu",
    "ohnivy pohar", "relikvie smrti"
}

def is_korean_original_work(text: str) -> bool:
    t_lower = text.lower()
    return any(k in t_lower for k in KOREAN_ORIGINAL_EXCLUSIONS)

def is_dark_romance_work(text: str) -> bool:
    t_lower = text.lower()
    return any(k in t_lower for k in DARK_ROMANCE_EXCLUSIONS)

def is_non_english_work(text: str) -> bool:
    t_lower = text.lower()
    if "non-english" in t_lower:
        return True
    return any(kw in t_lower for kw in NON_ENGLISH_KEYWORDS)

def is_robot_series_work(text: str) -> bool:
    t_lower = text.lower()
    if "asimov" in t_lower and any(r in t_lower for r in ["robot", "caves of steel", "naked sun", "positronic", "새벽의 로봇"]):
        return True
    return any(r in t_lower for r in ["i, robot", "i robot", "the complete robot", "the rest of the robots", "robot dreams", "robot visions", "the robots of dawn", "caves of steel", "naked sun", "robot series"])

_COMPLETED_TASK_IDS = set()
_QUARANTINED_TASK_IDS = set()
_FAILED_DISPATCH_COUNTS = defaultdict(int)
_CONFIG_LOAD_TIME = 0.0

def validate_and_heal_task_fields(t: dict) -> dict:
    """Ensures all essential fields exist with canonical paths before dispatch."""
    tid = t.get("id", "task")
    tid_clean = re.sub(r'[^a-zA-Z0-9_]', '', tid)
    
    if not t.get("work_dir"):
        t["work_dir"] = str(DESKTOP_LIB_ROOT / f"_translation_work_{tid_clean}")
        
    in_epub = t.get("input_epub", "")
    fname = Path(in_epub).name if in_epub else f"{tid}.epub"
    
    if not t.get("output_epub"):
        t["output_epub"] = str(DESKTOP_LIB_ROOT / "[k-e]" / "Literary_General_Fiction" / f"[k-e] {fname}")
        
    if not t.get("study_output_epub"):
        t["study_output_epub"] = str(DESKTOP_LIB_ROOT / "[study]" / "Literary_General_Fiction" / f"[study] {fname}")
        
    if not t.get("book_title_ko"):
        t["book_title_ko"] = t.get("title", fname.replace(".epub", ""))
        
    return t

def get_next_available_task(active_task_ids: set, active_titles: set = None, provider: str = None) -> dict | None:
    global _CONFIG_CACHE, _CONFIG_MTIME, _COMPLETED_TASK_IDS, _QUARANTINED_TASK_IDS, _CONFIG_LOAD_TIME
    if not CONFIG_PATH.exists():
        return None
    try:
        now = time.time()
        if _CONFIG_CACHE is None or (now - _CONFIG_LOAD_TIME > 60):
            cfg = json.loads(CONFIG_PATH.read_text())
            tasks = cfg.get("tasks", [])
            _CONFIG_CACHE = sorted(tasks, key=lambda t: t.get("priority", 0), reverse=True)
            _CONFIG_LOAD_TIME = now

        for t in _CONFIG_CACHE:
            tid = t.get("id")
            if tid in _QUARANTINED_TASK_IDS:
                continue
                
            validate_and_heal_task_fields(t)
            title = t.get("book_title_ko") or t.get("title") or ""
            clean_title = title.split(" (")[0].strip().lower()
            clean_key = re.sub(r'[^a-zA-Z0-9가-힣]', '', clean_title)
            
            if is_korean_original_work(title) or is_korean_original_work(t.get("input_epub", "")):
                _COMPLETED_TASK_IDS.add(tid)
                continue

            # Non-English Source Exclusion Guard: Skip translation of non-English editions
            if is_non_english_work(title) or is_non_english_work(t.get("input_epub", "")) or is_non_english_work(t.get("output_epub", "")):
                _COMPLETED_TASK_IDS.add(tid)
                continue

            # Robot Series Exclusion Guard
            if is_robot_series_work(title) or is_robot_series_work(t.get("input_epub", "")):
                _COMPLETED_TASK_IDS.add(tid)
                continue

            # ChatGPT Exclusion Principle: Strictly exclude Dark Romance works for ChatGPT
            if provider == "chatgpt":
                check_str = f"{title} {t.get('input_epub', '')} {t.get('work_dir', '')} {t.get('stage_name', '')}"
                if is_dark_romance_work(check_str):
                    continue

            if tid in active_task_ids or tid in _COMPLETED_TASK_IDS:
                continue
                
            # Check active running collision with fuzzy matching
            collision = False
            for at in active_titles:
                at_key = re.sub(r'[^a-zA-Z0-9가-힣]', '', at.lower())
                if clean_key and at_key and (clean_key in at_key or at_key in clean_key):
                    collision = True
                    break
            if collision:
                continue
                
            # Check if output files and all chunks are already completely produced for this task
            study_out = Path(t.get("study_output_epub", ""))
            w_dir = Path(t.get("work_dir", ""))
            if study_out.exists() and w_dir.exists():
                manifest_f = w_dir / "manifest.json"
                trans_dir = w_dir / "translations"
                if manifest_f.exists() and trans_dir.exists():
                    try:
                        m = json.loads(manifest_f.read_text())
                        c_cnt = m.get("chunk_count", 0)
                        d_cnt = len(list(trans_dir.glob("chunk_*.json")))
                        if c_cnt > 0 and d_cnt >= c_cnt:
                            _COMPLETED_TASK_IDS.add(tid)
                            continue
                    except:
                        pass

            # Check if already completed in library
            is_retrans = bool(t.get("stage") == 0 or t.get("force_retranslate") or t.get("stage") == 2 or "retrans_" in tid or "freida_" in tid)
            if is_book_already_completed_in_library(title, is_retranslate_task=is_retrans):
                _COMPLETED_TASK_IDS.add(tid)
                continue
                
            # Check input_epub file existence on disk
            in_epub = Path(t.get("input_epub", ""))
            if not in_epub.exists() or in_epub.stat().st_size == 0:
                _COMPLETED_TASK_IDS.add(tid)
                continue

            # Check work dir lock
            lock_f = w_dir / ".translation_in_progress.lock"
            if lock_f.exists():
                continue
                
            return t
    except Exception as e:
        log(f"Error reading config: {e}")
    return None

def dispatch_task_to_account(account: dict, task: dict):
    acc_id = account["id"]
    log(f"🚀 [AUTO-DISPATCH] [{account['name']}] -> '{task.get('book_title_ko')}' (Stage {task.get('stage')}, Priority {task.get('priority')})")
    
    # Clear lock
    profile_p = Path(account["profile_dir"]) / ("gemini" if account["provider"] == "gemini" else "chatgpt")
    lock_f = profile_p / ".audiobook_web_profile.lock"
    if lock_f.exists():
        try:
            lock_f.unlink()
        except:
            pass
            
    env = os.environ.copy()
    env["AUDIOBOOK_WEB_PROFILE_DIR"] = account["profile_dir"]
    
    w_dir_str = task.get("work_dir")
    if not w_dir_str:
        tid_clean = re.sub(r'[^a-zA-Z0-9_]', '', task.get("id", "task"))
        w_dir_str = str(DESKTOP_LIB_ROOT / f"_translation_work_{tid_clean}")
        task["work_dir"] = w_dir_str
    work_dir = Path(w_dir_str)
    work_dir.mkdir(parents=True, exist_ok=True)
    heartbeat_file = work_dir / "heartbeat.json"
    
    cmd = [
        sys.executable,
        str(BASE_DIR / "scripts" / "translate_epub_with_chatgpt_web_to_study_epub.py"),
        "--input-epub", task["input_epub"],
        "--output-epub", task["output_epub"],
        "--study-output-epub", task["study_output_epub"],
        "--work-dir", task["work_dir"],
        "--book-title-ko", task["book_title_ko"],
        "--max-chars-per-chunk", str(task.get("max_chars_per_chunk", 6000)),
        "--request-timeout-sec", str(task.get("request_timeout_sec", 1200)),
        "--web-max-attempts", str(task.get("web_max_attempts", 3)),
        "--chunks-per-conversation", str(task.get("chunks_per_conversation", 10 if account["provider"] == "gemini" else 8)),
        "--inter-request-delay-sec", str(task.get("inter_request_delay_sec", 8.0 if account["provider"] == "gemini" else 12.0)),
        "--heartbeat-file", str(heartbeat_file),
        "--web-provider", account["provider"],
    ]
    if task.get("force_retranslate") or task.get("stage") == 0:
        cmd.append("--force-retranslate")
    
    out_log = open(LOG_DIR / f"worker_{acc_id}.stdout.log", "a")
    err_log = open(LOG_DIR / f"worker_{acc_id}.stderr.log", "a")
    
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=out_log,
        stderr=err_log,
        start_new_session=True,
    )
    log(f"   -> Successfully launched PID {proc.pid} on [{account['name']}]!")
    task["status"] = "running"
    task["account_id"] = acc_id

_PREVIOUS_WORKER_PROGRESS = {}

def perform_visual_health_audit(active_workers: dict):
    """Performs scheduled visual health checks and saves status metadata every 3 minutes.
    Automatically detects and kills frozen/hung workers that showed zero progress over the audit interval.
    """
    global _PREVIOUS_WORKER_PROGRESS
    audit_time = time.strftime("%Y-%m-%d %H:%M:%S")
    now_ts = time.time()
    log(f"📸 [VISUAL HEALTH AUDIT] Performing scheduled visual check across 4 accounts...")
    
    audit_report = {
        "timestamp": audit_time,
        "accounts": {}
    }
    
    for acc in ACCOUNTS:
        acc_id = acc["id"]
        worker_info = active_workers.get(acc_id)
        
        hb_data = {}
        hb_time = 0.0
        chunks_done = 0
        w_dir_p = None
        
        if worker_info and worker_info.get("work_dir"):
            w_dir_p = Path(worker_info["work_dir"])
            hb_file = w_dir_p / "heartbeat.json"
            if hb_file.exists():
                try:
                    hb_data = json.loads(hb_file.read_text())
                    hb_time = float(hb_data.get("timestamp", 0))
                except:
                    pass
            trans_dir = w_dir_p / "translations"
            if trans_dir.exists():
                chunks_done = len(list(trans_dir.glob("*.json")))
                    
        stage = hb_data.get("stage", "idle" if not worker_info else "running")
        label = hb_data.get("label", "-" if not worker_info else "진행 중")
        detail = hb_data.get("detail", "")
        
        # 🚨 PROGRESS STALL DETECTION & SELF-HEALING
        # If worker is active, check if it made ANY progress since last visual audit (3 mins)
        if worker_info and w_dir_p:
            prev_info = _PREVIOUS_WORKER_PROGRESS.get(acc_id)
            if prev_info and prev_info.get("pid") == worker_info.get("pid"):
                prev_chunks = prev_info.get("chunks", 0)
                prev_hb_time = prev_info.get("hb_time", 0.0)
                
                # If chunk count hasn't moved AND heartbeat timestamp hasn't updated for > 180s (3 mins)
                if chunks_done == prev_chunks and (now_ts - hb_time > 180) and (hb_time == prev_hb_time or now_ts - prev_hb_time > 180):
                    w_pid = worker_info.get("pid")
                    log(f"🚨 [VISUAL AUDIT ANOMALY] [{acc['name']}] (PID {w_pid}) has been FROZEN with zero progress for {int(now_ts - hb_time)}s! Auto-terminating to self-heal...")
                    try:
                        psutil.Process(w_pid).kill()
                    except:
                        pass
                        
            # Record current progress for next audit comparison
            _PREVIOUS_WORKER_PROGRESS[acc_id] = {
                "pid": worker_info.get("pid"),
                "chunks": chunks_done,
                "hb_time": hb_time,
                "checked_at": now_ts
            }
        else:
            _PREVIOUS_WORKER_PROGRESS.pop(acc_id, None)
        
        # Self-healing check: detect session expiration or rate limit in heartbeat
        if "session_expired" in str(detail) or "login_required" in str(detail):
            log(f"⚠️ [SESSION ANOMALY] Detected session expiration on [{acc['name']}]. Triggering auto-recovery...")
            profile_p = Path(acc["profile_dir"]) / ("gemini" if acc["provider"] == "gemini" else "chatgpt")
            lock_f = profile_p / ".audiobook_web_profile.lock"
            if lock_f.exists():
                try: lock_f.unlink()
                except: pass
                
        # Screenshot capture & synchronization
        screenshot_path = None
        if w_dir_p:
            worker_ss = w_dir_p / "latest_screenshot.png"
            if worker_ss.exists():
                try:
                    dest_ss_dir = BASE_DIR / ".work" / "continuous_scheduler" / "screenshots"
                    dest_ss_dir.mkdir(parents=True, exist_ok=True)
                    dest_ss = dest_ss_dir / f"{acc_id}_latest.png"
                    shutil.copy2(worker_ss, dest_ss)
                    
                    webui_ss_dir = BASE_DIR / "webui" / "static" / "screenshots"
                    webui_ss_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(worker_ss, webui_ss_dir / f"{acc_id}_latest.png")
                    screenshot_path = str(dest_ss)
                    log(f"   📸 [{acc['name']}] Live screenshot synchronized ({worker_ss.stat().st_size} bytes)")
                except Exception as ss_err:
                    pass
                    
        audit_report["accounts"][acc_id] = {
            "name": acc["name"],
            "provider": acc["provider"],
            "pid": worker_info["pid"] if worker_info else None,
            "book": worker_info["book"] if worker_info else None,
            "stage": stage,
            "label": label,
            "detail": detail,
            "chunks_done": chunks_done,
            "screenshot": screenshot_path,
            "status": "active" if worker_info else "idle"
        }
        
    # Write latest visual audit status for Web UI & Monitoring Dashboard
    status_file = VISUAL_AUDIT_DIR / "latest_visual_status.json"
    status_file.write_text(json.dumps(audit_report, indent=2, ensure_ascii=False))
    log("   -> Visual Health Audit completed & status synchronized.")

def supervise_loop():
    log("==================================================================")
    log("🌟 Starting Continuous Worker Supervisor with Visual Health Auditor")
    log("==================================================================")
    
    last_visual_audit_time = 0
    VISUAL_AUDIT_INTERVAL_SEC = 180  # Visual Audit every 3 minutes
    
    while True:
        try:
            active_workers = get_running_workers()
            active_task_ids = set()
            active_titles = set()
            for w in active_workers.values():
                b = w.get("book", "")
                if b and b != "Unknown":
                    clean = b.split(" (")[0].strip().lower()
                    active_titles.add(clean)
            
            # 1. Zero-Idle Auto-Dispatcher Check (Every 20 seconds)
            for acc in ACCOUNTS:
                acc_id = acc["id"]
                
                # Check Weekday 09:00-17:00 Blackout Schedule
                if is_account_in_blackout_schedule(acc_id):
                    if acc_id in active_workers:
                        w_info = active_workers[acc_id]
                        w_pid = w_info.get("pid")
                        log(f"⏳ [SCHEDULE PAUSE] {acc['name']} is in Weekday Blackout (09:00-17:00). Pausing active worker PID {w_pid}...")
                        try:
                            psutil.Process(w_pid).terminate()
                        except:
                            pass
                    continue

                if acc_id not in active_workers:
                    log(f"⚡ [IDLE DETECTED] {acc['name']} is idle! Searching 3-Stage queue (provider={acc.get('provider')})...")
                    task = get_next_available_task(active_task_ids, active_titles, provider=acc.get("provider"))
                    if task:
                        tid = task.get("id")
                        try:
                            dispatch_task_to_account(acc, task)
                            active_task_ids.add(tid)
                            t_title = (task.get("book_title_ko") or task.get("title") or "").split(" (")[0].strip().lower()
                            if t_title:
                                active_titles.add(t_title)
                            time.sleep(4) # Stagger browser launches
                        except Exception as d_err:
                            log(f"❌ [DISPATCH ERROR] Failed to dispatch task '{tid}': {d_err}")
                            _FAILED_DISPATCH_COUNTS[tid] += 1
                            if _FAILED_DISPATCH_COUNTS[tid] >= 3:
                                log(f"⚠️ [AUTO-QUARANTINE] Task '{tid}' failed 3 consecutive dispatches. Quarantining to prevent worker deadlock!")
                                _QUARANTINED_TASK_IDS.add(tid)
                        active_workers = get_running_workers()
                        
            # 2. Stalled Worker Hang-Detector & Auto-Healer (Heartbeat Watchdog)
            for acc_id, w_info in active_workers.items():
                work_dir_p = Path(w_info.get("work_dir", ""))
                if work_dir_p.exists():
                    hb_f = work_dir_p / "heartbeat.json"
                    if hb_f.exists():
                        try:
                            hb_data = json.loads(hb_f.read_text())
                            hb_time = float(hb_data.get("timestamp", 0))
                            if hb_time > 0 and (time.time() - hb_time > 300):  # 5 minutes without heartbeat
                                w_pid = w_info.get("pid")
                                log(f"🚨 [STALL DETECTED] Account '{acc_id}' (PID {w_pid}) has been unresponsive for {int(time.time() - hb_time)}s! Auto-terminating to heal session...")
                                try:
                                    psutil.Process(w_pid).kill()
                                except:
                                    pass
                        except Exception:
                            pass

            # 3. Scheduled Visual Health Audit (Every 3 minutes)
            now = time.time()
            if now - last_visual_audit_time >= VISUAL_AUDIT_INTERVAL_SEC:
                perform_visual_health_audit(active_workers)
                last_visual_audit_time = now
                
        except Exception as e:
            log(f"Supervisor error: {e}")
            
        time.sleep(20)

if __name__ == "__main__":
    supervise_loop()
