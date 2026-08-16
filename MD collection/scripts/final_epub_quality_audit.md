# final_epub_quality_audit.py

생성된 학습용 EPUB(`[k-e]` 또는 `[k]`)에 대한 **구조/캐시 무결성 종합 감사**. 톤/대화 검수가 "말투가 자연스러운가"를 보는 것과 달리, 이 스크립트는 "번역 파이프라인이 기술적으로 온전하게 끝났는가"를 확인한다.

파일: `scripts/final_epub_quality_audit.py`
핵심 함수: `run_final_quality_audit()` (CLI에서 직접 부르는 이름은 `main()` 내부에서 호출), 감사 버전 `FINAL_QUALITY_AUDIT_VERSION = 5`

## 확인하는 항목

- **EPUB 구조**: `mimetype`이 첫 항목인지, XML 파싱 오류가 있는지, `nav`/`ncx` 목차 항목 수.
- **잔여 결함 마커**: `[번역 누락]` 표시, `readrobe.com` 워터마크 잔존, 웹 서비스 거절/안전문구 잔여 후보(`count_refusal_markers`).
- **한영 블록 구조** (`kind`별로 다르게 검사):
  - `k-e`(대조본): `ko`/`en` 블록 수가 비슷해야 하고, 최신 span/pair 방식 블록을 찾아야 한다.
  - `k`(한글본): 영어 학습용 마크업(`en`/`pair`)이 남아있으면 안 된다.
- **번역 캐시 대조** (`--work-dir` 제공 시): `source_sections.json`의 원문 블록 ID와 `manifest.json`/캐시 청크 파일을 대조해 누락된 번역 ID, 불완전한 청크, 읽을 수 없는 캐시 JSON을 찾는다. `translation_quality_checks.assess_translations()`로 페어링된 번역 블록의 품질(심각/경고)도 다시 집계한다.
- **최종 톤/대화 검수 결과 연동**: 같은 `work_dir`에 있는 `final_tone_reviews/`, `final_dialogue_reviews_pass2/` 결과의 `status`를 읽어와 이 감사 리포트에도 반영한다(검수 자체를 다시 실행하지는 않음).

`status`는 `issues`가 하나라도 있으면 `needs_attention`, 없으면 `pass`.

## CLI

```bash
python3 scripts/final_epub_quality_audit.py <epub 경로> \
  --kind {k-e,k} \
  --out-dir <리포트 저장 폴더> \
  [--work-dir <번역 작업 디렉터리>] \
  [--source-epub <참고용 원본 epub 경로>]
```

`--work-dir`을 생략하면 캐시 대조와 톤/대화 검수 연동 부분은 건너뛰고 EPUB 자체의 구조 검사만 수행한다.

## 언제 쓰는가

배치 파이프라인(`workflow_runner.py`)은 이 감사를 자동 호출하지 **않는다** — 정상 완료된 책은 곧바로 `done` 처리된다. 이 스크립트는 주로 **수동 재시도/사후 검증** 단계에서, 특정 책의 산출물이 기술적으로 온전한지 사람이 직접 확인하고 싶을 때 실행하는 용도다.

## 관련 문서
- [translate_epub_with_chatgpt_web_to_study_epub.md](translate_epub_with_chatgpt_web_to_study_epub.md)
- [EPUB 번역 품질 검증기 오탐 예외 처리 규칙](../EPUB%20번역%20품질%20검증기%20오탐%20예외%20처리%20규칙.md)
