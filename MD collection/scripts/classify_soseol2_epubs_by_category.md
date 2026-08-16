# classify_soseol2_epubs_by_category.py

`소설2/[k]`, `소설2/[k-e]` 바로 아래에 있는(아직 장르별로 정리되지 않은) EPUB들을 장르 하위 폴더로 옮기는 분류 스크립트. Open Library / Google Books 공개 서지 API로 장르를 조회하고, 실패하면 제목 키워드 추측으로 대체한다(Goodreads는 공개 API가 없어 사용하지 않음).

파일: `scripts/classify_soseol2_epubs_by_category.py` (약 1,015줄)

## 대상 폴더 및 장르 체계

`SOURCE_DIR = ~/Desktop/소설2`, `K_ROOT`/`KE_ROOT = 소설2/[k]`, `소설2/[k-e]`. 장르 폴더 목록(`CATEGORY_DIRS`)은 `webui/book_organizer.py`의 `CATEGORY_DIRS`와 동일한 체계(`Mystery_Thriller_Crime`, `Dark_Romance`, `Fantasy_Science_Fiction` 등)를 쓴다.

## 동작

1. `--files`로 특정 파일만 지정하지 않으면 `K_ROOT`/`KE_ROOT` 바로 아래(또는 `--recursive`면 이미 분류된 하위 폴더 포함)의 EPUB을 모두 대상으로 한다.
2. 각 EPUB의 메타데이터를 조회(`--offline`이면 캐시/파일명 규칙만 사용, 온라인 조회 생략)해 장르를 결정.
3. `shutil.move()`로 해당 장르 하위 폴더로 실제 이동.
4. 조회 결과를 `_classification/` 아래 캐시로 저장해 재실행 시 같은 책을 다시 조회하지 않는다.
5. 실행마다 타임스탬프 붙은 `category_move_report_*.json`/`.csv` 리포트를 남긴다.

## CLI

```bash
python3 scripts/classify_soseol2_epubs_by_category.py \
  [--files <epub1> <epub2> ...] \
  [--offline] [--recursive] [--dry-run] [--quiet]
```

## `webui/book_organizer.py`와의 관계

`webui/book_organizer.py`의 `organize_single_epub()`/`organize_from_output_dir()`도 거의 같은 장르 분류·이동 로직(같은 `CATEGORY_DIRS`, 같은 키워드 테이블)을 가지고 있지만, 그쪽은 **작가별 하위 폴더 자동 생성**(같은 작가 책이 2권 이상이면 작가 폴더로 모음)까지 처리하고 웹 UI의 "서재로 반영" 동작 및 배치 작업 완료 후크에서 호출된다. 이 스크립트는 그와 별개로 존재하는 **터미널 전용 일괄 분류 도구**이며, 온라인 서지 API 조회와 캐시 관리에 좀 더 무게가 실려 있다. 두 로직이 서로 다른 코드베이스에 중복 구현되어 있으므로, 분류 규칙(키워드/장르 목록)을 바꿀 때는 **양쪽 다 함께 수정해야** 서재 전체에서 일관된 결과가 나온다.

**2026-08-04 기준 갈라진 지점**: `book_organizer.py`는 이 스크립트에 없는 두 가지를 추가로 처리한다.
- **`[e]`(정제된 영어 원문)와 `[study]`(학습용 대조본) 버전도 분류**한다. `organize_single_epub()`가 인식하는 접두사는 `[k-e]`/`[k]`/`[e]`/`[study]` 네 가지이며, `organize_from_output_dir(output_dir, korean_root, bilingual_root, english_root=..., study_root=...)`처럼 `english_root`/`study_root`를 넘기면 그 두 버전도 각각의 서재 루트(`소설2/[e]`, `소설2/[study]`)로 장르/작가 분류돼 들어간다(생략하면 예전처럼 `[k]`/`[k-e]`만 처리).
- **Google Books 평균 평점을 파일명에 붙인다**: `guess_average_rating()`이 Google Books API의 `averageRating`(평가 수 0건인 항목은 무시)을 조회해 `_classification/rating_cache.json`에 캐시하고, `build_organized_filename()`이 그 값을 `"[k] 제목 작가 (4.34).epub"` 형식으로 파일명 끝에 붙인다. 평점을 못 찾으면 괄호 없이 그대로 둔다.

이 스크립트는 여전히 `[k]`/`[k-e]`만 다루고 평점도 붙이지 않는다. 지금은 "새 책을 vk 같은 스테이징 폴더에서 서재로 옮기는" 기본 동작은 `book_organizer.py` 쪽에서만 지원하므로, 그 흐름에서는 이 스크립트가 아니라 `organize_from_output_dir()`를 쓴다.

**2026-08-06 기준 추가로 갈라진 지점**: `book_organizer.py`의 장르 판정 로직 자체가 이 스크립트보다 훨씬 정교해졌다. 이 스크립트는 여전히 `CATEGORY_KEYWORDS`를 순서대로 훑다가 첫 매칭에서 멈추는 단순 방식이지만, `book_organizer.py`는:
- `classify_genre_subjects()`가 subject 전체에서 각 장르의 근거 개수를 채점해서 고른다(첫 매칭이 아니라 "가장 근거가 많은 장르"). BISAC 스타일(`"FICTION / X / Y"`) subject는 가중치 3배, `"fiction"`처럼 너무 흔한 단어는 채점에서 제외.
- `core_series_search_title()`이 "작가명 - 원제 Series 1-10 Anthology"처럼 여러 권을 묶은 팬 편집 합본 파일명에서 저자명 접두사·합본 표시를 걷어낸 대체 검색어로 한 번 더 조회한다.
- `Romance` / `Dark_Romance`가 분리됐다(예전엔 `"romance"`라는 단어만 있으면 무조건 다크 로맨스 폴더로 갔는데, 그러면 Abby Jimenez/Colleen Hoover 같은 일반 로맨스 작가가 잘못 분류된다 - 2026-08-06 서재 감사에서 발견). `"dark romance"/"erotic"/"billionaire"` 등 구체적인 신호가 있어야 다크 로맨스로 가고, 그냥 `"romance"`만 있으면 일반 `Romance` 폴더로 간다.
- `audit_author_genre_placements()`는 이미 서재에 자리 잡은 작가 폴더들을 다시 온라인 조회해서, 지금 자리 잡은 장르와 다르면 목록으로 보고한다(자동으로 옮기진 않음). `organize_single_epub()`의 "같은 작가 책이 이미 한 장르에 있으면 새 책도 무조건 그 폴더로"라는 규칙은, 그 작가의 첫 배치가 애초에 잘못 분류돼 있었을 경우 그 실수를 영구히 그대로 이어가게 만드는데(Paula Hawkins가 실제로 이 문제로 Historical_Fiction에 잘못 들어가 있었다), 이 감사 함수로 그런 "굳어진 오분류"를 찾아낼 수 있다.

이 스크립트는 이 중 어느 것도 갖고 있지 않다. 분류 정확도가 중요한 작업(재분류·감사)은 `book_organizer.py` 쪽 함수를 쓴다.

**2026-08-14 기준 추가로 갈라진 지점**: `book_organizer.py`에 `CURATED_GENRE_BY_TITLE`(`normalize_book_title(title) + "|" + normalize_book_author(author)`를 키로 쓰는 수동 큐레이션 표)가 생겼다. `guess_genre_online()`이 네트워크 조회보다 먼저 이 표를 확인한다 — 최신 출간작이라 Open Library에 subject 태그가 아직 없거나, 그 세션에서 Google Books API가 429(Too Many Requests)로 막혀 있어서 온라인 조회 자체가 실패하는 책들을 위한 것이다. 2026-08-14 서재 감사에서 두 원인(신간이라 subject 미등록 / API 레이트리밋)으로 Uncategorized에 쌓여 있던 책 30여 권을 이 표로 채워 넣어 서재 5개 루트(`[e]`/`[k]`/`[k-e]`/`[study]`/`[e-s]`) 전부에서 Uncategorized를 비웠다. 이 스크립트는 이 표를 갖고 있지 않다.

## 관련 문서
- [EPUB 배치 번역 중복작업 방지 처리절차](../EPUB%20배치%20번역%20중복작업%20방지%20처리절차.md) — `webui/book_organizer.py`의 다른 함수들(중복 대조용 레지스트리)에 대한 설명
