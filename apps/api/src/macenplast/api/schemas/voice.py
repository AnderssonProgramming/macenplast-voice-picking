"""Pydantic schemas for the voice API."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class ClipDescriptor(BaseModel):
    """One clip a device needs, and where to fetch its audio."""

    content_hash: str
    url: str
    text: str


class VoiceManifestResponse(BaseModel):
    """Every clip a device needs prefetched for one order."""

    order_id: uuid.UUID
    clips: list[ClipDescriptor]
