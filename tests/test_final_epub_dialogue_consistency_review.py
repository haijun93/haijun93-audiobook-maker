from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import final_epub_dialogue_consistency_review as dialogue  # noqa: E402
from final_epub_tone_review import classify_dialogue, sentence_tones  # noqa: E402


def test_interrupted_yeoya_connective_is_not_classified_as_casual() -> None:
    # "들어봐야" is the "-아야/-어야" connective ("must/only if you listen"), cut off
    # mid-clause by the trailing ellipsis - not a complete casual "-야" sentence.
    assert classify_dialogue("제 말을 들어봐야….") == "other"
    assert classify_dialogue("가야...") == "other"
    # A genuine, complete casual "-야" sentence must still be detected.
    assert classify_dialogue("그건 내 거야.") == "casual"
    assert classify_dialogue("가야.") == "casual"


def test_interrupted_connective_no_longer_triggers_mixed_tone() -> None:
    tones = sentence_tones("마르소 선생님, 이건 아니에요. 제 말을 들어봐야….")

    assert tones == {"polite"}


def test_second_dialogue_pass_detects_pronoun_and_honorific_conflicts(monkeypatch, tmp_path: Path) -> None:
    epub = tmp_path / "[k] Test.epub"
    epub.write_bytes(b"placeholder")
    blocks = [
        (
            "chapter.xhtml",
            "“너는 지금 괜찮으세요?” “선생님, 당장 여기서 나가.” " * 10,
        )
    ]
    guide = tmp_path / "relationship_guide.txt"
    guide.write_text(
        "[인물관계 요약]\n- 학생과 교사\n\n[말투 규칙]\n- 학생 -> 교사: 존댓말\n- 교사 -> 학생: 반말\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(dialogue, "read_metadata", lambda _path: ("Test", "Author"))
    monkeypatch.setattr(dialogue, "iter_korean_blocks", lambda _path: blocks)

    review = dialogue.review_dialogue_consistency(epub, relationship_guide=guide)

    assert review.pass_index == 2
    assert review.status == "needs_attention"
    assert review.casual_pronoun_polite_dialogues >= 8
    assert review.title_casual_dialogues >= 8


def test_second_dialogue_pass_is_independent_and_reports_checked(monkeypatch, tmp_path: Path) -> None:
    epub = tmp_path / "[k] Test.epub"
    epub.write_bytes(b"placeholder")
    guide = tmp_path / "relationship_guide.txt"
    guide.write_text(
        "[인물관계 요약]\n- 친구 관계\n\n[말투 규칙]\n- A -> B: 반말\n- B -> A: 반말\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(dialogue, "read_metadata", lambda _path: ("Test", "Author"))
    monkeypatch.setattr(
        dialogue,
        "iter_korean_blocks",
        lambda _path: [("chapter.xhtml", "“오늘 같이 가자.” “그래, 바로 출발하자.”")],
    )

    review = dialogue.review_dialogue_consistency(epub, relationship_guide=guide)

    assert review.status == "checked"
    assert review.dialogue_count == 2
