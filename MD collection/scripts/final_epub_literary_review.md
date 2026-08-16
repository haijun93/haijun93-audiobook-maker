# final_epub_literary_review.py

한글 번역문의 **문장 완성도/직역투(translationese)** 를 점검하는 독립 검수 스크립트. 존댓말/반말 일관성(톤 검사)이 아니라, "한국어 소설 문장으로서 자연스러운가"에 초점을 둔다.

파일: `scripts/final_epub_literary_review.py`
핵심 함수: `review_epub_literary_style()`

## 확인하는 항목

- **서술문에 섞인 존댓말** (`NARRATIVE_POLITE_RE`): 대사가 아닌 나레이션(지문)에 `~요/~습니다/~예요` 종결이 남아있는가 (대사는 `extract_dialogues()`로 먼저 제외하고 나머지만 검사).
- **어미 결합 오류** (`MALFORMED_ENDING_RE`): `습니다요`, `입니다다`처럼 두 종결어미가 겹쳐 붙은 명백한 오류.
- **이중 피동** (`DOUBLE_PASSIVE_RE`): `되어졌다`, `보여졌다`처럼 피동이 두 번 겹친 번역투.
- **직역투 패턴** (`TRANSLATIONESE_PATTERNS`): `~에 의해`, `~것이었다`, `그것은/그것이`, `~에 관하여` 등 영어 구문을 그대로 옮긴 흔적.
- **미번역 영문 잔존**, **반복된 긴 블록**(같은 번역이 여러 블록에 중복 등장), **잔여 결함 마커**(`RESIDUE_MARKERS`: `readrobe.com`, `[번역 누락]`, `content_refusal` 등).

각 항목은 카테고리별 발생 건수와 실제 발췌 샘플(카테고리당 최대 10건, `LiterarySample`)로 리포트된다.

## CLI

```bash
python3 scripts/final_epub_literary_review.py <epub 경로> \
  --kind {k-e,k} \
  --out-dir <리포트 저장 폴더>
```

`final_epub_tone_review.py`의 `extract_dialogues`/`iter_korean_blocks`/`read_metadata`/`safe_slug`를 그대로 재사용한다(중복 구현 없음).

## 언제 쓰는가

배치 파이프라인(`translate_epub_with_chatgpt_web_to_study_epub.py`)이 자동 호출하는 4종 최종 검수(톤/대화/용어/형식)에는 **포함되어 있지 않다.** 완성된 책의 문장 완성도를 별도로 더 깊이 점검하고 싶을 때 수동으로 실행하는 보조 검수 도구다.

## 관련 문서
- [EPUB 대화체(말투) 검수 작업지시서](../EPUB%20대화체(말투)%20검수%20작업지시서.md)
- [final_epub_tone_review.md](final_epub_tone_review.md)
