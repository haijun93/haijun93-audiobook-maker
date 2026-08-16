# CLAUDE.md — Claude Code Pair-Programming Guidelines

This repository (`haijun93-audiobook-maker`) contains an enterprise-grade AI translation, EPUB generation, and audiobook synthesis platform operating on macOS.

---

## 1. Environment & Execution
- **Python**: ALWAYS run commands using `.venv311/bin/python` (Python 3.11).
- **Pytest**: Run unit tests using `.venv311/bin/pytest tests/test_epub_integrity.py tests/test_web_app.py`.
- **Browser Binary**: Uses `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` via Playwright.

---

## 2. Multi-Account Parallel Translation Model
- Four accounts operate in parallel with dedicated user data directories:
  - Account 1 (`main`): `haijun93@gmail.com` -> `AudiobookStudio/browser_profiles/gemini`
  - Account 2 (`account2`): `haijun2be@gmail.com` -> `AudiobookStudio-account2/browser_profiles/gemini`
  - Account 3 (`account3`): `ngaytot9@gmail.com` -> `AudiobookStudio-account3/browser_profiles/gemini`
  - ChatGPT (`chatgpt`): `haijun93@gmail.com` -> `AudiobookStudio-chatgpt/browser_profiles/chatgpt`

---

## 3. Library Directory Standards (`소설2`)
- Destination: `/Users/hyeokjunkong/Desktop/소설2/`
- Every completed book must have 4 standard editions deposited into author folders:
  - `[k]/#Author/`: Korean-only
  - `[k-e]/#Author/`: Bilingual
  - `[study]/#Author/`: Korean + TOEIC 700+ Notes
  - `[e-s]/#Author/`: English + TOEIC 700+ Notes
- NEVER create temporary subdirectories inside the output folder.

---

## 4. Key Workflows & Scripts
- **Launch WebUI (Dark Mode)**: `.venv311/bin/python web_app.py --port 7870`
- **30-Min Audit**: `.venv311/bin/python scripts/check_accounts_and_report.py`
- **Build [k]**: `.venv311/bin/python scripts/make_korean_only_epubs.py <dir>`
- **Build [e-s]**: `.venv311/bin/python scripts/make_english_study_epubs.py <study_dir> --output-root <es_dir>`
- **Session Handover**: Update `docs/SESSION_HANDOFF_YYYYMMDD.md` and sync to `/Users/hyeokjunkong/Desktop/소설2/MD collection/`.
