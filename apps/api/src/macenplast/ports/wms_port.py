"""The hexagonal boundary between the app and whatever WMS holds stock.

`PLAN.md`'s source document doesn't name a real WMS, so this interface is
what every other layer (API routes, the state machine's effect handlers)
codes against. `macenplast.adapters.mock_wms.MockWmsAdapter` is the default,
Postgres-backed implementation; `macenplast.adapters.rest_wms.RestWmsAdapter`
is a stub for the real system, once one is identified.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod


class InsufficientStockError(Exception):
    """Raised when a reserve/commit would take stock below zero."""


class WmsPort(ABC):
    """Stock operations a picking flow needs from a WMS."""

    @abstractmethod
    def get_stock(self, sku_id: uuid.UUID, location_id: uuid.UUID) -> int:
        """Return available stock (on-hand minus already-reserved)."""

    @abstractmethod
    def reserve(
        self, sku_id: uuid.UUID, location_id: uuid.UUID, quantity: int, idempotency_key: str
    ) -> None:
        """Allocate `quantity` units to an in-progress pick line.

        Does not change on-hand stock — only what's available for *other*
        reservations. Idempotent: calling this again with the same
        `idempotency_key` is a no-op.

        Raises:
            InsufficientStockError: if fewer than `quantity` units are
                available.
        """

    @abstractmethod
    def commit_pick(
        self, sku_id: uuid.UUID, location_id: uuid.UUID, quantity: int, idempotency_key: str
    ) -> None:
        """Finalize a pick: decrement on-hand stock and its reservation.

        Idempotent: calling this again with the same `idempotency_key`
        does not decrement stock a second time.
        """

    @abstractmethod
    def release(
        self, sku_id: uuid.UUID, location_id: uuid.UUID, quantity: int, idempotency_key: str
    ) -> None:
        """Release a reservation without committing it (e.g. an excepted line).

        Idempotent: calling this again with the same `idempotency_key` is
        a no-op.
        """
