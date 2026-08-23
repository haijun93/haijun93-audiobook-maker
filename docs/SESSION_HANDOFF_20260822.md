# SESSION_HANDOFF_20260822.md — Amazon Kindle Genuine Word Wise & X-Ray Master Standard

## 1. Overview & Major Innovations
- **Amazon Kindle Genuine Word Wise Standard**:
  - Implemented authentic HTML5 overhead ruby annotations (`<ruby><rb>word</rb><rt class="wordwise-hint">문맥 뜻</rt></ruby>`).
  - **Zero Truncation Rule (글자 누락 영구 금지)**: Completely abolished hard length slicing (`[:8]`), preserving full natural phrases (e.g. `~할 여유가 없다`, `발끝으로 살금살금 지나가다`, `갈라진 신발 밑창`).
  - **Dynamic Conditional Line-Height Rule (동적 조건부 줄간격)**:
    - Sentences WITHOUT Word Wise: Standard `1.65` (100% identical to Korean standard line-height).
    - Sentences WITH Word Wise: Dynamically expanded to `1.85` (`span.en.has-ww`, `p.has-ww`).
  - **Elimination of Redundant 3rd Line**: In `[study]` and `[e-s]`, legacy separate 3rd-line `※` notes are completely streamlined into the overhead Word Wise annotations.
  - **Amazon Kindle X-Ray Directory Integration**: Every book includes the X-Ray Dramatis Personae & Terms directory (`000-xray-dramatis-personae.xhtml`) linked at the top of the Table of Contents.

## 2. Library Status
- All **1,141 books** across `/Users/hyeokjunkong/Desktop/소설2/[study]/` (582 books) and `[e-s]/` (559 books) have been upgraded to the Kindle Genuine Word Wise format.
- Prototyped and verified standalone `[ks]` and `[kindle]` editions.

## 3. General Rules & Agent Skills Updated
- `AGENTS.md` (Articles 7 & 8) updated with permanent Kindle Word Wise Master Standard and Mandatory Claude-based Fiction X-Ray Dossier Pipeline Standard.
- `.agents/skills/audiobook-studio-master/SKILL.md` (Section 8) updated with permanent specification.
- `scripts/harvest_fiction_xray_with_claude.py` and `scripts/claude_xray_harvester.py` deployed to harvest 100% authentic Korean X-Ray dossiers directly from Claude Web.
- `scripts/inject_rich_korean_xray_to_all_library.py` integrated into the 30-minute health audit (`scripts/check_accounts_and_report.py`) to guarantee 100% of newly translated novels automatically receive rich Korean X-Ray dossiers in the top of the Table of Contents across all 6 editions (`[k]`, `[k-e]`, `[study]`, `[e-s]`, `[xteink]/[study]`, `[xteink]/[e-s]`).
