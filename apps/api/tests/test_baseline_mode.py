"""Mirrors apps/web/src/operator/baselineMode.test.ts — same cases,
same assertions, so the Python and TypeScript "never block" wrappers
stay in lockstep the same way the shared pick_machine vectors do."""

from __future__ import annotations

from macenplast.domain.baseline_mode import apply_baseline_event
from macenplast.domain.pick_machine import PickContext, PickState, Qty, QueueSync, Scan

BASE_CONTEXT = PickContext(
    location_check_enabled=True,
    expected_location_barcode="LOC-A1",
    expected_sku_barcode="SKU-100",
    expected_qty=10,
)


def test_advances_normally_on_a_correct_scan_same_as_voice_mode() -> None:
    result = apply_baseline_event(PickState.AWAITING_LOCATION, BASE_CONTEXT, Scan("LOC-A1"))
    assert result.state is PickState.AWAITING_SCAN


def test_never_blocks_on_a_wrong_location_scan_forces_forward_instead() -> None:
    result = apply_baseline_event(PickState.AWAITING_LOCATION, BASE_CONTEXT, Scan("WRONG"))
    assert result.state is PickState.AWAITING_SCAN
    assert result.context.attempts == 0
    assert any(getattr(effect, "alert", None) == "MISMATCH_UNBLOCKED" for effect in result.effects)


def test_never_blocks_on_a_wrong_sku_scan() -> None:
    result = apply_baseline_event(PickState.AWAITING_SCAN, BASE_CONTEXT, Scan("WRONG-SKU"))
    assert result.state is PickState.AWAITING_QTY


def test_never_blocks_on_an_over_quantity_entry_completes_the_line_anyway() -> None:
    result = apply_baseline_event(PickState.AWAITING_QTY, BASE_CONTEXT, Qty(999))
    assert result.state is PickState.DONE
    assert any(isinstance(effect, QueueSync) for effect in result.effects)


def test_does_not_increment_attempts_across_repeated_mismatches() -> None:
    context = BASE_CONTEXT
    for _ in range(5):
        result = apply_baseline_event(PickState.AWAITING_LOCATION, context, Scan("WRONG"))
        assert result.state not in (PickState.BLOCKED, PickState.NEEDS_OVERRIDE)
        context = result.context
