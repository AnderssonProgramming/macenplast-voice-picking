# ADR 0002 — Pick line state machine: precise transition semantics

- Status: Accepted
- Date: 2026-09-18
- Source: `PLAN.md` section 6 ("Domain model and the pick state machine")

## Context

`PLAN.md` section 6 specifies the pick line state machine as a prose table.
That table is precise enough to describe the intended behavior to a human,
but two cells are ambiguous in a way that matters for a state machine
implemented twice (Python and TypeScript) and checked against the same
JSON test vectors — an ambiguity here would let the two implementations
agree with the prose while disagreeing with each other.

Per `PLAN.md`'s own rule ("when Claude Code disagrees with a decision... it
should stop, ask, and record the resolution as an ADR"), this ADR records
the two gaps and the resolution implemented in
`apps/api/src/macenplast/domain/pick_machine.py` and
`apps/web/src/shared/pickMachine.ts`. These are implementation-level
ambiguities (not product decisions), so they were resolved directly rather
than escalated; flag either resolution if it doesn't match how Macenplast
actually wants the floor to behave.

## Gap 1 — What "BLOCKED" recovers to

The table has one row for leaving BLOCKED:

> `BLOCKED | SCAN(expected barcode) | AWAITING_QTY | speak confirmation`

But BLOCKED can be entered from three different mismatches: a wrong
location label, a wrong SKU barcode, or (see Gap 2) a quantity overage. Read
literally, the table says *any* BLOCKED always resolves straight to
AWAITING_QTY on a SKU-barcode scan — meaning a wrong-location block could be
cleared by scanning the correct product, without ever re-confirming the
location.

**Decision:** BLOCKED remembers which check failed (`blockedOn: LOCATION |
SKU | QTY`) and only accepts the matching kind of recovery input:

| Blocked on | Recovers on | Goes to |
|---|---|---|
| LOCATION | correct location scan | AWAITING_SCAN |
| SKU | correct SKU scan | AWAITING_QTY |
| QTY | see Gap 2 | — |

**Why:** This keeps the Poka-Yoke guarantee intact for the location check —
RF-04 requires a match to confirm before proceeding, and collapsing
location-mismatch recovery into a SKU scan would silently drop that
guarantee for any order with location checking on.

## Gap 2 — BLOCKED from a quantity overage

The table has:

> `AWAITING_QTY | QTY(n above expected) | BLOCKED | alert clip`

but no row for what BLOCKED does next in that case — there's no `BLOCKED |
QTY(...) | ...` row at all.

**Decision:** `blockedOn: QTY` accepts further `QTY` events and applies the
same comparison rules as `AWAITING_QTY` (match → DONE, below → SHORT_PENDING,
above → stays BLOCKED and re-runs the attempt-counting logic below).

**Why:** It's the direct generalization of the existing AWAITING_QTY rules,
requires no new event type, and keeps the invariant "you can't reach DONE
without a matching quantity" true regardless of which state the match
happens from.

## Attempt counting and override, made precise

The table describes attempts reaching 3 as its own row ("`BLOCKED | attempts
reach 3 | NEEDS_OVERRIDE`"), which isn't a discrete event. The implemented
rule: every mismatch (wrong location scan, wrong SKU scan, or quantity
overage) increments a single `attempts` counter on the line's context. When
incrementing would put `attempts >= 3` (`MAX_ATTEMPTS`), the transition goes
straight to `NEEDS_OVERRIDE` instead of `BLOCKED`. `attempts` resets to 0
whenever a gate is actually resolved (correct scan, or a quantity match /
short).

`NEEDS_OVERRIDE` always resolves to `AWAITING_QTY` on `OVERRIDE`, regardless
of which gate triggered it — a supervisor override is a blanket "let this
pick through," consistent with `PLAN.md` section 1's framing of the
override as an escape hatch so RF-04's hard block "can't strand an operator
indefinitely." The plan's table only lists `LogOverride` as the override's
effect; the implementation also re-speaks the quantity prompt (`SPEAK
QTY_PROMPT`), since leaving the operator in `AWAITING_QTY` with no prompt
would violate the "operator is never left in silence" principle behind the
fallback-voice decision in ADR 0001.

## SHORT_PENDING

The table says SHORT_PENDING should "ask the operator to confirm the
shortage" but doesn't enumerate its outgoing events. Implemented as two
existing event types, no new vocabulary:

- `EXCEPTION(reason=short)` → `EXCEPTED`, logs an incident (operator
  confirms the shortage is real).
- `QTY(n = expectedQty)` → `DONE` (operator corrects an earlier mis-scan;
  the count was actually full).

## Consequences

- These rules are what the shared test vectors in
  `packages/machine-vectors/pick_line_transitions.json` encode; treat that
  file, not the prose table in `PLAN.md` section 6, as the executable spec
  for the state machine going forward.
- If Macenplast's pilot (Phase 7) shows operators expect location-mismatch
  recovery to also accept a SKU scan (i.e., the original literal reading),
  that's a one-line change in `_handle_blocked` / `handleBlocked` — the
  vectors would need updating to match.
