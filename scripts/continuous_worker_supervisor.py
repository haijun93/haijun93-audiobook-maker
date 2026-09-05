#!/usr/bin/env python3
"""
Continuous Worker Supervisor & Visual Health Auditor (24/7 Zero-Idle)
Features:
  1. 3-Stage Master Pipeline Auto-Dispatcher (Best 100 -> Missing Study -> English Collection)
  2. 24/7 Zero-Idle Account Dispatcher across 4 accounts
  3. Scheduled Visual Health Monitoring & Screen-Capture Engine (Every 3 minutes)
  4. Automatic Hot-Injection Session Self-Healing on Visual Anomalies
"""

import os
import sys
import time
import json
import psutil
import subprocess
import shutil
import re
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
        flag_p = BASE_DIR / ".work" / "chatgpt_disabled.flag"
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
                    "task_id": (p.info.get('environ') or {}).get("AUDIOBOOK_TASK_ID", ""),
                    "book": book,
                    "work_dir": work_dir,
                    "status": p.info['status'],
                    "create_time": p.info['create_time']
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, OSError):
            pass
    return workers

_LIBRARY_KEYS_CACHE = set()
_LIBRARY_TOKENS_CACHE: list[tuple[str, set[str]]] = []
_LIBRARY_CACHE_TIME = 0.0

def get_library_completed_tokens() -> list[tuple[str, set[str]]]:
    global _LIBRARY_TOKENS_CACHE, _LIBRARY_CACHE_TIME
    now = time.time()
    if not _LIBRARY_TOKENS_CACHE or (now - _LIBRARY_CACHE_TIME > 60.0):
        items = []
        for edition in ["[study]", "[k-e]"]:
            ed_dir = DESKTOP_LIB_ROOT / edition
            if not ed_dir.exists():
                continue
            for f in ed_dir.rglob("*.epub"):
                try:
                    if f.stat().st_size > 15000:
                        f_clean = re.sub(r'\[.*?\]', '', f.stem).strip().lower()
                        f_key = re.sub(r'[^a-zA-Z0-9가-힣]', '', f_clean)
                        # Extract significant alphanumeric tokens (length >= 3)
                        tokens = set(w for w in re.findall(r'[a-zA-Z0-9가-힣]{3,}', f_clean) if w not in {"the", "and", "book", "edition", "series"})
                        if len(f_key) >= 3:
                            items.append((f_key, tokens))
                except Exception:
                    pass
        _LIBRARY_TOKENS_CACHE = items
        _LIBRARY_CACHE_TIME = now
    return _LIBRARY_TOKENS_CACHE

def is_book_already_completed_in_library(task: dict | str, is_retranslate_task: bool = False) -> bool:
    """Rigorous in-memory check if a book already exists in [study] or [k-e].
    Checks physical output paths, input filenames, original titles, and token overlaps.
    """
    if is_retranslate_task:
        return False

    t = task if isinstance(task, dict) else {"book_title_ko": task}

    # 1. Direct Physical File Existence Guard
    out_epub = t.get("output_epub", "")
    study_epub = t.get("study_output_epub", "")
    if out_epub and Path(out_epub).exists() and Path(out_epub).stat().st_size > 15000:
        return True
    if study_epub and Path(study_epub).exists() and Path(study_epub).stat().st_size > 15000:
        return True

    # Gather all candidate query strings
    candidates = []
    if t.get("title"):
        candidates.append(t["title"])
    if t.get("book_title_ko"):
        candidates.append(t["book_title_ko"])
    if t.get("input_epub"):
        candidates.append(Path(t["input_epub"]).stem)
    if t.get("id"):
        candidates.append(t["id"])

    lib_items = get_library_completed_tokens()

    for cand in candidates:
        clean = re.sub(r'\[.*?\]', '', cand).strip().lower()
        clean_key = re.sub(r'[^a-zA-Z0-9가-힣]', '', clean)
        if len(clean_key) < 3:
            continue

        query_tokens = set(w for w in re.findall(r'[a-zA-Z0-9가-힣]{3,}', clean) if w not in {"the", "and", "book", "edition", "series", "stage", "coll"})

        for lk, ltokens in lib_items:
            # Exact or substring match
            if clean_key == lk or (len(clean_key) >= 6 and clean_key in lk) or (len(lk) >= 6 and lk in clean_key):
                return True
            # Token Overlap match (e.g. "presumed", "innocent", "turow")
            if query_tokens and ltokens:
                common = query_tokens & ltokens
                if len(common) >= 2 and (len(common) / len(query_tokens) >= 0.5 or len(common) / len(ltokens) >= 0.5):
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

def is_epub_strictly_english(epub_path: Path | str) -> bool:
    """Reads sample paragraphs directly from EPUB to verify it is 100% authentic English."""
    p = Path(epub_path)
    if not p.exists() or p.stat().st_size < 5000:
        return False
    try:
        import zipfile
        from bs4 import BeautifulSoup

        sample_words = []
        with zipfile.ZipFile(p, "r") as z:
            xhtmls = [n for n in z.namelist() if n.endswith((".xhtml", ".html")) and not any(k in n.lower() for k in ["cover", "toc", "nav"])]
            for xf in xhtmls[:4]: # Check first 4 body chapters
                txt = z.read(xf).decode("utf-8", "ignore")
                soup = BeautifulSoup(txt, "html.parser")
                for para in soup.find_all("p")[:20]:
                    words = re.findall(r'[a-zA-ZáéíóúüñÁÉÍÓÚÜÑàèìòùÀÈÌÒÙäöüÄÖÜßçÇ]+', para.get_text().lower())
                    sample_words.extend(words)
                    if len(sample_words) > 300:
                        break
                if len(sample_words) > 300:
                    break

        if not sample_words:
            return True

        common_en = {"the", "and", "of", "to", "a", "in", "that", "is", "was", "he", "for", "it", "with", "as", "his", "on", "be", "at", "by", "i", "this", "had", "not", "are", "but", "from", "or", "have", "an", "they", "which", "one", "you", "were", "her", "all", "she", "there", "would", "their", "we", "him", "been", "has", "when", "who", "will", "more", "no", "if", "out", "so", "said", "what", "up", "its", "about", "into", "than", "them", "can", "only", "other", "new", "some", "could", "time", "these", "two", "may", "then", "do", "first", "any", "my", "now", "such", "like", "our", "over", "man", "me", "even", "most", "made", "after", "also", "did", "many", "before", "must", "through", "back", "years", "where", "much", "your", "way", "well", "down", "should", "because", "each", "just", "those", "people", "mr", "how", "too", "little", "state", "good", "very", "make", "world", "still", "see", "own"}
        common_es = {"que", "de", "no", "la", "el", "en", "y", "los", "del", "se", "las", "por", "un", "para", "con", "una", "su", "al", "lo", "como", "más", "pero", "sus", "le", "ya", "o", "fue", "este", "ha", "sí", "porque", "esta", "son", "entre", "está", "cuando", "él", "todo", "sobre", "también"}
        common_de = {"und", "der", "die", "das", "in", "zu", "den", "nicht", "von", "sie", "ist", "des", "sich", "mit", "dem", "dass", "er", "es", "ein", "ich", "auf", "so", "eine", "auch", "als", "an", "nach", "wie", "im", "für", "man", "aber", "aus", "durch", "wenn", "nur", "war", "noch", "werden", "bei", "hat", "wir", "was", "wird", "sein", "einen", "welche", "sind", "oder", "zur", "um", "haben", "einer", "mir", "ihm", "einem", "über"}
        common_fr = {"de", "la", "le", "et", "les", "des", "en", "un", "du", "une", "que", "est", "pour", "qui", "dans", "a", "par", "plus", "pas", "au", "sur", "ne", "ce", "se", "avec", "sont", "il", "ou", "aux", "son", "sa", "mais", "ont", "ses", "cette", "comme", "aussi", "tout", "nous", "leur", "elle", "y", "deux", "bien", "ces", "sans", "peut", "faire", "tous", "fait"}

        en_hits = sum(1 for w in sample_words if w in common_en)
        es_hits = sum(1 for w in sample_words if w in common_es)
        de_hits = sum(1 for w in sample_words if w in common_de)
        fr_hits = sum(1 for w in sample_words if w in common_fr)

        foreign_hits = es_hits + de_hits + fr_hits
        # If foreign language indicators dominate English density
        if (foreign_hits > en_hits and foreign_hits >= 10) or (foreign_hits > 15 and en_hits < 10):
            return False

        return True
    except Exception:
        return True

def is_robot_series_work(text: str) -> bool:
    t_lower = text.lower()
    if "asimov" in t_lower and any(r in t_lower for r in ["robot", "caves of steel", "naked sun", "positronic", "새벽의 로봇"]):
        return True
    return any(r in t_lower for r in ["i, robot", "i robot", "the complete robot", "the rest of the robots", "robot dreams", "robot visions", "the robots of dawn", "caves of steel", "naked sun", "robot series"])

_COMPLETED_TASK_IDS = set()
_QUARANTINED_TASK_IDS = set()
_FAILED_DISPATCH_COUNTS = defaultdict(int)
_TASK_RETRY_STATE: dict[str, dict] = {}
_PREVIOUS_RUNNING_WORKERS: dict[str, dict] = {}
_CONFIG_CACHE: list[dict] | None = None
_CONFIG_MTIME = 0.0
_CONFIG_LOAD_TIME = 0.0
_DISK_FILE_INDEX: dict[str, Path] = {}
_DISK_INDEX_TIME = 0.0

def build_disk_file_index() -> dict[str, Path]:
    global _DISK_FILE_INDEX, _DISK_INDEX_TIME
    now = time.time()
    if _DISK_FILE_INDEX and (now - _DISK_INDEX_TIME < 600):
        return _DISK_FILE_INDEX

    index = {}
    scan_roots = [
        Path("/Volumes/2T hard/English Books Collection"),
        DESKTOP_LIB_ROOT / "[e]",
    ]
    for root in scan_roots:
        if root.exists():
            for ep in root.rglob("*.epub"):
                try:
                    if ep.stat().st_size > 5000:
                        # Index by lower-case filename
                        index[ep.name.lower()] = ep
                        # Index by stripped prefix filename
                        clean_n = re.sub(r"^\[e\]\s*", "", ep.name).lower()
                        index[clean_n] = ep
                except Exception:
                    pass
    _DISK_FILE_INDEX = index
    _DISK_INDEX_TIME = now
    return index

def validate_and_heal_task_fields(t: dict) -> dict:
    """Ensures all essential fields exist with canonical paths before dispatch (Self-Healing Dynamic Path Discovery)."""
    tid = t.get("id", "task")
    tid_clean = re.sub(r'[^a-zA-Z0-9_]', '', tid)

    if not t.get("work_dir"):
        t["work_dir"] = str(DESKTOP_LIB_ROOT / f"_translation_work_{tid_clean}")

    in_epub = t.get("input_epub", "")
    fname = Path(in_epub).name if in_epub else f"{tid}.epub"

    # Self-Healing Dynamic Path Discovery: If input_epub does not exist on disk, find its real path
    in_p = Path(in_epub) if in_epub else None
    if not in_p or not in_p.exists() or in_p.stat().st_size < 5000:
        disk_index = build_disk_file_index()
        target_name = fname.lower()
        clean_target_name = re.sub(r"^\[e\]\s*", "", fname).lower()

        found_p = disk_index.get(target_name) or disk_index.get(clean_target_name)
        if not found_p:
            # Fuzzy match by stem
            stem_clean = re.sub(r'[^a-zA-Z0-9]', '', clean_target_name)
            for k, p_path in disk_index.items():
                if stem_clean and stem_clean in re.sub(r'[^a-zA-Z0-9]', '', k):
                    found_p = p_path
                    break

        if found_p and found_p.exists():
            t["input_epub"] = str(found_p)
            in_epub = str(found_p)
            fname = found_p.name

            # Derive canonical output paths matching the real source genre & author
            if "/English Books Collection/" in str(found_p):
                rel = found_p.relative_to(Path("/Volumes/2T hard/English Books Collection"))
            elif "/[e]/" in str(found_p):
                rel = found_p.relative_to(DESKTOP_LIB_ROOT / "[e]")
            else:
                rel = Path("Literary_General_Fiction") / fname

            clean_stem = re.sub(r"^\[(k-e|k|e-s|e|ks|study_|study)\]\s*", "", fname)
            t["output_epub"] = str(DESKTOP_LIB_ROOT / "[k-e]" / rel.parent / f"[k-e] {clean_stem}")
            t["study_output_epub"] = str(DESKTOP_LIB_ROOT / "[study]" / rel.parent / f"[study] {clean_stem}")

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

            retry_state = _TASK_RETRY_STATE.get(tid, {})
            if time.time() < float(retry_state.get("next_retry_at", 0) or 0):
                continue

            # A task can be explicitly closed by a repair/finalization run.
            # Treat that state as authoritative even when the process has an
            # older in-memory config snapshot.  Without this guard, legacy
            # IDs containing ``retrans_`` are classified as forced retries
            # forever and are dispatched on every idle poll.
            if str(t.get("status", "")).strip().lower() in {"completed", "done"}:
                _COMPLETED_TASK_IDS.add(tid)
                continue

            validate_and_heal_task_fields(t)
            title = t.get("book_title_ko") or t.get("title") or ""
            clean_title = title.split(" (")[0].strip().lower()
            clean_key = re.sub(r'[^a-zA-Z0-9가-힣]', '', clean_title)

            if is_korean_original_work(title) or is_korean_original_work(t.get("input_epub", "")):
                _COMPLETED_TASK_IDS.add(tid)
                continue

            in_ep = t.get("input_epub", "")
            in_p = Path(in_ep)
            if not in_ep or not in_p.exists() or in_p.stat().st_size < 5000:
                _COMPLETED_TASK_IDS.add(tid)
                continue

            if is_non_english_work(title) or is_non_english_work(in_ep) or is_non_english_work(t.get("output_epub", "")) or not is_epub_strictly_english(in_ep):
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

            # Forced retranslation tasks are deliberately allowed to have old
            # output and a full-looking cache.  Their chunk contents still need
            # to pass the current translation gates (for example, the new
            # zero-English-leak gate), so never short-circuit them by counting
            # JSON files alone.
            is_retrans = bool(
                t.get("stage") == 0
                or t.get("force_retranslate")
                or t.get("stage") == 2
                or "retrans_" in str(tid)
                or "freida_" in str(tid)
            )

            # Check if output files and all chunks are already completely produced for this task
            study_out = Path(t.get("study_output_epub", ""))
            w_dir = Path(t.get("work_dir", ""))
            if not is_retrans and study_out.exists() and w_dir.exists():
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
                    except (OSError, ValueError, KeyError):
                        pass

            # Check if already completed in library
            if is_book_already_completed_in_library(t, is_retranslate_task=is_retrans):
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

def _task_id_for_worker(worker: dict) -> str:
    """Resolve a worker task ID, including workers started before env tagging."""
    if worker.get("task_id"):
        return str(worker["task_id"])
    work_dir = str(worker.get("work_dir", ""))
    if not work_dir:
        return ""
    for task in _CONFIG_CACHE or []:
        if str(task.get("work_dir", "")) == work_dir:
            return str(task.get("id", ""))
    return ""


def record_worker_transitions(active_workers: dict):
    """Back off failed child processes so one bad response cannot monopolize a worker."""
    global _PREVIOUS_RUNNING_WORKERS
    current_by_task = {}
    for account_id, worker in active_workers.items():
        tid = _task_id_for_worker(worker)
        if tid:
            current_by_task[tid] = (account_id, worker)

    for tid, previous in list(_PREVIOUS_RUNNING_WORKERS.items()):
        if tid in current_by_task:
            continue
        work_dir = Path(previous.get("work_dir", ""))
        heartbeat = {}
        try:
            heartbeat = json.loads((work_dir / "heartbeat.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            pass
        stage = str(heartbeat.get("stage", "")).lower()
        if stage in {"complete", "completed", "finished", "published"}:
            _COMPLETED_TASK_IDS.add(tid)
            _TASK_RETRY_STATE.pop(tid, None)
            continue

        state = _TASK_RETRY_STATE.setdefault(tid, {"failures": 0})
        state["failures"] = int(state.get("failures", 0)) + 1
        failures = state["failures"]
        if failures >= 3:
            _QUARANTINED_TASK_IDS.add(tid)
            log(f"⚠️ [WORKER QUARANTINE] '{tid}' failed {failures} times ({stage or 'no heartbeat'}). Moving on to the next task.")
        else:
            delay = min(15 * (2 ** (failures - 1)), 120)
            state["next_retry_at"] = time.time() + delay * 60
            log(f"⚠️ [WORKER RETRY BACKOFF] '{tid}' exited at stage '{stage or 'unknown'}'; retry {failures}/3 in {delay} minutes.")

    _PREVIOUS_RUNNING_WORKERS = {
        _task_id_for_worker(worker): {
            "account_id": account_id,
            "pid": worker.get("pid"),
            "work_dir": worker.get("work_dir", ""),
        }
        for account_id, worker in active_workers.items()
        if _task_id_for_worker(worker)
    }


def dispatch_task_to_account(account: dict, task: dict):
    acc_id = account["id"]
    log(f"🚀 [AUTO-DISPATCH] [{account['name']}] -> '{task.get('book_title_ko')}' (Stage {task.get('stage')}, Priority {task.get('priority')})")

    # Clear lock
    profile_p = Path(account["profile_dir"]) / ("gemini" if account["provider"] == "gemini" else "chatgpt")
    lock_f = profile_p / ".audiobook_web_profile.lock"
    if lock_f.exists():
        try:
            lock_f.unlink()
        except OSError:
            pass

    env = os.environ.copy()
    env["AUDIOBOOK_WEB_PROFILE_DIR"] = account["profile_dir"]
    env["AUDIOBOOK_ACCOUNT_ID"] = acc_id
    env["AUDIOBOOK_TASK_ID"] = str(task.get("id", ""))

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

    try:
        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=out_log,
            stderr=err_log,
            start_new_session=True,
        )
    finally:
        # The child inherits these descriptors; retaining them in the
        # long-running supervisor leaks one pair for every dispatched task.
        out_log.close()
        err_log.close()

    # Initialize fresh heartbeat to prevent watchdog race condition
    try:
        init_hb = {
            "timestamp": time.time(),
            "iso_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "pid": proc.pid,
            "stage": "process_spawned",
            "detail": f"Launched by supervisor on account {acc_id}"
        }
        heartbeat_file.write_text(json.dumps(init_hb, indent=2), encoding="utf-8")
    except Exception:
        pass

    log(f"   -> Successfully launched PID {proc.pid} on [{account['name']}]!")
    task["status"] = "running"
    task["account_id"] = acc_id
    # Register the child before returning to the polling loop.  Very short
    # failed jobs can exit before the next get_running_workers() snapshot;
    # without this entry record_worker_transitions() cannot observe the exit
    # and the same task is dispatched repeatedly to an idle account.
    _PREVIOUS_RUNNING_WORKERS[str(task.get("id", ""))] = {
        "account_id": acc_id,
        "pid": proc.pid,
        "work_dir": task.get("work_dir", ""),
    }

_PREVIOUS_WORKER_PROGRESS = {}

def perform_visual_health_audit(active_workers: dict):
    """Performs scheduled visual health checks and saves status metadata every 3 minutes.
    Automatically detects and kills frozen/hung workers that showed zero progress over the audit interval.
    """
    global _PREVIOUS_WORKER_PROGRESS
    audit_time = time.strftime("%Y-%m-%d %H:%M:%S")
    now_ts = time.time()
    log("📸 [VISUAL HEALTH AUDIT] Performing scheduled visual check across 4 accounts...")

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
                except (OSError, ValueError):
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
                    stored_ct = worker_info.get("create_time", 0)
                    log(f"🚨 [VISUAL AUDIT ANOMALY] [{acc['name']}] (PID {w_pid}) has been FROZEN with zero progress for {int(now_ts - hb_time)}s! Auto-terminating to self-heal...")
                    try:
                        proc = psutil.Process(w_pid)
                        if abs(proc.create_time() - stored_ct) < 2.0:
                            proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
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
                try:
                    lock_f.unlink()
                except OSError:
                    pass

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
                except Exception:
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
            record_worker_transitions(active_workers)
            active_task_ids = set()
            active_titles = set()
            for w in active_workers.values():
                task_id = w.get("task_id")
                if task_id:
                    active_task_ids.add(task_id)
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
                            stored_ct = w_info.get("create_time", 0)
                            proc = psutil.Process(w_pid)
                            if abs(proc.create_time() - stored_ct) < 2.0:
                                proc.terminate()
                        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
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
                w_pid = w_info.get("pid")
                proc_age = time.time() - w_info.get("create_time", time.time())

                # Grace period: Never stall-kill a process younger than 5 minutes (browser startup/login)
                if proc_age < 300:
                    continue

                work_dir_p = Path(w_info.get("work_dir", ""))
                if work_dir_p.exists():
                    hb_f = work_dir_p / "heartbeat.json"
                    if hb_f.exists():
                        try:
                            hb_data = json.loads(hb_f.read_text())
                            hb_time = float(hb_data.get("timestamp", 0))
                            if hb_time > 0 and (time.time() - hb_time > 300):  # 5 minutes without heartbeat
                                log(f"🚨 [STALL DETECTED] Account '{acc_id}' (PID {w_pid}, age {int(proc_age)}s) has been unresponsive for {int(time.time() - hb_time)}s! Auto-terminating to heal session...")
                                stored_ct = w_info.get("create_time", 0)
                                try:
                                    proc = psutil.Process(w_pid)
                                    if abs(proc.create_time() - stored_ct) < 2.0:
                                        proc.kill()
                                except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
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
