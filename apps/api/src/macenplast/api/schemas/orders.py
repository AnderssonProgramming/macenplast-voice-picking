"""Schemas for orders and pick lines."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel

from macenplast.db.models import OrderStatus
from macenplast.domain.pick_machine import BlockedOn, PickState


class AssignOrderRequest(BaseModel):
    session_id: uuid.UUID


class OrderResponse(BaseModel):
    id: uuid.UUID
    order_code: str
    status: OrderStatus
    session_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class PendingOrderSummary(BaseModel):
    """One order an operator could pick up — enough to choose from a list."""

    id: uuid.UUID
    order_code: str
    line_count: int


class OrderLineDetail(BaseModel):
    """Everything the offline client needs to run this line's pick machine
    locally, with no further round-trips — see `GET /orders/{id}/lines`."""

    line_id: uuid.UUID
    sequence: int
    state: PickState
    attempts: int
    blocked_on: BlockedOn | None
    last_qty: int | None
    location_check_enabled: bool
    aisle: str
    bay: str
    level: str
    location_barcode: str
    sku_code: str
    sku_barcode: str
    reference: str
    expected_qty: int


class NextLineResponse(BaseModel):
    line_id: uuid.UUID
    order_id: uuid.UUID
    sequence: int
    state: PickState
    attempts: int
    blocked_on: BlockedOn | None
    aisle: str
    bay: str
    level: str
    location_barcode: str
    sku_code: str
    reference: str
    expected_qty: int
    instruction_text: str
    effects: list[dict[str, Any]]
