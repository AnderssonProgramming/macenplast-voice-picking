"""Runs the pick machine against the shared cross-language test vectors.

The vectors live in `packages/machine-vectors/pick_line_transitions.json` and
are also consumed by `apps/web/src/shared/pickMachine.test.ts`, so both
implementations are checked against exactly the same cases.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

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
    PickState,
    PlayAlert,
    Present,
    Qty,
    QueueSync,
    Repeat,
    Scan,
    Speak,
    transition,
)

VECTORS_PATH = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "machine-vectors"
    / "pick_line_transitions.json"
)


def load_vectors() -> list[dict[str, Any]]:
    vectors: list[dict[str, Any]] = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
    return vectors


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


@pytest.mark.parametrize("vector", load_vectors(), ids=lambda v: v["name"])
def test_vector(vector: dict[str, Any]) -> None:
    state = PickState(vector["state"])
    context = context_from_json(vector["context"])
    event = event_from_json(vector["event"])

    result = transition(state, context, event)

    assert result.state.value == vector["expected"]["state"]
    assert context_to_json(result.context) == vector["expected"]["context"]
    assert [effect_to_json(e) for e in result.effects] == vector["expected"]["effects"]
