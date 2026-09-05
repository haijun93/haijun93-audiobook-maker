# build_ted_transcript_study_epub.py

사용자가 직접 붙여넣은 TED 강연 대본 텍스트 파일들로부터, 로컬 Ollama 모델(`gemma4:26b`)로 문단을 한국어로 번역해 **한영 대조 학습용 Kindle EPUB**을 만드는 스크립트. 이 파일의 `Talk`/`Segment` 데이터클래스와 `translate_talk()`/`unique_talks()` 함수는 [build_ted_sentence_inline_study_epub.py](build_ted_sentence_inline_study_epub.md)가 그대로 임포트해서 재사용하는 **기반 모듈** 역할도 한다.

파일: `scripts/build_ted_transcript_study_epub.py`

## 입력

`--paths`(위치 인자)로 대본 텍스트 파일을 직접 지정하거나, 지정하지 않으면 `DEFAULT_ATTACHMENT_PATHS`에 하드코딩된 과거 대화 첨부파일 경로들(`~/.codex/attachments/<uuid>/pasted-text.txt`)을 사용한다. `URL_BY_TITLE`에 강연 제목→TED 원본 URL 매핑이 미리 등록되어 있다(10개 강연).

## CLI

```bash
python3 scripts/build_ted_transcript_study_epub.py \
  [<대본 텍스트 파일...>] \
  --output <출력 epub, 기본: .work/TED_Transcript_Based_Korean_English_Study.epub> \
  --work-dir <작업 디렉터리> \
  --model gemma4:26b --ollama-url http://127.0.0.1:11434/api/generate \
  --max-chars 3000 --timeout 600 \
  [--skip-translation] [--limit N]
```

- `--skip-translation`: 번역 없이 영문만으로 EPUB 구조를 먼저 확인하고 싶을 때.
- `--limit N`: 테스트용으로 처음 N개 강연만 처리.

## 관련 문서
- [build_ted_sentence_inline_study_epub.md](build_ted_sentence_inline_study_epub.md) — 같은 대본/번역 로직을 재사용해 문장별 인라인 레이아웃으로 만드는 변형
- [build_ted_link_learning_epub.md](build_ted_link_learning_epub.md) — 대본 번역이 아니라 요약/어휘 중심의 다른 접근
