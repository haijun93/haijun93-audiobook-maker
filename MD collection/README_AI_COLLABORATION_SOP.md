# TED 100-Talk EPUB Translation & Collaboration Standard Operating Procedure (SOP)
*Last Updated: 2026-08-08 16:02:38*

본 문서는 다른 AI agent 및 번역 작업자가 프로젝트 현황을 완벽히 파악하고, 일관된 스타일 및 규칙에 따라 협업하기 위해 작성된 최상위 작업 지시서 및 현황판입니다.

---

## 1. 프로젝트 주요 현황 (Project Status Summary)
- **프로젝트명**: TED Top 100 Talk Master Transcript Collection EPUB Translation
- **캐시 데이터 베이스**: `/Users/hyeokjunkong/.gemini/antigravity/scratch/gemma4_100talks_cache.json`
- **생성된 EPUB 최종본**:
  - `[e]TED_Master_Transcript_Collection_EN_Only.epub` (영어 원문 - 98강연)
  - `[k]TED_Master_Transcript_Collection_KO_Only.epub` (한글 대화체 번역 - 98강연)
  - `[k-e]TED_Master_Transcript_Collection_EN_KO_Bilingual.epub` (한영 병기 대화체 - 98강연)
- **저장 위치**: `/Users/hyeokjunkong/Desktop/소설2/[s]/`

---

## 2. 다른 AI와의 협업 및 작업 규칙 (AI Collaboration Rules)

1. **MD Collection 필수 동기화 규칙**
   - 모든 번역 텍스트 수정, 스타일 변경, 검수 작업이 일어날 때마다 반드시 `/Users/hyeokjunkong/Desktop/소설2/MD collection/` 폴더 내 문서 및 `TED_Translation_Style_Guide` 개별 강연 MD를 즉시 동기화 업데이트합니다.
   - 캐시(`gemma4_100talks_cache.json`)와 MD collection 문서는 언제나 1:1로 일치해야 합니다.

2. **대화체(말투) 표준 유지**
   - 기본 어조: 격식 구어체 (`~합니다`, `~입니다`)와 친근한 유도체 (`~일까요?`, `~해보세요`)의 조화.
   - 불필요한 메타데이터 제거: `(Laughter)`, `(Applause)`, `[00:00]` 타임스탬프 등 무조건 제거.

3. **작업 이력 관리**
   - 새로운 강연 추가, 번역 수정 시 본 `README_AI_COLLABORATION_SOP.md` 파일의 변경 이력(Change Log) 섹션에 기록합니다.

---

## 3. 자동 동기화 및 유지관리 스크립트 안내

- **자동 동기화 스크립트**: `/Users/hyeokjunkong/.gemini/antigravity/scratch/sync_md_collection.py`
- 본 스크립트는 캐시 변경 사항 및 EPUB 재빌드 발생 시 MD collection 폴더 전체를 정기적/자동으로 갱신합니다.
