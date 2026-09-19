"""Submit pick events (scan, qty, override, repeat, exception).

This is where a `pick_line`'s row actually advances through the state
machine: it loads the line's current state/context, calls
`macenplast.domain.pick_machine.transition`, persists the result, executes
the returned effects against the WMS and the incidents table, and records
an append-only audit row. Idempotent on `client_event_id` — replaying the
same event (e.g. a retried offline sync batch) returns the previously
recorded result instead of re-applying it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from macenplast.adapters.mock_wms import MockWmsAdapter
from macenplast.api.deps import get_current_operator
from macenplast.api.schemas.events import (
    BatchEventOutcome,
    EventResult,
    SubmitEventBatchRequest,
    SubmitEventBatchResponse,
    SubmitEventRequest,
)
from macenplast.api.sse import broadcaster
from macenplast.config import get_settings
from macenplast.db.models import (
    Incident,
    Operator,
    OperatorRole,
    PickEvent,
    PickLine,
    PickSession,
    SessionMode,
)
from macenplast.db.session import get_db
from macenplast.domain.baseline_mode import apply_baseline_event
from macenplast.domain.pick_machine import (
    AdvanceLine,
    InvalidTransitionError,
    LogIncident,
    LogOverride,
    Override,
    PickContext,
    PickState,
    QueueSync,
    transition,
)
from macenplast.domain.pick_machine_json import effect_to_json, event_from_json

router = APIRouter(prefix="/events", tags=["events"])


class OverrideNotAuthorizedError(Exception):
    """Raised when a non-supervisor submits an OVERRIDE event."""


def _line_to_context(
    line: PickLine, expected_location_barcode: str, expected_sku_barcode: str
) -> PickContext:
    return PickContext(
        location_check_enabled=get_settings().location_check_enabled,
        expected_location_barcode=expected_location_barcode,
        expected_sku_barcode=expected_sku_barcode,
        expected_qty=line.expected_qty,
        attempts=line.attempts,
        blocked_on=line.blocked_on,
        last_qty=line.last_qty,
    )


def apply_event(db: Session, operator: Operator, request: SubmitEventRequest) -> EventResult:
    """Apply one event, idempotent on `request.client_event_id`."""
    existing = db.query(PickEvent).filter_by(client_event_id=request.client_event_id).one_or_none()
    if existing is not None:
        return EventResult(**existing.payload["result"])

    line = db.get(PickLine, request.pick_line_id)
    if line is None:
        raise HTTPException(status_code=404, detail="Pick line not found")

    session = db.get(PickSession, request.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    event = event_from_json(request.event)

    if isinstance(event, Override):
        if operator.role != OperatorRole.SUPERVISOR:
            raise OverrideNotAuthorizedError("Only a supervisor can clear a NEEDS_OVERRIDE line")
        event = Override(supervisor_id=str(operator.id))

    sku = line.sku
    location = line.location
    primary_barcode = sku.barcodes[0].barcode if sku.barcodes else None
    if primary_barcode is None:
        raise HTTPException(status_code=500, detail=f"SKU {sku.code} has no barcode")

    context = _line_to_context(
        line,
        expected_location_barcode=location.barcode,
        expected_sku_barcode=primary_barcode,
    )
    # BASELINE sessions replay every event through the same "never block"
    # override the offline PWA applies client-side (baseline_mode.py) —
    # otherwise the server's own copy of `line.state` independently drifts
    # into BLOCKED/NEEDS_OVERRIDE on a mismatch the client already forced
    # past, and a later queued event (a different type than what that
    # blocked state expects) raises InvalidTransitionError.
    result = (
        apply_baseline_event(PickState(line.state), context, event)
        if session.mode == SessionMode.BASELINE
        else transition(PickState(line.state), context, event)
    )

    line.state = result.state
    line.attempts = result.context.attempts
    line.blocked_on = result.context.blocked_on
    line.last_qty = result.context.last_qty

    wms = MockWmsAdapter(db)
    for effect in result.effects:
        if isinstance(effect, QueueSync):
            wms.commit_pick(
                line.sku_id,
                line.location_id,
                line.expected_qty,
                idempotency_key=f"commit:{request.client_event_id}",
            )
            line.completed_at = request.occurred_at
        elif isinstance(effect, LogIncident):
            db.add(
                Incident(
                    pick_line_id=line.id,
                    session_id=request.session_id,
                    reason=effect.reason,
                    reported_qty=line.last_qty,
                )
            )
            wms.release(
                line.sku_id,
                line.location_id,
                line.expected_qty,
                idempotency_key=f"release:{line.id}",
            )
        elif isinstance(effect, LogOverride | AdvanceLine):
            pass  # captured in the PickEvent audit row itself; no extra table.

    effects_json: list[dict[str, Any]] = [effect_to_json(e) for e in result.effects]
    event_result = EventResult(
        line_id=line.id,
        state=result.state,
        attempts=result.context.attempts,
        blocked_on=result.context.blocked_on,
        last_qty=result.context.last_qty,
        effects=effects_json,
    )

    db.add(
        PickEvent(
            pick_line_id=line.id,
            session_id=request.session_id,
            client_event_id=request.client_event_id,
            event_type=request.event.get("type", "UNKNOWN"),
            payload={"event": request.event, "result": event_result.model_dump(mode="json")},
            occurred_at=request.occurred_at,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        # Two concurrent requests replaying the same client_event_id (two
        # sync attempts overlapping, a retried batch) both pass the
        # check above before either commits — the unique constraint on
        # client_event_id is the real guard. Whichever loses the race
        # just returns the winner's already-committed result.
        db.rollback()
        existing = (
            db.query(PickEvent).filter_by(client_event_id=request.client_event_id).one_or_none()
        )
        if existing is None:
            raise
        return EventResult(**existing.payload["result"])

    broadcaster.publish(
        {
            "type": "pick_line_updated",
            "line_id": str(line.id),
            "session_id": str(request.session_id),
            "state": result.state.value,
        }
    )
    return event_result


@router.post("")
def submit_event(
    request: SubmitEventRequest,
    operator: Operator = Depends(get_current_operator),
    db: Session = Depends(get_db),
) -> EventResult:
    try:
        return apply_event(db, operator, request)
    except OverrideNotAuthorizedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/batch")
def submit_event_batch(
    request: SubmitEventBatchRequest,
    operator: Operator = Depends(get_current_operator),
    db: Session = Depends(get_db),
) -> SubmitEventBatchResponse:
    outcomes: list[BatchEventOutcome] = []
    for event_request in request.events:
        try:
            result = apply_event(db, operator, event_request)
            outcomes.append(
                BatchEventOutcome(
                    client_event_id=event_request.client_event_id, success=True, result=result
                )
            )
        except (OverrideNotAuthorizedError, HTTPException, InvalidTransitionError) as exc:
            db.rollback()
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            outcomes.append(
                BatchEventOutcome(
                    client_event_id=event_request.client_event_id,
                    success=False,
                    error=str(detail),
                )
            )
    return SubmitEventBatchResponse(outcomes=outcomes)
