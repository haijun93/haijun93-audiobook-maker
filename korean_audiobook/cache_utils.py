from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .utils import ensure_dir, read_json, write_json


@dataclass
class CacheEntry:
    key: str
    audio_path: Path
    metadata: dict[str, Any]


class AudioCache:
    def __init__(self, root: Path) -> None:
        self.root = ensure_dir(root)
        self.audio_dir = ensure_dir(self.root / "audio")
        self.index_path = self.root / "index.json"
        self.index = read_json(self.index_path, default={})

    def get(self, key: str) -> CacheEntry | None:
        payload = self.index.get(key)
        if not payload:
            return None
        audio_path = Path(payload["audio_path"])
        if not audio_path.exists():
            return None
        return CacheEntry(key=key, audio_path=audio_path, metadata=dict(payload.get("metadata", {})))

    def put(self, key: str, source_path: Path, *, metadata: dict[str, Any]) -> CacheEntry:
        cached_path = self.audio_dir / f"{key}{source_path.suffix.lower()}"
        if source_path.resolve() != cached_path.resolve():
            shutil.copy2(source_path, cached_path)
        entry = {
            "audio_path": str(cached_path),
            "metadata": metadata,
        }
        self.index[key] = entry
        write_json(self.index_path, self.index)
        return CacheEntry(key=key, audio_path=cached_path, metadata=metadata)

