from __future__ import annotations

import zipfile
from pathlib import Path

from webui.book_organizer import (
    CURATED_GENRE_BY_TITLE,
    audit_author_genre_placements,
    build_library_registry,
    build_organized_filename,
    classify_genre_subjects,
    core_series_search_title,
    find_finished_match,
    guess_genre_online,
    organize_from_output_dir,
    organize_single_epub,
    reclassify_uncategorized,
)


def _write_epub(path: Path, *, title: str, author: str) -> None:
    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
  </metadata>
</package>
"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("content.opf", opf)


def test_build_library_registry_scans_nested_genre_folders(tmp_path: Path) -> None:
    library_root = tmp_path / "[k]"
    genre_dir = library_root / "Mystery_Thriller_Crime"
    genre_dir.mkdir(parents=True)
    _write_epub(genre_dir / "[k] Gone Girl Gillian Flynn (4.12).epub", title="Gone Girl", author="Gillian Flynn")

    registry = build_library_registry(library_root)

    assert len(registry) == 1
    assert registry[0]["norm_title"] == "gone girl"


def test_build_library_registry_catches_duplicate_missed_by_static_snapshot(tmp_path: Path) -> None:
    # Simulates a book that was organized into the library *after* a static
    # snapshot (e.g. k_collection_blog.html) was generated - the live scan
    # must still catch it as a duplicate.
    library_root = tmp_path / "[k]"
    genre_dir = library_root / "Mystery_Thriller_Crime"
    genre_dir.mkdir(parents=True)
    _write_epub(genre_dir / "[k] Gone Girl Gillian Flynn (4.12).epub", title="Gone Girl", author="Gillian Flynn")

    registry = build_library_registry(library_root)
    match = find_finished_match("Gone Girl", "Gillian Flynn", registry)

    assert match is not None


def test_build_library_registry_returns_empty_for_missing_folder(tmp_path: Path) -> None:
    registry = build_library_registry(tmp_path / "does-not-exist")

    assert registry == []


def test_build_organized_filename_appends_rating_when_present() -> None:
    name = build_organized_filename("[k]", {"title": "Gone Girl", "author": "Gillian Flynn"}, rating=4.123)

    assert name == "[k] Gone Girl Gillian Flynn (4.12).epub"


def test_build_organized_filename_omits_rating_when_none() -> None:
    name = build_organized_filename("[k]", {"title": "Gone Girl", "author": "Gillian Flynn"}, rating=None)

    assert name == "[k] Gone Girl Gillian Flynn.epub"


def test_organize_single_epub_files_english_prefix_into_genre_folder(tmp_path: Path) -> None:
    source = tmp_path / "staging" / "[e] Dark Places Gillian Flynn.epub"
    source.parent.mkdir(parents=True)
    _write_epub(source, title="Dark Places", author="Gillian Flynn")
    target_root = tmp_path / "[e]"

    moved = organize_single_epub(source, target_root, use_network=False, mode="move", force_genre="Mystery_Thriller_Crime")

    assert moved is True
    assert not source.exists()
    matches = list(target_root.glob("Mystery_Thriller_Crime/*.epub"))
    assert len(matches) == 1
    assert matches[0].name == "[e] Dark Places Gillian Flynn.epub"


def test_organize_single_epub_files_study_prefix_into_genre_folder(tmp_path: Path) -> None:
    source = tmp_path / "staging" / "[study] Dark Places Gillian Flynn.epub"
    source.parent.mkdir(parents=True)
    _write_epub(source, title="Dark Places", author="Gillian Flynn")
    target_root = tmp_path / "[study]"

    moved = organize_single_epub(source, target_root, use_network=False, mode="move", force_genre="Mystery_Thriller_Crime")

    assert moved is True
    matches = list(target_root.glob("Mystery_Thriller_Crime/*.epub"))
    assert len(matches) == 1
    assert matches[0].name == "[study] Dark Places Gillian Flynn.epub"


def test_organize_single_epub_files_english_study_prefix_into_genre_folder(tmp_path: Path) -> None:
    source = tmp_path / "staging" / "[e-s] Dark Places Gillian Flynn.epub"
    source.parent.mkdir(parents=True)
    _write_epub(source, title="Dark Places", author="Gillian Flynn")
    target_root = tmp_path / "[e-s]"

    moved = organize_single_epub(source, target_root, use_network=False, mode="move", force_genre="Mystery_Thriller_Crime")

    assert moved is True
    matches = list(target_root.glob("Mystery_Thriller_Crime/*.epub"))
    assert len(matches) == 1
    assert matches[0].name == "[e-s] Dark Places Gillian Flynn.epub"


def test_organize_from_output_dir_moves_all_five_versions_when_roots_given(tmp_path: Path) -> None:
    staging = tmp_path / "vk"
    for prefix in ("[e]", "[k]", "[k-e]", "[study]", "[e-s]"):
        folder = staging / prefix
        folder.mkdir(parents=True)
        _write_epub(folder / f"{prefix} Dark Places Gillian Flynn.epub", title="Dark Places", author="Gillian Flynn")

    english_root = tmp_path / "[e]"
    korean_root = tmp_path / "[k]"
    bilingual_root = tmp_path / "[k-e]"
    study_root = tmp_path / "[study]"
    english_study_root = tmp_path / "[e-s]"

    moved_count = organize_from_output_dir(
        staging,
        korean_root,
        bilingual_root,
        english_root=english_root,
        study_root=study_root,
        english_study_root=english_study_root,
        use_network=False,
        mode="move",
    )

    assert moved_count == 5
    for root, prefix in (
        (english_root, "[e]"),
        (korean_root, "[k]"),
        (bilingual_root, "[k-e]"),
        (study_root, "[study]"),
        (english_study_root, "[e-s]"),
    ):
        matches = list(root.glob("*/*.epub"))
        assert len(matches) == 1
        assert matches[0].name == f"{prefix} Dark Places Gillian Flynn.epub"
    # Originals are gone from the staging folders (mode="move").
    for prefix in ("[e]", "[k]", "[k-e]", "[study]", "[e-s]"):
        assert not list((staging / prefix).glob("*.epub"))


def test_organize_from_output_dir_moves_all_four_versions_when_roots_given(tmp_path: Path) -> None:
    staging = tmp_path / "vk"
    for prefix in ("[e]", "[k]", "[k-e]", "[study]"):
        folder = staging / prefix
        folder.mkdir(parents=True)
        _write_epub(folder / f"{prefix} Dark Places Gillian Flynn.epub", title="Dark Places", author="Gillian Flynn")

    english_root = tmp_path / "[e]"
    korean_root = tmp_path / "[k]"
    bilingual_root = tmp_path / "[k-e]"
    study_root = tmp_path / "[study]"

    moved_count = organize_from_output_dir(
        staging,
        korean_root,
        bilingual_root,
        english_root=english_root,
        study_root=study_root,
        use_network=False,
        mode="move",
    )

    assert moved_count == 4
    for root, prefix in (
        (english_root, "[e]"),
        (korean_root, "[k]"),
        (bilingual_root, "[k-e]"),
        (study_root, "[study]"),
    ):
        matches = list(root.glob("*/*.epub"))
        assert len(matches) == 1
        assert matches[0].name == f"{prefix} Dark Places Gillian Flynn.epub"
    # Originals are gone from the staging folders (mode="move").
    for prefix in ("[e]", "[k]", "[k-e]", "[study]"):
        assert not list((staging / prefix).glob("*.epub"))


def test_organize_from_output_dir_ignores_e_and_study_when_roots_omitted(tmp_path: Path) -> None:
    staging = tmp_path / "vk"
    for prefix in ("[e]", "[k]", "[k-e]", "[study]"):
        folder = staging / prefix
        folder.mkdir(parents=True)
        _write_epub(folder / f"{prefix} Dark Places Gillian Flynn.epub", title="Dark Places", author="Gillian Flynn")

    korean_root = tmp_path / "[k]"
    bilingual_root = tmp_path / "[k-e]"

    moved_count = organize_from_output_dir(staging, korean_root, bilingual_root, use_network=False, mode="move")

    assert moved_count == 2
    assert list((staging / "[e]").glob("*.epub"))
    assert list((staging / "[study]").glob("*.epub"))


def test_reclassify_uncategorized_moves_books_whose_title_now_matches_a_keyword(tmp_path: Path) -> None:
    library_root = tmp_path / "[k]"
    uncategorized = library_root / "Uncategorized"
    uncategorized.mkdir(parents=True)
    _write_epub(
        uncategorized / "[k] The Silent Murder Jane Roe.epub",
        title="The Silent Murder",
        author="Jane Roe",
    )

    moved_count = reclassify_uncategorized(library_root, use_network=False, mode="move")

    assert moved_count == 1
    assert not list(uncategorized.glob("*.epub"))
    matches = list(library_root.glob("Mystery_Thriller_Crime/*.epub"))
    assert len(matches) == 1
    assert matches[0].name == "[k] The Silent Murder Jane Roe.epub"


def test_reclassify_uncategorized_leaves_unresolvable_books_in_place(tmp_path: Path) -> None:
    library_root = tmp_path / "[k]"
    uncategorized = library_root / "Uncategorized"
    uncategorized.mkdir(parents=True)
    source = uncategorized / "[k] Quiet Mornings John Doe.epub"
    _write_epub(source, title="Quiet Mornings", author="John Doe")

    moved_count = reclassify_uncategorized(library_root, use_network=False, mode="move")

    assert moved_count == 0
    assert source.exists()
    # No spurious "(2)"-suffixed duplicate from a self-move.
    assert [p.name for p in uncategorized.glob("*.epub")] == ["[k] Quiet Mornings John Doe.epub"]


def test_reclassify_uncategorized_processes_nested_author_folders_and_cleans_up_empty_dirs(tmp_path: Path) -> None:
    library_root = tmp_path / "[k]"
    author_dir = library_root / "Uncategorized" / "Jane Roe"
    author_dir.mkdir(parents=True)
    _write_epub(
        author_dir / "[k] The Silent Murder Jane Roe.epub",
        title="The Silent Murder",
        author="Jane Roe",
    )

    moved_count = reclassify_uncategorized(library_root, use_network=False, mode="move")

    assert moved_count == 1
    assert not author_dir.exists()
    matches = list(library_root.glob("Mystery_Thriller_Crime/*.epub"))
    assert len(matches) == 1


def test_organize_single_epub_does_not_treat_uncategorized_as_an_established_author_folder(tmp_path: Path) -> None:
    # Regression: two books by the same author landing in Uncategorized together
    # (e.g. a transient API outage) must not make Uncategorized "sticky" for that
    # author forever - a book with a real genre-keyword title should still escape it.
    library_root = tmp_path / "[k]"
    uncategorized = library_root / "Uncategorized"
    uncategorized.mkdir(parents=True)
    _write_epub(
        uncategorized / "[k] Some Other Book Jane Roe.epub",
        title="Some Other Book",
        author="Jane Roe",
    )

    incoming = tmp_path / "staging" / "[k] The Silent Murder Jane Roe.epub"
    incoming.parent.mkdir(parents=True)
    _write_epub(incoming, title="The Silent Murder", author="Jane Roe")

    moved = organize_single_epub(incoming, library_root, use_network=False, mode="move")

    assert moved is True
    matches = list(library_root.glob("Mystery_Thriller_Crime/*.epub"))
    assert len(matches) == 1
    assert matches[0].name == "[k] The Silent Murder Jane Roe.epub"


def test_classify_genre_subjects_returns_none_for_no_subjects() -> None:
    assert classify_genre_subjects([]) is None


def test_classify_genre_subjects_picks_genre_with_the_most_evidence() -> None:
    # Fantasy_Science_Fiction is checked before Business_Economics in CATEGORY_KEYWORDS,
    # so the old first-match-in-priority-order algorithm would have picked Fantasy here
    # purely because of table order, even though the real evidence points to Business.
    subjects = ["Magic tricks explained", "BUSINESS & ECONOMICS / Leadership", "Management"]

    assert classify_genre_subjects(subjects) == "Business_Economics"


def test_classify_genre_subjects_weighs_bisac_style_subjects_higher(tmp_path: Path) -> None:
    # A single BISAC-style "X / Y / Z" subject (weight 3) should outrank two loose
    # free-text subjects for a different genre (weight 1 each = 2).
    subjects = [
        "BUSINESS & ECONOMICS / Leadership",
        "history",
        "politic",
    ]

    assert classify_genre_subjects(subjects) == "Business_Economics"


def test_classify_genre_subjects_ignores_generic_fiction_keyword() -> None:
    # "fiction" alone is too generic to be a real signal for Literary_General_Fiction
    # once actual genre evidence (mystery) is present.
    subjects = ["Fiction", "FICTION / Mystery & Detective / General", "Crimes against"]

    assert classify_genre_subjects(subjects) == "Mystery_Thriller_Crime"


def test_classify_genre_subjects_returns_none_when_only_generic_terms_match() -> None:
    assert classify_genre_subjects(["Fiction", "A novel"]) is None


def test_classify_genre_subjects_does_not_treat_magic_realism_as_fantasy() -> None:
    subjects = ["Latin American literature", "Magic realism (Literature)", "Epic literature"]

    assert classify_genre_subjects(subjects) != "Fantasy_Science_Fiction"


def test_classify_genre_subjects_still_detects_real_fantasy_magic() -> None:
    subjects = ["Magic", "Dragons", "Fiction"]

    assert classify_genre_subjects(subjects) == "Fantasy_Science_Fiction"


def test_core_series_search_title_strips_author_prefix_and_anthology_noise() -> None:
    core = core_series_search_title(
        "Diana Gabaldon - Outlander Series 1-10 Anthology",
        "Diana Gabaldon",
    )

    assert core == "Outlander"


def test_core_series_search_title_strips_boxed_set_and_omnibus_noise() -> None:
    assert core_series_search_title("The Complete Witcher Boxed Set", "") == "The Complete Witcher"
    assert core_series_search_title("Foundation Omnibus", "") == "Foundation"


def test_core_series_search_title_returns_none_when_nothing_to_clean() -> None:
    assert core_series_search_title("Gone Girl", "Gillian Flynn") is None


def test_audit_author_genre_placements_flags_stale_mismatch(tmp_path: Path) -> None:
    # Regression for a real case (2026-08-06): a Paula Hawkins thriller had been
    # sitting under Historical_Fiction since before the current classifier existed.
    # organize_single_epub() would never re-check it (an author's *existing* folder
    # is trusted forever via _find_established_genre_folder), so this audit exists to
    # surface exactly that kind of stale placement for human review.
    library_root = tmp_path / "[k]"
    author_dir = library_root / "Historical_Fiction" / "Jane Roe"
    author_dir.mkdir(parents=True)
    _write_epub(
        author_dir / "[k] The Silent Murder Jane Roe.epub",
        title="The Silent Murder",
        author="Jane Roe",
    )

    findings = audit_author_genre_placements(library_root, use_network=False)

    assert len(findings) == 1
    assert findings[0]["author"] == "Jane Roe"
    assert findings[0]["current_folder"] == "Historical_Fiction"
    assert findings[0]["suggested_folder"] == "Mystery_Thriller_Crime"


def test_audit_author_genre_placements_no_finding_when_folder_matches(tmp_path: Path) -> None:
    library_root = tmp_path / "[k]"
    author_dir = library_root / "Mystery_Thriller_Crime" / "Jane Roe"
    author_dir.mkdir(parents=True)
    _write_epub(
        author_dir / "[k] The Silent Murder Jane Roe.epub",
        title="The Silent Murder",
        author="Jane Roe",
    )

    assert audit_author_genre_placements(library_root, use_network=False) == []


def test_audit_author_genre_placements_skips_curation_and_uncategorized_folders(tmp_path: Path) -> None:
    library_root = tmp_path / "[k]"
    for folder in ("#must read", "Uncategorized"):
        author_dir = library_root / folder / "Jane Roe"
        author_dir.mkdir(parents=True)
        _write_epub(
            author_dir / "[k] The Silent Murder Jane Roe.epub",
            title="The Silent Murder",
            author="Jane Roe",
        )

    assert audit_author_genre_placements(library_root, use_network=False) == []


def test_audit_author_genre_placements_returns_empty_for_missing_folder(tmp_path: Path) -> None:
    assert audit_author_genre_placements(tmp_path / "does-not-exist", use_network=False) == []


def test_classify_genre_subjects_routes_generic_romance_to_plain_romance_folder() -> None:
    # Regression (2026-08-06 library audit): "romance" alone used to map straight to
    # Dark_Romance, which wrongly flagged correctly-shelved contemporary/light
    # romance authors (Abby Jimenez, Colleen Hoover) as needing to move to the dark folder.
    subjects = ["Fiction, romance, contemporary", "Fiction, romance, general"]

    assert classify_genre_subjects(subjects) == "Romance"


def test_classify_genre_subjects_routes_dark_signals_to_dark_romance_folder() -> None:
    subjects = ["Dark romance", "Erotic fiction"]

    assert classify_genre_subjects(subjects) == "Dark_Romance"


def test_guess_genre_online_uses_curated_table_without_network() -> None:
    # Some recent releases have no subject tags yet on Open Library/Google Books (or the
    # lookup is rate-limited) - the curated title table lets those still resolve to the
    # right shelf instead of falling through to Uncategorized. Checked before any network
    # call, so use_network=False must still return the curated answer.
    title, genre = next(iter(CURATED_GENRE_BY_TITLE.items()))
    normalized_title, normalized_author = title.split("|", 1)

    genre_result = guess_genre_online(
        "irrelevant.epub",
        {"title": normalized_title, "author": normalized_author},
        use_network=False,
    )

    assert genre_result == genre
