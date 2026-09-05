# final_epub_tone_review.py

한영 대조/한글 EPUB의 **전체 톤(존댓말/반말 일관성) 1차 검사**를 수행하는 스크립트. 이 스크립트의 사용법과 판정 기준에 대한 상세 작업지시서는 이미 별도 문서로 존재한다.

파일: `scripts/final_epub_tone_review.py`
핵심 함수: `review_epub_tone()`

**자세한 절차·판정 기준·리포트 읽는 법은 [EPUB 대화체(말투) 검수 작업지시서](../EPUB%20대화체(말투)%20검수%20작업지시서.md)의 "1단계 — 전체 톤 검사 (pass 1)" 섹션을 참고.** 이 문서에서는 CLI/연동 관계만 보충한다.

## CLI

```bash
python3 scripts/final_epub_tone_review.py <epub 경로> \
  --relationship-guide <work_dir>/relationship_guide.txt \
  --out-dir <work_dir>/final_tone_reviews \
  --kind k-e
```

## 파이프라인 연동

- `translate_epub_with_chatgpt_web_to_study_epub.py`의 `main()`이 `[k-e]` EPUB 생성 직후 자동 호출한다(`--skip-final-tone-review`로 끌 수 있음).
- `final_epub_quality_audit.py`가 이 스크립트의 결과(`final_tone_reviews/*_latest.json`)를 읽어 종합 감사 리포트에 반영한다.
- 인물관계/말투 가이드(`relationship_guide.txt`)가 없으면 근거 부족으로 항상 `needs_attention` 판정.

## 관련 문서
- [EPUB 대화체(말투) 검수 작업지시서](../EPUB%20대화체(말투)%20검수%20작업지시서.md)
- [final_epub_dialogue_consistency_review.md](final_epub_dialogue_consistency_review.md) — 독립적인 2차 검사
- [final_epub_quality_audit.md](final_epub_quality_audit.md)
