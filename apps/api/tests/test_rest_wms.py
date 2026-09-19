"""RestWmsAdapter is a stub: every method must refuse to run until the real
WMS integration details are confirmed (see PLAN.md section 9)."""

from __future__ import annotations

import uuid

import pytest

from macenplast.adapters.rest_wms import RestWmsAdapter


@pytest.fixture
def adapter() -> RestWmsAdapter:
    return RestWmsAdapter(base_url="https://wms.example.invalid", api_key="unset")


def test_get_stock_not_implemented(adapter: RestWmsAdapter) -> None:
    with pytest.raises(NotImplementedError):
        adapter.get_stock(uuid.uuid4(), uuid.uuid4())


def test_reserve_not_implemented(adapter: RestWmsAdapter) -> None:
    with pytest.raises(NotImplementedError):
        adapter.reserve(uuid.uuid4(), uuid.uuid4(), 1, idempotency_key="k")


def test_commit_pick_not_implemented(adapter: RestWmsAdapter) -> None:
    with pytest.raises(NotImplementedError):
        adapter.commit_pick(uuid.uuid4(), uuid.uuid4(), 1, idempotency_key="k")


def test_release_not_implemented(adapter: RestWmsAdapter) -> None:
    with pytest.raises(NotImplementedError):
        adapter.release(uuid.uuid4(), uuid.uuid4(), 1, idempotency_key="k")
