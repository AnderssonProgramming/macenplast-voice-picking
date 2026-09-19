/**
 * Event outbox: every local pick-machine transition is queued here with
 * a client-generated idempotency key, then flushed to `/events/batch`
 * whenever the app is online. The picking screen never waits on this —
 * queuing is synchronous and local; syncing is best-effort background
 * work, retried on reconnect.
 */

import { submitEventBatch } from '../shared/apiClient'
import type { SubmitEventRequest } from '../shared/apiTypes'
import type { PickEvent } from '../shared/pickMachine'
import { db } from './db'

export interface QueueEventInput {
  pickLineId: string
  sessionId: string
  event: PickEvent
}

function generateClientEventId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `evt-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export async function queueEvent(input: QueueEventInput): Promise<string> {
  const clientEventId = generateClientEventId()
  const now = new Date().toISOString()
  await db.outbox.add({
    clientEventId,
    pickLineId: input.pickLineId,
    sessionId: input.sessionId,
    event: input.event,
    occurredAt: now,
    synced: 0,
    createdAt: now,
  })
  return clientEventId
}

export interface SyncSummary {
  attempted: number
  synced: number
  failed: number
}

let syncInFlight: Promise<SyncSummary> | null = null

/** Flushes every unsynced outbox entry. Safe to call repeatedly — a
 * failed batch just leaves those entries queued for the next attempt.
 *
 * Concurrent callers (a queued event tries an immediate sync, the
 * `online` listener fires, a periodic refresh ticks) all await the same
 * in-flight request rather than each firing their own: two overlapping
 * `/events/batch` calls for the same pending entries would otherwise
 * race the server's idempotency check against its own insert and can
 * surface as a raw unique-constraint error instead of a clean no-op. */
export function syncOutbox(token: string): Promise<SyncSummary> {
  if (syncInFlight) return syncInFlight
  syncInFlight = performSync(token).finally(() => {
    syncInFlight = null
  })
  return syncInFlight
}

async function performSync(token: string): Promise<SyncSummary> {
  const pending = await db.outbox.where('synced').equals(0).sortBy('createdAt')
  if (pending.length === 0) {
    return { attempted: 0, synced: 0, failed: 0 }
  }

  const requests: SubmitEventRequest[] = pending.map((entry) => ({
    client_event_id: entry.clientEventId,
    pick_line_id: entry.pickLineId,
    session_id: entry.sessionId,
    // PickEvent -> the wire format's untyped JSON body.
    event: entry.event as unknown as Record<string, unknown>,
    occurred_at: entry.occurredAt,
  }))

  let response: { outcomes: { client_event_id: string; success: boolean }[] }
  try {
    response = await submitEventBatch(token, requests)
  } catch {
    return { attempted: pending.length, synced: 0, failed: pending.length }
  }

  const succeededIds = response.outcomes.filter((o) => o.success).map((o) => o.client_event_id)
  if (succeededIds.length > 0) {
    await db.outbox.where('clientEventId').anyOf(succeededIds).modify({ synced: 1 })
  }

  return {
    attempted: pending.length,
    synced: succeededIds.length,
    failed: pending.length - succeededIds.length,
  }
}

export async function pendingCount(): Promise<number> {
  return db.outbox.where('synced').equals(0).count()
}
