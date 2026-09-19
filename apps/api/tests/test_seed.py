"""Verifies the seed script is idempotent against a real Postgres.

Requires a reachable database (see `DATABASE_URL` / `.env`); skips if one
isn't available rather than failing, since not every dev machine will have
Postgres running when `pytest` is invoked directly (CI provides one — see
`.github/workflows/ci.yml`).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from macenplast.db import seed
from macenplast.db.base import Base
from macenplast.db.session import engine

SEEDED_TABLES = (
    "operators",
    "devices",
    "locations",
    "skus",
    "sku_barcodes",
    "stock_levels",
    "pick_orders",
    "pick_lines",
)


@pytest.fixture
def seeded_db() -> Iterator[None]:
    try:
        with engine.connect():
            pass
    except OperationalError:
        pytest.skip("Postgres not reachable; start it with `docker compose up -d postgres`")

    Base.metadata.create_all(bind=engine)
    yield


def _row_counts() -> dict[str, int]:
    with engine.connect() as conn:
        return {
            table: conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
            for table in SEEDED_TABLES
        }


def test_seed_is_idempotent(seeded_db: None) -> None:
    seed.main()
    first_counts = _row_counts()
    assert all(count > 0 for count in first_counts.values())

    seed.main()
    second_counts = _row_counts()

    assert second_counts == first_counts
