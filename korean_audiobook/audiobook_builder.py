from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .audio_postprocess import chapter_ffmetadata, concat_audio, master_audio, write_silence_wav
from .cache_utils import AudioCache
from .config import AppConfig
from .korean_text_processing import ChapterPlan, DocumentPlan, NarrationChunk, build_document_plan
from .tts_engine import build_engine
from .utils import ensure_dir, ffprobe_duration_ms, sha1_payload, write_json


@dataclass
class BuildResult:
    output_dir: Path
    chapter_mp3_files: list[Path]
    final_mp3: Path
    final_m4b: Path | None
    manifest_path: Path
    total_chunks: int


class AudiobookBuilder:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.engine = build_engine(config)
        self.cache = AudioCache(config.cache_dir)
        self.state_path = config.work_dir / "state.json"
        self.plan_path = config.work_dir / "plan.json"
        self.manifest_path = config.output_dir / "audiobook_manifest.json"

    def build(self) -> BuildResult:
        try:
            ensure_dir(self.config.output_dir)
            ensure_dir(self.config.work_dir)
            ensure_dir(self.config.chapter_output_dir)

            source_text = self.config.input_file.read_text(encoding="utf-8")
            plan = build_document_plan(source_text, self.config.processing)
            if plan.total_chunks == 0:
                raise RuntimeError("오디오북으로 만들 한국어 문장을 찾지 못했습니다.")
            write_json(self.plan_path, serialize_plan(plan))

            state = self.load_state()
            raw_dir = ensure_dir(self.config.work_dir / "raw")
            mastered_dir = ensure_dir(self.config.work_dir / "mastered")
            silence_dir = ensure_dir(self.config.work_dir / "silence")
            chapter_wav_dir = ensure_dir(self.config.work_dir / "chapter_wav")

            chapter_wavs: list[Path] = []
            chapter_mp3s: list[Path] = []

            for chapter in plan.chapters:
                chapter_items = self.render_chapter(chapter, raw_dir, mastered_dir, silence_dir, state)
                chapter_wav = chapter_wav_dir / f"{chapter.slug}.wav"
                concat_audio(
                    chapter_items,
                    chapter_wav,
                    bitrate_kbps=self.config.mastering.bitrate_kbps,
                )
                chapter_mp3 = self.config.chapter_output_dir / f"{chapter.slug}.mp3"
                concat_audio(
                    [chapter_wav],
                    chapter_mp3,
                    bitrate_kbps=self.config.mastering.bitrate_kbps,
                )
                chapter_wavs.append(chapter_wav)
                chapter_mp3s.append(chapter_mp3)

            final_mp3 = self.config.final_mp3_path
            concat_audio(
                chapter_wavs,
                final_mp3,
                bitrate_kbps=self.config.mastering.bitrate_kbps,
            )

            final_m4b: Path | None = None
            if self.config.output.export_m4b:
                ffmetadata = chapter_ffmetadata(
                    self.config.title,
                    self.config.author,
                    [chapter.title for chapter in plan.chapters],
                    chapter_wavs,
                    self.config.work_dir / "chapters.ffmetadata",
                )
                final_m4b = self.config.final_m4b_path
                concat_audio(
                    chapter_wavs,
                    final_m4b,
                    bitrate_kbps=self.config.mastering.bitrate_kbps,
                    metadata_path=ffmetadata,
                )

            manifest = {
                "title": self.config.title,
                "author": self.config.author,
                "input_file": str(self.config.input_file),
                "engine": asdict(self.config.engine),
                "mastering": asdict(self.config.mastering),
                "processing": asdict(self.config.processing),
                "output": {
                    "directory": str(self.config.output_dir),
                    "chapter_files": [str(path) for path in chapter_mp3s],
                    "final_mp3": str(final_mp3),
                    "final_m4b": str(final_m4b) if final_m4b else None,
                },
                "chapters": [
                    {
                        "index": chapter.index,
                        "title": chapter.title,
                        "slug": chapter.slug,
                        "chunk_count": len(chapter.chunks),
                        "duration_ms": ffprobe_duration_ms(chapter_mp3s[chapter.index - 1]),
                    }
                    for chapter in plan.chapters
                ],
                "total_chunks": plan.total_chunks,
            }
            write_json(self.manifest_path, manifest)
            write_json(self.state_path, state)

            return BuildResult(
                output_dir=self.config.output_dir,
                chapter_mp3_files=chapter_mp3s,
                final_mp3=final_mp3,
                final_m4b=final_m4b,
                manifest_path=self.manifest_path,
                total_chunks=plan.total_chunks,
            )
        finally:
            self.engine.close()

    def render_chapter(
        self,
        chapter: ChapterPlan,
        raw_dir: Path,
        mastered_dir: Path,
        silence_dir: Path,
        state: dict[str, Any],
    ) -> list[Path]:
        chapter_files: list[Path] = []
        for chunk in chapter.chunks:
            mastered_path = self.render_chunk(chunk, raw_dir, mastered_dir, state)
            chapter_files.append(mastered_path)
            if chunk.pause_ms > 0:
                silence_path = silence_dir / f"gap_{self.config.mastering.output_sample_rate}_{chunk.pause_ms}ms.wav"
                if not silence_path.exists():
                    write_silence_wav(silence_path, chunk.pause_ms, self.config.mastering.output_sample_rate)
                chapter_files.append(silence_path)
        return chapter_files

    def render_chunk(
        self,
        chunk: NarrationChunk,
        raw_dir: Path,
        mastered_dir: Path,
        state: dict[str, Any],
    ) -> Path:
        cache_key = sha1_payload(
            {
                "engine": self.engine.signature(),
                "mastering": asdict(self.config.mastering),
                "text": chunk.text,
            }
        )
        state_entry = state.setdefault("chunks", {}).get(chunk.chunk_id)
        if state_entry:
            candidate = Path(state_entry["audio_path"])
            if candidate.exists():
                return candidate

        cached = self.cache.get(cache_key)
        if cached:
            state.setdefault("chunks", {})[chunk.chunk_id] = {
                "cache_key": cache_key,
                "audio_path": str(cached.audio_path),
                "text": chunk.text,
            }
            write_json(self.state_path, state)
            return cached.audio_path

        raw_output = raw_dir / f"{chunk.chunk_id}{self.engine.output_suffix}"
        mastered_output = mastered_dir / f"{chunk.chunk_id}.wav"
        ensure_dir(raw_output.parent)
        ensure_dir(mastered_output.parent)
        self.engine.synthesize_to_file(chunk.text, raw_output)
        master_audio(raw_output, mastered_output, self.config.mastering)
        cached_entry = self.cache.put(
            cache_key,
            mastered_output,
            metadata={
                "chunk_id": chunk.chunk_id,
                "chapter_title": chunk.chapter_title,
                "text": chunk.text,
            },
        )
        state.setdefault("chunks", {})[chunk.chunk_id] = {
            "cache_key": cache_key,
            "audio_path": str(cached_entry.audio_path),
            "text": chunk.text,
        }
        write_json(self.state_path, state)
        return cached_entry.audio_path

    def load_state(self) -> dict[str, Any]:
        if self.config.resume and self.state_path.exists():
            state = json_load(self.state_path)
            if state.get("config_signature") == self.config.build_signature():
                return state
        return {
            "config_signature": self.config.build_signature(),
            "chunks": {},
        }


def serialize_plan(plan: DocumentPlan) -> dict[str, Any]:
    return {
        "chapters": [
            {
                "index": chapter.index,
                "title": chapter.title,
                "slug": chapter.slug,
                "chunks": [
                    {
                        "chunk_id": chunk.chunk_id,
                        "text": chunk.text,
                        "pause_ms": chunk.pause_ms,
                        "is_dialogue": chunk.is_dialogue,
                    }
                    for chunk in chapter.chunks
                ],
            }
            for chapter in plan.chapters
        ]
    }


def json_load(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))
