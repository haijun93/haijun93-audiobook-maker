# 도서 자동 수집 & 서재 연동 표준 운영 절차 (SOP)
## (OceanofPDF + ReadRobe.com 듀얼 엔진 & 웹 대시보드 연동)

> **대상**: `haijun93-audiobook-maker` 프로젝트의 모든 AI 엔지니어 및 자동화 시스템

---

## 1. 개요 및 목적
- **목적**: `OceanofPDF` 및 `ReadRobe.com` 2대 원서 사이트에서 특정 작가 또는 키워드로 영문 원서를 교차 검색하고, 서재(`/Users/hyeokjunkong/Desktop/소설2/[e]/`)에 미보유된 도서를 자동으로 식별하여 다운로드한 뒤, ReadRobe/OceanofPDF 워터마크를 제거하고 표준 서재 규격(`[e] {제목} - {작가}.epub`)으로 보관 및 자동 번역 큐에 연동한다.
- **핵심 엔진**: `scripts/book_downloader_engine.py` (통합 엔진), `scripts/remove_readrobe_text_from_epubs.py` (워터마크 스크러버)

---

## 2. 주요 아키텍처 및 프로토콜

### ① 듀얼 소스 교차 탐색 & Fallback
- 1차로 `OceanofPDF`에서 영문 원서를 검색 및 다운로드.
- OceanofPDF에 없거나 링크가 누락된 경우 2차로 `ReadRobe.com`에서 자동 교차 검색하여 누락 없는 완전 수집 달성.

### ② 워터마크 자동 정제 (Watermark Scrubbing)
- 다운로드 완료 즉시 EPUB 내부의 `readrobe.com`, `oceanofpdf.com` 등의 광고 텍스트 및 불필요한 태그를 `scrub_epub()`를 통해 완전 무손실 정제.

### ③ 통합 웹 대시보드 (`http://127.0.0.1:7870`) 실시간 제어
- 대시보드의 **`📚 도서 수집`** 탭에서 작가명/도서명 입력 후 클릭 한 번으로 수집 요청.
- 실시간 수집 상태, 진행률, 다운로드 로그 및 최근 수집 목록을 대시보드에서 실시간 확인 가능.

---

## 3. 실행 가이드

### A. 웹 대시보드 (GUI)
1. 웹 브라우저에서 `http://127.0.0.1:7870` 접속
2. 상단 탭에서 **`📚 도서 수집`** 선택
3. 작가명(`Freida McFadden`) 또는 작품명 입력 후 소스 선택 (`통합 자동 / OceanofPDF / ReadRobe`)
4. **`원서 검색 및 자동 다운로드 시작`** 클릭

### B. CLI 명령어
```bash
# 특정 작가 전체 자동 수집 및 번역 큐 연동
.venv311/bin/python scripts/book_downloader_engine.py --author "Freida McFadden" --auto-queue

# ReadRobe 전용 수집
.venv311/bin/python scripts/book_downloader_engine.py --author "Freida McFadden" --source readrobe
```

---

## 4. 연계 파이프라인
1. **다운로드**: `scripts/download_oceanofpdf.py` → `소설2/[e]/#Author/[e] {Title} - {Author}.epub`
2. **번역 및 학습노트 생성**: `scripts/translate_epub_with_chatgpt_web_to_study_epub.py` → `[k-e]`, `[study]`
3. **파생 에디션 생성**:
   - `scripts/make_korean_only_epubs.py` → `[k]` (한글 전용본)
   - `scripts/make_english_study_epubs.py` → `[e-s]` (영문+토익 학습노트본)
