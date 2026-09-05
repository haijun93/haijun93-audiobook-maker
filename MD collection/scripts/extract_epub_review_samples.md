# extract_epub_review_samples.py

`audit_translated_epubs.py`가 만든 감사 JSON을 입력받아, 사람이 눈으로 훑어보기 좋은 **발췌 샘플 리포트**(대화 존댓말/반말 표본, 괄호 속 영어 잔존 후보)를 마크다운으로 만드는 보조 스크립트. 기본 대상 폴더도 `audit_translated_epubs.py`와 같은 구(舊) 서재(`~/Desktop/소설/#[k-e]`)다.

파일: `scripts/extract_epub_review_samples.py`

## CLI

```bash
python3 scripts/extract_epub_review_samples.py [폴더(기본: ~/Desktop/소설/#[k-e])] \
  --out-dir <출력 폴더(기본: .work)> \
  [--audit-json <audit_translated_epubs.py가 만든 JSON, 생략 시 out-dir에서 가장 최신 것 자동 사용>] \
  --max-each 6 --guide-chars 900
```

책마다 존댓말(`polite`)/반말(`casual`)/기타(`other`)/위험(`risk`) 대사 건수와 실제 표본 문장, `[k]` 괄호 속 영어 잔존 후보 문장을 뽑아 `epub_review_samples_<타임스탬프>.md`로 저장한다.

## 지금도 유효한가

`audit_translated_epubs.py`와 마찬가지로 구 서재(`소설/#[k-e]`) 전용이다. **현재 `소설2` 서재의 동등한 역할은 `final_epub_tone_review.py`/`final_epub_literary_review.py`가 각 책마다 만드는 리포트의 "Samples" 섹션이 대신한다.**

## 관련 문서
- [audit_translated_epubs.md](audit_translated_epubs.md)
- [final_epub_tone_review.md](final_epub_tone_review.md)
