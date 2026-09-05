# refine_corrupt_honorifics.py

`Corrupt`(Penelope Douglas 저) 한국어 번역의 특정 대사들을 하드코딩된 `REPLACEMENTS` 목록(문자열 찾기/바꾸기 쌍)으로 교정하는 일회성 스크립트. `refine_artemis_honorifics.py`와 같은 패턴이되, 여러 파일(`epubs` 인자로 여러 경로를 한 번에 받음)에 같은 치환 목록을 적용할 수 있다는 점이 다르다.

파일: `scripts/refine_corrupt_honorifics.py`
대상 폴더: `~/Desktop/소설2` (`_manual_backups/`에 백업)

## CLI

```bash
python3 scripts/refine_corrupt_honorifics.py <epub 경로...> [--dry-run]
```

`--dry-run`이면 실제로 파일을 고치지 않고 각 치환이 몇 건 매칭됐는지(`replacement_hits`, JSON)만 출력한다. `idle_completed_epub_tone_maintenance.py`가 바로 이 `--dry-run` 출력을 파싱(`parse_corrupt_replacements`)해 "실제로 고칠 내용이 있을 때만" 진짜로 적용하는 안전장치로 쓴다.

## 관련 문서
- [refine_artemis_honorifics.md](refine_artemis_honorifics.md) — 같은 패턴
- [idle_completed_epub_tone_maintenance.md](idle_completed_epub_tone_maintenance.md) — 이 스크립트를 자동 연동하는 유지보수 스크립트(dry-run 먼저 확인 후 적용)
