"""Tests for `GET /orders/pending` and `GET /orders/{id}/lines` — what the
offline PWA (Phase 5) uses to pick an order and cache everything it needs
to run the pick machine locally.

Uses `make_fresh_order` (from test_api_full_flow) rather than reading
seed data as-is: this suite runs repeatedly against one persistent dev
database, and other tests permanently assign seeded orders to sessions,
so "the seeded orders" isn't a stable fixture to assert against.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from macenplast.db.session import SessionLocal
from macenplast.main import app
from tests.test_api_full_flow import make_fresh_order

client = TestClient(app)


def _login() -> dict[str, str]:
    response = client.post("/auth/login", json={"badge_code": "0001", "pin": "1234"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_list_pending_orders_includes_a_fresh_unassigned_order(seeded_db: None) -> None:
    with SessionLocal() as db:
        order = make_fresh_order(db, num_lines=2)
        order_id = str(order.id)

    response = client.get("/orders/pending", headers=_login())
    assert response.status_code == 200
    orders = response.json()
    assert any(o["id"] == order_id and o["line_count"] == 2 for o in orders)


def test_get_order_lines_returns_full_detail(seeded_db: None) -> None:
    with SessionLocal() as db:
        order = make_fresh_order(db, num_lines=2)
        order_id = order.id

    response = client.get(f"/orders/{order_id}/lines", headers=_login())
    assert response.status_code == 200
    lines = response.json()
    assert len(lines) == 2
    first = lines[0]
    assert first["sku_barcode"]
    assert first["location_barcode"]
    assert first["state"] == "PENDING"
    assert first["location_check_enabled"] is True


def test_get_order_lines_404_for_unknown_order(seeded_db: None) -> None:
    response = client.get(f"/orders/{uuid.uuid4()}/lines", headers=_login())
    assert response.status_code == 404
