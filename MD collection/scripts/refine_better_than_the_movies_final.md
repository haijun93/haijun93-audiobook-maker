# refine_better_than_the_movies_final.py

`Better Than the Movies`의 한국어 번역에 대해, **사람(또는 AI 리뷰어)이 이미 문맥을 검토해 확정한** 교정 목록(`REVISIONS`)을 적용하고 그 검토 근거를 리포트로 남기는 스크립트. 단순 치환기가 아니라 "이미 끝난 수동 QA 결과를 코드/캐시/리포트에 반영"하는 마무리 단계에 가깝다.

파일: `scripts/refine_better_than_the_movies_final.py`

## 다른 honorifics 교정기와의 차이

- `REVISIONS`의 각 항목이 파일/문단 인덱스(`pair_index`)와 함께 **왜 고치는지(`reason`)** 를 명시적으로 담고 있다.
- 적용 후 `write_validation_report()`가 등장인물별 존댓말/반말 일관성, 임베디드 인용문, 헌사·감사의 글 등을 **문맥상 검토했다는 근거**를 담은 상세 검증 리포트(`manual_final_validation/better_than_the_movies_final_validation.md`)를 생성한다 — 나중에 "왜 이렇게 판단했는지" 되짚어볼 수 있게 한다.
- `synchronize_cache()`로 `[k-e]` EPUB뿐 아니라 **번역 캐시(chunk json)까지 같은 내용으로 동기화**한다 — 그래야 이후 그 책의 work_dir을 재사용해 무언가 재실행해도 교정 이전 캐시로 되돌아가지 않는다.
- 영문 원문 다이제스트(`digest_before == digest_after`)를 비교해 **영어 쪽 텍스트는 건드리지 않았음을 자체 검증**한다.

## CLI

```bash
python3 scripts/refine_better_than_the_movies_final.py \
  [--k-e-epub ...] [--k-epub ...] [--work-dir ...] \
  [--apply]
```

`--apply` 없이 실행하면 적용 대기 중인 항목과 이미 적용된 항목만 JSON으로 보여주고 아무것도 바꾸지 않는다(`inspect_targets`). `--apply`를 줘야 실제로 `[k-e]`를 다시 쓰고 `[k]`를 재생성하며 캐시를 동기화한다.

## 패턴으로서의 가치

"자동 검수(톤/대화 검사)가 지적한 항목을 사람이 하나하나 문맥 검토해서 확정 → 그 근거를 리포트로 남기고 → EPUB과 캐시를 함께 동기화"하는 이 흐름은, 자동 교정기(`refine_artemis_honorifics.py` 계열)로는 부족한 **미묘한 판단이 필요한 교정**에 적용할 수 있는 더 신중한 템플릿이다.

## 관련 문서
- [refine_lessons_in_sin_honorifics.md](refine_lessons_in_sin_honorifics.md) — Gemini 웹을 이용해 검토 자체를 자동화한 사례
- [make_korean_only_epubs.md](make_korean_only_epubs.md)
