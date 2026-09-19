"""Stub for the real Macenplast WMS integration.

`PLAN.md` section 9 flags the real WMS's identity and integration method
(REST? file drop? direct DB?) as an open question for Macenplast. Until
that's answered, every method here raises `NotImplementedError` describing
what needs to be confirmed before it can be implemented:

- Base URL and environment (staging vs. production).
- Auth scheme (API key, OAuth2 client credentials, mutual TLS?).
- Endpoint shapes for stock lookup, reservation, pick commit, and release
  — request/response bodies, status codes for "insufficient stock", and
  whether the WMS itself enforces idempotency or expects the caller to
  (this adapter would need to pass `idempotency_key` through as a header
  or body field, depending on what the WMS supports).
- Whether reservations expire server-side, and after how long.

Do not point this at a real endpoint without resolving the above first.
"""

from __future__ import annotations

import uuid

from macenplast.ports.wms_port import WmsPort

_NOT_IMPLEMENTED_MESSAGE = (
    "RestWmsAdapter is a stub. The real Macenplast WMS integration details "
    "(base URL, auth, endpoint shapes) are an open question — see PLAN.md "
    "section 9 and this module's docstring. Use MockWmsAdapter until "
    "those are confirmed."
)


class RestWmsAdapter(WmsPort):
    """Placeholder `WmsPort` implementation for the real WMS, once identified."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url
        self._api_key = api_key

    def get_stock(self, sku_id: uuid.UUID, location_id: uuid.UUID) -> int:
        raise NotImplementedError(_NOT_IMPLEMENTED_MESSAGE)

    def reserve(
        self, sku_id: uuid.UUID, location_id: uuid.UUID, quantity: int, idempotency_key: str
    ) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED_MESSAGE)

    def commit_pick(
        self, sku_id: uuid.UUID, location_id: uuid.UUID, quantity: int, idempotency_key: str
    ) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED_MESSAGE)

    def release(
        self, sku_id: uuid.UUID, location_id: uuid.UUID, quantity: int, idempotency_key: str
    ) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED_MESSAGE)
