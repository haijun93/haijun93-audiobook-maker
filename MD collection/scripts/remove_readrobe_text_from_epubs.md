# remove_readrobe_text_from_epubs.py

EPUB 내부 텍스트에서 불법 공유/유출 사이트 워터마크 문구(`readrobe.com`, `리드로브닷컴`, `oceanofpdf.com` 및 그 변형 표기)를 제거하는 스크립트. 이름과 달리 지금은 `readrobe.com`뿐 아니라 `oceanofpdf.com`도 함께 처리한다(`WATERMARK_PATTERN`).

파일: `scripts/remove_readrobe_text_from_epubs.py`
핵심 함수: `scrub_text()`(텍스트 단위), `scrub_epub()`(EPUB 파일 단위, 다른 스크립트들이 임포트해서 재사용)

## 동작

- `WATERMARK_PATTERN`으로 워터마크 문구를 찾아 제거(대소문자 무시, `www.`/점 사이 공백 등 변형 표기까지 매칭).
- 제거 후 텅 빈 `<p></p>`/`<h1~6></h1~6>` 태그, 중복 공백, 태그 사이 여백을 정리.
- BOM/UTF-16/EUC-KR 등 다양한 인코딩 선언을 자동 감지해 읽는다(`decode_text`).
- `atomic_output_path`로 원자적 쓰기(중간에 실패해도 원본이 깨지지 않음).

## CLI

```bash
python3 scripts/remove_readrobe_text_from_epubs.py <epub 또는 폴더...> [--dry-run] [--quiet]
```

폴더를 주면 그 안의 모든 `*.epub`을 재귀적으로 찾아 처리한다. 실행 후 `books=N changed=N replacements=N errors=N` 요약을 출력.

## 다른 스크립트에서의 재사용

이 파일의 `scrub_epub()`/`scrub_text()`/`clone_info()`는 파이프라인 전반에서 임포트되어 쓰인다 — `translate_epub_with_chatgpt_web_to_study_epub.py`(번역 EPUB 생성 직후), `make_korean_only_epubs.py`(`[k]` 변환 전후), `final_epub_quality_audit.py`(잔여 워터마크 카운트) 등. 즉 이 스크립트를 직접 실행할 일은 드물고, 주로 **다른 파이프라인 단계 안에서 자동으로 호출**되는 공용 정리 기능이다. 사람이 직접 실행하는 경우는 이미 만들어진 EPUB에서 뒤늦게 워터마크가 발견됐을 때 그 파일(들)만 다시 스크럽할 때다.
