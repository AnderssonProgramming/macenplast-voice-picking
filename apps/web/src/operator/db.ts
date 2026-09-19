/**
 * IndexedDB (via Dexie), per ADR 0001's "Offline support" row: cached
 * order lines (so the picking screen never needs a round-trip once a
 * shift starts) and an event outbox with idempotency keys, synced in
 * batches when connectivity returns.
 */

import Dexie, { type Table } from 'dexie'
import type { BlockedOn, PickEvent, PickState } from '../shared/pickMachine'

export interface CachedLine {
  lineId: string
  orderId: string
  sequence: number
  state: PickState
  attempts: number
  blockedOn: BlockedOn | null
  lastQty: number | null
  locationCheckEnabled: boolean
  aisle: string
  bay: string
  level: string
  locationBarcode: string
  skuCode: string
  skuBarcode: string
  reference: string
  expectedQty: number
}

export interface OutboxEntry {
  clientEventId: string
  pickLineId: string
  sessionId: string
  event: PickEvent
  occurredAt: string
  synced: 0 | 1
  createdAt: string
}

export interface AppState {
  key: 'current'
  token: string
  operatorId: string
  fullName: string
  role: 'operator' | 'supervisor'
  deviceId: string
  sessionId: string
  mode: 'BASELINE' | 'VOICE'
  orderId: string
}

export class OperatorDb extends Dexie {
  lines!: Table<CachedLine, string>
  outbox!: Table<OutboxEntry, string>
  appState!: Table<AppState, string>

  constructor() {
    super('macenplast-operator')
    this.version(1).stores({
      lines: 'lineId, orderId, sequence',
      outbox: 'clientEventId, pickLineId, synced',
      appState: 'key',
    })
  }
}

export const db = new OperatorDb()

export async function getCurrentAppState(): Promise<AppState | undefined> {
  return db.appState.get('current')
}

export async function setCurrentAppState(state: AppState): Promise<void> {
  await db.appState.put(state)
}

export async function clearCurrentAppState(): Promise<void> {
  await db.appState.delete('current')
  await db.lines.clear()
}

export async function getNextIncompleteLine(orderId: string): Promise<CachedLine | undefined> {
  const lines = await db.lines.where('orderId').equals(orderId).sortBy('sequence')
  return lines.find((line) => line.state !== 'DONE' && line.state !== 'EXCEPTED')
}
