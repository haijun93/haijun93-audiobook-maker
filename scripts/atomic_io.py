#!/usr/bin/env python3
"""Small atomic file writers for resumable batch artifacts."""

from __future__ import annotations

import json
import os
from pathlib import Path


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temp_path.write_text(text, encoding=encoding)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def atomic_write_json(path: Path, payload: object, *, trailing_newline: bool = False) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if trailing_newline:
        text += "\n"
    atomic_write_text(path, text)
