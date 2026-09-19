"""Server-Sent Events dashboard stream.

`macenplast.api.events` publishes here whenever a pick event or incident
is recorded; `GET /dashboard/stream` is what the supervisor dashboard
(Phase 6) subscribes to. One-directional, per ADR 0001's "Supervisor
dashboard" row — simpler to build and debug than WebSockets.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class Broadcaster:
    """In-process pub/sub. One process is enough for the MVP/pilot scale
    this system targets; a multi-instance deployment would need a shared
    backend (e.g. Postgres LISTEN/NOTIFY or Redis) instead."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        """Register a subscriber queue synchronously, before any
        streaming begins — this is what lets a caller publish an event
        immediately after opening a connection without a race against
        the response's own async generator starting up."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def publish(self, event: dict[str, Any]) -> None:
        for queue in self._subscribers:
            queue.put_nowait(event)


broadcaster = Broadcaster()


@router.get("/stream")
async def stream_dashboard_events() -> EventSourceResponse:
    queue = broadcaster.subscribe()

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        try:
            while True:
                event = await queue.get()
                yield {"event": event.get("type", "message"), "data": json.dumps(event)}
        finally:
            broadcaster.unsubscribe(queue)

    return EventSourceResponse(event_generator())
