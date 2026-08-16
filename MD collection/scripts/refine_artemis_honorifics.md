# refine_artemis_honorifics.py

책 한 권(`Artemis`, 구 서재 `~/Desktop/소설/#[k-e]/[k-e] Artemis.epub`)의 특정 대사들에 대해 **하드코딩된 문자열 찾기/바꾸기 목록**(`REPLACEMENTS: dict[파일경로, list[(원문, 교정문)]]`)을 적용해 반말→존댓말 등 말투를 수동 교정하는 일회성 스크립트.

파일: `scripts/refine_artemis_honorifics.py`

## 동작

- `REPLACEMENTS`에 정의된 `(찾을 문자열, 바꿀 문자열)` 쌍을 챕터 파일별로 정확히 매칭해 치환.
- 적용 전 원본을 `_batch_logs/[k-e] Artemis.before_honorific_refine.epub`으로 백업.
- `[k-e]` 교정 후 `make_korean_only_epubs.convert_epub()`을 다시 호출해 `[k]` 파생본도 함께 갱신.

## 이 스크립트를 어떻게 쓰는가 (패턴으로서의 가치)

CLI 인자가 없다 — 실행하면 무조건 `Artemis` 한 권에 미리 정해둔 교정을 적용한다. **다른 책에 그대로 쓸 수 없다.** 하지만 "톤 검수에서 특정 대사의 존댓말/반말이 어색하다고 나왔을 때, 정확한 문자열 매칭으로 그 대사만 콕 집어 고치고 `[k]`까지 재생성한다"는 **패턴 자체**는 다른 책에도 재사용 가치가 있다 — 실제로 `refine_corrupt_honorifics.py`, `refine_dark_notes_honorifics.py`가 같은 패턴을 각자의 책에 적용한 예다.

## 관련 문서
- [refine_corrupt_honorifics.md](refine_corrupt_honorifics.md), [refine_dark_notes_honorifics.md](refine_dark_notes_honorifics.md) — 같은 패턴의 다른 책 적용 사례
- [idle_completed_epub_tone_maintenance.md](idle_completed_epub_tone_maintenance.md) — 이런 책별 교정기를 "알려진 안전 교정기"로 자동 연동하는 유지보수 스크립트
- [make_korean_only_epubs.md](make_korean_only_epubs.md)
