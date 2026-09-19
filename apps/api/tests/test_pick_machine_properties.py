"""Property-based tests for the pick machine's core safety invariants.

These are the two invariants Phase 1's acceptance criteria call out
explicitly: the machine never reaches DONE without a matching scan and
quantity, and it never leaves BLOCKED without either a correct scan or a
logged override.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from macenplast.domain.pick_machine import (
    BlockedOn,
    LogOverride,
    Override,
    PickContext,
    PickState,
    Qty,
    QueueSync,
    Scan,
    transition,
)

barcodes = st.text(
    min_size=1, max_size=12, alphabet=st.characters(min_codepoint=48, max_codepoint=90)
)
quantities = st.integers(min_value=0, max_value=100)
attempts_below_max = st.integers(min_value=0, max_value=2)


def make_context(
    *,
    expected_location: str,
    expected_sku: str,
    expected_qty: int,
    attempts: int = 0,
    blocked_on: BlockedOn | None = None,
    last_qty: int | None = None,
) -> PickContext:
    return PickContext(
        location_check_enabled=True,
        expected_location_barcode=expected_location,
        expected_sku_barcode=expected_sku,
        expected_qty=expected_qty,
        attempts=attempts,
        blocked_on=blocked_on,
        last_qty=last_qty,
    )


@given(expected_qty=quantities, scanned_qty=quantities)
def test_done_only_reached_with_matching_quantity(expected_qty: int, scanned_qty: int) -> None:
    """AWAITING_QTY -> DONE only happens when the scanned quantity matches."""
    context = make_context(expected_location="LOC", expected_sku="SKU", expected_qty=expected_qty)
    result = transition(PickState.AWAITING_QTY, context, Qty(quantity=scanned_qty))

    if result.state is PickState.DONE:
        assert scanned_qty == expected_qty
        assert any(isinstance(e, QueueSync) for e in result.effects)
    else:
        assert scanned_qty != expected_qty


@given(expected_qty=quantities, scanned_qty=quantities, attempts=attempts_below_max)
def test_blocked_qty_only_reaches_done_with_matching_quantity(
    expected_qty: int, scanned_qty: int, attempts: int
) -> None:
    """The same invariant holds when quantity is re-entered from BLOCKED(QTY)."""
    context = make_context(
        expected_location="LOC",
        expected_sku="SKU",
        expected_qty=expected_qty,
        attempts=attempts,
        blocked_on=BlockedOn.QTY,
    )
    result = transition(PickState.BLOCKED, context, Qty(quantity=scanned_qty))

    if result.state is PickState.DONE:
        assert scanned_qty == expected_qty


@given(barcode=barcodes, attempts=attempts_below_max)
def test_blocked_location_never_advances_on_wrong_scan(barcode: str, attempts: int) -> None:
    """BLOCKED(LOCATION) only leaves the blocked family on the correct scan."""
    expected = "EXPECTED-LOC"
    context = make_context(
        expected_location=expected,
        expected_sku="SKU",
        expected_qty=5,
        attempts=attempts,
        blocked_on=BlockedOn.LOCATION,
    )
    result = transition(PickState.BLOCKED, context, Scan(barcode=barcode))

    if barcode == expected:
        assert result.state is PickState.AWAITING_SCAN
    else:
        assert result.state in (PickState.BLOCKED, PickState.NEEDS_OVERRIDE)


@given(barcode=barcodes, attempts=attempts_below_max)
def test_blocked_sku_never_advances_on_wrong_scan(barcode: str, attempts: int) -> None:
    """BLOCKED(SKU) only leaves the blocked family on the correct scan."""
    expected = "EXPECTED-SKU"
    context = make_context(
        expected_location="LOC",
        expected_sku=expected,
        expected_qty=5,
        attempts=attempts,
        blocked_on=BlockedOn.SKU,
    )
    result = transition(PickState.BLOCKED, context, Scan(barcode=barcode))

    if barcode == expected:
        assert result.state is PickState.AWAITING_QTY
    else:
        assert result.state in (PickState.BLOCKED, PickState.NEEDS_OVERRIDE)


@given(blocked_on=st.sampled_from(list(BlockedOn)), attempts=attempts_below_max)
def test_needs_override_requires_logged_override_to_proceed(
    blocked_on: BlockedOn, attempts: int
) -> None:
    """NEEDS_OVERRIDE can only advance via a logged OVERRIDE event."""
    context = make_context(
        expected_location="LOC",
        expected_sku="SKU",
        expected_qty=5,
        attempts=attempts,
        blocked_on=blocked_on,
    )
    result = transition(PickState.NEEDS_OVERRIDE, context, Override(supervisor_id="SUP-1"))

    assert result.state is PickState.AWAITING_QTY
    assert any(isinstance(e, LogOverride) for e in result.effects)
