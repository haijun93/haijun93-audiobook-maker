#!/usr/bin/env python3
"""Durable atomic file helpers for resumable batch artifacts."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def _sync_directory(path: Path) -> None:
    """Persist a rename where the platform supports directory fsync."""

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _existing_mode(path: Path) -> int | None:
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        return None


@contextmanager
def atomic_output_path(path: Path) -> Iterator[Path]:
    """Yield a unique same-directory path and replace ``path`` on success.

    Writers can create large structured artifacts such as EPUBs at the yielded
    path. An exception leaves the previous destination untouched.
    """

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = _existing_mode(path)
    descriptor, temp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    os.close(descriptor)
    temp_path = Path(temp_name)
    try:
        yield temp_path
        with temp_path.open("rb") as handle:
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temp_path, mode)
        os.replace(temp_path, path)
        _sync_directory(path.parent)
    finally:
        temp_path.unlink(missing_ok=True)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    with atomic_output_path(path) as temp_path:
        with temp_path.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    atomic_write_bytes(path, text.encode(encoding))


def atomic_write_json(path: Path, payload: object, *, trailing_newline: bool = False) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if trailing_newline:
        text += "\n"
    atomic_write_text(path, text)
