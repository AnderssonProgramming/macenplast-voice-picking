"""Thin wrapper around the ElevenLabs text-to-speech API.

Verified against ElevenLabs' docs on 2026-09-18 (see
`docs/adr/0003-elevenlabs-tts.md`): package `elevenlabs`, client class
`elevenlabs.client.ElevenLabs`, `client.text_to_speech.convert(...)`
returns `Iterator[bytes]` (joined here into one `bytes` object), endpoint
`POST /v1/text-to-speech/{voice_id}`. Re-verify before relying on this if
much time has passed — ElevenLabs' API has moved before.

Never call this from automated tests without mocking the client — the one
exception is the `@pytest.mark.live` test in `tests/test_tts_live.py`,
skipped by default.
"""

from __future__ import annotations

from elevenlabs.client import ElevenLabs

from macenplast.config import get_settings

DEFAULT_MODEL_ID = "eleven_flash_v2_5"
"""Low-latency model (ADR 0001, 'Voice output'). Used to pre-generate
clips ahead of time, not in the request/response hot path."""

DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"


def synthesize(
    text: str,
    voice_id: str,
    *,
    model_id: str = DEFAULT_MODEL_ID,
    output_format: str = DEFAULT_OUTPUT_FORMAT,
) -> bytes:
    """Synthesize `text` and return the complete audio bytes.

    Args:
        text: The exact text to speak (already rendered — no templating
            happens here; see `macenplast.voice.phrases`).
        voice_id: The ElevenLabs voice to use.
        model_id: Defaults to Flash v2.5 (see `DEFAULT_MODEL_ID`).
        output_format: An ElevenLabs `output_format` value, e.g.
            `"mp3_44100_128"`.
    """
    client = ElevenLabs(api_key=get_settings().elevenlabs_api_key)
    chunks = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id=model_id,
        output_format=output_format,
    )
    return b"".join(chunks)
