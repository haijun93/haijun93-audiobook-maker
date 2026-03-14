from __future__ import annotations

from pathlib import Path

from .config import MasteringConfig
from .utils import ensure_dir, ffprobe_duration_ms, require_binary, run_command


def ffmpeg_concat_line(path: Path) -> str:
    escaped = str(path).replace("'", r"'\''")
    return f"file '{escaped}'"


def write_silence_wav(path: Path, duration_ms: int, sample_rate: int) -> Path:
    ensure_dir(path.parent)
    if duration_ms <= 0:
        duration_ms = 1
    import numpy as np
    import soundfile as sf

    frame_count = max(1, int(sample_rate * (duration_ms / 1000.0)))
    samples = np.zeros((frame_count, 1), dtype=np.float32)
    sf.write(str(path), samples, sample_rate, subtype="PCM_16")
    return path


def mastering_filter(config: MasteringConfig) -> str:
    filters: list[str] = []
    if config.trim_silence:
        filters.append(
            "silenceremove="
            f"start_periods=1:start_duration={config.trim_start_silence_sec}:start_threshold={config.trim_threshold_db}dB:"
            f"stop_periods=-1:stop_duration={config.trim_stop_silence_sec}:stop_threshold={config.trim_threshold_db}dB"
        )
    if config.highpass_hz > 0:
        filters.append(f"highpass=f={config.highpass_hz}")
    if config.lowpass_hz > 0:
        filters.append(f"lowpass=f={config.lowpass_hz}")
    filters.append(
        f"loudnorm=I={config.target_lufs}:TP={config.true_peak_db}:LRA={config.loudness_range}"
    )
    return ",".join(filters)


def master_audio(input_path: Path, output_path: Path, config: MasteringConfig) -> Path:
    require_binary("ffmpeg")
    ensure_dir(output_path.parent)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-ac",
        "1",
        "-ar",
        str(config.output_sample_rate),
    ]
    if config.enable:
        cmd.extend(["-af", mastering_filter(config)])
    cmd.extend([str(output_path)])
    run_command(cmd)
    return output_path


def concat_audio(inputs: list[Path], output_path: Path, *, bitrate_kbps: int, metadata_path: Path | None = None) -> Path:
    require_binary("ffmpeg")
    ensure_dir(output_path.parent)
    if not inputs:
        raise RuntimeError(f"concat할 오디오가 없습니다: {output_path}")
    list_path = output_path.with_suffix(".concat.txt")
    list_path.write_text(
        "\n".join(ffmpeg_concat_line(path) for path in inputs),
        encoding="utf-8",
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
    ]
    if metadata_path:
        cmd.extend(["-i", str(metadata_path), "-map_metadata", "1"])
    if output_path.suffix.lower() == ".m4b":
        cmd.extend(["-vn", "-c:a", "aac", "-b:a", f"{bitrate_kbps}k", str(output_path)])
    elif output_path.suffix.lower() == ".wav":
        cmd.extend(["-vn", "-c:a", "pcm_s16le", str(output_path)])
    else:
        cmd.extend(["-vn", "-c:a", "libmp3lame", "-b:a", f"{bitrate_kbps}k", str(output_path)])
    run_command(cmd)
    list_path.unlink(missing_ok=True)
    return output_path


def chapter_ffmetadata(title: str, author: str, chapter_names: list[str], chapter_files: list[Path], output_path: Path) -> Path:
    ensure_dir(output_path.parent)
    start_ms = 0
    lines = [
        ";FFMETADATA1",
        f"title={title}",
        f"artist={author}",
        f"album={title}",
    ]
    for chapter_name, chapter_file in zip(chapter_names, chapter_files):
        duration_ms = ffprobe_duration_ms(chapter_file)
        end_ms = start_ms + duration_ms
        lines.extend(
            [
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={start_ms}",
                f"END={end_ms}",
                f"title={chapter_name}",
            ]
        )
        start_ms = end_ms
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path
