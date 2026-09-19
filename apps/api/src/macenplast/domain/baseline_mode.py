"""BASELINE mode: same pick machine, but a mismatch never blocks progress.

Ports `apps/web/src/operator/baselineMode.ts` to the backend. The offline
PWA replays every event it queues against the server's own copy of
`PickLine` state (`macenplast.api.events.apply_event`) — without this,
BASELINE's client-side "never block" behavior silently diverges from
what the strict `pick_machine.transition()` computes server-side, and
eventually raises `InvalidTransitionError` once a later event doesn't
match whatever BLOCKED/NEEDS_OVERRIDE state the server independently
arrived at (confirmed live: a wrong location scan pushed the server to
BLOCKED(LOCATION) while the client had already moved on, and the next
queued event — a QTY submission — then 500'd against a state the
client never knew existed).

Per PLAN.md section 6: "In BASELINE mode the same machine still
validates and logs every mismatch, but doesn't block progress... the
event is logged as MISMATCH_UNBLOCKED." Wraps `transition()` rather than
modifying it, for the same reason the TypeScript port does: VOICE mode's
blocking behavior is the audited Poka-Yoke contract the shared test
vectors pin down, and BASELINE's "never block" rule is a policy layered
on top of the same machine, not a different one.

Because every mismatch here is immediately forced forward instead of
being persisted, BLOCKED/NEEDS_OVERRIDE are never actually reached in
BASELINE mode — `attempts` never has a chance to climb, so this only
ever needs to force-advance from the four non-blocked active states.
"""

from __future__ import annotations

from macenplast.domain.pick_machine import (
    Event,
    InvalidTransitionError,
    PickContext,
    PickState,
    PlayAlert,
    Qty,
    Scan,
    TransitionResult,
    transition,
)


def apply_baseline_event(state: PickState, context: PickContext, event: Event) -> TransitionResult:
    """Same as `transition()`, but a mismatch forces progress instead of
    landing on BLOCKED/NEEDS_OVERRIDE."""
    result = transition(state, context, event)
    if result.state not in (PickState.BLOCKED, PickState.NEEDS_OVERRIDE):
        return result

    forced_event = _matching_event_for(state, context)
    forced_result = transition(state, context, forced_event)
    return TransitionResult(
        forced_result.state,
        forced_result.context,
        (*forced_result.effects, PlayAlert("MISMATCH_UNBLOCKED")),
    )


def _matching_event_for(state: PickState, context: PickContext) -> Event:
    if state is PickState.AWAITING_LOCATION:
        return Scan(context.expected_location_barcode or "")
    if state is PickState.AWAITING_SCAN:
        return Scan(context.expected_sku_barcode)
    if state in (PickState.AWAITING_QTY, PickState.SHORT_PENDING):
        return Qty(context.expected_qty)
    raise InvalidTransitionError(f"apply_baseline_event: unexpected mismatch from state {state!r}")
