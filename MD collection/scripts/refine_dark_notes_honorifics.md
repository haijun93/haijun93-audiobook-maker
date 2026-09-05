# refine_dark_notes_honorifics.py

`Dark Notes`(Pam Godwin 저, `~/Desktop/소설2/[k]/#must read/[k] Dark Notes Pam Godwin.epub`)의 한국어 대화 말투(존댓말/반말 일관성)를 교정하는 일회성 스크립트. `refine_artemis_honorifics.py`/`refine_corrupt_honorifics.py`와 같은 "하드코딩된 치환 목록 + dry-run 지원" 패턴이다.

파일: `scripts/refine_dark_notes_honorifics.py`

## CLI

```bash
python3 scripts/refine_dark_notes_honorifics.py \
  [--epub <경로, 기본: Dark Notes 고정 경로>] \
  [--dry-run]
```

실행하면 마지막 줄에 `total_replacements=N` 형태로 요약을 출력한다 — `idle_completed_epub_tone_maintenance.py`가 이 형식을 정규식(`parse_total_replacements`)으로 파싱해, dry-run에서 실제 교체 건수가 0보다 클 때만 진짜로 적용하는 안전장치로 쓴다.

## 관련 문서
- [refine_artemis_honorifics.md](refine_artemis_honorifics.md), [refine_corrupt_honorifics.md](refine_corrupt_honorifics.md) — 같은 패턴
- [idle_completed_epub_tone_maintenance.md](idle_completed_epub_tone_maintenance.md) — 이 스크립트를 자동 연동하는 유지보수 스크립트
