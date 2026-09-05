# dedupe_against_finished.py

`finished` 폴더(이미 번역이 끝난 원서 EPUB 모음)와 지정한 소스 폴더의 EPUB들을 제목/작가 기준으로 대조해, 이미 완료된 작품이 소스 폴더에 남아있으면 `finished`로 옮기는 **수동 사전 정리용** CLI 래퍼.

파일: `scripts/dedupe_against_finished.py` (77줄, 로직은 전부 `webui/book_organizer.py`에 있는 함수 재사용)

## 중요 — 이미 배치가 자동으로 하는 일

이 스크립트가 쓰는 `build_finished_registry()` / `extract_metadata_from_epub()` / `find_finished_match()` / `archive_duplicate_source()`는 `webui/workflow_runner.py`가 배치 번역 중 **각 항목을 처리하기 직전에 자동으로 실행하는 것과 완전히 같은 함수**다. 즉 배치를 그냥 돌리면 이 중복 제거는 자동으로 일어난다. 이 스크립트는 배치를 시작하기 전에 **미리 눈으로 확인**하고 싶을 때, 혹은 배치 없이 폴더만 정리하고 싶을 때 쓰는 수동 도구다.

전체 로직(등록부 3종, 정규화, 유사도 임계값 등)에 대한 자세한 설명은 [EPUB 배치 번역 중복작업 방지 처리절차](../EPUB%20배치%20번역%20중복작업%20방지%20처리절차.md)의 "2단계"를 참고.

## CLI

```bash
python3 scripts/dedupe_against_finished.py \
  --source-dir <점검할 폴더> \
  --finished-dir <finished 폴더> \
  [--dry-run]
```

`--dry-run`이면 실제로 파일을 옮기지 않고 어떤 파일이 중복으로 판단되는지만 출력한다. 실행하면 finished로 이동될 항목, 그리고 번역 대기열에 남을 항목(최대 20개 미리보기)을 각각 나눠 보여준다.

## 관련 문서
- [EPUB 배치 번역 중복작업 방지 처리절차](../EPUB%20배치%20번역%20중복작업%20방지%20처리절차.md)
