# convert_artemis_inline_to_span.py

책 한 권(`Artemis`, 구 서재 `~/Desktop/소설/#[k-e]/[k-e] Artemis.epub`)을 위한 **일회성 마이그레이션 스크립트**. 예전 방식인 "괄호 속 영어 병기"(`한국어 문장 (English sentence)`) 형식으로 만들어진 문단을, 지금 파이프라인이 쓰는 구조화된 `<span class="ko">`/`<span class="en">` 대조 쌍 형식으로 변환한다.

파일: `scripts/convert_artemis_inline_to_span.py`

## 동작

- `<p>` 태그 안 텍스트 끝의 괄호 쌍(중첩 괄호 깊이 추적)을 찾아 한국어/영어 부분으로 분리(`split_inline_pair`, 실패 시 `split_inline_pair_fallback`으로 대체 시도).
- 분리에 성공하면 `class="pair"` 문단 + `class="ko"`/`class="en"` span 구조로 다시 작성.
- 실행 전 `--backup-dir`(기본 `~/Desktop/소설/#[k-e]/_batch_logs`)에 원본을 백업.

## CLI

```bash
python3 scripts/convert_artemis_inline_to_span.py \
  [--epub <경로, 기본: Artemis 고정 경로>] \
  [--backup-dir <백업 폴더>]
```

## 다른 책에도 쓸 수 있는가

기본 경로가 `Artemis` 한 권으로 고정되어 있을 뿐, 변환 로직 자체(`split_inline_pair` 등)는 일반적인 "괄호 병기 → span/pair 구조" 변환이라 `--epub`으로 다른 파일을 지정하면 비슷한 구조의 다른 책에도 적용할 수 있다. 다만 검증되지 않은 책에 쓸 때는 반드시 백업 후 결과를 직접 확인한다. `make_korean_only_epubs.py`의 `uses_structured_pairs()`가 바로 이 신/구 형식 차이를 자동 판별해주므로, 대부분의 최신 책은 이 변환이 필요 없다.

## 관련 문서
- [make_korean_only_epubs.md](make_korean_only_epubs.md)
