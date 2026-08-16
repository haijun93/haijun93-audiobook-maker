# ensure_missing_epub_covers.py

표지 이미지가 없는 EPUB에 표지를 채워 넣는 스크립트. 온라인 서지 API에서 표지를 찾을 수 있으면 그것을 쓰고, 못 찾으면 제목/저자를 텍스트로 그린 플레이스홀더 표지 이미지를 직접 생성(`PIL`)해 넣는다.

파일: `scripts/ensure_missing_epub_covers.py`
공용 함수(다른 스크립트가 재사용): `has_recognized_cover`, `manifest_items`, `read_opf_path`, `write_epub` 등 — `replace_generated_epub_covers_with_online.py`가 이 파일에서 직접 임포트한다.

## 동작

1. 대상 EPUB의 OPF 매니페스트를 읽어 이미 인식 가능한 표지가 있는지 확인(`has_recognized_cover`).
2. 없으면 `book_cover_lookup.find_online_cover(title, author)`로 **Google Books → Open Library** 순서로 온라인 표지를 조회.
3. 그래도 못 찾으면 제목/저자 텍스트를 그려 넣은 플레이스홀더 이미지를 생성해 표지로 삽입.
4. OPF 매니페스트/네비게이션에 표지 항목과 `properties="cover-image"`를 등록해 리더 앱이 표지로 인식하게 만든다.

## CLI

```bash
python3 scripts/ensure_missing_epub_covers.py <폴더 또는 단일 epub> \
  [--dry-run] [--include-work-dirs] [--no-online]
```

- `--include-work-dirs`가 없으면 `_chatgpt_translate_work`, `_batch_logs`, `__MACOSX` 같은 임시/작업 폴더는 스캔 대상에서 제외한다(`DEFAULT_SKIP_DIRS`).
- `--no-online`이면 온라인 조회 없이 곧바로 플레이스홀더 표지를 생성한다.

## 관련 문서
- [replace_generated_epub_covers_with_online.md](replace_generated_epub_covers_with_online.md) — 이 스크립트가 만든 플레이스홀더 표지를 나중에 실제 온라인 표지로 교체
