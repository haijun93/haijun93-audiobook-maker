# build_yale_oyc_all_courses_epubs.py

`build_yale_oyc_game_theory_course_epub.py`가 ECON 159 한 코스에 대해 구현한 로직(`Section`, `Session`, `fetch_text`, `extract_lecture_sections`, `sentence_items_from_paragraphs`, `translate_session` 등을 그대로 임포트)을 **Open Yale Courses 전체 코스 목록**으로 확장한 스크립트. OYC 코스 목록 페이지(`https://oyc.yale.edu/courses`)를 가져와 각 코스마다 문장 인라인 영한 대조 EPUB을 하나씩 만든다.

파일: `scripts/build_yale_oyc_all_courses_epubs.py`

## CLI

```bash
python3 scripts/build_yale_oyc_all_courses_epubs.py \
  --courses-url https://oyc.yale.edu/courses \
  --work-dir <작업 디렉터리> --output-dir <출력 폴더> \
  --max-chars 4200 \
  [--skip-translation] [--force] \
  [--limit-courses N] [--start-index N(1-based)] \
  [--only-code "ECON 159"] [(반복 가능)] \
  [--shutdown]
```

- `--only-code`를 여러 번 줘서 특정 코스만 골라 처리할 수 있다.
- `--start-index`로 중간에 끊긴 실행을 이어서 할 수 있다.
- `--shutdown`: 모든 코스 처리가 끝나면 macOS를 종료 — 오래 걸리는 전체 배치를 밤새 돌릴 때 쓰는 옵션(`run_k_e_batch_with_shutdown.py`의 `--shutdown`과 같은 목적).

## 관련 문서
- [build_yale_oyc_game_theory_course_epub.md](build_yale_oyc_game_theory_course_epub.md) — 이 스크립트가 로직을 가져오는 기반 모듈(단일 코스)
- [build_yale_oyc_sentence_inline_epub.md](build_yale_oyc_sentence_inline_epub.md)
