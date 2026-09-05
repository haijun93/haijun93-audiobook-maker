# AGENTS.md — Master AI Engineering & Operations Specification

> **Target Audience**: Any AI pair-programmer or autonomous coding agent (Claude Code, ChatGPT, Gemini, Codex, Cursor, GitHub Copilot) working on `haijun93-audiobook-maker`.

---

## 1. Project Mission & Core Rules

1. **Python Virtual Environment**:
   - ALWAYS use `.venv311/bin/python` for executing scripts, tests, and CLI tools.
2. **Library Standard Output & Taxonomy (`/Users/hyeokjunkong/Desktop/소설2/` & GDrive `#Books`)**:
   - NEVER create arbitrary temporary folders like `pam_general_translation`, `finished`, `non-english`, `[e]`, or `Uncategorized` inside output destinations.
   - ALWAYS output and synchronize to the standard root editions:
     - `소설2/[k]/...` (Korean-only)
     - `소설2/[k-e]/...` (Bilingual)
     - `소설2/[study]/...` (Korean + TOEIC 700+ Study Notes)
     - `소설2/[e-s]/...` (English Original + Study Notes)
     - `소설2/[xteink]/[study_x]/...` (Xteink Dedicated Korean Study Edition)
     - `소설2/[xteink]/[e-s_x]/...` (Xteink Dedicated English Study Edition)
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
7. **Amazon Kindle Genuine Word Wise & Master Publishing Standard (킨들 순정 Word Wise 표준)**:
   - **Zero Truncation Rule (글자 누락 영구 금지)**: NEVER mechanically slice or truncate Korean contextual meanings (e.g. no `[:8]` length chopping). All authentic AI phrases (e.g. `~할 여유가 없다`, `발끝으로 살금살금 지나가다`, `갈라진 신발 밑창`) must remain 100% intact and complete.
   - **Overhead Native HTML5 Ruby Layout**: In `[study]`, `[e-s]`, and `[ks]`, all AI study notes are positioned directly above words as overhead cloud hints (`ruby-position: over; font-size: 0.58em; color: #0284c7;`) using `<ruby><rb>word</rb><rt class="wordwise-hint">문맥 뜻</rt></ruby>`.
   - **Dynamic Conditional Line-Height Rule (동적 조건부 줄간격)**:
     - Sentences WITHOUT Word Wise: Standard `1.65` (100% identical to Korean standard line-height).
     - Sentences WITH Word Wise: Dynamically expanded to `1.85` (`span.en.has-ww`, `p.has-ww`) for ample breathing space.
   - **Elimination of Redundant 3rd Line**: In `[study]` and `[e-s]`, the legacy separate 3rd-line `※` notes are completely streamlined into the overhead Word Wise annotations.
8. **Complete X-Ray Elimination & Pure Narrative Focus Standard (엑스레이 전면 배제 및 순수 본문 완역 집중 표준)**:
   - **Zero X-Ray Principle (엑스레이 생성 및 탑재 전면 영구 금지)**:
     - 모든 신규 번역 및 기존 서재의 모든 EPUB에서 엑스레이 도감(`000-xray-dramatis-personae.xhtml`) 및 목차 내 엑스레이 링크를 일절 생성하지 않고 전면 영구 배제한다.
     - 오직 원작 소설의 순수한 텍스트 흐름과 정밀한 문맥 완역, 그리고 고순도 TOEIC 700+ to 990 학습 루비만에 집중하여 독자의 몰입감과 전자책 완성도를 극대화한다.
9. **Non-English Source Translation Exclusion & OceanofPDF English Replacement Principle (비영어 원서 번역 금지 및 영문본 자동 대체 원칙)**:
   - Foreign language editions (German, French, Czech, Turkish, Italian, Indonesian, etc.) are STRICTLY PROHIBITED from being queued or translated into Korean, as they destroy the English learning value of `[study]` and `[e-s]` editions.
   - All non-English tasks are automatically skipped, and their official English editions are retrieved directly via `oceanofpdf.com` (`scripts/handle_non_english_books.py`) and placed into standard `소설2/[e]/[Genre]/#[Author]/` directories before entering the translation pipeline.
10. **Authentic Original TOC & Zero Untranslated Leak Standard (원작 목차 100% 보존 및 영문 누락 원천 차단 표준)**:
    - **Authentic Original TOC Preservation**: NEVER mechanically index chapter numbers (e.g. `2장, 3장, 5장`). ALWAYS preserve the author's authentic chapter names (Prologue, Chapter Names, Epilogue, etc.) from the English original edition (`[e]`), placing the X-Ray Dramatis Personae at the very top.
    - **Post-Translation Full Korean Integrity Guard**: Every built `[k]` edition must be strictly verified against untranslated English text leaks. All frontmatter (Title, Copyright, Dedication, Prologue) and backmatter must be 100% translated into authentic Korean without leaving any raw English sentences.
11. **Mandatory Pre-Publishing Master Quality Gate Protocol (출판 전 자동 품질 검수 신설 의무화 원칙)**:
    - **Automated Pre-Publish Quality Interceptor (`audiobook_studio/master_quality_inspector.py`)**:
      모든 번역 워커는 결과물 EPUB을 최종 서재(`소설2/` 및 Google Drive `#Books`)에 배포하기 전에 반드시 **자동 품질 검수기(`inspect_epub_quality`)**를 거쳐야 하며, 아래 5대 검수 게이트를 100% 통과하지 못한 파일은 서재 진입을 원천 차단한다:
      1. 🖼️ **Cover Gate**: 정품 고화질 표지 이미지(`cover.jpeg`, >10KB), 표지 페이지(`000-cover.xhtml`), OPF 메타데이터 완전 탑재.
      2. 📑 **TOC 3-Tier Gate**: `nav.xhtml` & `toc.ncx` XML Well-formedness 100% 무결성 (특수문자 `&` 이스케이프 강제, 최소 3개 이상 정규 챕터 링크).
      3. 🚫 **Zero Untranslated Leak Gate**: 한글 번역 영역(`span.ko`) 내 영문 원문 단순 복사 0건 검증 (100% 순수 완역 보장).
      4. 🎯 **TOEIC 700+ to 990 Vocab Gate**: 중학교 기초 단어 루비 포함 0건, 글자 잘림(Truncation) 0건, Overhead Ruby 표준 준수.
      5. 🛡️ **XML Well-Formedness Gate**: EPUB 내부 모든 XHTML/XML 파일 파서 파싱 에러 0건.
12. **Mandatory 2-Tier Master Dual Inspector Protocol (2인 상호 교차 검수 의무화 무결성 원칙)**:
    - **Tier-1 Master Inspector (`master_quality_inspector.py`)**:
      - 1차 구조, 기본 XML 문법, 표지, 3중 TOC, 1차 기초 단어 소거 및 즉각적 자동 자가치유(Auto-Healing) 수행.
    - **Tier-2 Ultimate Integrity Sentinel (`ultimate_integrity_sentinel.py` - 수석 검수관)**:
      - 제1검수관을 통과한 파일에 대해 단 0.001%의 결함도 허용하지 않는 **6대 무관용 무결성 심층 정밀 검증(Zero-Tolerance Deep Verification)** 집행:
        1. 🔬 **Bi-Text Parity**: 영한 문단 1:1 대칭 및 문장 누락 제로 검증.
        2. 🚫 **Absolute Zero-Leak**: `span.ko` 내 비-한글 원시 영문 잔류 0건 (1건이라도 발견 시 즉시 탈락).
        3. 🎯 **Lexicon Purity**: TOEIC 700+ to 990 엄선 어휘 순도 100%, 말줄임표(`...`) 잘림 0건.
        4. 📑 **TOC-Spine Sync**: `nav.xhtml`, `toc.ncx`, `<spine>` 간 깨진 링크 0건.
        5. 🖼️ **HD Cover Gate**: 고화질 표지(>15KB), `000-cover.xhtml` 및 OPF 속성 100% 선언.
        6. 🛡️ **W3C Strict XML**: EPUB 내부 모든 문서의 엄격한 W3C XML 파싱 에러 0건.
13. **Mandatory 3-Tier Master Visual Inspector Protocol (3인 검수관 팀 시각적 화면 캡처 검수 의무화 원칙)**:
    - **제1검수관: Tier-1 Master Inspector (`master_quality_inspector.py`)**:
      - 1차 구조, 기본 XML 문법, 표지, 3중 TOC, 1차 기초 단어 소거 및 즉각적 자동 자가치유(Auto-Healing) 수행.
    - **제2검수관: Tier-2 Ultimate Integrity Sentinel (`ultimate_integrity_sentinel.py` - 수석 검수관)**:
      - 제1검수관을 통과한 파일에 대해 단 0.001%의 결함도 허용하지 않는 6대 무관용 무결성 심층 정밀 검증(Bi-Text Parity, Absolute Zero-Leak, Lexicon Purity, TOC-Spine Sync, HD Cover, W3C Strict XML) 집행.
    - **제3검수관: Tier-3 Visual Screen Sentinel (`visual_screen_sentinel.py` - 시각적 화면 캡처 검수관)**:
      - 실제 헤드리스 브라우저(Playwright / Chromium)를 기동하여 EPUB 내부의 **최소 10~20개 대표 페이지(표지, 목차, 본문 챕터들, 백마터)를 실제 전자책 뷰포트(800x1200)로 렌더링하고 화면 캡처(Screen Capture)** 검수를 집행:
        1. 🖼️ **Visual Cover Render**: 표지 이미지가 화면에 꽉 차게 정상 렌더링되는지(Collapsed/Broken Image 0건) 시각 검증.
        2. 📑 **Visual TOC & Layout**: 목차 및 네비게이션이 올바른 타이포그래피로 깨짐 없이 렌더링되는지 시각 검증.
        3. 📖 **Visual Ruby Line-Height**: Word Wise 오버헤드 루비가 본문 텍스트와 겹치지 않고 충분한 행간(1.85)으로 시각적 가독성을 확보하는지 검증.
        4. 🚫 **Zero Blank/Broken Resources**: 빈 페이지(Blank Screen) 0건, 로드 실패 리소스(Missing CSS/Image) 0건 검증.
    - **🌟 3-Tier Ultimate Master Digital Seal**: 3인 검수관 팀(제1검수관 + 제2수석검수관 + 제3시각검수관)의 만장일치 인증(100% Unanimous Approval)을 획득한 완벽한 전자책만이 최종 서재에 출판 및 동기화된다.

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
