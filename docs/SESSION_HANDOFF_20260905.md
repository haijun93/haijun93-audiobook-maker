# Session Handoff — 2026-09-05

> **Target Agent**: Incoming AI Assistant (ChatGPT) resuming operations on `haijun93-audiobook-maker`.

---

## 1. Executive Summary & Core Context

- **Current Repository State**: Clean working tree on branch `codex/extend-audiobook-workflows`, 100% synchronized and pushed to GitHub remote `origin/codex/extend-audiobook-workflows`.
- **Python Environment**: Always use `.venv311/bin/python` for executing all scripts, audits, and CLI tools.
- **Active Supervisor**: `continuous_worker_supervisor.py` is actively running in background (PID `86001`), orchestrating 4 browser profiles simultaneously (`main`, `account2`, `account3`, `chatgpt`).

---

## 2. Completed Items & Key Decisions in This Session

### 1) Investigation of `Presumed Innocent - Scott Turow` & Study Notes Quality
- Analyzed `/Users/hyeokjunkong/Desktop/소설2/[study]/#apple tv original/#Scott Turow/[study] Presumed Innocent - Scott Turow.epub`.
- **Finding**: Identified that the vocabulary in this EPUB contained low-difficulty words (`words`, `smile`, `room`, `afraid`, `dinner`, `ticket`, `travel`) and truncated contextual meanings (`~할 수 있는 능...`, `...`) caused by older legacy extraction logic and static dictionary pollution prior to the adoption of the Pure AI TOEIC 700+ to 990 standard.
- **Root Cause & Resolution Plan**: Clarified the timeline and workflow for re-translating and purifying flawed study editions.

### 2) User Directive on Priority Realignment (최우선 업무 정책 변경)
- **Rule 1**: Flawed study notes repair tasks are strictly demoted to the **lowest priority** (`P100`).
- **Rule 2**: Genuine **new novel translations** are promoted to the **highest priority** (`P10000`).
- **Rule 3 (Strict Deduplication)**: Cross-referenced all existing 2,156 books in `/Users/hyeokjunkong/Desktop/소설2/` against the task scheduler (`.work/continuous_scheduler/config.json`).
  - **435 duplicate tasks purged** immediately from the active queue.
  - Total **7,148 genuine new translation tasks** prioritized at `P10000`.
- **Rule 4 (Active Worker Verification)**: Verified all 4 live workers to confirm none were duplicating library books:
  - Gemini 1 (`main`): *The Sentence - Louise Erdrich* (New book)
  - Gemini 2 (`account2`): *The Master Butchers Singing Club - Louise Erdrich* (New book)
  - Gemini 3 (`account3`): *LaRose - Louise Erdrich* (New book)
  - ChatGPT (`chatgpt`): *The Round House - Louise Erdrich* (New book)

### 3) ChatGPT Web Normal Mode Guard (`ensure_chatgpt_normal_chat_mode`)
- **Problem**: ChatGPT web worker would occasionally land on or switch to the `Work` tab, which quickly exhausted weekly work quotas and locked out the worker.
- **Solution**: Implemented `ensure_chatgpt_normal_chat_mode()` in `audiobook_maker.py`.
  - Automatically detects and clicks the standard `Chat` mode toggle button.
  - Automatically detects and waits out Cloudflare verification challenges without throwing fatal timeouts.
  - Integrated into `prepare_chatgpt_web_page()` and `send_chatgpt_web_prompt()`.

### 4) Master Rules Protocol Updates (AGENTS.md)
- **Rule 8 (Zero X-Ray Principle)**: Complete and permanent elimination of X-Ray dossier files (`000-xray-dramatis-personae.xhtml`) and TOC links across all editions. Pure narrative + TOEIC 700+ ruby hints focus.
- **Rule 11 (Mandatory Pre-Publishing Quality Gate)**: 5-gate automated pre-publish check.
- **Rule 12 (Tier-2 Ultimate Integrity Sentinel)**: 6-item zero-tolerance deep verification.
- **Rule 13 (Tier-3 Visual Screen Sentinel)**: Headless Chromium rendering & visual screenshot inspection.

### 5) Git Commit & Remote Push
- Staged all architectural files, scripts, quality gates, dependency files, and tests.
- Pushed commits `b0707ac` and `1126c7b` cleanly to `origin/codex/extend-audiobook-workflows`.

---

## 3. Current Active Infrastructure & Workers

| Account / Profile | Target Genre / Role | Current Status | Notes |
|---|---|---|---|
| **Gemini 1 (`main`)** | Louise Erdrich / Nonfiction / Fiction | Active | Chrome Profile 1 (`haijun93@gmail.com`) |
| **Gemini 2 (`account2`)** | Louise Erdrich / Fiction | Active | Chrome Profile 2 (`haijun2be@gmail.com`) |
| **Gemini 3 (`account3`)** | Louise Erdrich / Fiction | Active | Chrome Profile 18 (`ngaytot9@gmail.com`) |
| **ChatGPT (`chatgpt`)** | Louise Erdrich / General Fiction | Active | Chrome Profile 1 (`haijun93@gmail.com`), Non-Dark Romance only |

- **Supervisor Process**: PID `86001` (`.venv311/bin/python -m scripts.continuous_worker_supervisor`)
- **Supervisor Log**: `.work/continuous_scheduler/supervisor.log`
- **Scheduler Config**: `.work/continuous_scheduler/config.json`

---

## 4. Operational Guidelines for ChatGPT (Next Agent)

1. **Python Environment**:
   ```bash
   .venv311/bin/python <script_path>
   ```
2. **Do NOT Restart Workers Unnecessarily**:
   - The supervisor (PID `86001`) automatically restarts dead workers and rotates tasks.
   - Do not launch overlapping worker processes for accounts that are already running.
3. **Check Worker Status**:
   ```bash
   .venv311/bin/python scripts/check_accounts_and_report.py
   # or inspect supervisor log
   tail -n 30 .work/continuous_scheduler/supervisor.log
   ```
4. **Study Notes Standard (AGENTS.md Rule 4 & 7)**:
   - TOEIC 700+ to 990 targeted vocabulary only.
   - Zero truncation: Never slice contextual Korean meanings.
   - Pure AI translation: Never mechanically inject static dictionaries (e.g. KALDIC).
5. **Zero X-Ray Rule (AGENTS.md Rule 8)**:
   - Do not generate or attach X-Ray dossiers (`000-xray-dramatis-personae.xhtml`).
6. **ChatGPT Dark Romance Exclusion (AGENTS.md Rule 6)**:
   - ChatGPT is strictly prohibited from translating any Dark Romance works.

---

## 5. Synchronized Files Reference
- `AGENTS.md` (Workspace root & `/Users/hyeokjunkong/Desktop/소설2/MD collection/AGENTS.md`)
- `data/master_study_lexicon.json`
- `docs/SESSION_HANDOFF_20260905.md` (This document)
