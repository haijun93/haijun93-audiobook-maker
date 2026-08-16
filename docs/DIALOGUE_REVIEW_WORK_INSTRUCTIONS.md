# EPUB 대화체(말투) 검수 작업지시서

이 문서는 번역된 한국어 EPUB(`[k-e]`, `[k]`)의 **대화체(존댓말/반말, 호칭, 인물 간 말투 일관성)** 를 검수하는 절차를 설명한다. 이미 이 저장소에 구현되어 있는 자동 검사 스크립트를 실행하고 그 결과를 해석·판단하는 작업이며, 새로운 도구를 만들 필요는 없다. 아래 절차를 순서대로 따른다.

저장소 루트: `/Users/hyeokjunkong/Desktop/myproject_python/haijun93-audiobook-maker`

## 0. 사전 준비물

검수 대상마다 다음 두 가지가 필요하다.

1. **검수 대상 EPUB** — 보통 `[k-e]`(한영 대조본) 파일을 기준으로 검수한다. `[k]`(한글 단독본)는 `[k-e]`에서 파생되므로 `[k-e]`가 정상이면 `[k]`도 정상으로 본다.
2. **관계/말투 가이드 파일** (`relationship_guide.txt`) — 번역 파이프라인이 책마다 한 번 생성해 작업 디렉터리(`work_dir`)에 저장해 둔 텍스트 파일. 다음 네 개 섹션을 포함한다.
   - `[인물관계 요약]`
   - `[말투 규칙]` — 예: `A -> B: 반말/존댓말/격식체, 이유`
   - `[주의할 호칭과 일관성]`
   - `[고유명사 표기]`

   이 파일이 없으면 검수 스크립트는 근거 부족으로 **항상 `needs_attention`(재검토 필요)** 판정을 내린다. 배치 작업 디렉터리(`.webui/jobs/<job_id>/work/<번호>_<책이름>/translation/relationship_guide.txt`)에서 찾을 수 있다. 없다면 검수를 진행하기 전에 이 파일부터 찾아서 확보한다.

## 1단계 — 전체 톤 검사 (pass 1)

책 전체를 훑어 인물별 존댓말/반말 사용이 관계 가이드와 맞는지, 눈에 띄는 오류가 있는지 확인하는 1차 검사다.

```bash
python3 scripts/final_epub_tone_review.py \
  "<검수 대상 [k-e] epub 경로>" \
  --relationship-guide "<work_dir>/relationship_guide.txt" \
  --out-dir "<work_dir>/final_tone_reviews" \
  --kind k-e
```

이 스크립트가 실제로 확인하는 것:

- **혼합 어투**: 대사 하나 안에 존댓말 문장과 반말 문장이 섞여 있는가.
- **호칭+반말 충돌**: `선생님/교수님/박사님/사장님/원장님/형사님/변호사님` 등 존칭 호칭을 쓰면서 문장 종결은 반말인가.
- **친밀 호칭+존댓말 충돌**: `자기야/예쁜/내 거/너/사랑` 같은 친밀한 표현과 존댓말 종결이 함께 쓰였는가.
- **서술문 같은 대사**: 대사가 나레이션처럼 딱딱하게 끝나는가.
- **영문 고유명사 잔존**: 인물 이름 등이 번역 없이 영어 그대로 남아있는가.
- 관계 가이드에서 파싱한 인물관계 규칙을 리포트에 그대로 나열해, 사람이 규칙과 실제 대사를 대조하기 쉽게 해준다.

결과물: `<work_dir>/final_tone_reviews/` 아래 `*.tone_review_<타임스탬프>.md/.json` 과 `*_latest.md/.json`. 리포트 상단 `status` 필드가 `checked`(정상) 또는 `needs_attention`(재검토 필요)이다.

## 2단계 — 국소 대화 일관성 검사 (pass 2, 독립적인 2차 검사)

1단계와 **완전히 별개로** 반드시 실행해야 하는 2차 검사다. 책 전체 통계가 아니라, 인접한 대사끼리 말투가 급변하지 않는지에 집중한다.

```bash
python3 scripts/final_epub_dialogue_consistency_review.py \
  "<검수 대상 [k-e] epub 경로>" \
  --relationship-guide "<work_dir>/relationship_guide.txt" \
  --out-dir "<work_dir>/final_dialogue_reviews_pass2" \
  --kind k-e
```

이 스크립트가 확인하는 것 (1단계와 겹치지 않는 부분 위주):

- **반말 대명사 + 존댓말 종결 충돌**: `너/네가/자네` 등을 쓰면서 문장은 `~요/~습니다`로 끝나는가.
- **존칭 호칭 + 반말 종결 충돌**: 1단계와 같은 개념을 국소적으로 재확인.
- **한 대사 안의 존대/반말 혼합**.
- **인접 대화의 말투 급변 후보**: 같은 화자로 보이는 연속된 대사에서 갑자기 존댓말↔반말이 뒤바뀌는 지점을 표본으로 뽑아준다. 다만 이건 화자가 바뀐 정상적인 경우일 수도 있으므로 **자동 확정 오류가 아니라 사람이 확인해야 할 후보**로만 취급한다.

결과물: `<work_dir>/final_dialogue_reviews_pass2/` 아래 `*.dialogue_pass2_<타임스탬프>.md/.json` 과 `*_latest.md/.json`. 역시 `status: checked | needs_attention`.

## 3. 두 리포트 읽는 법

각 리포트는 다음 구조를 갖는다.

```
헤더 (epub / kind / title / creator / status / created / 적용된 관계 규칙 개수)
## Counts   — 항목별 발생 건수
## Notes    — 요약 설명
## Samples  — 실제 문제로 의심되는 원문 발췌 (최대 8~10건)
```

`status`가 `needs_attention`이 되는 조건(대략적 임계값, 정확한 수치는 스크립트 참고):

- 관계 가이드 파일이 아예 없을 때 (무조건 `needs_attention`)
- 반말 대명사+존댓말 종결 충돌이 일정 건수 이상
- 호칭+반말 종결 충돌이 일정 건수 이상
- 한 대사 내 혼합 어투가 일정 건수 이상

**판단 원칙**: `status: checked`라도 `## Samples`에 남아있는 항목은 가볍게라도 훑어본다. 임계값 미만이라 통과했을 뿐, 실제로 명백한 오류가 1~2건 섞여 있을 수 있다. 반대로 `needs_attention`이라도 관계 가이드 자체가 아직 만들어지지 않은 경우처럼 절차상의 이유일 수 있으니, `## Notes`를 먼저 읽고 원인을 구분한다.

## 3.5. 알려진 오탐(false positive) 패턴 — 실제 오류로 착각하지 말 것

지금까지 실제 검수 과정에서 반복적으로 확인된, **번역 오류가 아닌** 자동 검사 특유의 오탐 패턴이다. `## Samples`에서 아래 패턴이 보이면 실제 문제가 아닐 가능성이 높으니 먼저 이 목록과 대조한다.

- **사제/권위자 관계의 의도적 반말↔존댓말 비대칭**: 교사가 학생에게 반말로 명령하고 학생은 존댓말을 쓰는 등, 인물관계 규칙(`[말투 규칙]`)에 이미 정의된 권력관계 비대칭은 정상이다. `호칭+반말 종결 충돌`이나 `혼합 어투`로 잡히더라도, 관계 가이드의 방향성 규칙(`A -> B: 반말, 이유`)과 대조해 실제로 그 관계에 맞는 화자인지부터 확인한다.
- **영어 원문(.en) 블록에 우연히 등장하는 거절 문구**: `final_epub_quality_audit.py`의 "AI 응답 거절 문구 잔존" 검사는 EPUB 파일 텍스트 전체(한글 `.ko`뿐 아니라 영어 학습용 `.en` 블록까지)를 대상으로 스캔한다. 소설 속 인물이 실제로 "I'm unable to help you" 같은 대사를 하면 원문에 그 문구가 그대로 있으므로 오탐이 발생한다. 반드시 해당 위치의 **한글 번역이 정말 비어있거나 거절 문구인지**를 직접 확인해서 판단한다 (원문 영어에 있다고 곧바로 문제로 보지 않는다).
- **책 뒤 색인(index)의 정상적인 교차 참조**: 학술서/논픽션의 색인 섹션에서는 같은 페이지-참조 목록이 서로 다른 표제어 아래(예: "public sphere of, 65..."와 "public sphere of letters, 65...") 반복 등장하는 것이 정상이다. `final_epub_quality_audit.py`의 "동일 번역 반복(`repeated_translation`)" 검사가 이를 고위험 후보로 잡을 수 있는데, 원문 자체도 근소하게 다를 뿐 사실상 같은 목록이라면 오탐이다. 파일명이 `index`류인지, 원문끼리도 서로 거의 동일한지 확인한다.
- **[수정 완료] "-아야/-어야" 연결어미가 말줄임표 앞에서 반말 종결로 오분류되던 문제**: "제 말을 들어봐야…."처럼 대사가 중간에 끊긴 경우, "들어봐야"의 "야"를 반말 종결어미로 착각해 실제로는 존댓말 문장인데 "혼합 어투"로 잘못 잡던 버그. `scripts/final_epub_tone_review.py`와 `scripts/final_epub_dialogue_consistency_review.py`의 `CASUAL_END_RE`에 부정형 전방탐색(`야(?!\s*(?:\.{2,}|…))`)을 추가해 수정했다(회귀 테스트: `tests/test_final_epub_dialogue_consistency_review.py`). 이 수정 이후 생성된 리포트에는 이 패턴이 나타나지 않아야 하며, 만약 다시 보인다면 코드 회귀를 의심한다.

이 목록에 없는 새로운 오탐 패턴을 발견하면, 이 문서와 해당 검사 스크립트에 함께 반영해 다음 검수자가 같은 시간을 낭비하지 않게 한다.

## 4. 문제를 발견했을 때 고치는 방법

**우선순위 1 — 관계 가이드를 먼저 의심한다.** 대사가 잘못된 게 아니라 관계 가이드의 말투 규칙(`[말투 규칙]`) 자체가 애매하거나 누락된 관계가 있어서 번역이 일관되지 못했을 가능성이 높다. 이 경우 가이드를 보완하고, 이후 번역 청크는 자동으로 새 가이드를 반영하지만 **이미 캐시된 과거 번역은 자동으로 다시 쓰이지 않으므로** 문제 대사는 직접 고쳐야 한다.

**우선순위 2 — 문제 대사를 직접 패치한다.** 이 저장소에는 재사용 가능한 공용 "호칭 교정 라이브러리"가 없다. 지금까지의 실제 사례(`scripts/refine_*_honorifics.py`)는 모두 **책 한 권 전용의 일회성 스크립트**이며 두 가지 패턴 중 하나를 따른다.

- **패턴 A (문자열 치환, 대부분의 사례)**: 챕터 파일명별로 `(고칠 원문 문장, 고친 문장)` 튜플 리스트를 하드코딩하고 `str.replace`로 EPUB 내부 XHTML을 직접 고친다. 오탐 없이 정확한 문장을 정확히 한 번만 고칠 수 있을 때 이 방식을 쓴다. 예: `scripts/refine_dark_notes_honorifics.py`, `scripts/refine_artemis_honorifics.py`, `scripts/refine_corrupt_honorifics.py`.
- **패턴 B (LLM 재검토 루프, 대사량이 많고 규칙이 복잡할 때)**: `.ko`/`.en` 대사 쌍을 추출하고, 그 책의 인물관계 규칙을 프롬프트에 자연어로 박아 넣어 웹 LLM에게 "고쳐야 할 대사 ID만 알려달라"고 요청한 뒤, 반환된 ID의 번역만 다시 써서 EPUB과 번역 캐시에 반영한다. 대사 수가 많거나 화자가 여럿이라 문자열 치환으로는 감당이 안 될 때 이 패턴을 쓴다. 예: `scripts/refine_lessons_in_sin_honorifics.py` (1차/2차 검증 패스, 그리고 특정 인물쌍만 노리는 추가 최종 패스 지원).

새로 패치 스크립트를 작성할 때는 반드시:
1. `--dry-run` 옵션으로 먼저 바뀔 내용을 출력해 확인한 뒤 실제 적용한다.
2. `[k-e]`를 고친 뒤 `scripts/make_korean_only_epubs.py`의 `convert_epub`으로 `[k]`도 반드시 재생성한다 (두 산출물이 어긋나면 안 된다).
3. 고친 뒤에는 **1단계, 2단계 검사를 처음부터 다시 실행**해 실제로 개선됐는지, 새로운 문제를 만들지 않았는지 확인한다.

## 5. 완료 판정 기준 (목차 누락 여부 포함)

`scripts/final_epub_quality_audit.py`가 최종 게이트다. 1단계/2단계 리포트를 이미 생성해 두었다면, 이 스크립트 하나로 **대화체 검수 결과 재확인 + 목차(TOC) 누락 여부 + EPUB 구조 무결성**을 한 번에 확인할 수 있다.

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from final_epub_quality_audit import audit_epub
from pathlib import Path

audit = audit_epub(
    Path('<검수 대상 [k-e] epub 경로>'),
    kind='k-e',
    work_dir=Path('<work_dir>/translation'),
)
print('status:', audit.status)
print('nav_items:', audit.nav_items, 'ncx_points:', audit.ncx_points)  # 0이면 목차 누락
print('issues:', audit.issues)
print('warnings:', audit.warnings)
"
```

이 스크립트는 다음을 모두 요구한다.

- 1단계(`final_tone_reviews/*_latest.json`)와 2단계(`final_dialogue_reviews_pass2/*_latest.json`) 리포트가 **둘 다 존재**할 것.
- 두 리포트 모두 `status: needs_attention`이 아닐 것 (다만 이 자체는 `issues`가 아니라 `warnings`로만 반영되므로, 최종 `status`를 좌우하는 건 아래의 구조적 항목들이다).
- 두 번의 독립된 대화 검사가 실제로 완료되었을 것(하나만 돌리고 통과시키지 않는다).
- **목차(TOC) 완전성**: `nav_items > 0`이고 `ncx_points > 0`일 것. 둘 중 하나라도 0이면 `"목차가 불완전합니다"` 이슈로 잡혀 목차 누락으로 확정 실패 처리된다.
- 그 밖에 mimetype 위치, XML 파싱 오류, `[번역 누락]`/watermark 잔존, 한영 블록 수 일치, 번역 캐시 정합성(누락 ID, 미완성 chunk 등), 미번역/과도한 축약/반복 후보(`repeated_translation` 등 — 3.5절의 오탐 패턴에 해당하는지 먼저 확인) 등도 함께 검사한다.

`audit.status`가 `"pass"`면 구조적으로는 완료 처리 가능하고, `"needs_attention"`이면 `audit.issues` 목록을 하나씩 확인해 3.5절의 오탐 패턴에 해당하는지, 실제 문제인지 판단한다. 이 조건을 만족하지 못하면 해당 EPUB은 완료(`finished`) 처리되지 않고 큐에 남는다. 검수 작업의 최종 산출물은 "1단계 리포트, 2단계 리포트, 목차/구조 감사 결과, (필요시) 패치 diff, 최종 판정(pass/needs_attention과 근거)"이다.

## 6. 빠른 체크리스트

- [ ] 대상 EPUB(`[k-e]`)과 `relationship_guide.txt` 위치 확인
- [ ] `final_epub_tone_review.py` 실행, `status`/`Samples` 확인
- [ ] `final_epub_dialogue_consistency_review.py` 실행, `status`/`Samples` 확인 (1단계와 별개로 반드시 실행)
- [ ] 발견된 `Samples`를 3.5절 "알려진 오탐 패턴"과 먼저 대조 (사제관계 비대칭, 영어 원문 우연 일치, 색인 교차참조 등)
- [ ] 남은 문제를 "가이드 미비" vs "실제 번역 오류"로 구분
- [ ] 필요시 관계 가이드 보완 + 문제 대사 패치 (패턴 A/B 중 선택, `--dry-run` 먼저)
- [ ] `[k-e]` 패치 후 `[k]` 재생성
- [ ] 두 검사 재실행으로 개선 확인
- [ ] `final_epub_quality_audit.py`로 목차(TOC) 누락 여부 + 구조 무결성 + 최종 판정 확인
