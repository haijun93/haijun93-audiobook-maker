#!/usr/bin/env python3
"""Create the current multi-account general-translation queue."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from audiobook_maker import WEB_ACCOUNT_PROFILE_BASES
from scripts.atomic_io import atomic_write_json
from webui.continuous_scheduler import validate_config


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / ".work" / "continuous_scheduler" / "config.json"
DEFAULT_STATE_DIR = ROOT / ".work" / "continuous_scheduler"

VK_ACCOUNT2_BOOKS = (
    ("14. MAD MABEL by Sally Hepworth.epub", "Mad Mabel", -100),
    ("15. THE FIVE-STAR WEEKEND by Elin Hilderbrand.epub", "The Five-Star Weekend", -99),
    ("@my_fiction_books_Edition (Matt Haig, Chris Riddell.epub", "How to Stop Time", -98),
)
PAM_BOOKS = (
    (
        "Dark Notes Pam Godwin (3.92)",
        "[e] Dark Notes Pam Godwin (3.92).epub",
        "account3",
        1,
    ),
    (
        "Unshackle Godwin Pam (4.22)",
        "[e] Unshackle Godwin Pam (4.22).epub",
        "account2",
        10,
    ),
    (
        "Cage of Ice and Echoes Pam Godwin (4.43)",
        "[e] Cage of Ice and Echoes Pam Godwin (4.43).epub",
        "main",
        10,
    ),
    (
        "Beneath the Burn Pam Godwin (4.02)",
        "[e] Beneath the Burn Pam Godwin (4.02).epub",
        "account2",
        20,
    ),
    (
        "Dead of Eve Godwin Pam (3.81)",
        "[e] Dead of Eve Godwin Pam (3.81).epub",
        "main",
        20,
    ),
    (
        "Sea of Ruin Pam Godwin (3.89)",
        "[e] Sea of Ruin Pam Godwin (3.89).epub",
        "account2",
        30,
    ),
    (
        "Dominate Godwin Pam (4.08)",
        "[e] Dominate Godwin Pam (4.08).epub",
        "account3",
        20,
    ),
    (
        "Lessons in Sin Pam Godwin (3.96)",
        "[e] Lessons in Sin Pam Godwin (3.96).epub",
        "main",
        30,
    ),
    (
        "Heart of Frost and Scars Frozen Fate Book 3 Pam Godwin",
        "[e] Heart of Frost and Scars Frozen Fate Book 3 Pam Godwin.epub",
        "account2",
        30,
    ),
)


def task_id(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def safe_work_slug(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9가-힣._-]+", "_", text).strip("_")
    return re.sub(r"_+", "_", slug)[:120] or "book"


def make_vk_task(
    *,
    source_name: str,
    title: str,
    priority: int,
    library_root: Path,
) -> dict[str, object]:
    source = library_root / "new books from vk" / source_name
    stem = source.stem
    work_dir = (
        library_root
        / "_chatgpt_translate_work"
        / f"new_books_from_vk__{safe_work_slug(stem)}"
    )
    return {
        "id": f"vk-account2-{task_id(title)}",
        "title": f"VK · {title}",
        "providers": ["chatgpt", "gemini"],
        "preferred_accounts": ["chatgpt"],
        "priority": priority,
        "max_attempts": 20,
        "max_stall_restarts": 1,
        "work_dir": str(work_dir),
        "command": [
            "{python}",
            "scripts/run_soseol2_chatgpt_k_e_batch.py",
            "--only",
            stem,
            "--watch-new-seconds",
            "0",
            "--web-provider",
            "{provider}",
            "--web-max-attempts",
            "3",
            "--inter-request-delay-sec",
            "8",
        ],
        "completion_paths": [
            str(library_root / "[k-e]" / f"[k-e] {stem}.epub"),
            str(library_root / "[k]" / f"[k] {stem}.epub"),
        ],
    }


def make_pam_general_task(
    *,
    title: str,
    input_epub: Path,
    stage_root: Path,
    library_root: Path,
    preferred_account: str,
    priority: int,
) -> dict[str, object]:
    book_stage = stage_root / title
    work_dir = library_root / "_chatgpt_translate_work" / f"pam_general__{safe_work_slug(title)}"
    study_output = book_stage / f"[study] {title}.epub"
    bilingual_output = book_stage / f"[k-e] {title}.epub"
    korean_output = book_stage / f"[k] {title}.epub"
    english_study_output = book_stage / "[e-s]" / f"[e-s] {title}.epub"
    bilingual_destination = library_root / "[k-e]" / "#Pam Godwin" / f"[k-e] {title}.epub"
    korean_destination = library_root / "[k]" / "#Pam Godwin" / f"[k] {title}.epub"
    study_destination = library_root / "[study]" / "#Pam Godwin" / f"[study] {title}.epub"
    english_study_destination = library_root / "[e-s]" / "#Pam Godwin" / f"[e-s] {title}.epub"
    return {
        "id": f"pam-general-{task_id(title)}",
        "title": title,
        "providers": ["gemini"],
        "preferred_accounts": [preferred_account],
        "priority": priority,
        "max_attempts": 20,
        "max_stall_restarts": 1,
        "work_dir": str(work_dir),
        "command": [
            "{python}",
            "scripts/translate_epub_with_chatgpt_web_to_study_epub.py",
            "--input-epub",
            str(input_epub),
            "--output-epub",
            str(bilingual_output),
            "--study-output-epub",
            str(study_output),
            "--work-dir",
            str(work_dir),
            "--book-title-ko",
            title,
            "--max-chars-per-chunk",
            "6000",
            "--request-timeout-sec",
            "1200",
            "--web-max-attempts",
            "3",
            "--chunks-per-conversation",
            "10",
            "--inter-request-delay-sec",
            "8",
            "--heartbeat-file",
            str(work_dir / "heartbeat.json"),
            "--web-provider",
            "{provider}",
        ],
        "post_commands": [
            [
                "{python}",
                "scripts/make_korean_only_epubs.py",
                str(book_stage),
                "--overwrite",
            ],
            [
                "{python}",
                "scripts/make_english_study_epubs.py",
                str(book_stage),
                "--output-root",
                str(book_stage / "[e-s]"),
                "--overwrite",
            ]
        ],
        "deploy": [
            {"source": str(bilingual_output), "destination": str(bilingual_destination)},
            {"source": str(korean_output), "destination": str(korean_destination)},
            {"source": str(study_output), "destination": str(study_destination)},
            {"source": str(english_study_output), "destination": str(english_study_destination)},
        ],
        "completion_paths": [
            str(bilingual_destination),
            str(korean_destination),
            str(study_destination),
            str(english_study_destination),
        ],
    }


def build_config(*, library_root: Path, scratch_root: Path, state_dir: Path) -> dict[str, object]:
    tasks = [
        make_vk_task(
            source_name=source_name,
            title=title,
            priority=priority,
            library_root=library_root,
        )
        for source_name, title, priority in VK_ACCOUNT2_BOOKS
    ]
    for title, input_name, preferred_account, priority in PAM_BOOKS:
        tasks.append(
            make_pam_general_task(
                title=title,
                input_epub=library_root / "[e]" / "#Pam Godwin" / input_name,
                stage_root=scratch_root / "pam_general_translation",
                library_root=library_root,
                preferred_account=preferred_account,
                priority=priority,
            )
        )
    payload: dict[str, object] = {
        "version": 1,
        "repo_dir": str(ROOT),
        "python": str(ROOT / ".venv311" / "bin" / "python"),
        "state_dir": str(state_dir),
        "poll_seconds": 2,
        "startup_adoption_grace_seconds": 8,
        "external_missing_grace_seconds": 8,
        "browser_launch_stale_seconds": 3 * 60,
        "heartbeat_stale_seconds": 30 * 60,
        "operations_audit_interval_seconds": 30 * 60,
        "operations_audit_provider_error_threshold": 6,
        "operations_audit_format_error_threshold": 3,
        "accounts": [
            {
                "id": "main",
                "label": "Gemini main",
                "provider": "gemini",
                "profile_dir": str(WEB_ACCOUNT_PROFILE_BASES["main"]),
            },
            {
                "id": "account2",
                "label": "Gemini account2",
                "provider": "gemini",
                "profile_dir": str(WEB_ACCOUNT_PROFILE_BASES["account2"]),
            },
            {
                "id": "account3",
                "label": "Gemini account3",
                "provider": "gemini",
                "profile_dir": str(WEB_ACCOUNT_PROFILE_BASES["account3"]),
            },
            {
                "id": "chatgpt",
                "label": "ChatGPT web",
                "provider": "chatgpt",
                "profile_dir": str(WEB_ACCOUNT_PROFILE_BASES["chatgpt"]),
                "env": {
                    "AUDIOBOOK_CHATGPT_ACCOUNT_TIER": "paid",
                    "AUDIOBOOK_CHATGPT_EXPECTED_ACCOUNT": "haijun93@gmail.com",
                    "AUDIOBOOK_CHATGPT_EXPECTED_TIER": "plus",
                    "AUDIOBOOK_CHATGPT_PACING_SCOPE": "general_translation",
                    # 2026-08-16 haijun93@gmail.com이 Plus 계정으로 재로그인 확인됨(재로그인
                    # 전 300/450/900초였던 건 실제로는 세션 만료를 rate limit으로 오진한 결과).
                    # Gemini 계정 기본 간격(8~12초)에 맞춰 대폭 단축하되 ChatGPT 웹 UI가 더
                    # 불안정했던 이력을 고려해 약간의 여유를 둔다.
                    "AUDIOBOOK_CHATGPT_MIN_REQUEST_INTERVAL_SEC": "20",
                    "AUDIOBOOK_CHATGPT_PENALTY_REQUEST_INTERVAL_SEC": "60",
                    "AUDIOBOOK_CHATGPT_MAX_REQUEST_INTERVAL_SEC": "240",
                    "AUDIOBOOK_CHATGPT_PACING_RECOVERY_SUCCESS_COUNT": "3",
                },
            },
        ],
        "tasks": tasks,
    }
    validate_config(payload)
    return payload


def validate_sources(config: dict[str, object]) -> list[Path]:
    missing: list[Path] = []
    for task in config["tasks"]:  # type: ignore[index]
        command = task["command"]  # type: ignore[index]
        for option in ("--input-epub",):
            if option not in command:
                continue
            path = Path(command[command.index(option) + 1])
            if not path.exists():
                missing.append(path)
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-root", type=Path, default=Path.home() / "Desktop" / "소설2")
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    args = parser.parse_args()

    config = build_config(
        library_root=args.library_root.expanduser().resolve(),
        scratch_root=args.scratch_root.expanduser().resolve(),
        state_dir=args.state_dir.expanduser().resolve(),
    )
    missing = validate_sources(config)
    if missing:
        raise SystemExit("Missing queue sources:\n" + "\n".join(str(path) for path in missing))
    config_path = args.config.expanduser().resolve()
    atomic_write_json(config_path, config, trailing_newline=True)
    completed = sum(
        all(Path(path).is_file() for path in task["completion_paths"])
        for task in config["tasks"]
    )
    print(f"Wrote {len(config['tasks'])} tasks to {config_path} ({completed} already completed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
