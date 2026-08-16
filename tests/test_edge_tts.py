import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import argparse

from audiobook_maker import (
    EDGE_TTS_VOICES,
    EDGE_TTS_DEFAULT_VOICE,
    edge_tts_voice_choices,
    default_edge_tts_voice,
    normalize_voice_name,
    validate_voice,
    temp_audio_suffix,
    synthesize_edge_tts_sections,
    AudioSection,
)
from web_app import create_app


def test_edge_tts_constants_and_helpers():
    assert len(edge_tts_voice_choices()) >= 10
    assert default_edge_tts_voice() == "ko-KR-SunHiNeural"
    assert "ko-KR-SunHiNeural" in EDGE_TTS_VOICES
    assert "ko-KR-InJoonNeural" in EDGE_TTS_VOICES
    assert "en-US-AvaNeural" in EDGE_TTS_VOICES

    # Normalization
    assert normalize_voice_name("edge_tts", "ko-kr-sunhineural") == "ko-KR-SunHiNeural"
    assert normalize_voice_name("edge_tts", "en-us-avaneural") == "en-US-AvaNeural"


def test_validate_voice_edge_tts():
    args = argparse.Namespace(provider="edge_tts")
    validate_voice(args, "ko-KR-SunHiNeural")
    validate_voice(args, "en-US-AvaNeural")

    with pytest.raises(RuntimeError, match="설정한 Edge TTS 음성을 찾지 못했습니다"):
        validate_voice(args, "invalid_voice_name_123")


def test_temp_audio_suffix_edge_tts():
    args = argparse.Namespace(provider="edge_tts")
    assert temp_audio_suffix(args) == ".mp3"


def test_synthesize_edge_tts_sections(tmp_path):
    sections = [
        AudioSection(index=1, title="1장", text="안녕하세요. 테스트 텍스트입니다."),
        AudioSection(index=2, title="2장", text="두 번째 섹션 테스트 텍스트입니다."),
    ]
    args = argparse.Namespace(
        provider="edge_tts",
        edge_tts_max_attempts=3,
        edge_tts_rate="+0%",
        edge_tts_pitch="+0Hz",
        edge_tts_volume="+0%",
        heartbeat_file=None,
    )

    with patch("audiobook_maker.request_edge_tts_audio_file") as mock_req:
        def fake_create(text, output_path, **kwargs):
            output_path.write_bytes(b"dummy_mp3_content")
        mock_req.side_effect = fake_create

        audio_files = synthesize_edge_tts_sections(
            sections,
            args=args,
            voice="ko-KR-SunHiNeural",
            work_dir=tmp_path,
        )

        assert len(audio_files) == 2
        assert audio_files[0] == tmp_path / "section_0001.mp3"
        assert audio_files[1] == tmp_path / "section_0002.mp3"
        assert (tmp_path / "section_0001.txt").read_text(encoding="utf-8") == "안녕하세요. 테스트 텍스트입니다."


def test_web_app_tts_api(tmp_path):
    app = create_app(data_root=tmp_path)
    client = app.test_client()

    # Voices API
    res = client.get("/api/tts/voices?provider=edge_tts")
    assert res.status_code == 200
    data = res.get_json()
    assert data["provider"] == "edge_tts"
    assert any(v["id"] == "ko-KR-SunHiNeural" for v in data["voices"])
    assert any(v["id"] == "en-US-AvaNeural" for v in data["voices"])

    # Preview API
    with patch("web_app.request_edge_tts_audio_file") as mock_req:
        def fake_create(text, output_path, **kwargs):
            output_path.write_bytes(b"dummy_mp3_sample")
        mock_req.side_effect = fake_create

        preview_res = client.get("/api/tts/preview?provider=edge_tts&voice=ko-KR-SunHiNeural")
        assert preview_res.status_code == 200
        assert preview_res.mimetype == "audio/mpeg"
        assert preview_res.data == b"dummy_mp3_sample"
