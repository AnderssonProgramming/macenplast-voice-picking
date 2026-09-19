"""Pure pick-line state machine.

No I/O: this module never touches the database, the network, or the voice
service. It takes a state, a context, and an event, and returns the next
state, the next context, and a list of effects for the caller to execute
(speak a phrase, play an alert, log an incident, queue a sync, ...).

The transition table is specified in `PLAN.md` section 6. Two cells of that
table are under-specified for a state machine that must behave identically
on the server and the offline client (see `docs/adr/0002-pick-machine.md`
for the reasoning):

- How BLOCKED recovers depends on what caused it. This module tracks
  `blocked_on` (LOCATION, SKU, or QTY) and requires the matching kind of
  event to recover, rather than always accepting a SKU scan.
- A BLOCKED caused by a quantity overage (`blocked_on=QTY`) accepts further
  `Qty` events using the same comparison rules as `AWAITING_QTY`, since the
  plan's table has no explicit row for that case.

The same semantics are ported to TypeScript in
`apps/web/src/shared/pickMachine.ts`; both are tested against the shared
vectors in `packages/machine-vectors/pick_line_transitions.json`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum


class PickState(StrEnum):
    """States a single pick line can be in."""

    PENDING = "PENDING"
    AWAITING_LOCATION = "AWAITING_LOCATION"
    AWAITING_SCAN = "AWAITING_SCAN"
    BLOCKED = "BLOCKED"
    NEEDS_OVERRIDE = "NEEDS_OVERRIDE"
    AWAITING_QTY = "AWAITING_QTY"
    SHORT_PENDING = "SHORT_PENDING"
    DONE = "DONE"
    EXCEPTED = "EXCEPTED"


TERMINAL_STATES = frozenset({PickState.DONE, PickState.EXCEPTED})

MAX_ATTEMPTS = 3
"""Consecutive mismatches allowed before a supervisor override is required."""


class BlockedOn(StrEnum):
    """Which check a BLOCKED or NEEDS_OVERRIDE state is blocked on."""

    LOCATION = "LOCATION"
    SKU = "SKU"
    QTY = "QTY"


class IncidentReason(StrEnum):
    """Reasons an operator can raise an exception on a pick line."""

    SHORT = "short"
    EMPTY_LOCATION = "empty_location"
    DAMAGED = "damaged"


class InvalidTransitionError(Exception):
    """Raised when an event is not valid for the current state."""


@dataclass(frozen=True)
class PickContext:
    """Everything the machine needs to decide a transition for one line."""

    location_check_enabled: bool
    expected_sku_barcode: str
    expected_qty: int
    expected_location_barcode: str | None = None
    attempts: int = 0
    blocked_on: BlockedOn | None = None
    last_qty: int | None = None


# --- Events -----------------------------------------------------------------


@dataclass(frozen=True)
class Present:
    """The line becomes the operator's current line."""


@dataclass(frozen=True)
class Scan:
    """Operator scanned a barcode (location label or SKU barcode)."""

    barcode: str


@dataclass(frozen=True)
class Qty:
    """Operator confirmed a quantity."""

    quantity: int


@dataclass(frozen=True)
class Override:
    """A supervisor cleared a NEEDS_OVERRIDE line."""

    supervisor_id: str


@dataclass(frozen=True)
class Repeat:
    """Operator asked to hear the current instruction again."""


@dataclass(frozen=True)
class ExceptionEvent:
    """Operator or system raised an exception (short/empty/damaged)."""

    reason: IncidentReason


Event = Present | Scan | Qty | Override | Repeat | ExceptionEvent


# --- Effects ------------------------------------------------------------


@dataclass(frozen=True)
class Speak:
    """Play a catalog phrase, optionally with substitution args."""

    phrase: str
    args: dict[str, int | str] = field(default_factory=dict)


@dataclass(frozen=True)
class PlayAlert:
    """Play an alert clip."""

    alert: str = "MISMATCH"


@dataclass(frozen=True)
class LogIncident:
    """Record an incident for this line."""

    reason: IncidentReason


@dataclass(frozen=True)
class LogOverride:
    """Record which supervisor cleared a block."""

    supervisor_id: str


@dataclass(frozen=True)
class QueueSync:
    """Queue the completed line for sync to the server / WMS."""


@dataclass(frozen=True)
class AdvanceLine:
    """Move the operator on to the next line in the order."""


Effect = Speak | PlayAlert | LogIncident | LogOverride | QueueSync | AdvanceLine


@dataclass(frozen=True)
class TransitionResult:
    """The outcome of applying one event to one (state, context) pair."""

    state: PickState
    context: PickContext
    effects: tuple[Effect, ...]


def transition(state: PickState, context: PickContext, event: Event) -> TransitionResult:
    """Apply `event` to `(state, context)` and return the next state.

    Raises:
        InvalidTransitionError: if `event` is not valid for `state`.
    """
    if state in TERMINAL_STATES:
        raise InvalidTransitionError(f"{state} is terminal; no further events accepted")

    if isinstance(event, ExceptionEvent):
        return TransitionResult(
            PickState.EXCEPTED,
            context,
            (LogIncident(event.reason), AdvanceLine()),
        )

    if isinstance(event, Repeat):
        return TransitionResult(state, context, (_repeat_effect(state, context),))

    if state is PickState.PENDING:
        if isinstance(event, Present):
            next_state = (
                PickState.AWAITING_LOCATION
                if context.location_check_enabled
                else PickState.AWAITING_SCAN
            )
            return TransitionResult(next_state, context, (Speak("INSTRUCTION"),))
        raise InvalidTransitionError(f"PENDING does not accept {event!r}")

    if state is PickState.AWAITING_LOCATION:
        if isinstance(event, Scan):
            return _handle_location_scan(context, event)
        raise InvalidTransitionError(f"AWAITING_LOCATION does not accept {event!r}")

    if state is PickState.AWAITING_SCAN:
        if isinstance(event, Scan):
            return _handle_sku_scan(context, event)
        raise InvalidTransitionError(f"AWAITING_SCAN does not accept {event!r}")

    if state is PickState.BLOCKED:
        return _handle_blocked(context, event)

    if state is PickState.NEEDS_OVERRIDE:
        if isinstance(event, Override):
            next_context = replace(context, attempts=0, blocked_on=None)
            return TransitionResult(
                PickState.AWAITING_QTY,
                next_context,
                (
                    LogOverride(event.supervisor_id),
                    Speak("QTY_PROMPT", {"quantity": context.expected_qty}),
                ),
            )
        raise InvalidTransitionError(f"NEEDS_OVERRIDE does not accept {event!r}")

    if state is PickState.AWAITING_QTY:
        if isinstance(event, Qty):
            return _handle_qty(context, event)
        raise InvalidTransitionError(f"AWAITING_QTY does not accept {event!r}")

    if state is PickState.SHORT_PENDING:
        if isinstance(event, Qty):
            if event.quantity == context.expected_qty:
                return TransitionResult(PickState.DONE, context, (Speak("CORRECT"), QueueSync()))
            next_context = replace(context, last_qty=event.quantity)
            return TransitionResult(
                PickState.SHORT_PENDING,
                next_context,
                (Speak("ASK_CONFIRM_SHORT", {"quantity": event.quantity}),),
            )
        raise InvalidTransitionError(f"SHORT_PENDING does not accept {event!r}")

    raise InvalidTransitionError(f"Unhandled state {state!r}")


def _handle_location_scan(context: PickContext, event: Scan) -> TransitionResult:
    if event.barcode == context.expected_location_barcode:
        next_context = replace(context, attempts=0, blocked_on=None)
        return TransitionResult(PickState.AWAITING_SCAN, next_context, (Speak("LOCATION_CORRECT"),))
    return _mismatch(context, BlockedOn.LOCATION)


def _handle_sku_scan(context: PickContext, event: Scan) -> TransitionResult:
    if event.barcode == context.expected_sku_barcode:
        next_context = replace(context, attempts=0, blocked_on=None)
        return TransitionResult(
            PickState.AWAITING_QTY,
            next_context,
            (Speak("QTY_PROMPT", {"quantity": context.expected_qty}),),
        )
    return _mismatch(context, BlockedOn.SKU)


def _handle_qty(context: PickContext, event: Qty) -> TransitionResult:
    if event.quantity == context.expected_qty:
        next_context = replace(context, attempts=0, blocked_on=None)
        return TransitionResult(PickState.DONE, next_context, (Speak("CORRECT"), QueueSync()))
    if event.quantity < context.expected_qty:
        next_context = replace(context, attempts=0, blocked_on=None, last_qty=event.quantity)
        return TransitionResult(
            PickState.SHORT_PENDING,
            next_context,
            (Speak("ASK_CONFIRM_SHORT", {"quantity": event.quantity}),),
        )
    return _mismatch(context, BlockedOn.QTY)


def _handle_blocked(context: PickContext, event: Event) -> TransitionResult:
    blocked_on = context.blocked_on
    if blocked_on is None:
        raise InvalidTransitionError("BLOCKED context is missing blocked_on")

    if blocked_on is BlockedOn.LOCATION:
        if isinstance(event, Scan):
            return _handle_location_scan(context, event)
        raise InvalidTransitionError(f"BLOCKED(LOCATION) does not accept {event!r}")

    if blocked_on is BlockedOn.SKU:
        if isinstance(event, Scan):
            return _handle_sku_scan(context, event)
        raise InvalidTransitionError(f"BLOCKED(SKU) does not accept {event!r}")

    if isinstance(event, Qty):
        return _handle_qty(context, event)
    raise InvalidTransitionError(f"BLOCKED(QTY) does not accept {event!r}")


def _mismatch(context: PickContext, blocked_on: BlockedOn) -> TransitionResult:
    attempts = context.attempts + 1
    next_context = replace(context, attempts=attempts, blocked_on=blocked_on)
    if attempts >= MAX_ATTEMPTS:
        return TransitionResult(PickState.NEEDS_OVERRIDE, next_context, (Speak("CALL_SUPERVISOR"),))
    return TransitionResult(PickState.BLOCKED, next_context, (PlayAlert(),))


def _repeat_effect(state: PickState, context: PickContext) -> Effect:
    if state in (PickState.PENDING, PickState.AWAITING_LOCATION, PickState.AWAITING_SCAN):
        return Speak("INSTRUCTION")
    if state is PickState.BLOCKED:
        return PlayAlert()
    if state is PickState.NEEDS_OVERRIDE:
        return Speak("CALL_SUPERVISOR")
    if state is PickState.AWAITING_QTY:
        return Speak("QTY_PROMPT", {"quantity": context.expected_qty})
    if state is PickState.SHORT_PENDING:
        return Speak("ASK_CONFIRM_SHORT", {"quantity": context.last_qty or 0})
    raise InvalidTransitionError(f"No repeat effect defined for {state!r}")
