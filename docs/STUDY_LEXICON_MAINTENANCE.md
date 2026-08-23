# Master Study Lexicon Maintenance Guide (215,000+ Entries)

> **문서 버전**: 1.0 (2026-08-17)  
> **사전 저장 위치**:  
> 1. 프로젝트 내부: `data/master_study_lexicon.json`  
> 2. 로컬 서재: `/Users/hyeokjunkong/Desktop/소설2/MD collection/master_study_lexicon.json`  
> 3. Google Drive: `/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books/MD collection/master_study_lexicon.json`

---

## 1. 개요 및 목적

`master_study_lexicon.json`은 320여 권의 방대한 완역 전자책(`Sea of Ruin`, `Dark Notes`, `Cage of Ice and Echoes`, `The Silent Patient` 등)에서 추출된 **215,786개 이상의 고품질 TOEIC 700+ 어휘, 고급 콜로케이션, 이디엄 및 문맥 기반 한국어 뜻풀이**를 영구 보관하고 실시간으로 확장하는 마스터 사전 데이터베이스입니다.

---

## 2. 자동 수집 및 증분 업데이트 파이프라인

- **실행 스크립트**: `.venv311/bin/python scripts/update_master_study_lexicon.py`
- **트리거 시점**:
  1. **30분 주기 자동 감사 (`scripts/check_accounts_and_report.py`)**: 30분마다 신규 완역 도서가 감지되면 백그라운드에서 자동 증분 병합.
  2. **신규 도서 완역 및 입고 훅**: 웹 LLM 워커가 신규 도서 완역 후 서재에 저장할 때 자동 실행.
  3. **수동 CLI 실행**: 언제든지 터미널에서 즉시 실행 가능.

---

## 3. 사전 활용 원칙

1. **학습 노트 누락 도서 복구**:
   - 구버전 도서나 학습 정보가 누락된 도서가 발견되면 마스터 사전을 활용하여 수초 내에 9,000단락 이상의 고품질 학습 노트를 일괄 주입 복구.
2. **번역 엔진 일관성 유지**:
   - 동일 작가 및 시리즈 내에서 주요 전문 용어, 관용 표현의 일관된 한국어 번역 유지.
3. **3곳 상시 미러 동기화**:
   - 사전이 갱신될 때마다 프로젝트 `data/`, 로컬 `소설2/MD collection/`, Google Drive `#Books/MD collection/` 3곳에 원자적으로 자동 저장.
