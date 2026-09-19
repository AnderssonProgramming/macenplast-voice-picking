/**
 * Typed fetch wrapper for the backend (`apps/api`). Every call here is
 * one the operator PWA makes *while online* — the actual picking flow
 * (Phase 5's whole point) runs on cached data and the shared
 * `pickMachine`, with results queued to the offline outbox instead of
 * calling these directly. See `operator/outbox.ts`.
 */

import type {
  AssignOrderRequest,
  BatchEventOutcome,
  DeviceResponse,
  EventResult,
  LoginRequest,
  LoginResponse,
  OrderLineDetail,
  OrderResponse,
  PendingOrderSummary,
  SessionResponse,
  StartSessionRequest,
  SubmitEventRequest,
  VoiceManifestResponse,
} from './apiTypes'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(
  path: string,
  options: { method?: string; token?: string; body?: unknown } = {},
): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options.token) headers.Authorization = `Bearer ${options.token}`

  const response = await fetch(`${BASE_URL}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new ApiError(response.status, detail || response.statusText)
  }
  return (await response.json()) as T
}

export function login(payload: LoginRequest): Promise<LoginResponse> {
  return request('/auth/login', { method: 'POST', body: payload })
}

export function listDevices(token: string): Promise<DeviceResponse[]> {
  return request('/devices', { token })
}

export function startSession(
  token: string,
  payload: StartSessionRequest,
): Promise<SessionResponse> {
  return request('/sessions/start', { method: 'POST', token, body: payload })
}

export function endSession(token: string, sessionId: string): Promise<SessionResponse> {
  return request(`/sessions/${sessionId}/end`, { method: 'POST', token })
}

export function listPendingOrders(token: string): Promise<PendingOrderSummary[]> {
  return request('/orders/pending', { token })
}

export function getOrderLines(token: string, orderId: string): Promise<OrderLineDetail[]> {
  return request(`/orders/${orderId}/lines`, { token })
}

export function assignOrder(
  token: string,
  orderId: string,
  payload: AssignOrderRequest,
): Promise<OrderResponse> {
  return request(`/orders/${orderId}/assign`, { method: 'POST', token, body: payload })
}

export function submitEvent(token: string, payload: SubmitEventRequest): Promise<EventResult> {
  return request('/events', { method: 'POST', token, body: payload })
}

export function submitEventBatch(
  token: string,
  events: SubmitEventRequest[],
): Promise<{ outcomes: BatchEventOutcome[] }> {
  return request('/events/batch', { method: 'POST', token, body: { events } })
}

export function clipAudioUrl(contentHash: string): string {
  return `${BASE_URL}/voice/clips/${contentHash}`
}

export async function getVoiceManifest(
  token: string,
  orderId: string,
): Promise<VoiceManifestResponse> {
  const manifest = await request<VoiceManifestResponse>(`/voice/orders/${orderId}/manifest`, {
    token,
  })
  // The backend's `url` field is a path relative to *its own* root
  // (`/voice/clips/{hash}`), not to whatever the frontend is deployed
  // behind (e.g. Vercel Services routes only `/api/*` to the backend —
  // fetching the bare path resolves against the frontend's own origin
  // instead, silently hitting its SPA catch-all). Route every clip
  // through `clipAudioUrl()` so it resolves against BASE_URL like every
  // other API call here does.
  return {
    ...manifest,
    clips: manifest.clips.map((clip) => ({ ...clip, url: clipAudioUrl(clip.content_hash) })),
  }
}
