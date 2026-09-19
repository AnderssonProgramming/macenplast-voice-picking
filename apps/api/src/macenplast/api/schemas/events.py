"""Schemas for submitting pick events (scan, qty, override, ...)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from macenplast.domain.pick_machine import BlockedOn, PickState


class SubmitEventRequest(BaseModel):
    client_event_id: str
    pick_line_id: uuid.UUID
    session_id: uuid.UUID
    event: dict[str, Any]
    occurred_at: datetime | None = None


class EventResult(BaseModel):
    line_id: uuid.UUID
    state: PickState
    attempts: int
    blocked_on: BlockedOn | None
    last_qty: int | None
    effects: list[dict[str, Any]]


class BatchEventOutcome(BaseModel):
    client_event_id: str
    success: bool
    result: EventResult | None = None
    error: str | None = None


class SubmitEventBatchRequest(BaseModel):
    events: list[SubmitEventRequest]


class SubmitEventBatchResponse(BaseModel):
    outcomes: list[BatchEventOutcome]
