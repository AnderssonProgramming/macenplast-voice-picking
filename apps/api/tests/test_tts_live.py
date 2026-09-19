"""Real ElevenLabs API smoke test.

Skipped by default (see `addopts = "-m 'not live'"` in `pyproject.toml`).
Run explicitly with a real API key:

    ELEVENLABS_API_KEY=... pytest -m live tests/test_tts_live.py
"""

from __future__ import annotations

import pytest

from macenplast.config import get_settings
from macenplast.voice.tts import synthesize


@pytest.mark.live
def test_synthesize_returns_real_audio_bytes() -> None:
    if not get_settings().elevenlabs_api_key:
        pytest.skip("ELEVENLABS_API_KEY not set")

    audio = synthesize("Correcto.", voice_id=get_settings().elevenlabs_voice_id)

    assert isinstance(audio, bytes)
    assert len(audio) > 0
