#!/usr/bin/env python3
"""Run deterministic checks that do not require web accounts or API keys."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(label: str, command: list[str]) -> None:
    print(f"\n== {label} ==", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    run("Installed dependency consistency", [sys.executable, "-m", "pip", "check"])
    ruff = shutil.which("ruff")
    ruff_command = [ruff, "check", "."] if ruff else [sys.executable, "-m", "ruff", "check", "."]
    run("Ruff", ruff_command)
    run(
        "Python bytecode compilation",
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "audiobook_maker.py",
            "web_app.py",
            "webui",
            "scripts",
            "tests",
        ],
    )

    zsh = shutil.which("zsh")
    if zsh is None:
        raise RuntimeError("zsh is required to validate the macOS workflow wrappers")
    shell_scripts = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "scripts").glob("*.sh"))
    if shell_scripts:
        run("zsh wrapper syntax", [zsh, "-n", *shell_scripts])

    run("Pytest", [sys.executable, "-m", "pytest", "-q"])

    git = shutil.which("git")
    if git and (ROOT / ".git").exists():
        run("Git whitespace validation", [git, "diff", "--check", "HEAD"])
    print("\nAll deterministic quality checks passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
