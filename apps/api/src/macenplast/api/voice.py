"""Voice endpoints: dynamic per-SKU clip synthesis, the per-order voice
manifest (so a device knows what to prefetch), and serving clip audio.

Phase 4 owns the rest of the API surface (auth, sessions, order
assignment, events, incidents, SSE); this router only covers what Phase 3
needs to be usable standalone.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from macenplast.api.schemas.voice import ClipDescriptor, VoiceManifestResponse
from macenplast.config import get_settings
from macenplast.db.models import PickLine, PickOrder, Sku, VoiceClip
from macenplast.db.session import get_db
from macenplast.domain.pick_machine import PickState
from macenplast.voice.clip_cache import get_or_synthesize
from macenplast.voice.phrases import render_phrase

router = APIRouter(prefix="/voice", tags=["voice"])

_CONTENT_TYPE_BY_FORMAT_PREFIX = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "opus": "audio/opus",
    "pcm": "audio/L16",
}

_FIXED_PHRASES = ("LOCATION_CORRECT", "CORRECT", "CALL_SUPERVISOR", "MISMATCH")


def _clip_url(content_hash: str) -> str:
    return f"/voice/clips/{content_hash}"


def _content_type_for(audio_format: str) -> str:
    prefix = audio_format.split("_", 1)[0]
    return _CONTENT_TYPE_BY_FORMAT_PREFIX.get(prefix, "application/octet-stream")


def _to_descriptor(clip: VoiceClip) -> ClipDescriptor:
    return ClipDescriptor(
        content_hash=clip.content_hash, url=_clip_url(clip.content_hash), text=clip.text
    )


@router.get("/clips/{content_hash}")
def get_clip_audio(content_hash: str, db: Session = Depends(get_db)) -> Response:
    """Serve a cached clip's audio bytes by its content hash."""
    clip = db.query(VoiceClip).filter_by(content_hash=content_hash).one_or_none()
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found")
    return Response(content=clip.audio_data, media_type=_content_type_for(clip.audio_format))


@router.get("/skus/{sku_id}/clip")
def get_sku_clip(sku_id: uuid.UUID, db: Session = Depends(get_db)) -> ClipDescriptor:
    """Synthesize (or fetch cached) a SKU's spoken name.

    This is the "dynamic per-SKU clip" from ADR 0001: unlike numbers and
    fixed phrases (pre-built by `tools/voice-clips/build_static_clips.py`),
    a SKU's clip is only synthesized the first time it's requested.
    """
    sku = db.get(Sku, sku_id)
    if sku is None:
        raise HTTPException(status_code=404, detail="SKU not found")

    text = sku.voice_alias or sku.description
    clip = get_or_synthesize(db, text, voice_id=get_settings().elevenlabs_voice_id)
    db.commit()
    return _to_descriptor(clip)


@router.get("/orders/{order_id}/manifest")
def get_voice_manifest(order_id: uuid.UUID, db: Session = Depends(get_db)) -> VoiceManifestResponse:
    """List every clip a device needs prefetched to run this order in VOICE
    mode, synthesizing (and caching) anything not already built."""
    order = db.get(PickOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    voice_id = get_settings().elevenlabs_voice_id
    clips_by_hash: dict[str, VoiceClip] = {}

    for key in _FIXED_PHRASES:
        clip = get_or_synthesize(db, render_phrase(key), voice_id=voice_id)
        clips_by_hash[clip.content_hash] = clip

    lines = (
        db.query(PickLine)
        .filter(PickLine.order_id == order_id, PickLine.state != PickState.DONE)
        .all()
    )
    for line in lines:
        sku = line.sku
        location = line.location
        instruction_text = render_phrase(
            "INSTRUCTION",
            aisle=location.aisle,
            bay=int(location.bay),
            level=int(location.level),
            reference=sku.voice_alias or sku.description,
            quantity=line.expected_qty,
        )
        for text in (instruction_text, render_phrase("QTY_PROMPT", quantity=line.expected_qty)):
            clip = get_or_synthesize(db, text, voice_id=voice_id)
            clips_by_hash[clip.content_hash] = clip

    db.commit()
    return VoiceManifestResponse(
        order_id=order_id,
        clips=[_to_descriptor(clip) for clip in clips_by_hash.values()],
    )
