# refine_lessons_in_sin_honorifics.py

`Lessons in Sin`의 한국어 대화 말투를, **실제 Gemini 웹 브라우저 세션을 열어 다시 검토**시킨 뒤 그 결과를 반영하는 honorifics 교정기. 다른 책들의 교정기(하드코딩된 치환 목록)와 달리, 이 스크립트는 검토 자체를 웹 AI에게 맡긴다.

파일: `scripts/refine_lessons_in_sin_honorifics.py`

## 동작

1. EPUB에서 대화 쌍(`extract_dialogue_pairs`)을 뽑는다.
2. `audiobook_maker.py`의 Gemini 웹 자동화 모듈(`load_gemini_web_cookies`, `sync_playwright` 등 — [translate_epub_with_chatgpt_web_to_study_epub.md](translate_epub_with_chatgpt_web_to_study_epub.md)가 쓰는 것과 같은 기반)로 실제 브라우저를 띄워 Gemini에 로그인한 쿠키로 접속.
3. `--passes`(2 또는 3)만큼 검토 패스를 반복 실행(`run_review_pass`) — 프롬프트 최대 길이는 `--max-prompt-chars`(기본 18000자)로 잘라 나눠 보낸다.
4. `--focused-tinsley-pass`: 특정 등장인물(Tinsley)의 대사만 따로 한 번 더 집중 검토하는 추가 패스(`--focused-pass-index`로 순서 지정).
5. `--apply`가 있으면 검토 결과를 EPUB에 반영하고, **번역 캐시(chunk json)도 함께 갱신**(`synchronize_cache`류 로직 — 블록 ID 기준으로 캐시된 번역문을 새 번역으로 교체)해 이후 재작업 시 옛 번역으로 되돌아가지 않게 한다.

## CLI

```bash
python3 scripts/refine_lessons_in_sin_honorifics.py \
  [--k-e-epub ...] [--k-epub ...] [--work-dir ...] \
  [--max-prompt-chars 18000] [--passes {2,3}] \
  [--focused-tinsley-pass] [--focused-pass-index 5] \
  [--apply]
```

`--apply` 없이 실행하면 검토만 하고 실제 파일은 바꾸지 않는다(다른 교정기들의 `--dry-run`과 같은 역할).

## 주의

Gemini 웹 브라우저 세션을 직접 여는 스크립트이므로, **메인 배치 번역(`translate_epub_with_chatgpt_web_to_study_epub.py`)이나 다른 웹 자동화 작업과 동시에 실행하면 안 된다** (같은 규칙: "동시에 두 개의 웹 자동화 세션을 띄우지 않는다").

## 관련 문서
- [refine_better_than_the_movies_final.md](refine_better_than_the_movies_final.md) — 사람이 먼저 검토하고 그 결과만 반영하는 대조적인 접근
- [translate_epub_with_chatgpt_web_to_study_epub.md](translate_epub_with_chatgpt_web_to_study_epub.md) — 같은 웹 자동화 기반(Gemini 쿠키/Playwright) 재사용
