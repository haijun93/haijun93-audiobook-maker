from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from atomic_io import atomic_output_path, atomic_write_text  # noqa: E402


def test_atomic_output_preserves_existing_file_after_writer_failure(tmp_path: Path) -> None:
    destination = tmp_path / "artifact.epub"
    destination.write_bytes(b"known-good")

    with pytest.raises(RuntimeError, match="injected failure"):
        with atomic_output_path(destination) as temporary:
            temporary.write_bytes(b"partial replacement")
            raise RuntimeError("injected failure")

    assert destination.read_bytes() == b"known-good"
    assert list(tmp_path.glob(f".{destination.name}.*.tmp")) == []


def test_atomic_write_preserves_existing_permissions(tmp_path: Path) -> None:
    destination = tmp_path / "state.json"
    destination.write_text("old", encoding="utf-8")
    destination.chmod(0o640)

    atomic_write_text(destination, "new")

    assert destination.read_text(encoding="utf-8") == "new"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o640
