# replace_generated_epub_covers_with_online.py

`ensure_missing_epub_covers.py`가 만들어 넣은 **텍스트 플레이스홀더 표지**를, 나중에 온라인에서 실제 표지 이미지를 찾아 교체하는 후속 스크립트. `ensure_missing_epub_covers.py`의 여러 내부 함수를 그대로 임포트해서 쓴다(중복 구현 없음).

파일: `scripts/replace_generated_epub_covers_with_online.py`

## 동작

- 대상 EPUB에서 현재 표지가 플레이스홀더인지 판별하고, `book_cover_lookup.find_online_cover()`로 온라인 표지를 다시 조회해 있으면 교체.
- **제목 별칭 테이블** (`TITLE_ALIAS_RULES`): 파일명이 뭉개져 있거나 한국어 제목만 있어서 온라인 검색이 실패하는 특정 책들을, 파일명 속 키워드 조합(예: `("housemaid", "watching")`)으로 실제 영문 제목/저자로 매핑해준다(예: `"지켜보고..."` → `"The Housemaid Is Watching" / "Freida McFadden"`). 이런 책이 새로 생기면 이 테이블에 항목을 추가한다.

## CLI

```bash
python3 scripts/replace_generated_epub_covers_with_online.py <폴더 또는 단일 epub> \
  [--dry-run] [--include-work-dirs] [--limit N]
```

`--limit`으로 한 번 실행에서 교체할 최대 건수를 제한할 수 있다(온라인 API 호출량 조절용).

## 관련 문서
- [ensure_missing_epub_covers.md](ensure_missing_epub_covers.md)
