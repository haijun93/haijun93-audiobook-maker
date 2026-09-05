# build_yale_oyc_sentence_inline_epub.py

Open Yale Courses(OYC)의 강의 한 개(기본값: ECON 159 2강, `https://oyc.yale.edu/economics/econ-159/lecture-2`) 웹페이지에서 강의록(transcript)을 직접 가져와, 문장 단위로 영어 원문과 한국어 번역을 나란히 배치한 EPUB을 만드는 스크립트. `build_ted_sentence_inline_study_epub.py`와 같은 "문장 인라인" 레이아웃 아이디어를 Yale 강의록에 적용한 버전이다.

파일: `scripts/build_yale_oyc_sentence_inline_epub.py`

## CLI

```bash
python3 scripts/build_yale_oyc_sentence_inline_epub.py \
  --url https://oyc.yale.edu/economics/econ-159/lecture-2 \
  --output <출력 epub> --work-dir <작업 디렉터리> \
  --model gemma4:26b --ollama-url http://127.0.0.1:11434/api/generate \
  --max-chars 7000 --timeout 1200 \
  [--skip-translation] [--limit N(챕터 수 제한)]
```

## 다른 Yale 스크립트와의 관계

이 스크립트는 강의 **한 개**만 대상으로 하는 독립 실행형이다. 강의 전체 코스를 한 번에 만들려면 [build_yale_oyc_game_theory_course_epub.py](build_yale_oyc_game_theory_course_epub.md)(ECON 159 전 강의)나 [build_yale_oyc_all_courses_epubs.py](build_yale_oyc_all_courses_epubs.md)(OYC 전체 코스)를 쓴다.

## 관련 문서
- [build_yale_oyc_game_theory_course_epub.md](build_yale_oyc_game_theory_course_epub.md)
- [build_yale_oyc_all_courses_epubs.md](build_yale_oyc_all_courses_epubs.md)
- [build_ted_sentence_inline_study_epub.md](build_ted_sentence_inline_study_epub.md) — 같은 레이아웃 아이디어를 TED 강연에 적용한 버전
