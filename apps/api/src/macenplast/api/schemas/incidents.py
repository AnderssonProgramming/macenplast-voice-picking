"""Schemas for incidents."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from macenplast.domain.pick_machine import IncidentReason


class IncidentResponse(BaseModel):
    id: uuid.UUID
    pick_line_id: uuid.UUID
    session_id: uuid.UUID
    reason: IncidentReason
    reported_qty: int | None
    resolved: bool
    created_at: datetime

    model_config = {"from_attributes": True}
