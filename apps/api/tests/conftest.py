"""Shared pytest fixtures.

Tests share one persistent dev Postgres across runs (there's no
per-test-run fresh database), so anything that *mutates* shared seed rows
(e.g. assigning an order) must not depend on "some seeded row is still in
its original state" — that assumption quietly breaks after enough runs.
See `make_fresh_order` in the test modules that need an order to assign.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.exc import OperationalError

from macenplast.db import seed
from macenplast.db.base import Base
from macenplast.db.session import engine


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
