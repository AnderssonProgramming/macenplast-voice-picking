"""Drives a full order through the API: login, start a session, assign an
order, walk a pick line through a BLOCKED -> NEEDS_OVERRIDE -> override ->
DONE path, and check stock and audit events land correctly.

Requires a reachable Postgres; skips otherwise (see conftest.py's
`seeded_db`). TTS is irrelevant here (voice endpoints aren't exercised) so
it isn't mocked.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from macenplast.db.models import Device, PickEvent, PickLine, PickOrder, Sku, StockLevel
from macenplast.db.session import SessionLocal
from macenplast.domain.pick_machine import PickState
from macenplast.main import app

client = TestClient(app)


def make_fresh_order(db: Session, num_lines: int = 1) -> PickOrder:
    """Create a brand-new PENDING order with `num_lines` lines, using
    already-seeded SKUs/stock. Deliberately doesn't reuse a shared seeded
    order: this suite runs repeatedly against one persistent dev
    database, and a test that instead queried for "any seeded order with
    no session yet" would find fewer and fewer of them over time as prior
    runs assign them, eventually failing outright.
    """
    skus = db.query(Sku).limit(num_lines).all()
    assert len(skus) == num_lines, "Not enough seeded SKUs — run `make seed` first"

    order = PickOrder(order_code=f"TEST-ORD-{uuid.uuid4().hex[:8]}")
    db.add(order)
    db.flush()
    for i, sku in enumerate(skus):
        stock = db.query(StockLevel).filter_by(sku_id=sku.id).first()
        assert stock is not None, f"No stock for seeded sku {sku.code}"
        db.add(
            PickLine(
                order_id=order.id,
                sku_id=sku.id,
                location_id=stock.location_id,
                sequence=i,
                expected_qty=5 + i,
                state=PickState.PENDING,
            )
        )
    db.commit()
    db.refresh(order)
    return order


def _login(badge_code: str, pin: str) -> str:
    response = client.post("/auth/login", json={"badge_code": badge_code, "pin": pin})
    assert response.status_code == 200, response.text
    token: str = response.json()["access_token"]
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_login_rejects_wrong_pin(seeded_db: None) -> None:
    response = client.post("/auth/login", json={"badge_code": "0001", "pin": "0000"})
    assert response.status_code == 401


def test_full_order_flow_blocked_override_done(seeded_db: None) -> None:
    operator_token = _login("0001", "1234")
    supervisor_token = _login("9001", "9999")

    with SessionLocal() as db:
        device = db.query(Device).first()
        assert device is not None
        order = make_fresh_order(db)
        order_id = order.id
        device_id = device.id
        line = db.query(PickLine).filter_by(order_id=order.id).one()
        initial_stock = (
            db.query(StockLevel)
            .filter_by(sku_id=line.sku_id, location_id=line.location_id)
            .one()
        )
        initial_quantity = initial_stock.quantity
        initial_reserved_qty = initial_stock.reserved_qty

    start_response = client.post(
        "/sessions/start",
        json={"device_id": str(device_id), "mode": "VOICE"},
        headers=_auth(operator_token),
    )
    assert start_response.status_code == 200, start_response.text
    session_id = start_response.json()["id"]

    assign_response = client.post(
        f"/orders/{order_id}/assign",
        json={"session_id": session_id},
        headers=_auth(operator_token),
    )
    assert assign_response.status_code == 200, assign_response.text

    next_line_response = client.get(
        f"/orders/{order_id}/next-line", headers=_auth(operator_token)
    )
    assert next_line_response.status_code == 200, next_line_response.text
    line_data = next_line_response.json()
    line_id = line_data["line_id"]
    assert line_data["state"] == "AWAITING_LOCATION"

    with SessionLocal() as db:
        pick_line = db.get(PickLine, uuid.UUID(line_id))
        assert pick_line is not None
        expected_qty = pick_line.expected_qty
        sku_id = pick_line.sku_id
        location_id = pick_line.location_id

    def submit_event(event: dict[str, object]) -> dict[str, object]:
        response = client.post(
            "/events",
            json={
                "client_event_id": str(uuid.uuid4()),
                "pick_line_id": line_id,
                "session_id": session_id,
                "event": event,
            },
            headers=_auth(operator_token),
        )
        assert response.status_code == 200, response.text
        result: dict[str, object] = response.json()
        return result

    # Three wrong location scans: BLOCKED, BLOCKED, then escalate.
    result = submit_event({"type": "SCAN", "barcode": "WRONG-LOCATION-1"})
    assert result["state"] == "BLOCKED"
    assert result["attempts"] == 1

    result = submit_event({"type": "SCAN", "barcode": "WRONG-LOCATION-2"})
    assert result["state"] == "BLOCKED"
    assert result["attempts"] == 2

    result = submit_event({"type": "SCAN", "barcode": "WRONG-LOCATION-3"})
    assert result["state"] == "NEEDS_OVERRIDE"
    assert result["attempts"] == 3

    # An operator cannot grant their own override.
    self_override_response = client.post(
        "/events",
        json={
            "client_event_id": str(uuid.uuid4()),
            "pick_line_id": line_id,
            "session_id": session_id,
            "event": {"type": "OVERRIDE", "supervisorId": "does-not-matter"},
        },
        headers=_auth(operator_token),
    )
    assert self_override_response.status_code == 403

    # A supervisor can.
    override_response = client.post(
        "/events",
        json={
            "client_event_id": str(uuid.uuid4()),
            "pick_line_id": line_id,
            "session_id": session_id,
            "event": {"type": "OVERRIDE", "supervisorId": "does-not-matter"},
        },
        headers=_auth(supervisor_token),
    )
    assert override_response.status_code == 200, override_response.text
    assert override_response.json()["state"] == "AWAITING_QTY"

    # Confirming the expected quantity completes the line.
    qty_event_id = str(uuid.uuid4())
    qty_response = client.post(
        "/events",
        json={
            "client_event_id": qty_event_id,
            "pick_line_id": line_id,
            "session_id": session_id,
            "event": {"type": "QTY", "quantity": expected_qty},
        },
        headers=_auth(operator_token),
    )
    assert qty_response.status_code == 200, qty_response.text
    done_result = qty_response.json()
    assert done_result["state"] == "DONE"
    assert any(effect["type"] == "QUEUE_SYNC" for effect in done_result["effects"])

    # Stock was committed exactly once: on-hand decremented, reservation cleared.
    # (reserved_qty is a shared per-(sku, location) counter, not scoped to
    # this line, so it's asserted as a delta too — other orders sharing
    # this SKU may hold their own outstanding reservations.)
    with SessionLocal() as db:
        stock = db.query(StockLevel).filter_by(sku_id=sku_id, location_id=location_id).one()
        assert stock.quantity == initial_quantity - expected_qty
        assert stock.reserved_qty == initial_reserved_qty

        events = db.query(PickEvent).filter_by(session_id=uuid.UUID(session_id)).all()
        assert len(events) == 5  # 3 wrong scans + 1 override + 1 qty

    # Idempotent replay: resubmitting the same client_event_id doesn't
    # double-commit stock or duplicate the audit row.
    replay_response = client.post(
        "/events",
        json={
            "client_event_id": qty_event_id,
            "pick_line_id": line_id,
            "session_id": session_id,
            "event": {"type": "QTY", "quantity": expected_qty},
        },
        headers=_auth(operator_token),
    )
    assert replay_response.status_code == 200
    assert replay_response.json() == done_result

    with SessionLocal() as db:
        stock = db.query(StockLevel).filter_by(sku_id=sku_id, location_id=location_id).one()
        assert stock.quantity == initial_quantity - expected_qty  # unchanged
        events = db.query(PickEvent).filter_by(session_id=uuid.UUID(session_id)).all()
        assert len(events) == 5  # unchanged


def test_baseline_mode_mismatches_never_block_the_server_either(seeded_db: None) -> None:
    """Regression test for a live-found bug: BASELINE's "never block" rule
    was only implemented in the TypeScript client (baselineMode.ts). The
    offline PWA still queues the *actual* mismatched event (for the audit
    trail), and the server replayed it through the strict, blocking
    `transition()` with no idea the session was BASELINE — so the
    server's own copy of the line drifted into BLOCKED while the client
    had already moved on, and the next queued event (a different type
    than what that blocked state expects) 500'd with
    InvalidTransitionError. This drives three wrong events — location,
    SKU, and an over-quantity — through the real `/events/batch`
    endpoint the PWA actually calls, and expects the line to complete
    anyway, with no error outcome anywhere in the batch.
    """
    operator_token = _login("0001", "1234")

    with SessionLocal() as db:
        device = db.query(Device).first()
        assert device is not None
        order = make_fresh_order(db)
        order_id = order.id
        device_id = device.id
        line = db.query(PickLine).filter_by(order_id=order.id).one()
        line_id = line.id
        expected_qty = line.expected_qty

    start_response = client.post(
        "/sessions/start",
        json={"device_id": str(device_id), "mode": "BASELINE"},
        headers=_auth(operator_token),
    )
    assert start_response.status_code == 200, start_response.text
    session_id = start_response.json()["id"]

    assign_response = client.post(
        f"/orders/{order_id}/assign",
        json={"session_id": session_id},
        headers=_auth(operator_token),
    )
    assert assign_response.status_code == 200, assign_response.text

    batch_response = client.post(
        "/events/batch",
        json={
            "events": [
                {
                    "client_event_id": str(uuid.uuid4()),
                    "pick_line_id": str(line_id),
                    "session_id": session_id,
                    "event": {"type": "PRESENT"},
                },
                {
                    "client_event_id": str(uuid.uuid4()),
                    "pick_line_id": str(line_id),
                    "session_id": session_id,
                    "event": {"type": "SCAN", "barcode": "WRONG-LOCATION"},
                },
                {
                    "client_event_id": str(uuid.uuid4()),
                    "pick_line_id": str(line_id),
                    "session_id": session_id,
                    "event": {"type": "SCAN", "barcode": "WRONG-SKU"},
                },
                {
                    "client_event_id": str(uuid.uuid4()),
                    "pick_line_id": str(line_id),
                    "session_id": session_id,
                    "event": {"type": "QTY", "quantity": expected_qty + 999},
                },
            ]
        },
        headers=_auth(operator_token),
    )
    assert batch_response.status_code == 200, batch_response.text
    outcomes = batch_response.json()["outcomes"]
    assert all(o["success"] for o in outcomes), outcomes
    assert outcomes[-1]["result"]["state"] == "DONE"

    with SessionLocal() as db:
        pick_line = db.get(PickLine, line_id)
        assert pick_line is not None
        assert pick_line.state == PickState.DONE
        assert pick_line.attempts == 0
        assert pick_line.blocked_on is None
