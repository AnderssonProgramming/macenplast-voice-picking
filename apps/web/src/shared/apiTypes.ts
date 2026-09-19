/**
 * Request/response shapes mirroring `apps/api/src/macenplast/api/schemas/*`.
 * Hand-written rather than codegen'd from `apps/api/openapi.json` for this
 * phase — a generated client is a reasonable follow-up once the API
 * surface settles, but isn't worth the tooling setup yet.
 */

import type { BlockedOn, PickEffect, PickState } from './pickMachine'

export interface LoginRequest {
  badge_code: string
  pin: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  operator_id: string
  full_name: string
  role: 'operator' | 'supervisor'
}

export interface DeviceResponse {
  id: string
  device_code: string
  label: string
}

export interface StartSessionRequest {
  device_id: string
  mode: 'BASELINE' | 'VOICE'
}

export interface SessionResponse {
  id: string
  operator_id: string
  device_id: string
  mode: 'BASELINE' | 'VOICE'
  started_at: string
  ended_at: string | null
}

export interface PendingOrderSummary {
  id: string
  order_code: string
  line_count: number
}

export interface OrderLineDetail {
  line_id: string
  sequence: number
  state: PickState
  attempts: number
  blocked_on: BlockedOn | null
  last_qty: number | null
  location_check_enabled: boolean
  aisle: string
  bay: string
  level: string
  location_barcode: string
  sku_code: string
  sku_barcode: string
  reference: string
  expected_qty: number
}

export interface AssignOrderRequest {
  session_id: string
}

export interface OrderResponse {
  id: string
  order_code: string
  status: string
  session_id: string | null
}

export interface SubmitEventRequest {
  client_event_id: string
  pick_line_id: string
  session_id: string
  event: Record<string, unknown>
  occurred_at?: string | null
}

export interface EventResult {
  line_id: string
  state: PickState
  attempts: number
  blocked_on: BlockedOn | null
  last_qty: number | null
  effects: PickEffect[]
}

export interface BatchEventOutcome {
  client_event_id: string
  success: boolean
  result: EventResult | null
  error: string | null
}

export interface ClipDescriptor {
  content_hash: string
  url: string
  text: string
}

export interface VoiceManifestResponse {
  order_id: string
  clips: ClipDescriptor[]
}
