"""Postgres-backed `WmsPort`, built on Phase 1's `stock_levels` table.

Every mutating call is idempotent: it first checks the `stock_movements`
ledger for a row with the same `(movement_type, idempotency_key)` and, if
found, returns without touching stock again. The unique constraint on that
pair (`uq_movement_idempotency`) is the actual safety net under concurrent
callers — the ledger check just avoids the extra write in the common case.

Callers own the session's transaction boundary (commit/rollback); this
adapter only flushes so `get_stock` reads its own uncommitted writes within
the same session.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from macenplast.db.models import MovementType, StockLevel, StockMovement
from macenplast.ports.wms_port import InsufficientStockError, WmsPort


class MockWmsAdapter(WmsPort):
    """Default `WmsPort` implementation, backed by the local database."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_stock(self, sku_id: uuid.UUID, location_id: uuid.UUID) -> int:
        stock = self._get_stock_level(sku_id, location_id)
        if stock is None:
            return 0
        return stock.quantity - stock.reserved_qty

    def reserve(
        self, sku_id: uuid.UUID, location_id: uuid.UUID, quantity: int, idempotency_key: str
    ) -> None:
        if self._already_applied(MovementType.RESERVE, idempotency_key):
            return

        stock = self._get_stock_level(sku_id, location_id)
        available = (stock.quantity - stock.reserved_qty) if stock is not None else 0
        if available < quantity:
            raise InsufficientStockError(
                f"Requested {quantity} of sku={sku_id} at location={location_id}, "
                f"only {available} available"
            )

        assert stock is not None  # available > 0 implies a row exists
        stock.reserved_qty += quantity
        self._record(MovementType.RESERVE, sku_id, location_id, quantity, idempotency_key)

    def commit_pick(
        self, sku_id: uuid.UUID, location_id: uuid.UUID, quantity: int, idempotency_key: str
    ) -> None:
        if self._already_applied(MovementType.COMMIT, idempotency_key):
            return

        stock = self._get_stock_level(sku_id, location_id)
        if stock is None or stock.quantity < quantity:
            on_hand = stock.quantity if stock is not None else 0
            raise InsufficientStockError(
                f"Cannot commit {quantity} of sku={sku_id} at location={location_id}, "
                f"only {on_hand} on hand"
            )

        stock.quantity -= quantity
        stock.reserved_qty = max(0, stock.reserved_qty - quantity)
        self._record(MovementType.COMMIT, sku_id, location_id, quantity, idempotency_key)

    def release(
        self, sku_id: uuid.UUID, location_id: uuid.UUID, quantity: int, idempotency_key: str
    ) -> None:
        if self._already_applied(MovementType.RELEASE, idempotency_key):
            return

        stock = self._get_stock_level(sku_id, location_id)
        if stock is not None:
            stock.reserved_qty = max(0, stock.reserved_qty - quantity)
        self._record(MovementType.RELEASE, sku_id, location_id, quantity, idempotency_key)

    def _get_stock_level(self, sku_id: uuid.UUID, location_id: uuid.UUID) -> StockLevel | None:
        return (
            self._session.query(StockLevel)
            .filter_by(sku_id=sku_id, location_id=location_id)
            .one_or_none()
        )

    def _already_applied(self, movement_type: MovementType, idempotency_key: str) -> bool:
        existing = (
            self._session.query(StockMovement)
            .filter_by(movement_type=movement_type, idempotency_key=idempotency_key)
            .one_or_none()
        )
        return existing is not None

    def _record(
        self,
        movement_type: MovementType,
        sku_id: uuid.UUID,
        location_id: uuid.UUID,
        quantity: int,
        idempotency_key: str,
    ) -> None:
        self._session.add(
            StockMovement(
                sku_id=sku_id,
                location_id=location_id,
                movement_type=movement_type,
                quantity=quantity,
                idempotency_key=idempotency_key,
            )
        )
        self._session.flush()
