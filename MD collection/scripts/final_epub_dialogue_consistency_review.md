# final_epub_dialogue_consistency_review.py

한영 대조/한글 EPUB의 **국소 대화 일관성 2차 검사**(인접 대사 간 말투 급변 탐지 등)를 수행하는 스크립트. 1차 톤 검사와 완전히 독립적으로 실행되며, 상세 절차는 이미 별도 문서로 존재한다.

파일: `scripts/final_epub_dialogue_consistency_review.py`
핵심 함수: `review_dialogue_consistency()`

**자세한 절차·판정 기준·리포트 읽는 법은 [EPUB 대화체(말투) 검수 작업지시서](../EPUB%20대화체(말투)%20검수%20작업지시서.md)의 "2단계 — 국소 대화 일관성 검사 (pass 2)" 섹션을 참고.**

## CLI

```bash
python3 scripts/final_epub_dialogue_consistency_review.py <epub 경로> \
  --relationship-guide <work_dir>/relationship_guide.txt \
  --out-dir <work_dir>/final_dialogue_reviews_pass2 \
  --kind k-e
```

## 파이프라인 연동

- `translate_epub_with_chatgpt_web_to_study_epub.py`의 `main()`이 톤 검사 직후 자동으로 이어서 호출한다.
- `final_epub_quality_audit.py`가 이 결과도 함께 종합 감사에 반영한다.
- `tests/test_final_epub_dialogue_consistency_review.py`에 회귀 테스트가 있다 — 판정 로직을 수정하면 이 테스트를 먼저 통과시킨다.

## 관련 문서
- [EPUB 대화체(말투) 검수 작업지시서](../EPUB%20대화체(말투)%20검수%20작업지시서.md)
- [final_epub_tone_review.md](final_epub_tone_review.md) — 독립적인 1차 검사
