"""Tests for `MockWmsAdapter` against a real Postgres.

Requires a reachable database; skips (doesn't fail) if none is available —
see `tests/test_seed.py` for the same pattern.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from macenplast.adapters.mock_wms import MockWmsAdapter
from macenplast.db.base import Base
from macenplast.db.models import Location, Sku, StockLevel
from macenplast.db.session import SessionLocal, engine
from macenplast.ports.wms_port import InsufficientStockError


@pytest.fixture
def db() -> Iterator[Session]:
    try:
        with engine.connect():
            pass
    except OperationalError:
        pytest.skip("Postgres not reachable; start it with `docker compose up -d postgres`")

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def stock(db: Session) -> StockLevel:
    sku = Sku(code=f"TEST-{uuid.uuid4().hex[:8]}", description="Test SKU")
    location = Location(
        aisle=uuid.uuid4().hex[:8],
        bay="1",
        level="1",
        barcode=f"LOC-{uuid.uuid4().hex[:8]}",
    )
    db.add_all([sku, location])
    db.flush()
    stock_level = StockLevel(sku_id=sku.id, location_id=location.id, quantity=10, reserved_qty=0)
    db.add(stock_level)
    db.flush()
    return stock_level


def test_get_stock_with_no_row_is_zero(db: Session) -> None:
    adapter = MockWmsAdapter(db)
    assert adapter.get_stock(uuid.uuid4(), uuid.uuid4()) == 0


def test_reserve_reduces_available_not_on_hand(db: Session, stock: StockLevel) -> None:
    adapter = MockWmsAdapter(db)

    adapter.reserve(stock.sku_id, stock.location_id, 4, idempotency_key="res-1")

    assert adapter.get_stock(stock.sku_id, stock.location_id) == 6
    assert stock.quantity == 10


def test_reserve_beyond_available_raises(db: Session, stock: StockLevel) -> None:
    adapter = MockWmsAdapter(db)

    with pytest.raises(InsufficientStockError):
        adapter.reserve(stock.sku_id, stock.location_id, 11, idempotency_key="res-over")


def test_reserve_is_idempotent(db: Session, stock: StockLevel) -> None:
    adapter = MockWmsAdapter(db)

    adapter.reserve(stock.sku_id, stock.location_id, 4, idempotency_key="res-dup")
    adapter.reserve(stock.sku_id, stock.location_id, 4, idempotency_key="res-dup")

    assert stock.reserved_qty == 4
    assert adapter.get_stock(stock.sku_id, stock.location_id) == 6


def test_commit_pick_decrements_stock_exactly_once_per_idempotency_key(
    db: Session, stock: StockLevel
) -> None:
    adapter = MockWmsAdapter(db)
    adapter.reserve(stock.sku_id, stock.location_id, 3, idempotency_key="res-a")

    adapter.commit_pick(stock.sku_id, stock.location_id, 3, idempotency_key="commit-a")
    adapter.commit_pick(stock.sku_id, stock.location_id, 3, idempotency_key="commit-a")

    assert stock.quantity == 7
    assert stock.reserved_qty == 0


def test_commit_pick_beyond_on_hand_raises(db: Session, stock: StockLevel) -> None:
    adapter = MockWmsAdapter(db)

    with pytest.raises(InsufficientStockError):
        adapter.commit_pick(stock.sku_id, stock.location_id, 100, idempotency_key="commit-over")


def test_release_returns_reservation_and_is_idempotent(db: Session, stock: StockLevel) -> None:
    adapter = MockWmsAdapter(db)
    adapter.reserve(stock.sku_id, stock.location_id, 5, idempotency_key="res-b")

    adapter.release(stock.sku_id, stock.location_id, 5, idempotency_key="release-b")
    adapter.release(stock.sku_id, stock.location_id, 5, idempotency_key="release-b")

    assert stock.reserved_qty == 0
    assert adapter.get_stock(stock.sku_id, stock.location_id) == 10
