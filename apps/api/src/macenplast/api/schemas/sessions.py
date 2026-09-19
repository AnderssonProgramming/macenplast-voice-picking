"""Schemas for pick sessions."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from macenplast.db.models import SessionMode


class StartSessionRequest(BaseModel):
    device_id: uuid.UUID
    mode: SessionMode


class SessionResponse(BaseModel):
    id: uuid.UUID
    operator_id: uuid.UUID
    device_id: uuid.UUID
    mode: SessionMode
    started_at: datetime
    ended_at: datetime | None

    model_config = {"from_attributes": True}
