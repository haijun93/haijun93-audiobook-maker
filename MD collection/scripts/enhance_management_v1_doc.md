# enhance_management_v1_doc.py

`enhance_civil_v1_doc.py`와 완전히 같은 구조·처리 흐름(파싱 → 초점 추출 → 해설 재작성 → Kiwi 띄어쓰기 보정 → 대단원순 재조립)을 **경영학 OX 학습자료**에 적용한 스크립트. 공통 패턴 설명은 [enhance_civil_v1_doc.md](enhance_civil_v1_doc.md)를 참고.

파일: `scripts/enhance_management_v1_doc.py`
기본 입력: `~/Desktop/1차 시험/#STD/260416/management_OX_integrated_2026_v1.docx`

## 경영학 전용 대단원 순서 (`SECTION_ORDER`)

```
경영일반·전략 / 조직행동·인사 / 마케팅 / 생산·운영관리 / 재무·회계 / 기타
```

## CLI

```bash
python3 scripts/enhance_management_v1_doc.py [입력 docx 경로(기본값 위 참고)]
```

## 관련 문서
- [enhance_civil_v1_doc.md](enhance_civil_v1_doc.md) — 공통 패턴 상세 설명
