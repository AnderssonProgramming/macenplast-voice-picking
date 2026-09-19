/**
 * BASELINE mode: same pick machine, but a mismatch never blocks progress.
 *
 * Per `PLAN.md` section 6: "In BASELINE mode the same machine still
 * validates and logs every mismatch, but doesn't block progress... the
 * event is logged as MISMATCH_UNBLOCKED." This wraps `transition()`
 * rather than modifying it: VOICE mode's blocking behavior is the
 * audited Poka-Yoke contract the shared test vectors pin down, and
 * BASELINE's "never block" rule is a presentation-layer policy on top of
 * the same machine, not a different one.
 *
 * Because every mismatch here is immediately forced forward instead of
 * being persisted, BLOCKED/NEEDS_OVERRIDE are never actually reached in
 * BASELINE mode — `attempts` never has a chance to climb, so this only
 * ever needs to force-advance from the five non-blocked active states.
 */

import type { PickContext, PickEvent, PickState, TransitionResult } from '../shared/pickMachine'
import { transition } from '../shared/pickMachine'

export interface BaselineResult extends TransitionResult {
  mismatchUnblocked: boolean
}

export function applyBaselineEvent(
  state: PickState,
  context: PickContext,
  event: PickEvent,
): BaselineResult {
  const result = transition(state, context, event)

  if (result.state !== 'BLOCKED' && result.state !== 'NEEDS_OVERRIDE') {
    return { ...result, mismatchUnblocked: false }
  }

  const forcedEvent = matchingEventFor(state, context)
  const forcedResult = transition(state, context, forcedEvent)
  return {
    ...forcedResult,
    effects: [...forcedResult.effects, { type: 'PLAY_ALERT', alert: 'MISMATCH_UNBLOCKED' }],
    mismatchUnblocked: true,
  }
}

function matchingEventFor(state: PickState, context: PickContext): PickEvent {
  switch (state) {
    case 'AWAITING_LOCATION':
      return { type: 'SCAN', barcode: context.expectedLocationBarcode ?? '' }
    case 'AWAITING_SCAN':
      return { type: 'SCAN', barcode: context.expectedSkuBarcode }
    case 'AWAITING_QTY':
    case 'SHORT_PENDING':
      return { type: 'QTY', quantity: context.expectedQty }
    default:
      throw new Error(`applyBaselineEvent: unexpected mismatch from state ${state}`)
  }
}
