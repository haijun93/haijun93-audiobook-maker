# quality_gate.py

이 저장소 전체(EPUB 번역 파이프라인, 공무원 시험 자료 파이프라인, TED/Yale 빌더 등 전부)에 대한 **웹 계정/API 키 없이 실행 가능한 결정론적 검사**를 한 번에 순서대로 돌리는 커밋 전 점검 스크립트.

파일: `scripts/quality_gate.py`

## 실행 순서

1. `pip check` — 설치된 의존성 버전 충돌 확인.
2. `ruff check .` — 린트(있으면 `ruff` 실행파일, 없으면 `python -m ruff`로 대체).
3. `python -m compileall` — `audiobook_maker.py`, `web_app.py`, `webui/`, `scripts/`, `tests/`를 바이트코드로 컴파일해 문법 오류를 조기에 잡는다.
4. `zsh -n <scripts/*.sh>` — macOS 워크플로 셸 래퍼들의 문법 검사(zsh 필수).
5. `pytest -q` — 전체 테스트 스위트.
6. (git 저장소일 때) `git diff --check HEAD` — 트레일링 스페이스 등 공백 오류 검사.

각 단계는 실패하면 즉시 예외를 던지며(`subprocess.run(..., check=True)`) 전체 실행이 중단된다. 모두 통과하면 마지막에 `"All deterministic quality checks passed."`를 출력한다.

## CLI

```bash
python3 scripts/quality_gate.py
```

## 언제 쓰는가

코드를 변경한 뒤(특히 `scripts/translation_quality_checks.py`처럼 여러 스크립트가 공유하는 모듈을 고쳤을 때) 커밋 전에 한 번 실행해 린트/컴파일/테스트가 모두 정상인지 빠르게 확인하는 용도다. 실제로 이번 세션의 [검증기 오탐 예외 처리 규칙 수정](../EPUB%20번역%20품질%20검증기%20오탐%20예외%20처리%20규칙.md) 작업에서도 `pytest`로 회귀 여부를 확인했다 — `quality_gate.py`는 그 개별 확인들을 하나의 표준 절차로 묶어놓은 것이다.
