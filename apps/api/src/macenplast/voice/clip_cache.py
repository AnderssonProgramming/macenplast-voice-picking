"""Content-hash-keyed cache for synthesized voice clips.

One layer, per ADR 0001 ("Audio strategy") as later revised for the Vercel
deployment: a `voice_clips` DB row per distinct `(text, voice_id, model_id,
output_format)` combination, with the audio bytes stored directly on the
row (see `VoiceClip.audio_data`'s docstring for why — no local disk).
Requesting the same phrase twice calls ElevenLabs once — the second call is
a cache hit on the content hash.
"""

from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from macenplast.db.models import VoiceClip
from macenplast.voice.tts import DEFAULT_MODEL_ID, DEFAULT_OUTPUT_FORMAT, synthesize


def content_hash(text: str, voice_id: str, model_id: str, output_format: str) -> str:
    """Stable hash identifying one exact clip request.

    Two requests differing in any of these fields are different clips —
    the same phrase text spoken by a different voice is not the same
    cache entry.
    """
    payload = "\x1f".join((text, voice_id, model_id, output_format))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_or_synthesize(
    session: Session,
    text: str,
    voice_id: str,
    *,
    model_id: str = DEFAULT_MODEL_ID,
    output_format: str = DEFAULT_OUTPUT_FORMAT,
) -> VoiceClip:
    """Return the cached `VoiceClip` for this exact request, synthesizing
    and storing it on a cache miss."""
    clip_hash = content_hash(text, voice_id, model_id, output_format)

    existing = session.query(VoiceClip).filter_by(content_hash=clip_hash).one_or_none()
    if existing is not None:
        return existing

    audio = synthesize(text, voice_id, model_id=model_id, output_format=output_format)

    clip = VoiceClip(
        content_hash=clip_hash,
        text=text,
        voice_id=voice_id,
        model_id=model_id,
        audio_format=output_format,
        audio_data=audio,
    )
    session.add(clip)
    session.flush()
    return clip
