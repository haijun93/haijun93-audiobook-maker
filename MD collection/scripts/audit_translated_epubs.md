# audit_translated_epubs.py

`final_epub_quality_audit.py`보다 먼저 만들어진, **구(舊) 서재 폴더**(`~/Desktop/소설/#[k-e]`) 전용 구조 감사 스크립트. EPUB의 mimetype 순서, OPF/목차 존재, 깨진 링크, 번역 누락 마커, 한영 블록 구조, 대사 존댓말/반말 패턴(`POLITE_RE`/`CASUAL_RE`)을 점검하고 폴더 전체에 대한 요약 리포트를 만든다.

파일: `scripts/audit_translated_epubs.py`

## CLI

```bash
python3 scripts/audit_translated_epubs.py [폴더 경로(기본: ~/Desktop/소설/#[k-e])] \
  --out-dir <리포트 저장 폴더(기본: .work)>
```

## 지금도 유효한가

대상 폴더가 지금 작업 중인 `소설2`가 아니라 구 서재(`소설/#[k-e]`)로 고정되어 있다. **현재 `소설2` 서재/배치에는 `final_epub_quality_audit.py`를 쓴다.** 이 스크립트는 구 서재를 다시 점검할 일이 있을 때만 참고한다.

## 관련 문서
- [final_epub_quality_audit.md](final_epub_quality_audit.md) — 현재 사용하는 동등한 역할의 스크립트
- [run_k_e_batch_with_shutdown.md](run_k_e_batch_with_shutdown.md) — 같은 구 서재를 대상으로 한 배치 러너
