# Audiobook Maker 세션 인수인계서

기준 일시: 2026-08-16 14:40 KST

---

## 1. 🚀 최종 운영 상태 요약

- **4대 계정 동시 병렬 번역 체계 가동 중**:
  - `main` (Gemini 계정 1, `haijun93@gmail.com`): *Dead of Eve* (82%+ 고속 번역 중)
  - `account2` (Gemini 계정 2, `haijun2be@gmail.com`): *Beneath the Burn* (정상 번역 중)
  - `account3` (Gemini 계정 3, `ngaytot9@gmail.com`): *Dominate* 완역 후 *Heart of Frost and Scars* 큐 배정
  - `chatgpt` (ChatGPT web, `haijun93@gmail.com`): *How to Stop Time* (88%+ 쾌속 번역 중)
- **30분 주기 정기 감사 데몬 (`scripts/check_accounts_and_report.py`) 상시 가동 중**:
  - Background Task (`task-1407`, Cron `*/30 * * * *`)
- **실시간 다크 모드 GUI 대시보드 (`http://127.0.0.1:7870/`) 운영 중**:
  - 시간대별 완역 작품 및 처리 계정, 총 소요 시간(`⏱️ X시간 Y분`) 실시간 표시.
- **macOS Automator 전용 컨트롤러 앱 탑재 완료**:
  - `/Users/hyeokjunkong/Library/Mobile Documents/com~apple~Automator/Documents/오디오북_스튜디오_컨트롤러.app`

---

## 2. 🛠️ 핵심 구현 및 개선 내역 (2026-08-16)

### ① 제미나이 계정 로그인 영구 유지 & 무중단 자가치유 (Self-Healing)
* **원인 분석**:
  - Google의 단기 보안 세션 토큰(`__Secure-1PSIDTS`)이 12~24시간 주기로 만료되나, Playwright 기본 플래그(`--disable-sync`)로 인해 백그라운드 토큰 롤링이 차단되었음.
  - 만료 시 URL 변경 없이 조용히 게스트(비로그인) 모드로 전환되는 문제 발생.
* **해결 조치**:
  - `WEB_CHROME_IGNORED_PLAYWRIGHT_DEFAULT_ARGS`에서 `--disable-sync`, `--disable-component-update` 무시 설정 적용 (`audiobook_maker.py`).
  - `prepare_gemini_web_page()`에 **실시간 쿠키 핫스왑 자가치유(Self-Healing)** 로직 탑재:
    게스트 모드 감지 시 실제 Chrome 프로필(`Profile 1`, `Profile 2`, `Profile 18`)의 최신 쿠키를 즉각 브라우저 메모리에 핫 주입하고 페이지를 새로고침하여 에러 없이 자동 복구.

### ② 서재 4대 에디션 자동화 및 표준 경로 전면 동기화 ([`소설2`](file:///Users/hyeokjunkong/Desktop/%EC%86%8C%EC%84%A42/))
* 임시 폴더(`pam_general_translation`)를 제거하고 `소설2` 표준 서재 디렉터리로 완벽 일원화:
  - `[k]` (한국어 전용본): [`make_korean_only_epubs.py`](file:///Users/hyeokjunkong/Desktop/myproject_python/haijun93-audiobook-maker/scripts/make_korean_only_epubs.py)
  - `[k-e]` (한영 대역본)
  - `[study]` (학습 단어/표현 노트본)
  - `[e-s]` (영어 원문 + 단어 노트본): [`make_english_study_epubs.py`](file:///Users/hyeokjunkong/Desktop/myproject_python/haijun93-audiobook-maker/scripts/make_english_study_epubs.py)
* 서재 전체 278권에 대한 `[e-s]` 에디션 배치 생성 및 배포 완료.

### ③ GUI 대시보드 다크 모드 (Dark Mode) 전면 개편
* `webui/static/app.css` 전면 리팩토링:
  - 딥 슬레이트/차콜 배경(`--background: #0b0f19`, `--card-bg: #1e293b`), 고대비 텍스트(`--ink: #f8fafc`).
  - 네온 시안 & 에메랄드 그린 상태 인디케이터.
  - 시간대별 완료 도서 타임라인 및 소요시간 뱃지 추가.

---

## 3. 📚 오늘 완역 및 라이브러리 배포 완료 도서 (6권)

1. **Dark Notes** (*Pam Godwin 3.92*) 🏆
2. **Lessons in Sin** (*Pam Godwin 3.96*) 🏆
3. **Sea of Ruin** (*Pam Godwin 3.89*) 🏆
4. **Cage of Ice and Echoes** (*Pam Godwin 4.43*) 🏆
5. **Unshackle** (*Pam Godwin 4.22*) 🏆
6. **Dominate** (*Pam Godwin 4.08*) 🏆

---

## 4. 📂 `MD collection` 핵심 업무 규정 및 SOP 현행화 내역

`/Users/hyeokjunkong/Desktop/소설2/MD collection`에 보관된 프로젝트 관리 및 번역 표준 지침의 현행화 내용입니다.

| 문서명 | 주요 내용 및 2026-08-16 현행화 사항 |
| :--- | :--- |
| **`EPUB 영어학습자용 [study] 버전 토익 학습노트 절차.md`** | • `[study]` 및 `[e-s]` 에디션 생성 메커니즘 문서화.<br>• `make_english_study_epubs.py` 공식 파이프라인 승격 및 서재 278권 일괄 생성 반영.<br>• 임시 폴더 없이 `소설2` 4대 표준 폴더 직행 규칙 명시. |
| **`EPUB 배치 번역 중복작업 방지 처리절차.md`** | • 3단계 방어선(파일명 사전 필터 → 서지정보 정규화 퍼지 매칭 → 서재 4대 에디션 직접 스캔) 운영.<br>• 다중 계정 병렬 프로필 락(`.audiobook_web_profile.lock`) 및 계정별 독립 격리 규정 현행화. |
| **`EPUB 번역 품질 검증기 오탐 예외 처리 규칙.md`** | • `is_prose_source()` 기반 서사 본문/라틴어/비영어 오탐 검증기 예외 규칙 관리. |
| **`EPUB 대화체(말투) 검수 작업지시서.md`** | • 캐릭터 말투 일관성, 하오체/하게체 오용 방지 및 사후 검수 스크립트 SOP. |
| **`chatgpt_book_enrichment_sop.md`** | • 소설 수장고 5대 핵심 메타데이터(장르, 발간연도, 10문장 줄거리, 키워드 5개, 평점) 표준 질의 규격. |
| **`README_AI_COLLABORATION_SOP.md`** | • 다른 AI 에이전트 간의 캐시 DB 및 MD collection 1:1 동기화 협업 SOP. |

---

## 5. 📂 주요 코드 및 스크립트 참조

- `audiobook_maker.py`: 백그라운드 토큰 자동 롤링, Self-Healing 쿠키 핫 주입, 게스트 모드 자동 복구.
- `web_app.py`: 완료 타임라인 총 소요 시간(`duration_text`) 계산 및 서재 직접 스캔.
- `webui/static/app.css`, `webui/static/app.js`, `webui/templates/index.html`: 다크 모드 UI, 타임라인 및 계정 뱃지 렌더링.
- `scripts/check_accounts_and_report.py`: 30분 주기 4대 계정 로그인 및 진행 현황 종합 점검 리포터.
- `scripts/make_english_study_epubs.py`: `[study]` 기반 `[e-s]` 생성 스크립트.
- `scripts/desktop_app.py`, `scripts/gui_launcher.py`: 데스크톱 독립형 컨트롤러 및 Always-on-top 창.
