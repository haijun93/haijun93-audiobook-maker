from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def slugify(text: str, fallback: str = "item") -> str:
    value = re.sub(r"[^\w\-가-힣]+", "-", text.strip(), flags=re.UNICODE)
    value = re.sub(r"-{2,}", "-", value).strip("-_.")
    return value or fallback


def sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def sha1_payload(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha1_text(encoded)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_command(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        text=True,
        capture_output=True,
    )


def require_binary(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise RuntimeError(f"`{name}` 명령을 찾지 못했습니다. 먼저 설치하세요.")
    return resolved


def detect_torch_device(requested: str = "auto") -> str:
    if requested and requested != "auto":
        return requested
    try:
        import torch
    except Exception:
        return "cpu"

    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def ffprobe_duration_ms(path: Path) -> int:
    require_binary("ffprobe")
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    payload = json.loads(result.stdout or "{}")
    duration = float(payload.get("format", {}).get("duration", 0.0) or 0.0)
    return int(round(duration * 1000))

