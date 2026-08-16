# AGENTS.md — Master AI Engineering & Operations Specification

> **Target Audience**: Any AI pair-programmer or autonomous coding agent (Claude Code, ChatGPT, Gemini, Codex, Cursor, GitHub Copilot) working on `haijun93-audiobook-maker`.

---

## 1. Project Mission & Core Rules

1. **Python Virtual Environment**:
   - ALWAYS use `.venv311/bin/python` for executing scripts, tests, and CLI tools.
2. **Library Standard Output (`/Users/hyeokjunkong/Desktop/소설2/`)**:
   - NEVER create arbitrary temporary folders like `pam_general_translation` inside output destinations.
   - ALWAYS output and synchronize to the 4 standard root directories:
     - `소설2/[k]/#Author/` (Korean-only)
     - `소설2/[k-e]/#Author/` (Bilingual)
     - `소설2/[study]/#Author/` (Korean + TOEIC 700+ Study Notes)
     - `소설2/[e-s]/#Author/` (English Original + Study Notes)
3. **4-Account Isolation & Concurrency**:
   - Four separate browser profiles run simultaneously:
     - `main`: `~/Library/Application Support/AudiobookStudio/browser_profiles/gemini` (Chrome Profile 1, `haijun93@gmail.com`)
     - `account2`: `~/Library/Application Support/AudiobookStudio-account2/browser_profiles/gemini` (Chrome Profile 2, `haijun2be@gmail.com`)
     - `account3`: `~/Library/Application Support/AudiobookStudio-account3/browser_profiles/gemini` (Chrome Profile 18, `ngaytot9@gmail.com`)
     - `chatgpt`: `~/Library/Application Support/AudiobookStudio-chatgpt/browser_profiles/chatgpt` (Chrome Profile 1, `haijun93@gmail.com`)
   - Each profile enforces `.audiobook_web_profile.lock` before starting Chrome.

---

## 2. Key Architecture Protocols

### Session Self-Healing (Hot-Injection)
- When Gemini drops into Guest Mode (`gemini.google.com/app` showing "로그인"), `audiobook_maker.py:prepare_gemini_web_page` intercepts the state, automatically extracts live cookies from the account's Chrome profile (`Profile 1`, `Profile 2`, `Profile 18`) via `browser_cookie3`, injects them via `page.context.add_cookies()`, and reloads the page to seamlessly recover without crashing.

### Background Token Refresh
- `WEB_CHROME_IGNORED_PLAYWRIGHT_DEFAULT_ARGS` in `audiobook_maker.py` ignores `--disable-sync` and `--disable-component-update` so Google's background sync engine can rotate `__Secure-1PSIDTS` tokens.

### Automated 30-Minute Health Audit
- `.venv311/bin/python scripts/check_accounts_and_report.py` audits all 4 profiles, logs active worker health, and performs self-healing keep-alive checks.

---

## 3. Essential Scripts Directory

| Script | Purpose |
|---|---|
| `audiobook_maker.py` | Core engine: chunking, translation, TOEIC study note extraction, Edge-TTS audio |
| `web_app.py --port 7870` | Flask Web UI with real-time SSE stream, Dark Mode, and 30-min audit dashboard |
| `scripts/desktop_app.py` | Native macOS Always-on-top Cocoa desktop window (`pywebview`) |
| `scripts/gui_launcher.py` | 4-button Automator controller (Start, Pause, Refresh, Exit) |
| `scripts/make_korean_only_epubs.py` | Derives `[k]` Korean-only EPUBs from `[k-e]` |
| `scripts/make_english_study_epubs.py` | Derives `[e-s]` (English + Study Notes) from `[study]` |
| `scripts/check_accounts_and_report.py` | 30-minute scheduled health audit and progress report |

---

## 4. Documentation & Handover Standard
- Always document session status and snapshots in `docs/SESSION_HANDOFF_YYYYMMDD.md`.
- Keep `/Users/hyeokjunkong/Desktop/소설2/MD collection/` synchronized with current repository standards.
