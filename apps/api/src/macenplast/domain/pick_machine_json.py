"""JSON (de)serialization for `macenplast.domain.pick_machine` types.

Kept separate from `pick_machine.py` so that module stays purely about
transition logic. Used by the shared test vectors
(`tests/test_pick_machine_vectors.py`) and by the API layer
(`macenplast.api.events`, `macenplast.api.orders`) to move state machine
values in and out of HTTP/DB-friendly dicts — the same shape the
TypeScript port (`apps/web/src/shared/pickMachine.ts`) uses natively.
"""

from __future__ import annotations

from typing import Any

from macenplast.domain.pick_machine import (
    AdvanceLine,
    BlockedOn,
    Effect,
    Event,
    ExceptionEvent,
    IncidentReason,
    LogIncident,
    LogOverride,
    Override,
    PickContext,
    PlayAlert,
    Present,
    Qty,
    QueueSync,
    Repeat,
    Scan,
    Speak,
)


def context_from_json(data: dict[str, Any]) -> PickContext:
    return PickContext(
        location_check_enabled=data["locationCheckEnabled"],
        expected_location_barcode=data["expectedLocationBarcode"],
        expected_sku_barcode=data["expectedSkuBarcode"],
        expected_qty=data["expectedQty"],
        attempts=data["attempts"],
        blocked_on=BlockedOn(data["blockedOn"]) if data["blockedOn"] is not None else None,
        last_qty=data["lastQty"],
    )


def context_to_json(context: PickContext) -> dict[str, Any]:
    return {
        "locationCheckEnabled": context.location_check_enabled,
        "expectedLocationBarcode": context.expected_location_barcode,
        "expectedSkuBarcode": context.expected_sku_barcode,
        "expectedQty": context.expected_qty,
        "attempts": context.attempts,
        "blockedOn": context.blocked_on.value if context.blocked_on is not None else None,
        "lastQty": context.last_qty,
    }


def event_from_json(data: dict[str, Any]) -> Event:
    kind = data["type"]
    if kind == "PRESENT":
        return Present()
    if kind == "SCAN":
        return Scan(barcode=data["barcode"])
    if kind == "QTY":
        return Qty(quantity=data["quantity"])
    if kind == "OVERRIDE":
        return Override(supervisor_id=data["supervisorId"])
    if kind == "REPEAT":
        return Repeat()
    if kind == "EXCEPTION":
        return ExceptionEvent(reason=IncidentReason(data["reason"]))
    raise ValueError(f"Unknown event type: {kind}")


def effect_to_json(effect: Effect) -> dict[str, Any]:
    if isinstance(effect, Speak):
        result: dict[str, Any] = {"type": "SPEAK", "phrase": effect.phrase}
        if effect.args:
            result["args"] = effect.args
        return result
    if isinstance(effect, PlayAlert):
        return {"type": "PLAY_ALERT", "alert": effect.alert}
    if isinstance(effect, LogIncident):
        return {"type": "LOG_INCIDENT", "reason": effect.reason.value}
    if isinstance(effect, LogOverride):
        return {"type": "LOG_OVERRIDE", "supervisorId": effect.supervisor_id}
    if isinstance(effect, QueueSync):
        return {"type": "QUEUE_SYNC"}
    if isinstance(effect, AdvanceLine):
        return {"type": "ADVANCE_LINE"}
    raise ValueError(f"Unknown effect: {effect!r}")
