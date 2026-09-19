"""Content-hash-keyed cache for synthesized voice clips.

Two layers, per ADR 0001 ("Audio strategy"): a `voice_clips` DB row per
distinct `(text, voice_id, model_id, output_format)` combination, and the
audio file itself on disk under `Settings.voice_clip_dir`. Requesting the
same phrase twice calls ElevenLabs once — the second call is a cache hit
on the content hash.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy.orm import Session

from macenplast.config import get_settings
from macenplast.db.models import VoiceClip
from macenplast.voice.tts import DEFAULT_MODEL_ID, DEFAULT_OUTPUT_FORMAT, synthesize

_EXTENSION_BY_FORMAT_PREFIX = {
    "mp3": "mp3",
    "wav": "wav",
    "pcm": "pcm",
    "opus": "opus",
    "ulaw": "ulaw",
    "alaw": "alaw",
}


def content_hash(text: str, voice_id: str, model_id: str, output_format: str) -> str:
    """Stable hash identifying one exact clip request.

    Two requests differing in any of these fields are different clips —
    the same phrase text spoken by a different voice is not the same
    cache entry.
    """
    payload = "\x1f".join((text, voice_id, model_id, output_format))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _extension_for(output_format: str) -> str:
    prefix = output_format.split("_", 1)[0]
    return _EXTENSION_BY_FORMAT_PREFIX.get(prefix, "bin")


def get_or_synthesize(
    session: Session,
    text: str,
    voice_id: str,
    *,
    model_id: str = DEFAULT_MODEL_ID,
    output_format: str = DEFAULT_OUTPUT_FORMAT,
) -> VoiceClip:
    """Return the cached `VoiceClip` for this exact request, synthesizing it
    (and writing both the DB row and the file) on a cache miss."""
    clip_hash = content_hash(text, voice_id, model_id, output_format)

    existing = session.query(VoiceClip).filter_by(content_hash=clip_hash).one_or_none()
    if existing is not None:
        return existing

    audio = synthesize(text, voice_id, model_id=model_id, output_format=output_format)

    clip_dir = Path(get_settings().voice_clip_dir)
    clip_dir.mkdir(parents=True, exist_ok=True)
    file_path = clip_dir / f"{clip_hash}.{_extension_for(output_format)}"
    file_path.write_bytes(audio)

    clip = VoiceClip(
        content_hash=clip_hash,
        text=text,
        voice_id=voice_id,
        model_id=model_id,
        audio_format=output_format,
        file_path=str(file_path),
    )
    session.add(clip)
    session.flush()
    return clip
