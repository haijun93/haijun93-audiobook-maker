# build_yale_oyc_game_theory_course_epub.py

Open Yale Courses의 `ECON 159 Game Theory` 코스 전체(강의 1~24강 + 시험)를 웹에서 가져와 한 권의 문장 인라인 영한 대조 EPUB으로 만드는 스크립트. 이 파일이 정의한 `Section`/`Session`, `fetch_text`/`extract_lecture_sections`/`sentence_items_from_paragraphs`/`translate_session` 등은 [build_yale_oyc_all_courses_epubs.py](build_yale_oyc_all_courses_epubs.md)가 그대로 임포트해서 재사용하는 **기반 모듈**이다.

파일: `scripts/build_yale_oyc_game_theory_course_epub.py`

## CLI

```bash
python3 scripts/build_yale_oyc_game_theory_course_epub.py \
  --course-url https://oyc.yale.edu/economics/econ-159 \
  --output <출력 epub> --work-dir <작업 디렉터리> \
  --max-chars 4200 \
  [--limit N(세션 수 제한, 테스트용)] [--skip-translation]
```

`--limit`을 지정하지 않으면 코스 전체(강의+시험)를 순서대로 가져와 한 EPUB에 담는다.

## 관련 문서
- [build_yale_oyc_all_courses_epubs.md](build_yale_oyc_all_courses_epubs.md) — 이 파일의 로직을 재사용해 OYC 전체 코스로 확장한 버전
- [build_yale_oyc_sentence_inline_epub.md](build_yale_oyc_sentence_inline_epub.md) — 강의 한 개만 대상으로 하는 더 단순한 버전
