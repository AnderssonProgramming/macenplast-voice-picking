# ADR 0003 — ElevenLabs TTS integration details, verified 2026-09-18

- Status: Accepted
- Date: 2026-09-18
- Source: ElevenLabs' own docs (see links below), checked before writing
  `apps/api/src/macenplast/voice/tts.py`, per `CLAUDE.md`'s rule to verify
  current model IDs/endpoints/output formats before coding against
  ElevenLabs.

## Context

`PLAN.md` names `eleven_flash_v2_5` as the TTS model (ADR 0001) but flags
that names may have moved since the plan was written. This ADR records
what was confirmed and where, so a future session doesn't have to
re-verify from scratch — but should still spot-check if much time has
passed, per the same rule.

## What was confirmed

- **Model**: `eleven_flash_v2_5` is still current and still the
  low-latency option (~75ms inference). `PLAN.md`'s choice stands.
- **Python package**: `pip install elevenlabs`.
- **Client**: `from elevenlabs.client import ElevenLabs` (sync) /
  `AsyncElevenLabs` (async). Constructor takes `api_key` explicitly — this
  project always passes it explicitly from `Settings.elevenlabs_api_key`
  rather than relying on the SDK's own environment-variable fallback,
  since sources disagreed on whether that variable is `ELEVENLABS_API_KEY`
  or `ELEVEN_API_KEY`.
- **Synthesis call**:
  `client.text_to_speech.convert(text=..., voice_id=..., model_id=..., output_format=...)`.
- **Return type**: `Iterator[bytes]` — a generator of audio chunks, not a
  single `bytes` value. Callers must consume it
  (`b"".join(client.text_to_speech.convert(...))` for the whole-file case
  this project needs, since clips are cached as complete files, not
  streamed).
- **HTTP endpoint** (for reference — the SDK is what's actually used):
  `POST /v1/text-to-speech/{voice_id}`, header `xi-api-key`, body field
  `model_id` (default `eleven_multilingual_v2` — this project always
  passes `eleven_flash_v2_5` explicitly), `output_format` as a query
  param.
- **`output_format` values actually used here**: `mp3_44100_128` (the
  API's own default, and what `macenplast.voice.tts.DEFAULT_OUTPUT_FORMAT`
  uses) — one of a longer list of mp3/pcm/wav/opus/alaw/ulaw options at
  various sample rates.

## Consequences

- `macenplast.voice.tts.synthesize()` always passes `model_id` and
  `api_key` explicitly rather than relying on ElevenLabs SDK defaults, so
  behavior doesn't silently change if ElevenLabs changes its own default
  model or env var name.
- If ElevenLabs changes the SDK's method signature or return type again,
  only `macenplast/voice/tts.py` needs to change — every other module
  calls `synthesize()`, never the ElevenLabs client directly.

## Sources

- https://elevenlabs.io/docs/overview/capabilities/text-to-speech
- https://elevenlabs.io/docs/api-reference/text-to-speech/convert
- https://github.com/elevenlabs/elevenlabs-python
