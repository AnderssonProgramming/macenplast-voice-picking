"""Drives a full order through the API: login, start a session, assign an
order, walk a pick line through a BLOCKED -> NEEDS_OVERRIDE -> override ->
DONE path, and check stock and audit events land correctly.

Requires a reachable Postgres; skips otherwise (see test_seed.py). TTS is
irrelevant here (voice endpoints aren't exercised) so it isn't mocked.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from macenplast.db import seed
from macenplast.db.base import Base
from macenplast.db.models import Device, PickEvent, PickLine, PickOrder, StockLevel
from macenplast.db.session import SessionLocal, engine
from macenplast.main import app

client = TestClient(app)


@pytest.fixture
def seeded_db() -> Iterator[None]:
    try:
        with engine.connect():
            pass
    except OperationalError:
        pytest.skip("Postgres not reachable; start it with `docker compose up -d postgres`")

    Base.metadata.create_all(bind=engine)
    seed.main()
    yield


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
        order = db.query(PickOrder).filter(PickOrder.session_id.is_(None)).first()
        assert order is not None
        order_id = order.id
        device_id = device.id

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
    with SessionLocal() as db:
        stock = db.query(StockLevel).filter_by(sku_id=sku_id, location_id=location_id).one()
        assert stock.quantity == 100 - expected_qty
        assert stock.reserved_qty == 0

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
        assert stock.quantity == 100 - expected_qty  # unchanged
        events = db.query(PickEvent).filter_by(session_id=uuid.UUID(session_id)).all()
        assert len(events) == 5  # unchanged
