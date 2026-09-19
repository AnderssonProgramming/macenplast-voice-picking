"""Tests for `GET /devices` — what the operator PWA picks from at shift start."""

from __future__ import annotations

from fastapi.testclient import TestClient

from macenplast.main import app

client = TestClient(app)


def _login() -> dict[str, str]:
    response = client.post("/auth/login", json={"badge_code": "0001", "pin": "1234"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_list_devices_includes_seeded_device(seeded_db: None) -> None:
    response = client.get("/devices", headers=_login())
    assert response.status_code == 200
    devices = response.json()
    assert any(d["device_code"] == "HANDHELD-01" for d in devices)


def test_list_devices_requires_auth(seeded_db: None) -> None:
    response = client.get("/devices")
    assert response.status_code == 401
