# idle_completed_epub_tone_maintenance.py

"웹 번역 서비스 재시도 대기 시간(idle time)"을 활용해, 이미 완료된 `[k-e]`/`[k]` EPUB들을 돌아보며 검수를 다시 실행하고 **안전하다고 알려진 범위 안에서만** 자동 교정을 적용하는 유지보수 스크립트.

파일: `scripts/idle_completed_epub_tone_maintenance.py`

## 동작 순서

1. **후보 발견** (`discover_candidates`): `소설2/[k-e]`, `소설2/[k]` 아래 모든 EPUB을 훑고, `_chatgpt_translate_work/**/manifest.json`으로부터 만든 "작업 가이드" 목록(`work_guides`)과 파일명/제목 유사도로 매칭(`match_guide`)해 각 EPUB에 원래 작업 디렉터리(`relationship_guide.txt` 포함)를 연결한다. 매칭되는 작업 디렉터리를 못 찾으면 `_completed_epub_reviews/<slug>/`에 새 폴백 디렉터리를 만든다.
2. **재검수 필요 여부 판단** (`needs_review`): 다음 중 하나라도 해당하면 재검수 대상.
   - 톤/대화2차/문예/품질 4종 리뷰 결과 파일이 아예 없거나, EPUB 파일보다 더 오래됐다(EPUB이 그 후 갱신됨).
   - 품질 감사 버전(`audit_version`)이 4 미만(과거 버전 감사라 재감사 필요).
   - 톤 검수가 `needs_attention`이면서, 그 책에 **알려진 안전 교정기가 적용 가능한 경우**(아래).
3. **알려진 안전 교정기 적용** (`known_safe_refiner_applies` → `run_known_safe_refiner`): 지금은 딱 두 책에 대해서만 하드코딩되어 있다.
   - 제목에 `"dark notes"`+저자 `"pam godwin"` → [`refine_dark_notes_honorifics.py`](refine_dark_notes_honorifics.md)를 먼저 `--dry-run`으로 돌려 실제 교체 건수(`total_replacements=N`)가 있을 때만 진짜로 적용.
   - 제목에 `"corrupt"`+저자 `"penelope"`/`"douglas"` → [`refine_corrupt_honorifics.py`](refine_corrupt_honorifics.md)도 동일하게 dry-run 먼저 확인 후 적용.
   - 그 외 책은 이 자동교정 대상이 아니며, 검수만 다시 돌리고 결과를 리포트에 남긴다.
4. 처리 결과를 `_completed_epub_reviews/`(혹은 매칭된 작업 디렉터리) 아래 실행 리포트로 남기고, 아직 처리하지 못한 후보 목록(`write_pending_queue`)과 진행 상황(`write_live_progress`)도 기록한다.

## CLI

```bash
python3 scripts/idle_completed_epub_tone_maintenance.py \
  --source-dir ~/Desktop/소설2 \
  --max-files 40 \
  --time-budget-sec 600 \
  [--force]
```

`--time-budget-sec`(기본 600초)를 넘기면 남은 후보는 다음 실행으로 미룬다 — 원래 취지대로 "짧게 남는 유휴 시간에 조금씩" 돌리기 위한 설계다. `--force`는 재검수 필요 여부 판단을 무시하고 전부 다시 검수한다.

## 언제 쓰는가

`run_soseol2_chatgpt_k_e_batch.py`(레거시 CLI 배치)가 배치 실행 사이 유휴 시간에 자동으로 연동하도록 설계되어 있다. 현재 웹 UI 배치 엔진(`workflow_runner.py`)에서는 자동 호출되지 않으므로, 완료된 서재 전체를 정기적으로 점검하고 싶을 때 수동으로 실행하는 유지보수 도구로 쓴다.

## 관련 문서
- [run_soseol2_chatgpt_k_e_batch.md](run_soseol2_chatgpt_k_e_batch.md)
- [refine_dark_notes_honorifics.md](refine_dark_notes_honorifics.md)
- [refine_corrupt_honorifics.md](refine_corrupt_honorifics.md)
- [final_epub_tone_review.md](final_epub_tone_review.md), [final_epub_dialogue_consistency_review.md](final_epub_dialogue_consistency_review.md), [final_epub_literary_review.md](final_epub_literary_review.md), [final_epub_quality_audit.md](final_epub_quality_audit.md)
