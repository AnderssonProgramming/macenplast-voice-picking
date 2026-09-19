"""Order assignment and the operator's "what's next" endpoint.

Voice manifest for an order lives in `macenplast.api.voice`
(`GET /voice/orders/{order_id}/manifest`) — introduced in Phase 3, reused
here rather than duplicated.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from macenplast.adapters.mock_wms import MockWmsAdapter
from macenplast.api.deps import get_current_operator
from macenplast.api.schemas.orders import AssignOrderRequest, NextLineResponse, OrderResponse
from macenplast.config import get_settings
from macenplast.db.models import Operator, OrderStatus, PickLine, PickOrder, PickSession
from macenplast.db.session import get_db
from macenplast.domain.pick_machine import PickContext, PickState, Present, transition
from macenplast.domain.pick_machine_json import effect_to_json
from macenplast.domain.routing import RouteLocation, plan_route
from macenplast.ports.wms_port import InsufficientStockError
from macenplast.voice.phrases import render_phrase

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/{order_id}/assign")
def assign_order(
    order_id: uuid.UUID,
    payload: AssignOrderRequest,
    operator: Operator = Depends(get_current_operator),
    db: Session = Depends(get_db),
) -> OrderResponse:
    order = db.get(PickOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    session = db.get(PickSession, payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    lines = db.query(PickLine).filter(PickLine.order_id == order_id).all()
    if not lines:
        raise HTTPException(status_code=400, detail="Order has no pick lines")

    route_locations = [
        RouteLocation(
            id=line.id,
            pos_x=line.location.pos_x,
            pos_y=line.location.pos_y,
            level=line.location.level,
        )
        for line in lines
    ]
    ordered = plan_route(route_locations, strategy=get_settings().routing_strategy)
    sequence_by_line_id = {loc.id: index for index, loc in enumerate(ordered)}

    wms = MockWmsAdapter(db)
    try:
        for line in lines:
            line.sequence = sequence_by_line_id[line.id]
            wms.reserve(
                line.sku_id,
                line.location_id,
                line.expected_qty,
                idempotency_key=f"reserve:{line.id}",
            )
    except InsufficientStockError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    order.session_id = session.id
    order.status = OrderStatus.IN_PROGRESS
    db.commit()
    db.refresh(order)
    return OrderResponse.model_validate(order)


@router.get("/{order_id}/next-line")
def get_next_line(
    order_id: uuid.UUID,
    operator: Operator = Depends(get_current_operator),
    db: Session = Depends(get_db),
) -> NextLineResponse:
    order = db.get(PickOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    line = (
        db.query(PickLine)
        .filter(
            PickLine.order_id == order_id,
            PickLine.state.notin_([PickState.DONE, PickState.EXCEPTED]),
        )
        .order_by(PickLine.sequence.asc())
        .first()
    )
    if line is None:
        raise HTTPException(status_code=404, detail="No pending lines — order is complete")

    sku = line.sku
    location = line.location
    primary_barcode = sku.barcodes[0].barcode if sku.barcodes else None
    if primary_barcode is None:
        raise HTTPException(status_code=500, detail=f"SKU {sku.code} has no barcode")

    effects_json: list[dict[str, object]] = []
    if line.state == PickState.PENDING:
        context = PickContext(
            location_check_enabled=get_settings().location_check_enabled,
            expected_location_barcode=location.barcode,
            expected_sku_barcode=primary_barcode,
            expected_qty=line.expected_qty,
            attempts=line.attempts,
            blocked_on=line.blocked_on,
            last_qty=line.last_qty,
        )
        result = transition(PickState(line.state), context, Present())
        line.state = result.state
        line.attempts = result.context.attempts
        line.blocked_on = result.context.blocked_on
        line.last_qty = result.context.last_qty
        db.commit()
        effects_json = [effect_to_json(e) for e in result.effects]

    reference = sku.voice_alias or sku.description
    instruction_text = render_phrase(
        "INSTRUCTION",
        aisle=location.aisle,
        bay=int(location.bay),
        level=int(location.level),
        reference=reference,
        quantity=line.expected_qty,
    )

    return NextLineResponse(
        line_id=line.id,
        order_id=order.id,
        sequence=line.sequence,
        state=line.state,
        attempts=line.attempts,
        blocked_on=line.blocked_on,
        aisle=location.aisle,
        bay=location.bay,
        level=location.level,
        location_barcode=location.barcode,
        sku_code=sku.code,
        reference=reference,
        expected_qty=line.expected_qty,
        instruction_text=instruction_text,
        effects=effects_json,
    )
