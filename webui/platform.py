from __future__ import annotations

import os
import shutil
from pathlib import Path


def discover_ebook_convert() -> str:
    configured = os.getenv("EBOOK_CONVERT_PATH", "").strip()
    if configured:
        return str(Path(configured).expanduser())
    executable = shutil.which("ebook-convert")
    if executable:
        return executable
    candidates = [
        Path("/Applications/calibre.app/Contents/MacOS/ebook-convert"),
        Path.home() / "Applications/calibre.app/Contents/MacOS/ebook-convert",
    ]
    for env_name in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        base = os.getenv(env_name, "").strip()
        if base:
            candidates.append(Path(base) / "Calibre2/ebook-convert.exe")
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return ""
