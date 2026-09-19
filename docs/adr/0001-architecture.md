# ADR 0001 — Core architecture decisions

- Status: Accepted
- Date: 2026-09-18
- Source: `PLAN.md` section 3 ("Key decisions and why")

## Context

Macenplast needs a voice-guided picking system: spoken pick instructions,
scanner-based Poka-Yoke confirmation, real-time WMS updates, and a
supervisor view with KPIs comparing the new process against a measured
baseline. The decisions below were made up front, before implementation, so
later phases have a stable contract to build against. Each row states the
decision and the reasoning; if a later phase finds a decision wrong, that
should produce a new ADR superseding the relevant row here, not a silent
deviation.

## Decisions

### Voice output

**Decision:** ElevenLabs TTS, Flash v2.5 model, but never called in the hot
path.

**Why:** Flash is ElevenLabs' low-latency model (roughly 75 ms inference,
125-225 ms end-to-end under good network) and supports Spanish with
streaming. But plant wifi plus the offline requirement (RNF-03) make a live
cloud call between scan and confirmation a threat to the sub-1-second
requirement (RNF-02). So audio is generated ahead of time and played from
the device.

### Audio strategy

**Decision:** Two layers: a static clip library (numbers, commands, alerts)
generated at build time, plus dynamic per-SKU clips synthesized once on the
backend, cached by content hash, and prefetched to the device when an order
is assigned.

**Why:** Keeps the real ElevenLabs voice while playback is fully local. Cost
stays negligible since each distinct phrase is synthesized once and reused.

### Fallback voice

**Decision:** Browser `speechSynthesis` (es-CO/es-ES) if a needed clip is
missing on-device.

**Why:** The operator is never left in silence, even on a cache miss or
first run.

### Voice input

**Decision:** ElevenLabs Scribe v2 Realtime over WebSocket, closed command
vocabulary, push-to-talk, feature-flagged, built last (Phase 8).

**Why:** Scribe supports Spanish with sub-150ms partials. The scanner stays
the primary confirmation channel — voice input is a convenience for short
commands ("siguiente", "repetir", "cantidad diez"), which is also what keeps
ASR accuracy manageable on a noisy floor (RNF-04).

### Operator client

**Decision:** React + TypeScript + Vite, built as a PWA, targeting an
Android handheld running Chrome.

**Why:** Installable, offline-capable, works with rugged Android scanners,
and a hardware scanner in keyboard-wedge mode just works as text input.

### Scanner input

**Decision:** Keyboard-wedge detection (fast keystroke timing) as primary;
`BarcodeDetector` with a ZXing-js fallback via the camera as backup.

**Why:** Covers both dedicated Bluetooth scanners and a lost/broken
scanner.

### Backend

**Decision:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16.

**Why:** Matches the language/tooling conventions in `CLAUDE.md`; gives a
typed OpenAPI contract the frontend can generate a client from.

### WMS integration

**Decision:** Hexagonal `WmsPort` interface, with a `MockWmsAdapter`
(Postgres-backed, default) and a `RestWmsAdapter` stub.

**Why:** The real WMS isn't named in the source document. The mock lets the
whole system be built, tested, and piloted now; swapping in the real system
later is isolated to one adapter.

### Routing

**Decision:** Pure function `plan_route`; default nearest-neighbor /
S-shape (serpentine) heuristic; optional OR-Tools optimization behind a
flag for larger orders.

**Why:** Simple and testable by default; upgradeable without changing the
interface.

### Pick state machine

**Decision:** One state machine, specified once, implemented twice — Python
on the server, TypeScript on the offline client — both tested against the
same shared JSON test vectors.

**Why:** The client must keep working with no connection; the server stays
the source of truth. Shared vectors are what keeps the two implementations
from drifting apart.

### Offline support

**Decision:** IndexedDB (Dexie) plus an event outbox with idempotency keys,
synced in batches when connectivity returns.

**Why:** Satisfies RNF-03; makes RF-05 (real-time inventory update)
eventually consistent, with server-side conflict flags surfaced to
supervisors.

### Supervisor dashboard

**Decision:** Server-Sent Events for live updates.

**Why:** One-directional live updates are all it needs; simpler to build
and debug than WebSockets.

### Measuring results

**Decision:** Every session is tagged BASELINE (on-screen list, mismatches
logged but non-blocking) or VOICE (spoken, blocking).

**Why:** Produces both the missing baseline numbers and the before/after
comparison for R-01-R-03 from one codebase, addressing the "no measurable
targets" gap flagged in the earlier document review.

### Deployment

**Decision:** Docker Compose — Caddy (reverse proxy + automatic HTTPS),
API, Postgres, clip storage volume — on the plant LAN or a small cloud VM.

**Why:** HTTPS is mandatory (microphone access and service workers require
a secure context); Caddy makes that close to zero-config.

## Consequences

- Every phase after Phase 0 builds against these contracts (`WmsPort`,
  the pick state machine's states/events, the BASELINE/VOICE session tag,
  SSE for the dashboard). Changing one of these later is a breaking change
  across phases and should get its own ADR.
- The mock WMS and stubbed REST WMS mean the real Macenplast WMS
  integration is deliberately deferred; see `PLAN.md` section 9 for the
  open question this leaves.
