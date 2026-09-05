# build_ted_link_learning_epub.py

TED 강연 10개를 엄선해, 각 강연의 주제/발표자/요약(한/영)/어휘/표현/질문거리를 코드 안에 직접 정리해둔 `TALKS` 데이터셋으로부터 영어 학습용 EPUB(`TED_Link_Based_English_Learning_10_Talks.epub`)을 만드는 스크립트. 실제 강연 대본을 실시간으로 가져오거나 번역하지 않고, **미리 정리된 요약/어휘 콘텐츠를 EPUB으로 조립**만 한다.

파일: `scripts/build_ted_link_learning_epub.py`

## 특징

- CLI 인자가 없다(`argparse` 미사용) — 실행하면 항상 같은 고정 산출물(`.work/TED_Link_Based_English_Learning_10_Talks.epub`)을 만든다.
- 각 `Talk`는 주제, 제목, 발표자, 행사, 날짜, 조회수, 원본 URL, 학습 초점(`focus`), 난이도(`level`), 한국어/영어 요약, 어휘 3종 세트, 표현, 강연 전/후 질문, 대조 학습 문장 쌍(`study_pairs`)을 담는다 — 실제 대본 번역이 아니라 **강연 링크와 함께 보는 보조 학습자료**에 가깝다.

## CLI

```bash
python3 scripts/build_ted_link_learning_epub.py
```

## 관련 문서
- [build_ted_transcript_study_epub.md](build_ted_transcript_study_epub.md), [build_ted_sentence_inline_study_epub.md](build_ted_sentence_inline_study_epub.md) — 실제 대본을 가져와 문장 단위로 번역하는 다른 두 TED 스크립트와는 접근 방식이 다르다(이 스크립트는 요약/링크 중심)
