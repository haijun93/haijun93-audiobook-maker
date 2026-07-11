from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import final_epub_literary_review as literary  # noqa: E402
from idle_completed_epub_tone_maintenance import discover_candidates  # noqa: E402


def test_literary_review_detects_high_confidence_translation_style_errors(monkeypatch, tmp_path: Path) -> None:
    epub = tmp_path / "[k] Test Book.epub"
    epub.write_bytes(b"placeholder")
    blocks = [
        ("chapter1.xhtml", "나는 그 결정이 잘못되어졌다는 것을 알고 있었다."),
        ("chapter1.xhtml", "그날 방 안에서 벌어진 기묘하고 불편한 일을 나는 아주 오랜 시간이 지난 지금까지도 생생하게 기억해요."),
        ("chapter2.xhtml", "그의 갑작스러운 대답은 앞뒤 문맥과 맞지 않았고 그 자리에 있던 모든 사람에게 이상하게 들렸습니다요."),
    ]
    monkeypatch.setattr(literary, "read_metadata", lambda _path: ("Test Book", "Author"))
    monkeypatch.setattr(literary, "iter_korean_blocks", lambda _path: blocks)

    review = literary.review_epub_literary_style(epub)

    assert review.status == "needs_attention"
    assert review.double_passive_blocks == 1
    assert review.malformed_ending_blocks == 1
    assert review.narrative_polite_blocks == 2


def test_literary_review_keeps_translationese_as_nonblocking_candidate(monkeypatch, tmp_path: Path) -> None:
    epub = tmp_path / "[k] Test Book.epub"
    epub.write_bytes(b"placeholder")
    blocks = [("chapter1.xhtml", "그것은 오래된 규칙에 의해 만들어진 관습에 관한 것이었다.")]
    monkeypatch.setattr(literary, "read_metadata", lambda _path: ("Test Book", "Author"))
    monkeypatch.setattr(literary, "iter_korean_blocks", lambda _path: blocks)

    review = literary.review_epub_literary_style(epub)

    assert review.status == "checked"
    assert review.translationese_counts


def test_completed_epubs_without_work_manifest_are_still_discovered(tmp_path: Path) -> None:
    k_dir = tmp_path / "[k]" / "Thriller"
    ke_dir = tmp_path / "[k-e]" / "Thriller"
    k_dir.mkdir(parents=True)
    ke_dir.mkdir(parents=True)
    (k_dir / "[k] Example Author.epub").write_bytes(b"epub")
    (ke_dir / "[k-e] Example Author.epub").write_bytes(b"epub")

    candidates = discover_candidates(tmp_path)

    assert len(candidates) == 2
    assert {candidate.kind for candidate in candidates} == {"k", "k-e"}
    assert all(candidate.guide is None for candidate in candidates)
