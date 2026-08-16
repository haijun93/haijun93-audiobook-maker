# AI Agent Master Architecture & Operations SOP
*Last Updated: 2026-08-16 14:42 KST*

본 문서는 향후 어떤 AI 에이전트(ChatGPT, Claude, Gemini, Cursor, Codex 등)나 새로운 개발자가 프로젝트 작업을 이어받더라도 **100% 동일한 품질과 연속성**으로 시스템을 운영하고 확장할 수 있도록 작성된 최상위 표준 기술 명세서(Master Architecture & SOP)입니다.

---

## 1. 🌐 시스템 개요 및 기술 스택 (System Overview)

* **저장소 루트**: `/Users/hyeokjunkong/Desktop/myproject_python/haijun93-audiobook-maker`
* **표준 서재 저장소**: `/Users/hyeokjunkong/Desktop/소설2`
* **Python 런타임**: Python 3.11 (`.venv311/bin/python`)
* **핵심 엔진**:
  - `Playwright Sync API` + macOS 공식 Google Chrome (`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`)
  - `Flask` + Server-Sent Events (SSE) 실시간 웹 대시보드 (`web_app.py`, Port 7870)
  - `pywebview` Cocoa 기반 데스크톱 Always-on-top GUI 창 (`scripts/desktop_app.py`)
  - `Edge-TTS` 한국어 신경망 성우 음성 합성 (`edge_tts`)
  - `lxml` / `BeautifulSoup4` EPUB 파싱 및 구조적 재조립

---

## 2. ⚡ 4대 계정 병렬 번역 아키텍처 (Multi-Account Parallel Engine)

각 계정은 독립된 영구 브라우저 프로필 디렉터리를 사용하며 프로세스 락(`.audiobook_web_profile.lock`)을 통해 동시성 충돌을 방지합니다:

| 계정 식별자 | 공급자 | 구글/OpenAI 로그인 계정 | 영구 프로필 디렉터리 | Chrome 쿠키 부트스트랩 원본 |
|:---:|:---:|:---:|:---:|:---:|
| **`main`** | Gemini Web | `haijun93@gmail.com` | `~/Library/Application Support/AudiobookStudio/browser_profiles/gemini` | `Profile 1/Cookies` |
| **`account2`** | Gemini Web | `haijun2be@gmail.com` | `~/Library/Application Support/AudiobookStudio-account2/browser_profiles/gemini` | `Profile 2/Cookies` |
| **`account3`** | Gemini Web | `ngaytot9@gmail.com` | `~/Library/Application Support/AudiobookStudio-account3/browser_profiles/gemini` | `Profile 18/Cookies` |
| **`chatgpt`** | ChatGPT Web | `haijun93@gmail.com` | `~/Library/Application Support/AudiobookStudio-chatgpt/browser_profiles/chatgpt` | `Profile 1/Cookies` |

---

## 3. 🛡️ 세션 영구 유지 & 무중단 자가치유 (Self-Healing Hot-Injection)

1. **Google 백그라운드 토큰 자동 롤링**:
   - `audiobook_maker.py`의 `WEB_CHROME_IGNORED_PLAYWRIGHT_DEFAULT_ARGS`에서 `--disable-sync`, `--disable-component-update`를 무시 목록에 등록하여 일반 Chrome의 토큰 갱신 데몬이 `__Secure-1PSIDTS` 토큰을 계속 연장하도록 보장합니다.
2. **실시간 쿠키 핫스왑 자가치유 (`prepare_gemini_web_page`)**:
   - 번역 도중 일시적인 세션 만료나 게스트 모드가 감지되면, 작업 에러를 내지 않고 즉시 해당 계정의 실제 Chrome 프로필(`Profile 1, 2, 18`)에서 최신 쿠키를 캡처하여 Playwright 브라우저 메모리에 핫 주입(`context.add_cookies`)하고 새로고침하여 2초 내로 무인 자동 복구합니다.
3. **30분 주기 정기 감사 (`scripts/check_accounts_and_report.py`)**:
   - 백그라운드 Cron(`task-1407`)이 30분마다 4개 계정의 로그인 상태와 도서별 청크 진행률을 자동 감사하여 리포트를 생성합니다.

---

## 4. 📚 4대 표준 에디션 라이브러리 파이프라인 (`소설2`)

배치 번역을 거친 모든 도서는 반드시 `/Users/hyeokjunkong/Desktop/소설2/`의 4대 표준 폴더 내 작가별 하위 디렉터리(예: `#Pam Godwin`)로 즉시 자동 분류 저장되어야 합니다:

```
/Users/hyeokjunkong/Desktop/소설2/
├── [k]/              # 1. 한국어 전용본 (make_korean_only_epubs.py로 생성)
│   └── #작가명/
├── [k-e]/            # 2. 한영 대역본 (번역 워커가 직접 생성)
│   └── #작가명/
├── [study]/          # 3. 토익 700+ 어휘/구동사 학습노트본 (번역 워커가 생성)
│   └── #작가명/
└── [e-s]/            # 4. 영어 원문 + 학습노트본 (make_english_study_epubs.py로 생성)
    └── #작가명/
```

> **규칙**: 임시 하위 폴더(예: `pam_general_translation`)를 만들지 않고 반드시 4대 표준 서재 루트로 직행 배치합니다.

---

## 5. 💻 필수 CLI 명령어 총람 (CLI Command Cheatsheet)

### 1) 대시보드 및 컨트롤러 실행
```bash
# 다크 모드 웹 대시보드 서버 (백그라운드 포트 7870)
.venv311/bin/python web_app.py --port 7870

# 데스크톱 Always-on-top GUI 창
.venv311/bin/python scripts/desktop_app.py

# 4버튼 Automator 컨트롤러 앱
.venv311/bin/python scripts/gui_launcher.py
```

### 2) 서재 후처리 및 에디션 생성
```bash
# [k] 한국어 전용본 생성
.venv311/bin/python scripts/make_korean_only_epubs.py "/Users/hyeokjunkong/Desktop/소설2/[k-e]/#Author" --overwrite

# [e-s] 영어 원문 + 학습노트본 생성
.venv311/bin/python scripts/make_english_study_epubs.py "/Users/hyeokjunkong/Desktop/소설2/[study]/#Author" --output-root "/Users/hyeokjunkong/Desktop/소설2/[e-s]/#Author" --overwrite
```

### 3) 30분 정기 계정 감사 및 리포트
```bash
.venv311/bin/python scripts/check_accounts_and_report.py
```

---

## 6. 🔄 AI 에이전트 인수인계 및 협업 수칙

1. 모든 Python 명령어는 반드시 `.venv311/bin/python`으로 실행합니다.
2. 새 작업이나 버그 수정 완료 시 반드시 `docs/SESSION_HANDOFF_YYYYMMDD.md` 및 `/Users/hyeokjunkong/Desktop/소설2/MD collection/` 문서를 현행화한 후 커밋 및 푸시합니다.
3. 단위 테스트는 `.venv311/bin/pytest tests/test_epub_integrity.py tests/test_web_app.py`로 검증합니다.
