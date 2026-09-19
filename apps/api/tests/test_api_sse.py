"""Tests the dashboard SSE stream against a real, live server.

Neither `TestClient` nor `httpx.AsyncClient(transport=ASGITransport(...))`
work here: both fully buffer the ASGI response body before returning
anything, so a stream that never terminates on its own (this one runs
forever, by design) just hangs the test forever — this is a documented
httpx/ASGITransport limitation, not specific to sse-starlette or this
app. A real Uvicorn server sends headers immediately and streams the body
incrementally, like any real HTTP server, so this spins one up on a
background thread and talks to it over a real socket.

That also sidesteps a second hazard: `Broadcaster.publish()` calls
`asyncio.Queue.put_nowait()`, which isn't safe to call from a different
thread than the queue's own event loop. Calling it directly from the test
thread (as an earlier version of this test did) would have the same
"never wakes up" failure mode as the two approaches above, for a related
reason. Publishing here happens by making a real `/events` request against
the live server, so the publish call runs on the server's own event-loop
thread, same as every other coroutine handling that connection.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections.abc import Iterator

import httpx
import pytest
import uvicorn

from macenplast.db.models import Device, PickLine, PickOrder
from macenplast.db.session import SessionLocal
from macenplast.main import app


@pytest.fixture
def live_server() -> Iterator[str]:
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started, "Uvicorn did not start in time"

    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_dashboard_stream_receives_a_real_event_update(seeded_db: None, live_server: str) -> None:
    with SessionLocal() as db:
        pick_line = db.query(PickLine).join(PickOrder).first()
        assert pick_line is not None
        line_id = pick_line.id
        device = db.query(Device).first()
        assert device is not None
        device_id = device.id

    login = httpx.post(f"{live_server}/auth/login", json={"badge_code": "0001", "pin": "1234"})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    start_response = httpx.post(
        f"{live_server}/sessions/start",
        json={"device_id": str(device_id), "mode": "VOICE"},
        headers=headers,
    )
    assert start_response.status_code == 200, start_response.text
    session_id = start_response.json()["id"]

    received: list[dict[str, object]] = []
    stream_ready = threading.Event()

    def consume_stream() -> None:
        with (
            httpx.Client(timeout=10) as client,
            client.stream("GET", f"{live_server}/dashboard/stream", headers=headers) as resp,
        ):
            stream_ready.set()
            for line in resp.iter_lines():
                if line.startswith("data:"):
                    received.append(json.loads(line[len("data:") :].strip()))
                    return

    consumer = threading.Thread(target=consume_stream, daemon=True)
    consumer.start()
    assert stream_ready.wait(timeout=5), "SSE stream never opened"
    time.sleep(0.2)  # let the server finish registering the subscriber

    event_response = httpx.post(
        f"{live_server}/events",
        json={
            "client_event_id": str(uuid.uuid4()),
            "pick_line_id": str(line_id),
            "session_id": session_id,
            "event": {"type": "REPEAT"},
        },
        headers=headers,
    )
    assert event_response.status_code == 200, event_response.text

    consumer.join(timeout=5)
    assert not consumer.is_alive(), "SSE stream never delivered the update"
    assert received == [
        {
            "type": "pick_line_updated",
            "line_id": str(line_id),
            "session_id": session_id,
            "state": event_response.json()["state"],
        }
    ]
