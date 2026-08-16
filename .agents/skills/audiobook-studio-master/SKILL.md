---
name: audiobook-studio-master
description: Complete master engineering and operations guide for the Audiobook Studio & AI Multi-Account Translation system. Covers 4-account parallel architecture (Gemini 1/2/3, ChatGPT), session self-healing, 4-edition library pipeline ([k], [k-e], [study], [e-s]), CLI commands, and automated background audit protocols.
---

# Audiobook Studio Master Engineering & Operations Guide

This skill provides a 100% comprehensive operational specification for AI agents (Claude, ChatGPT, Gemini, Codex, Cursor, etc.) working on or inheriting the `haijun93-audiobook-maker` codebase.

---

## 1. System Architecture & Tech Stack

```
                               ┌────────────────────────────────────────┐
                               │   macOS Controller / Desktop UI        │
                               │   (pywebview / Automator .app)         │
                               └──────────────────┬─────────────────────┘
                                                  │ HTTP / SSE
                               ┌──────────────────▼─────────────────────┐
                               │   Flask Web Dashboard (:7870)          │
                               │   (web_app.py / Dark Mode WebUI)       │
                               └──────────────────┬─────────────────────┘
                                                  │ IPC / Subprocess / Cron
           ┌──────────────────────────┬───────────┴──────────────┬──────────────────────────┐
           ▼                          ▼                          ▼                          ▼
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│  Gemini Account 1    │  │  Gemini Account 2    │  │  Gemini Account 3    │  │  ChatGPT Web Account │
│  (haijun93@gmail)    │  │  (haijun2be@gmail)   │  │  (ngaytot9@gmail)    │  │  (haijun93@gmail)    │
│  Profile: main       │  │  Profile: account2   │  │  Profile: account3   │  │  Profile: chatgpt    │
│  Port / Isolated Env │  │  Port / Isolated Env │  │  Port / Isolated Env │  │  Cloudflare Bypassed │
└──────────┬───────────┘  └──────────┬───────────┘  └──────────┬───────────┘  └──────────┬───────────┘
           │                         │                         │                         │
           └─────────────────────────┼─────────────────────────┴─────────────────────────┘
                                     │ Self-Healing Cookie Hot-Injection & Chunk Pipeline
                                     ▼
                   ┌───────────────────────────────────┐
                   │    audiobook_maker.py Core        │
                   │    (EPUB Chunking, Translation,   │
                   │     TOEIC Study Notes, Edge-TTS)  │
                   └─────────────────┬─────────────────┘
                                     │ Post-Processing & Normalization
                                     ▼
                   ┌───────────────────────────────────┐
                   │    4-Edition Library Pipeline     │
                   │    /Users/hyeokjunkong/Desktop/소설2 │
                   │    ├── [k]/     (Korean Only)     │
                   │    ├── [k-e]/   (Bilingual)       │
                   │    ├── [study]/ (Korean + Notes)  │
                   │    └── [e-s]/   (English + Notes) │
                   └───────────────────────────────────┘
```

- **Runtime**: Python 3.11 (`.venv311/bin/python`) on macOS (Darwin arm64).
- **Core Automation**: Playwright (`playwright.sync_api`) controlling official Google Chrome binary (`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`).
- **Web UI & Streaming**: Flask + Server-Sent Events (SSE) live updates + Pure CSS Dark Theme.
- **Desktop Window**: `pywebview` Always-on-top Cocoa window (`scripts/desktop_app.py`).
- **TTS Engine**: Microsoft Edge-TTS (`edge_tts`) supporting Korean voices (`ko-KR-SunHiNeural`, `ko-KR-InJoonNeural`, `ko-KR-HyunsuNeural`).

---

## 2. 4-Account Parallel Translation Architecture

Four independent accounts run concurrently without race conditions or cookie collision:

| 계정 식별자 | 공급자 (Provider) | 구글/OpenAI 로그인 계정 | 영구 브라우저 프로필 디렉터리 | Chrome 쿠키 부트스트랩 원본 |
|---|---|---|---|---|
| **`main`** | Gemini Web | `haijun93@gmail.com` | `~/Library/Application Support/AudiobookStudio/browser_profiles/gemini` | `Chrome/Profile 1/Cookies` |
| **`account2`** | Gemini Web | `haijun2be@gmail.com` | `~/Library/Application Support/AudiobookStudio-account2/browser_profiles/gemini` | `Chrome/Profile 2/Cookies` |
| **`account3`** | Gemini Web | `ngaytot9@gmail.com` | `~/Library/Application Support/AudiobookStudio-account3/browser_profiles/gemini` | `Chrome/Profile 18/Cookies` |
| **`chatgpt`** | ChatGPT Web | `haijun93@gmail.com` | `~/Library/Application Support/AudiobookStudio-chatgpt/browser_profiles/chatgpt` | `Chrome/Profile 1/Cookies` |

### Profile Concurrency Lock Protocol
- Before launching Chrome against any profile, each process acquires `.audiobook_web_profile.lock` in the profile root directory.
- `WEB_CHROME_IGNORED_PLAYWRIGHT_DEFAULT_ARGS` ignores `--disable-sync` and `--disable-component-update` to allow Google background token rolling (`__Secure-1PSIDTS`).

---

## 3. Gemini Session Self-Healing (Hot-Injection) Protocol

### Why Sessions Degrade
Google rotates short-term security timestamp tokens (`__Secure-1PSIDTS`) every 12–24 hours. When Playwright automation runs, Gemini Web may silently downgrade to **Guest Mode** (URL remains `https://gemini.google.com/app`, but blue "로그인" button appears and prompts fail).

### Self-Healing Implementation (`audiobook_maker.py:5672`)
1. **Detection**: `prepare_gemini_web_page()` checks `page.get_by_text("로그인", exact=True)` visibility across all DOM occurrences or `accounts.google.com` redirect.
2. **Interception**: If guest mode is detected, the worker catches the condition before raising an error.
3. **Hot-Injection**: It immediately reads the latest live cookies from the account's Chrome profile (`Profile 1`, `Profile 2`, or `Profile 18`) via `browser_cookie3`.
4. **Context Injection & Reload**: Injects the fresh cookies into `page.context.add_cookies()`, reloads `gemini.google.com/app`, waits for DOM rehydration, and re-verifies.
5. **Seamless Continuation**: Translation proceeds uninterrupted without crashing or terminating the task.

---

## 4. Standard 4-Edition Library Pipeline (`소설2`)

All book translations must generate **4 distinct standard editions** directly deposited into `/Users/hyeokjunkong/Desktop/소설2/`:

```
/Users/hyeokjunkong/Desktop/소설2/
├── [k]/              # 한국어 전용본 (make_korean_only_epubs.py로 생성)
│   └── #작가명/
├── [k-e]/            # 한영 대역본 (번역 워커가 직접 생성)
│   └── #작가명/
├── [study]/          # 토익 700+ 어휘/구동사 학습노트 포함본 (번역 워커가 생성)
│   └── #작가명/
└── [e-s]/            # 영어 원문 + 학습노트본 (make_english_study_epubs.py로 생성)
    └── #작가명/
```

> **CRITICAL RULE**: Do NOT create temporary subfolders (e.g., `pam_general_translation`) inside output roots. Output must be deployed directly into the standard `[k]`, `[k-e]`, `[study]`, and `[e-s]` author directories.

---

## 5. Master CLI Command Cheat Sheet

### Running Web UI & Desktop App
```bash
# Start Web UI server in background (Port 7870)
.venv311/bin/python web_app.py --port 7870

# Launch Native Always-on-top Cocoa Desktop App
.venv311/bin/python scripts/desktop_app.py

# Launch Automator GUI Controller (4 Buttons: Start, Pause, Refresh, Exit)
.venv311/bin/python scripts/gui_launcher.py
```

### Running 30-Minute Account & Batch Audit
```bash
.venv311/bin/python scripts/check_accounts_and_report.py
```

### Library Post-Processing & Edition Generation
```bash
# Generate [k] (Korean-only) from [k-e]
.venv311/bin/python scripts/make_korean_only_epubs.py "/path/to/folder_or_epub" --overwrite

# Generate [e-s] (English + Study Notes) from [study]
.venv311/bin/python scripts/make_english_study_epubs.py "/Users/hyeokjunkong/Desktop/소설2/[study]/#Author" --output-root "/Users/hyeokjunkong/Desktop/소설2/[e-s]/#Author" --overwrite
```

### Single Book Translation CLI
```bash
# Gemini Translation (Account 1, 2, or 3)
AUDIOBOOK_WEB_PROFILE_DIR="$HOME/Library/Application Support/AudiobookStudio/browser_profiles" \
.venv311/bin/python audiobook_maker.py input.epub \
  --translation-provider gemini-web \
  --output-dir "/Users/hyeokjunkong/Desktop/소설2/[k-e]/#Author" \
  --chunks-per-conversation 10

# ChatGPT Web Translation
AUDIOBOOK_WEB_PROFILE_DIR="$HOME/Library/Application Support/AudiobookStudio-chatgpt/browser_profiles" \
.venv311/bin/python audiobook_maker.py input.epub \
  --translation-provider chatgpt-web \
  --output-dir "/Users/hyeokjunkong/Desktop/소설2/[k-e]/#Author"
```

---

## 6. Duplicate Prevention: 3-Layer Defense
1. **Filename Pre-Filter (`source_files`)**: Skips `.epub` files already present as `[k] Filename.epub` in the `[k]` library root.
2. **Metadata Fuzzy Matching (`run_batch`)**: Normalizes book title and author (`SequenceMatcher` >= 0.92 title, >= 0.6 author), checking against `finished` archive, HTML collection catalog, and live `[k]` library.
3. **Artifact Existence Check (`translate_one`)**: Checks if target `[k-e]` or `[k]` EPUB is already finalized.

---

## 7. Troubleshooting & Diagnostics for Inheriting AI Agents

- **Guest Mode or Login Alert**:
  - Run `.venv311/bin/python scripts/check_accounts_and_report.py`.
  - If Account 3 needs 2FA refresh, run `osascript -e 'tell application "Google Chrome" to activate' && open -na "Google Chrome" --args --profile-directory="Profile 18" "https://gemini.google.com/app"`.
- **Heartbeat & Zombie Process Cleanup**:
  - Check active worker heartbeats in `/Users/hyeokjunkong/Desktop/소설2/_chatgpt_translate_work/*/heartbeat.json`.
  - Web UI automatically displays `recovering` or `degraded` if a worker's heartbeat is older than 180 seconds.
- **Git & Documentation Policy**:
  - Always update `docs/SESSION_HANDOFF_*.md` and sync changes to `/Users/hyeokjunkong/Desktop/소설2/MD collection/` before pushing commits.
