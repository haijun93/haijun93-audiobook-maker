# AGENTS.md — Master AI Engineering & Operations Specification

> **Target Audience**: Any AI pair-programmer or autonomous coding agent (Claude Code, ChatGPT, Gemini, Codex, Cursor, GitHub Copilot) working on `haijun93-audiobook-maker`.

---

## 1. Project Mission & Core Rules

1. **Python Virtual Environment**:
   - ALWAYS use `.venv311/bin/python` for executing scripts, tests, and CLI tools.
2. **Library Standard Output & Taxonomy (`/Users/hyeokjunkong/Desktop/소설2/` & GDrive `#Books`)**:
   - NEVER create arbitrary temporary folders like `pam_general_translation`, `finished`, `non-english`, `[e]`, or `Uncategorized` inside output destinations.
   - ALWAYS output and synchronize to the 4 standard root editions:
     - `소설2/[k]/...` (Korean-only)
     - `소설2/[k-e]/...` (Bilingual)
     - `소설2/[study]/...` (Korean + TOEIC 700+ Study Notes)
     - `소설2/[e-s]/...` (English Original + Study Notes)
   - **Master Hierarchy & Directory Classification Rules**:
     1. **Best 100 & Major Genres**: Must reside in standard genre subdirectories matching original sources:
        - `Fiction_Literary_Historical/#Author/` (`#Hanya Yanagihara`, `#Gabrielle Zevin`, `#Barbara Kingsolver`, `#Fredrik Backman`, `#Khaled Hosseini`, `#Ursula Rani Sarma`, `#Arthur Golden`, `#Ken Follett`, `#Markus Zusak`, `#Paulo Coelho`, `#Patrick Süskind`)
        - `Mystery_Thriller_Crime/#Author/` (`#Alex Michaelides`, `#Haper Lee`, `#Agatha Christie`, `#Keigo Higashino`, `#Lisa Jewell`, `#Stieg Larsson`)
        - `Fantasy_Science_Fiction/#Author/` (`#Brandon Sanderson`, `#Suzanne Collins`, `#Isaac Asimov`, `#Guy Gavriel Kay`)
        - `Romance_Contemporary/#Author/` (`#Abby Jimenez`, `#Casey McQuiston`, `#Ali Hazelwood`, `#Rebecca Yarros`)
        - `Historical_Fiction/#Author/` (`#Mark Sullivan`, `#Kristin Hannah`, `#Diana Gabaldon`)
        - `Dark_Romance/#Author/`
        - `Nonfiction_History_Politics/#Author/`, `Business_Economics/#Author/`, `Biography_Memoir/#Author/`, `Young_Adult_Children/#Author/`
     2. **Full-Catalogue & Dedicated Franchise Collections**: Only dedicated complete-works series reside at edition roots:
        - `#Freida McFadden/` (Full catalog)
        - `#Pam Godwin/` (Full catalog)
        - `#Leigh Rivers/` (Full catalog)
        - `#Top 10 dark romance/` (VK Top 10 Dark Romance series)
        - `#apple tv original/` (Apple TV+ Original Novel Adaptations)
        - `#original books/` (Movie & TV Series Screen Adaptation Novels)
     3. **1:1 Mirroring Rule**: All 4 editions (`[k]`, `[k-e]`, `[study]`, `[e-s]`) must have 100% identical relative folder paths for every book.
3. **4-Account Isolation & Concurrency**:
   - Four separate browser profiles run simultaneously:
     - `main`: `~/Library/Application Support/AudiobookStudio/browser_profiles/gemini` (Chrome Profile 1, `haijun93@gmail.com`)
     - `account2`: `~/Library/Application Support/AudiobookStudio-account2/browser_profiles/gemini` (Chrome Profile 2, `haijun2be@gmail.com`)
     - `account3`: `~/Library/Application Support/AudiobookStudio-account3/browser_profiles/gemini` (Chrome Profile 18, `ngaytot9@gmail.com`)
     - `chatgpt`: `~/Library/Application Support/AudiobookStudio-chatgpt/browser_profiles/chatgpt` (Chrome Profile 1, `haijun93@gmail.com`)
   - Each profile enforces `.audiobook_web_profile.lock` before starting Chrome.
4. **Pure AI Translation & AI-Generated Study Notes Principle (절대 불변 원칙)**:
   - ALWAYS and ONLY use authentic AI (Gemini, ChatGPT) contextual translation and AI-generated TOEIC 700+ study notes (`※ 단어 - 문맥 뜻`).
   - NEVER mechanically inject external static dictionary databases (e.g. KALDIC, static wordbooks) or overwrite authentic AI context translations with arbitrary dictionary matching. All library content must come directly from authentic AI LLM comprehension of the text.
   - **TOEIC 700+ to 990 Target Standard (토익 700점~만점 도약 타깃 어휘 엄선 원칙)**:
     - 중학교/초급 수준의 평이한 기본 단어(예: `happy, afraid, hell, words, smile, dinner, travel, ticket, teeth, friend, room, hand, look, voice` 등)는 학습정보 및 Word Wise 루비 힌트로의 추출을 엄격히 금지한다.
     - 오직 토익 700점대 학습자가 만점(990점)을 달성하는 데 실질적으로 필요한 **고급 어휘(`plummet, musty, threshold, flicker, unfixable, subjugate...`), 고급 숙어/구동사(`bleed dry, cross the threshold...`), 다의어의 특수 문맥 뜻**만을 선별 추출한다.
     - 고난도 어휘가 없는 평이한 문장은 억지로 단어를 쥐어짜내지 않고 학습 노트를 과감히 생략하여 시각적 피로도를 최소화하고 학습 효율을 극대화한다.
5. **Korean Original Literature Handling Principle**:
   - Pure Korean original works (e.g. Pak Kyongni 『Land/토지』, Shin Young-bok 『Lectures/강의』, etc.) are authentic Korean literature and must NEVER be queued for English-to-Korean translation/retranslation. They are preserved in their original form as Korean masterpieces.
6. **ChatGPT Dark Romance Exclusion Principle (ChatGPT 다크로맨스 번역 제외 원칙)**:
   - ChatGPT web worker is STRICTLY PROHIBITED from translating any Dark Romance works (including `Dark_Romance`, `#Leigh Rivers`, `#Pam Godwin`, `#Top 10 dark romance`, and related dark/taboo romance authors) due to strict content safety moderation guardrails.
   - All Dark Romance works MUST ONLY be processed by Gemini workers (`main`, `account2`, `account3`).
   - ChatGPT is exclusively routed to non-dark genres (Freida McFadden, Mystery/Thriller, Historical Fiction, Fantasy/Sci-Fi, Nonfiction, YA, etc.).
7. **Amazon Kindle Genuine Word Wise & X-Ray Master Publishing Standard (킨들 순정 Word Wise & X-Ray 일반 규칙)**:
   - **Zero Truncation Rule (글자 누락 영구 금지)**: NEVER mechanically slice or truncate Korean contextual meanings (e.g. no `[:8]` length chopping). All authentic AI phrases (e.g. `~할 여유가 없다`, `발끝으로 살금살금 지나가다`, `갈라진 신발 밑창`) must remain 100% intact and complete.
   - **Overhead Native HTML5 Ruby Layout**: In `[study]`, `[e-s]`, and `[ks]`, all AI study notes are positioned directly above words as overhead cloud hints (`ruby-position: over; font-size: 0.58em; color: #0284c7;`) using `<ruby><rb>word</rb><rt class="wordwise-hint">문맥 뜻</rt></ruby>`.
   - **Dynamic Conditional Line-Height Rule (동적 조건부 줄간격)**:
     - Sentences WITHOUT Word Wise: Standard `1.65` (100% identical to Korean standard line-height).
     - Sentences WITH Word Wise: Dynamically expanded to `1.85` (`span.en.has-ww`, `p.has-ww`) for ample breathing space.
   - **Elimination of Redundant 3rd Line**: In `[study]` and `[e-s]`, the legacy separate 3rd-line `※` notes are completely streamlined into the overhead Word Wise annotations.
   - **Kindle X-Ray Directory Integration**: Every book includes the X-Ray Dramatis Personae & Terms directory (`000-xray-dramatis-personae.xhtml`) linked at the top of the Table of Contents.
8. **Mandatory Fiction X-Ray Dossier Pipeline Standard (소설 번역 시 AI 웹서비스 직접 질의 및 클로드 비간섭 일괄 수집 원칙)**:
   - **신규 번역 작업 (New Translations)**: 앞으로 진행되는 모든 신규 소설 번역은 담당 워커(Gemini 1/2/3, ChatGPT)가 번역 파이프라인의 필수 단계로서 **자체 제미나이 웹 및 챗지피티 웹 서비스에 직접 질의하여 고품질 100% 한국어 X-Ray 도감(`000-xray-dramatis-personae.xhtml`)을 생성**하고 목차 최상단에 자동 탑재한다 (휴리스틱 추측 금지, 클로드 미사용).
   - **기존 서재 일괄 수집 (Bulk Retroactive Library Harvest)**: 클로드 웹 수확기(`scripts/harvest_fiction_xray_with_claude.py`)는 **오직 현재 서재에 이미 완성되어 보관 중인 기존 파일들만을 대상**으로 하며, 진행 중인 워커들의 실시간 번역 세션을 일절 방해하지 않고 독립적으로 엑스레이 정보를 수집·보강한다.
   - Required 4 sections (100% Authentic Korean):
     1. 👥 주요 등장인물 도감 (인물명, 원어명, 역할/신분, 성격, 행동 동기, 서사적 비중)
     2. 🔗 등장인물 관계도 및 핵심 갈등 구조 (주인공 ↔ 대립자/조력자 심리 역학)
     3. 🗺️ 주요 무대 및 공간적 배경 (핵심 장소들의 분위기 및 공간적 상징성)
     4. 🔍 핵심 테마 및 세계관·복선 해설 (중심 메시지 및 핵심 용어)
   - Every fiction novel across all 6 editions (`[k]`, `[k-e]`, `[study]`, `[e-s]`, `[xteink]/[study]`, `[xteink]/[e-s]`) must have the X-Ray directory attached as the very top item in the Table of Contents (`nav.xhtml` & `toc.ncx`).
9. **Non-English Source Translation Exclusion & OceanofPDF English Replacement Principle (비영어 원서 번역 금지 및 영문본 자동 대체 원칙)**:
   - Foreign language editions (German, French, Czech, Turkish, Italian, Indonesian, etc.) are STRICTLY PROHIBITED from being queued or translated into Korean, as they destroy the English learning value of `[study]` and `[e-s]` editions.
   - All non-English tasks are automatically skipped, and their official English editions are retrieved directly via `oceanofpdf.com` (`scripts/handle_non_english_books.py`) and placed into standard `소설2/[e]/[Genre]/#[Author]/` directories before entering the translation pipeline.
10. **Authentic Original TOC & Zero Untranslated Leak Standard (원작 목차 100% 보존 및 영문 누락 원천 차단 표준)**:
    - **Authentic Original TOC Preservation**: NEVER mechanically index chapter numbers (e.g. `2장, 3장, 5장`). ALWAYS preserve the author's authentic chapter names (Prologue, Chapter Names, Epilogue, etc.) from the English original edition (`[e]`), placing the X-Ray Dramatis Personae at the very top.
    - **Post-Translation Full Korean Integrity Guard**: Every built `[k]` edition must be strictly verified against untranslated English text leaks. All frontmatter (Title, Copyright, Dedication, Prologue) and backmatter must be 100% translated into authentic Korean without leaving any raw English sentences.
11. **Mandatory Pre-Publishing Master Quality Gate Protocol (출판 전 자동 품질 검수 신설 의무화 원칙)**:
    - **Automated Pre-Publish Quality Interceptor (`audiobook_studio/master_quality_inspector.py`)**:
      모든 번역 워커는 결과물 EPUB을 최종 서재(`소설2/` 및 Google Drive `#Books`)에 배포하기 전에 반드시 **자동 품질 검수기(`inspect_epub_quality`)**를 거쳐야 하며, 아래 6대 검수 게이트를 100% 통과하지 못한 파일은 서재 진입을 원천 차단한다:
      1. 🖼️ **Cover Gate**: 정품 고화질 표지 이미지(`cover.jpeg`, >10KB), 표지 페이지(`000-cover.xhtml`), OPF 메타데이터 완전 탑재.
      2. 📑 **TOC 3-Tier Gate**: `nav.xhtml` & `toc.ncx` XML Well-formedness 100% 무결성 (특수문자 `&` 이스케이프 강제, 최소 3개 이상 정규 챕터 링크).
      3. 👥 **X-Ray Dossier Gate**: X-Ray 도감 최상단 탑재 및 4대 필수 섹션(등장인물, 관계도, 무대, 테마) 완비.
      4. 🚫 **Zero Untranslated Leak Gate**: 한글 번역 영역(`span.ko`) 내 영문 원문 단순 복사 0건 검증 (100% 순수 완역 보장).
      5. 🎯 **TOEIC 700+ to 990 Vocab Gate**: 중학교 기초 단어 루비 포함 0건, 글자 잘림(Truncation) 0건, Overhead Ruby 표준 준수.
      6. 🛡️ **XML Well-Formedness Gate**: EPUB 내부 모든 XHTML/XML 파일 파서 파싱 에러 0건.
12. **Mandatory 2-Tier Master Dual Inspector Protocol (2인 상호 교차 검수 의무화 무결성 원칙)**:
    - **Tier-1 Master Inspector (`master_quality_inspector.py`)**:
      - 1차 구조, 기본 XML 문법, 표지, 3중 TOC, X-Ray 도감, 1차 기초 단어 소거 및 즉각적 자동 자가치유(Auto-Healing) 수행.
    - **Tier-2 Ultimate Integrity Sentinel (`ultimate_integrity_sentinel.py` - 수석 검수관)**:
      - 제1검수관을 통과한 파일에 대해 단 0.001%의 결함도 허용하지 않는 **7대 무관용 무결성 심층 정밀 검증(Zero-Tolerance Deep Verification)** 집행:
        1. 🔬 **Bi-Text Parity**: 영한 문단 1:1 대칭 및 문장 누락 제로 검증.
        2. 🚫 **Absolute Zero-Leak**: `span.ko` 내 비-한글 원시 영문 잔류 0건 (1건이라도 발견 시 즉시 탈락).
        3. 🎯 **Lexicon Purity**: TOEIC 700+ to 990 엄선 어휘 순도 100%, 말줄임표(`...`) 잘림 0건.
        4. 📑 **TOC-Spine Sync**: `nav.xhtml`, `toc.ncx`, `<spine>` 간 깨진 링크 0건.
        5. 🖼️ **HD Cover Gate**: 고화질 표지(>15KB), `000-cover.xhtml` 및 OPF 속성 100% 선언.
        6. 👥 **X-Ray Quad-Section**: 등장인물, 관계도, 공간배경, 핵심테마 4대 섹션 100% 한글 수록.
        7. 🛡️ **W3C Strict XML**: EPUB 내부 모든 문서의 엄격한 W3C XML 파싱 에러 0건.
      - **Digital Integrity Seal**: 제1검수관과 제2수석검수관의 2단계 인증을 모두 획득한 완벽한 전자책만이 서재에 최종 출판 및 동기화된다.

---

## 2. Key Architecture Protocols

### Session Self-Healing (Hot-Injection)
- When Gemini drops into Guest Mode (`gemini.google.com/app` showing "로그인"), `audiobook_maker.py:prepare_gemini_web_page` intercepts the state, automatically extracts live cookies from the account's Chrome profile (`Profile 1`, `Profile 2`, `Profile 18`) via `browser_cookie3`, injects them via `page.context.add_cookies()`, and reloads the page to seamlessly recover without crashing.

### Background Token Refresh
- `WEB_CHROME_IGNORED_PLAYWRIGHT_DEFAULT_ARGS` in `audiobook_maker.py` ignores `--disable-sync` and `--disable-component-update` so Google's background sync engine can rotate `__Secure-1PSIDTS` tokens.

### Automated 30-Minute Health Audit & Lexicon Sync
- `.venv311/bin/python scripts/check_accounts_and_report.py` audits all 4 profiles, logs active worker health, performs self-healing keep-alive checks, and automatically invokes `update_master_study_lexicon.py` to continuously harvest new vocabulary.

### Master Study Lexicon Maintenance (215,000+ Entries)
- `data/master_study_lexicon.json` stores the master dictionary of high-yield TOEIC 700+ vocabulary, collocations, idioms, and contextual Korean definitions harvested across the entire library.
- Automatically synchronized across `data/`, `소설2/MD collection/`, and Google Drive `#Books/MD collection/`.

---

## 3. Essential Scripts Directory

| Script | Purpose |
|---|---|
| `audiobook_maker.py` | Core engine: chunking, translation, TOEIC study note extraction, Edge-TTS audio |
| `scripts/update_master_study_lexicon.py` | Continuous incremental harvester for 215,000+ Master Study Lexicon |
| `web_app.py --port 7870` | Flask Web UI with real-time SSE stream, Dark Mode, and 30-min audit dashboard |
| `scripts/desktop_app.py` | Native macOS Always-on-top Cocoa desktop window (`pywebview`) |
| `scripts/gui_launcher.py` | 4-button Automator controller (Start, Pause, Refresh, Exit) |
| `scripts/make_korean_only_epubs.py` | Derives `[k]` Korean-only EPUBs from `[k-e]` |
| `scripts/make_english_study_epubs.py` | Derives `[e-s]` (English + Study Notes) from `[study]` |
| `scripts/check_accounts_and_report.py` | 30-minute scheduled health audit and progress report |
| `scripts/download_oceanofpdf.py` | OceanofPDF automated book search, download & library integration |

---

## 4. Documentation & Handover Standard
- Always document session status and snapshots in `docs/SESSION_HANDOFF_YYYYMMDD.md`.
- Keep `/Users/hyeokjunkong/Desktop/소설2/MD collection/` synchronized with current repository standards.
