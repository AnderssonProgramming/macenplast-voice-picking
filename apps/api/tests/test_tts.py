"""Tests for the ElevenLabs TTS wrapper. Always mocked — see
`tests/test_tts_live.py` for the real-API smoke test."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from macenplast.voice.tts import DEFAULT_MODEL_ID, DEFAULT_OUTPUT_FORMAT, synthesize


@patch("macenplast.voice.tts.ElevenLabs")
def test_synthesize_joins_chunks_into_bytes(mock_elevenlabs_cls: MagicMock) -> None:
    mock_client = mock_elevenlabs_cls.return_value
    mock_client.text_to_speech.convert.return_value = iter([b"chunk1", b"chunk2"])

    result = synthesize("Correcto.", voice_id="voice-123")

    assert result == b"chunk1chunk2"


@patch("macenplast.voice.tts.ElevenLabs")
def test_synthesize_passes_flash_model_by_default(mock_elevenlabs_cls: MagicMock) -> None:
    mock_client = mock_elevenlabs_cls.return_value
    mock_client.text_to_speech.convert.return_value = iter([b"audio"])

    synthesize("Correcto.", voice_id="voice-123")

    mock_client.text_to_speech.convert.assert_called_once_with(
        text="Correcto.",
        voice_id="voice-123",
        model_id=DEFAULT_MODEL_ID,
        output_format=DEFAULT_OUTPUT_FORMAT,
    )


@patch("macenplast.voice.tts.ElevenLabs")
def test_synthesize_allows_overriding_model_and_format(mock_elevenlabs_cls: MagicMock) -> None:
    mock_client = mock_elevenlabs_cls.return_value
    mock_client.text_to_speech.convert.return_value = iter([b"audio"])

    synthesize("Correcto.", voice_id="voice-123", model_id="eleven_v3", output_format="wav_44100")

    mock_client.text_to_speech.convert.assert_called_once_with(
        text="Correcto.",
        voice_id="voice-123",
        model_id="eleven_v3",
        output_format="wav_44100",
    )
