/**
 * Pure pick-line state machine — TypeScript port of
 * `apps/api/src/macenplast/domain/pick_machine.py`.
 *
 * No I/O: this module never touches IndexedDB, the network, or audio
 * playback. It takes a state, a context, and an event, and returns the next
 * state, the next context, and a list of effects for the caller to execute.
 *
 * Both implementations are tested against the same shared vectors in
 * `packages/machine-vectors/pick_line_transitions.json`. See
 * `docs/adr/0002-pick-machine.md` for the two transitions this table fills
 * in beyond `PLAN.md` section 6's prose (BLOCKED recovery depends on what
 * caused it, and BLOCKED(QTY) accepts further quantity events).
 */

export type PickState =
  | 'PENDING'
  | 'AWAITING_LOCATION'
  | 'AWAITING_SCAN'
  | 'BLOCKED'
  | 'NEEDS_OVERRIDE'
  | 'AWAITING_QTY'
  | 'SHORT_PENDING'
  | 'DONE'
  | 'EXCEPTED'

export const TERMINAL_STATES: ReadonlySet<PickState> = new Set(['DONE', 'EXCEPTED'])

export const MAX_ATTEMPTS = 3

export type BlockedOn = 'LOCATION' | 'SKU' | 'QTY'

export type IncidentReason = 'short' | 'empty_location' | 'damaged'

export interface PickContext {
  locationCheckEnabled: boolean
  expectedSkuBarcode: string
  expectedQty: number
  expectedLocationBarcode: string | null
  attempts: number
  blockedOn: BlockedOn | null
  lastQty: number | null
}

// --- Events ------------------------------------------------------------

export interface PresentEvent {
  type: 'PRESENT'
}

export interface ScanEvent {
  type: 'SCAN'
  barcode: string
}

export interface QtyEvent {
  type: 'QTY'
  quantity: number
}

export interface OverrideEvent {
  type: 'OVERRIDE'
  supervisorId: string
}

export interface RepeatEvent {
  type: 'REPEAT'
}

export interface ExceptionEvent {
  type: 'EXCEPTION'
  reason: IncidentReason
}

export type PickEvent =
  PresentEvent | ScanEvent | QtyEvent | OverrideEvent | RepeatEvent | ExceptionEvent

// --- Effects -------------------------------------------------------------

export interface SpeakEffect {
  type: 'SPEAK'
  phrase: string
  args?: Record<string, number | string>
}

export interface PlayAlertEffect {
  type: 'PLAY_ALERT'
  alert: string
}

export interface LogIncidentEffect {
  type: 'LOG_INCIDENT'
  reason: IncidentReason
}

export interface LogOverrideEffect {
  type: 'LOG_OVERRIDE'
  supervisorId: string
}

export interface QueueSyncEffect {
  type: 'QUEUE_SYNC'
}

export interface AdvanceLineEffect {
  type: 'ADVANCE_LINE'
}

export type PickEffect =
  | SpeakEffect
  | PlayAlertEffect
  | LogIncidentEffect
  | LogOverrideEffect
  | QueueSyncEffect
  | AdvanceLineEffect

export interface TransitionResult {
  state: PickState
  context: PickContext
  effects: PickEffect[]
}

export class InvalidTransitionError extends Error {}

export function transition(
  state: PickState,
  context: PickContext,
  event: PickEvent,
): TransitionResult {
  if (TERMINAL_STATES.has(state)) {
    throw new InvalidTransitionError(`${state} is terminal; no further events accepted`)
  }

  if (event.type === 'EXCEPTION') {
    return {
      state: 'EXCEPTED',
      context,
      effects: [{ type: 'LOG_INCIDENT', reason: event.reason }, { type: 'ADVANCE_LINE' }],
    }
  }

  if (event.type === 'REPEAT') {
    return { state, context, effects: [repeatEffect(state, context)] }
  }

  switch (state) {
    case 'PENDING':
      return handlePending(context, event)
    case 'AWAITING_LOCATION':
      return handleAwaitingLocation(context, event)
    case 'AWAITING_SCAN':
      return handleAwaitingScan(context, event)
    case 'BLOCKED':
      return handleBlocked(context, event)
    case 'NEEDS_OVERRIDE':
      return handleNeedsOverride(context, event)
    case 'AWAITING_QTY':
      return handleAwaitingQty(context, event)
    case 'SHORT_PENDING':
      return handleShortPending(context, event)
    default:
      throw new InvalidTransitionError(`Unhandled state ${state as string}`)
  }
}

function handlePending(context: PickContext, event: PickEvent): TransitionResult {
  if (event.type !== 'PRESENT') {
    throw new InvalidTransitionError(`PENDING does not accept ${event.type}`)
  }
  const nextState: PickState = context.locationCheckEnabled ? 'AWAITING_LOCATION' : 'AWAITING_SCAN'
  return { state: nextState, context, effects: [{ type: 'SPEAK', phrase: 'INSTRUCTION' }] }
}

function handleAwaitingLocation(context: PickContext, event: PickEvent): TransitionResult {
  if (event.type !== 'SCAN') {
    throw new InvalidTransitionError(`AWAITING_LOCATION does not accept ${event.type}`)
  }
  return handleLocationScan(context, event)
}

function handleAwaitingScan(context: PickContext, event: PickEvent): TransitionResult {
  if (event.type !== 'SCAN') {
    throw new InvalidTransitionError(`AWAITING_SCAN does not accept ${event.type}`)
  }
  return handleSkuScan(context, event)
}

function handleBlocked(context: PickContext, event: PickEvent): TransitionResult {
  const blockedOn = context.blockedOn
  if (blockedOn === null) {
    throw new InvalidTransitionError('BLOCKED context is missing blockedOn')
  }

  if (blockedOn === 'LOCATION') {
    if (event.type !== 'SCAN') {
      throw new InvalidTransitionError(`BLOCKED(LOCATION) does not accept ${event.type}`)
    }
    return handleLocationScan(context, event)
  }

  if (blockedOn === 'SKU') {
    if (event.type !== 'SCAN') {
      throw new InvalidTransitionError(`BLOCKED(SKU) does not accept ${event.type}`)
    }
    return handleSkuScan(context, event)
  }

  if (event.type !== 'QTY') {
    throw new InvalidTransitionError(`BLOCKED(QTY) does not accept ${event.type}`)
  }
  return handleQty(context, event)
}

function handleNeedsOverride(context: PickContext, event: PickEvent): TransitionResult {
  if (event.type !== 'OVERRIDE') {
    throw new InvalidTransitionError(`NEEDS_OVERRIDE does not accept ${event.type}`)
  }
  const nextContext: PickContext = { ...context, attempts: 0, blockedOn: null }
  return {
    state: 'AWAITING_QTY',
    context: nextContext,
    effects: [
      { type: 'LOG_OVERRIDE', supervisorId: event.supervisorId },
      { type: 'SPEAK', phrase: 'QTY_PROMPT', args: { quantity: context.expectedQty } },
    ],
  }
}

function handleAwaitingQty(context: PickContext, event: PickEvent): TransitionResult {
  if (event.type !== 'QTY') {
    throw new InvalidTransitionError(`AWAITING_QTY does not accept ${event.type}`)
  }
  return handleQty(context, event)
}

function handleShortPending(context: PickContext, event: PickEvent): TransitionResult {
  if (event.type !== 'QTY') {
    throw new InvalidTransitionError(`SHORT_PENDING does not accept ${event.type}`)
  }
  if (event.quantity === context.expectedQty) {
    return {
      state: 'DONE',
      context,
      effects: [{ type: 'SPEAK', phrase: 'CORRECT' }, { type: 'QUEUE_SYNC' }],
    }
  }
  const nextContext: PickContext = { ...context, lastQty: event.quantity }
  return {
    state: 'SHORT_PENDING',
    context: nextContext,
    effects: [{ type: 'SPEAK', phrase: 'ASK_CONFIRM_SHORT', args: { quantity: event.quantity } }],
  }
}

function handleLocationScan(context: PickContext, event: ScanEvent): TransitionResult {
  if (event.barcode === context.expectedLocationBarcode) {
    const nextContext: PickContext = { ...context, attempts: 0, blockedOn: null }
    return {
      state: 'AWAITING_SCAN',
      context: nextContext,
      effects: [{ type: 'SPEAK', phrase: 'LOCATION_CORRECT' }],
    }
  }
  return mismatch(context, 'LOCATION')
}

function handleSkuScan(context: PickContext, event: ScanEvent): TransitionResult {
  if (event.barcode === context.expectedSkuBarcode) {
    const nextContext: PickContext = { ...context, attempts: 0, blockedOn: null }
    return {
      state: 'AWAITING_QTY',
      context: nextContext,
      effects: [{ type: 'SPEAK', phrase: 'QTY_PROMPT', args: { quantity: context.expectedQty } }],
    }
  }
  return mismatch(context, 'SKU')
}

function handleQty(context: PickContext, event: QtyEvent): TransitionResult {
  if (event.quantity === context.expectedQty) {
    const nextContext: PickContext = { ...context, attempts: 0, blockedOn: null }
    return {
      state: 'DONE',
      context: nextContext,
      effects: [{ type: 'SPEAK', phrase: 'CORRECT' }, { type: 'QUEUE_SYNC' }],
    }
  }
  if (event.quantity < context.expectedQty) {
    const nextContext: PickContext = {
      ...context,
      attempts: 0,
      blockedOn: null,
      lastQty: event.quantity,
    }
    return {
      state: 'SHORT_PENDING',
      context: nextContext,
      effects: [{ type: 'SPEAK', phrase: 'ASK_CONFIRM_SHORT', args: { quantity: event.quantity } }],
    }
  }
  return mismatch(context, 'QTY')
}

function mismatch(context: PickContext, blockedOn: BlockedOn): TransitionResult {
  const attempts = context.attempts + 1
  const nextContext: PickContext = { ...context, attempts, blockedOn }
  if (attempts >= MAX_ATTEMPTS) {
    return {
      state: 'NEEDS_OVERRIDE',
      context: nextContext,
      effects: [{ type: 'SPEAK', phrase: 'CALL_SUPERVISOR' }],
    }
  }
  return {
    state: 'BLOCKED',
    context: nextContext,
    effects: [{ type: 'PLAY_ALERT', alert: 'MISMATCH' }],
  }
}

function repeatEffect(state: PickState, context: PickContext): PickEffect {
  switch (state) {
    case 'PENDING':
    case 'AWAITING_LOCATION':
    case 'AWAITING_SCAN':
      return { type: 'SPEAK', phrase: 'INSTRUCTION' }
    case 'BLOCKED':
      return { type: 'PLAY_ALERT', alert: 'MISMATCH' }
    case 'NEEDS_OVERRIDE':
      return { type: 'SPEAK', phrase: 'CALL_SUPERVISOR' }
    case 'AWAITING_QTY':
      return { type: 'SPEAK', phrase: 'QTY_PROMPT', args: { quantity: context.expectedQty } }
    case 'SHORT_PENDING':
      return {
        type: 'SPEAK',
        phrase: 'ASK_CONFIRM_SHORT',
        args: { quantity: context.lastQty ?? 0 },
      }
    default:
      throw new InvalidTransitionError(`No repeat effect defined for ${state}`)
  }
}
