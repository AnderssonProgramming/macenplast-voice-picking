# Progress log

One entry per phase: what was built, deviations from `PLAN.md`, and open
questions for the next phase.

## Phase 0 — Repo bootstrap (2026-09-18)

**Built**

- Repo skeleton per `PLAN.md` section 5 (`apps/api`, `apps/web`,
  `packages/machine-vectors`, `tools/voice-clips`, `analysis`, `docs/`).
- `CLAUDE.md` generated from `PLAN.md` section 2.
- `docs/adr/0001-architecture.md` capturing the section 3 decisions table.
- `apps/api`: FastAPI app with a `/health` endpoint, `pyproject.toml`
  (ruff + mypy strict + pytest, with a `live` marker for ElevenLabs smoke
  tests, deselected by default), a Dockerfile targeting Python 3.12.
- `apps/web`: Vite + React + TypeScript PWA scaffold (the default template
  ships `oxlint`; swapped for ESLint (flat config) + Prettier + Vitest to
  match `CLAUDE.md`'s TypeScript rules).
- Root `docker-compose.yml` (Postgres 16, API, web dev server),
  `Makefile` (`up`, `down`, `logs`, `test`, `lint`, `format`, `seed`,
  `e2e`), `.env.example`, `.gitignore`.
- `.github/workflows/ci.yml` running lint + typecheck + test for both apps.

**Deviations from the plan**

- Local dev machine has Python 3.13 installed, not 3.12 (no 3.12 available
  via the Windows `py` launcher on this machine). The API's `pyproject.toml`
  pins `requires-python = ">=3.12"` and the Dockerfile uses
  `python:3.12-slim`, so the deployed/CI target stays 3.12; local venvs on
  this machine run 3.13. Worth installing 3.12 locally before Phase 1 if
  strict version parity matters.
- `make` is not installed in the Git Bash environment used for local
  verification on this Windows machine, so Phase 0 was verified by running
  the underlying commands directly (`docker compose up --build -d`,
  `pytest`, `ruff`, `mypy`, `npm run lint/typecheck/test`) rather than via
  `make up` itself. `docker compose up --build -d` confirmed all three
  containers (`postgres`, `api`, `web`) start and `GET /health` and the
  Vite dev server both return 200. The Makefile targets are written for a
  standard `make`-equipped shell (CI, WSL, or Git Bash with `make`
  installed) — install `make` (or use WSL) to run `make up` literally on
  this machine.
- `apps/api/alembic/` exists as an empty directory (per the section 5
  layout) but has no `alembic.ini`/`env.py` yet — those land in Phase 1
  alongside the first migration. The API Dockerfile does not yet copy an
  `alembic/` directory for the same reason.

**Open questions for Phase 1**

- None yet — proceeding to Phase 1 (domain model, migrations, pick state
  machine) as planned.

## Phase 1 — Domain model, migrations, pick state machine (2026-09-18)

**Built**

- `apps/api/src/macenplast/domain/pick_machine.py`: the pure pick-line
  state machine (no DB/network calls) — states, events, effects, and
  `transition()`, per `PLAN.md` section 6.
- `apps/web/src/shared/pickMachine.ts`: identical semantics in TypeScript.
- `packages/machine-vectors/pick_line_transitions.json`: 28 shared test
  vectors covering every row of section 6's table, the 3-attempt override
  path for all three block types (location/SKU/quantity), all three
  `EXCEPTION` reasons, and `REPEAT` from five different states. Both
  `apps/api/tests/test_pick_machine_vectors.py` and
  `apps/web/src/shared/pickMachine.test.ts` load this same file.
- `apps/api/tests/test_pick_machine_properties.py`: Hypothesis
  property-based tests for the two invariants Phase 1's acceptance
  criteria call out — DONE is only reached with a matching quantity, and
  BLOCKED only advances via a correct scan or a logged override.
- `docs/adr/0002-pick-machine.md`: records two transitions `PLAN.md`
  section 6 leaves ambiguous (how BLOCKED recovers depending on what
  caused it; what BLOCKED-from-quantity-overage does next) and the
  resolution both implementations use.
- SQLAlchemy 2.0 models for every table in section 6
  (`apps/api/src/macenplast/db/models.py`), an Alembic migration
  environment wired to `Settings.database_url`
  (`apps/api/src/macenplast/db/session.py`, `apps/api/alembic/`), and the
  first migration (`80b43eafa829_initial_schema.py`), generated and
  applied against a real Postgres.
- `apps/api/src/macenplast/db/seed.py`: idempotent seed data (24
  locations across 3 aisles, 30 SKUs with barcodes and stock, 2 operators,
  1 device, 3 open orders with 5 lines each) using a `get_or_create`
  helper keyed on each table's natural unique key.
- `apps/api/tests/test_seed.py`: runs the seed script twice against a real
  Postgres and asserts row counts don't change; skips (doesn't fail) if no
  DB is reachable.
- CI (`.github/workflows/ci.yml`) now runs a Postgres 16 service for the
  API job and applies `alembic upgrade head` before `pytest`.
- The API's Dockerfile now runs `alembic upgrade head` before starting
  uvicorn, so `docker compose up` / `make up` always serves a migrated DB.

**Deviations from the plan**

- **Port conflict, not a plan deviation but worth recording prominently:**
  this dev machine runs three native Windows PostgreSQL services
  (`postgresql-x64-16/17/18`) already bound to ports 5432, 5433, *and*
  5434. `docker-compose.yml`'s `postgres` service now maps to host port
  **5442** instead of 5432 (container-internal port is still 5432, so the
  `api` container's `postgres:5432` connection inside the Docker network
  is unaffected). `apps/api/src/macenplast/config.py`'s default
  `DATABASE_URL` and `.env.example` were updated to match. If this repo
  moves to a machine without that conflict, 5432 would work fine, but
  there's no reason to change it back.
- The two state-machine ambiguities resolved in ADR 0002 (BLOCKED recovery
  depending on cause; BLOCKED-from-quantity-overage's next step) were
  decided directly rather than escalated, since they're implementation
  details of an already-agreed design, not product decisions. Flag if the
  Phase 7 pilot suggests operators expect different behavior.
- Enum columns (`role`, `mode`, `state`, `blocked_on`, `reason`, `status`)
  use SQLAlchemy's `Enum(..., native_enum=False)`, stored as `VARCHAR`
  with a check constraint, rather than native Postgres enum types — adding
  a new value later is a plain migration instead of `ALTER TYPE`.

**Open questions for Phase 2**

- None yet — proceeding to Phase 2 (`WmsPort`, mock/stub adapters, route
  planning) as planned. Phase 2 will need its own idempotency ledger
  (e.g. a `stock_movements` table) for `MockWmsAdapter.commit_pick` — not
  part of section 6's table list, so it's introduced there rather than
  here.

## Phase 2 — WMS port and route planning (2026-09-18)

**Built**

- `apps/api/src/macenplast/ports/wms_port.py`: the `WmsPort` ABC
  (`get_stock`, `reserve`, `commit_pick`, `release`) plus
  `InsufficientStockError`.
- `apps/api/src/macenplast/adapters/mock_wms.py`: Postgres-backed
  `MockWmsAdapter`. Added a `stock_movements` ledger table and a
  `reserved_qty` column on `stock_levels` (migration
  `a563f76c6c7e_wms_stock_movements_ledger.py`) — `reserve`/`commit_pick`/
  `release` are idempotent per `(movement_type, idempotency_key)`, backed
  by a real unique constraint, not just an in-app check.
- `apps/api/src/macenplast/adapters/rest_wms.py`: `RestWmsAdapter` stub —
  every method raises `NotImplementedError` with a docstring listing what
  Macenplast needs to confirm (base URL, auth, endpoint shapes,
  idempotency handling) before it can be implemented for real.
- `apps/api/src/macenplast/domain/routing.py`: pure `plan_route()` —
  default serpentine (S-shape) heuristic with a documented tie-break
  (level, then id), and an optional `or_tools` strategy (exact/near-exact
  TSP via Google OR-Tools) behind the optional `routing` extra
  (`pip install ".[routing]"`); raises a clear `RuntimeError` if selected
  without the dependency installed.
- Tests: `test_mock_wms.py` (idempotent reserve/commit/release,
  insufficient-stock errors, available-vs-on-hand distinction),
  `test_rest_wms.py` (every method raises), `test_routing.py`
  (single-aisle, multi-aisle zigzag, tie-break, unknown-strategy error,
  or-tools path skipped when the extra isn't installed, and a
  deterministic test of the "dependency missing" error message via
  `monkeypatch` on `__import__` rather than requiring an uninstalled
  package).

**Deviations from the plan**

- `ortools` is an optional extra (`routing`), not a base dependency —
  `PLAN.md` section 3 calls the OR-Tools mode "optional... for larger
  orders," so it isn't installed by default; CI and local dev run without
  it, and `test_or_tools_strategy_visits_every_location` is skipped
  (`pytest.importorskip`) rather than failing when it's absent.
- `WmsPort.reserve`/`release` (not just `commit_pick`) required adding
  `reserved_qty` to `stock_levels` — section 6 didn't list it, but the
  reserve/commit split described by the port's method names
  (`PLAN.md` section 3) needs somewhere to track "allocated but not yet
  picked" stock separately from on-hand.

**Open questions for Phase 3**

- None yet — proceeding to Phase 3 (voice service and clip pipeline) as
  planned.

## Phase 3 — Voice service and clip pipeline (2026-09-18)

**Built**

- `apps/api/src/macenplast/domain/numbers_es.py`: pure Spanish
  number-to-speech, 0-999, nominal form only (per section 6's
  phrase-writing rule). Hypothesis property tests plus a full-range
  uniqueness check and hand-checked known values (`ciento uno` vs `cien`,
  accented `dieciséis`/`veintidós`, etc.).
- `apps/api/src/macenplast/voice/phrases.es.yaml` +
  `apps/api/src/macenplast/voice/phrases.py`: the Spanish phrase catalog,
  keyed exactly by the phrase strings the pick machine's `Speak`/
  `PlayAlert` effects already carry (`INSTRUCTION`, `LOCATION_CORRECT`,
  `QTY_PROMPT`, `CORRECT`, `CALL_SUPERVISOR`, `ASK_CONFIRM_SHORT`,
  `MISMATCH`). `render_phrase()` converts any integer argument to its
  spoken word via `numbers_es` automatically, so no caller ever formats a
  number itself.
- `docs/adr/0003-elevenlabs-tts.md`: records what was verified against
  ElevenLabs' current docs (package, client, method signature, return
  type, endpoint, output formats) before writing the wrapper, per
  `CLAUDE.md`'s rule.
- `apps/api/src/macenplast/voice/tts.py`: `synthesize()` wraps
  `elevenlabs.client.ElevenLabs().text_to_speech.convert(...)`, always
  passing `model_id`/`api_key` explicitly (never relying on SDK/env
  defaults). Mocked in `tests/test_tts.py`; `tests/test_tts_live.py` is
  the real-API smoke test, marked `@pytest.mark.live` and skipped by
  default.
- `apps/api/src/macenplast/voice/clip_cache.py`: `get_or_synthesize()` —
  content-hash-keyed cache (`voice_clips` DB row, audio bytes stored in
  the row itself — no local disk, so this also works on Vercel's
  ephemeral filesystem). Hash covers `(text, voice_id, model_id,
  output_format)`.
- `tools/voice-clips/build_static_clips.py`: builds numbers 0-999, the 4
  fixed phrases, every SKU's `voice_alias`, and INSTRUCTION/QTY_PROMPT for
  every currently-PENDING pick line — everything a demo run through the
  seeded warehouse needs. Deliberately does not pre-build
  `ASK_CONFIRM_SHORT` (the shortage quantity isn't known ahead of time —
  documented in the script's own docstring as an intentional, not missed,
  dynamic case).
- `apps/api/src/macenplast/api/voice.py` (+ `api/schemas/voice.py`): three
  endpoints — `GET /voice/skus/{sku_id}/clip` (the dynamic per-SKU clip),
  `GET /voice/orders/{order_id}/manifest` (dedup'd list of every clip a
  device needs for an order, synthesizing anything missing), and `GET
  /voice/clips/{content_hash}` (serves the audio file). Wired into
  `main.py`.

**Deviations from the plan**

- The plan's "static clip library (numbers, commands, alerts)" vs.
  "dynamic per-SKU clips" split is about *when* something is generated
  (build time vs. first use), not a hard rule about content. Rather than
  composing spoken instructions from concatenated word-level clips at
  playback time (which would let "Pasillo", "Estante", numbers, etc. be
  pure static fragments reused across every line), this phase synthesizes
  each full rendered sentence (`INSTRUCTION`, `QTY_PROMPT`) as one clip,
  cached by its complete text's content hash. Simpler to build and test
  now; clip-sequence playback is a Phase 5 (`ClipPlayer`) concern and can
  be revisited later without changing this phase's cache/manifest
  contracts either way.
- `build_static_clips.py` pre-warms INSTRUCTION/QTY_PROMPT for
  *currently-PENDING* pick lines specifically (not a content-agnostic
  "static" set), so Phase 3's acceptance criterion ("produces every clip
  needed for a full seeded order with zero dynamic-clip fallbacks at
  runtime") is testable against real seeded data. `test_build_static_clips.py`
  checks this the robust way — running the build twice makes zero
  synthesis calls the second time — rather than asserting a call count
  tied to a "fresh" cache, since tests share a persistent dev Postgres
  across runs.
- Voice endpoints landed in Phase 3, not Phase 4, because Phase 3's own
  deliverables explicitly call for a dynamic-clip endpoint and a voice
  manifest response. They use `PickOrder`/`PickLine` directly rather than
  waiting for Phase 4's orders router.

**Open questions for Phase 4**

- None yet — proceeding to Phase 4 (backend API: auth, sessions, orders,
  events, incidents, override, SSE) as planned.

## Phase 4 — Backend API (2026-09-18)

**Built**

- `apps/api/src/macenplast/security.py`: PIN hashing (sha256 placeholder,
  same as Phase 1's seed script — now shared, not duplicated) and JWT
  access tokens (`create_access_token`/`decode_access_token`), signed with
  `Settings.secret_key` (an intentionally-insecure default that every
  non-dev deployment must override — a Phase 9 hardening item).
- `apps/api/src/macenplast/api/deps.py`: `get_current_operator` and
  `require_role(...)` (role-based access — an addition beyond the source
  document, per section 1 — plus `require_supervisor`, a predefined
  dependency singleton).
- Routers, wired into `main.py`: `auth` (PIN login), `sessions`
  (start/end), `orders` (`assign` — computes the route via Phase 2's
  `plan_route` and reserves stock via `MockWmsAdapter`; `next-line` —
  drives the `PRESENT` transition and renders the instruction), `events`
  (`POST /events` and `/events/batch` — the core: loads a line's state,
  calls `pick_machine.transition`, persists the result, executes effects
  against the WMS/incidents, records an append-only `PickEvent`, publishes
  to the SSE broadcaster; idempotent on `client_event_id`), `incidents`
  (list/resolve), `reports` (minimal per-session summary — see scope note
  below), and `sse` (`GET /dashboard/stream`).
- `apps/api/src/macenplast/domain/pick_machine_json.py`: JSON
  (de)serialization for pick machine types, factored out of
  `test_pick_machine_vectors.py` so the API layer and the tests share one
  conversion instead of duplicating it.
- `apps/api/scripts/export_openapi.py` + committed `apps/api/openapi.json`
  + a CI step (`--check`) that fails the build if it's stale — what Phase
  5 codegens a client against.
- Integration tests: `test_api_full_flow.py` drives a full order through
  the real API — login, start session, assign (reserve stock), next-line,
  three wrong location scans (BLOCKED, BLOCKED, escalate to
  NEEDS_OVERRIDE), a rejected self-override, a supervisor override, a
  qty confirmation to DONE, and a check that stock was committed exactly
  once even after replaying the same `client_event_id`. `test_api_sse.py`
  covers the SSE stream (see deviation below). `test_api_voice.py` from
  Phase 3 needed no changes.

**Deviations from the plan**

- **`GET /dashboard/stream` cannot be tested with `TestClient` or
  `httpx.AsyncClient(transport=ASGITransport(...))` at all** — both fully
  buffer the ASGI response body before returning anything, so a stream
  that (by design) never terminates on its own just hangs forever. This
  is a documented `httpx`/`ASGITransport` limitation, unrelated to
  `sse-starlette` or this app (confirmed by reproducing it in isolation
  before concluding it wasn't a code bug). `test_api_sse.py` instead
  spins up a real Uvicorn server on a background thread and talks to it
  over an actual socket, which streams incrementally like any real HTTP
  server. That also sidesteps a second, related hazard:
  `Broadcaster.publish()`'s `asyncio.Queue.put_nowait()` isn't safe to
  call across threads/event loops — the test triggers it by making a real
  `/events` request (so the publish call runs on the live server's own
  event loop, same as in production), not by calling `broadcaster.publish`
  directly from the test.
- `macenplast.api.reports` is intentionally minimal (lines completed,
  mismatch count, incident count per session) — full KPI reporting
  (lines/hour, BASELINE vs. VOICE comparison, idle time) is explicitly
  Phase 6's job per `PLAN.md`, and Phase 6 is outside this build's chosen
  MVP scope (Phases 0-5).
- `Location.aisle`/`bay`/`level` values are spoken via templated
  formatting, not stored as a general n-ary location tree — a location
  "aisle" is treated as a letter spoken literally and "bay"/"level" as
  numbers rendered through `numbers_es`. This matches the seeded schema
  and is easy to extend if a real warehouse's location codes need
  different handling.
- Fixed a latent fragility in `db/seed.py`'s `seed_orders`: it previously
  derived a pick line's location from
  `(order_num * LINES_PER_ORDER + line_num) % len(locations)`, independent
  of the index `seed_stock()` used to decide *which* location actually
  holds that SKU's stock. For the current seed parameters (3 orders x 5
  lines, well under both list lengths) the two formulas happened to agree,
  but that was incidental. Fixed to derive the location from the same SKU
  index `seed_stock()` uses, so a pick line's location is guaranteed to be
  where its SKU's stock actually is, regardless of future `SKU_COUNT`/
  `ORDER_COUNT` changes.

**Open questions for Phase 5**

- None yet — proceeding to Phase 5 (operator PWA: core voice-picking flow)
  as planned.

## Phase 5 — Operator PWA, core voice-picking flow (2026-09-18)

**Built**

- Two small Phase-4-router additions the offline PWA needs and didn't yet
  have: `GET /orders/pending` (orders an operator can pick up) and `GET
  /orders/{id}/lines` (every line's full detail, including expected
  barcodes — what the offline client caches once, while online, so the
  rest of picking needs zero round-trips) plus `GET /devices` (device
  picker at shift start). CORS middleware, also new — the PWA (port 5173)
  and API (port 8000) are different origins in dev.
- `apps/web/src/shared/`: `numbersEs.ts` and `phrases.ts`, hand-ported
  from the Python modules (needed for the `speechSynthesis` fallback to
  render text locally); `apiClient.ts` + `apiTypes.ts`, a typed fetch
  wrapper for every endpoint the PWA calls while online.
- `apps/web/src/operator/`:
  - `db.ts` — Dexie (IndexedDB): cached order lines, an event outbox
    (client-generated idempotency keys), and current app/session state.
  - `outbox.ts` — queues every local pick-machine transition and flushes
    it to `/events/batch` when online; single-flight guarded (see
    deviation below).
  - `clipPlayer.ts` — plays clips from Cache Storage (prefetched from the
    voice manifest at shift start), falling back to `speechSynthesis`;
    `unlock()` runs inside the "Start shift" tap to satisfy the
    autoplay-after-gesture browser policy (section 4's constraint).
  - `useScannerInput.ts` — keyboard-wedge detection by keystroke timing,
    with plain typing as the always-available fallback (see deviation:
    camera scanning is out of scope for this pass).
  - `baselineMode.ts` — BASELINE's non-blocking wrapper around the shared
    `transition()` (see deviation below).
  - `ShiftStart.tsx`, `PickingScreen.tsx`, `OperatorApp.tsx` — login, mode
    + order selection, shift start (unlocks audio, requests a Wake Lock,
    caches lines + voice manifest), and the picking flow itself, entirely
    driven by the shared TypeScript `pickMachine`.
- `public/sw.js` — a small hand-written service worker precaching the app
  shell (not a bundled/Workbox setup — see deviation); `public/manifest.webmanifest`
  for installability.
- `apps/api/scripts/create_test_order.py` + `apps/web/e2e/global-setup.ts`
  + `apps/web/e2e/offline-sync.spec.ts` (Playwright, real Chromium): logs
  in, starts a BASELINE shift, goes offline
  (`context.setOffline(true)`), completes one line and scans most of a
  second fully offline, confirms the outbox has queued events, reconnects,
  confirms the outbox drains to zero with no user action, finishes the
  order, and verifies via a direct API call that both lines report `DONE`
  server-side — the phase's required acceptance test.

**Deviations from the plan**

- **Camera/BarcodeDetector scanning is out of scope for this pass** — the
  human confirmed this scoping call directly (see the conversation).
  Keyboard-wedge (real hardware scanner) plus plain typing (the
  "lost/broken scanner" fallback) are both implemented and tested;
  BarcodeDetector/ZXing camera input isn't, since it can't be verified in
  this environment (no camera, headless CI) and would be unverified code.
  Flag before a pilot if a camera fallback turns out to matter in
  practice.
- **Supervisor override requires connectivity** — clearing a
  NEEDS_OVERRIDE line calls `/events` with a supervisor's own token
  (obtained via a fresh, separate login), not through the offline outbox.
  This isn't a corner cut so much as what override *means*: verifying a
  supervisor's identity inherently requires checking the server, so an
  override occurring while fully offline isn't something the current
  design (or the plan) specifies a resolution for. The e2e test avoids
  triggering NEEDS_OVERRIDE, staying on the golden path plus one
  in-progress line, which is what the acceptance criterion asks for.
- **A real concurrency bug surfaced and got fixed on both sides**: queuing
  many events in quick succession (a full pick line: PRESENT + 2 SCANs +
  QTY) fired overlapping `syncOutbox()` calls, which raced the server's
  idempotency check against its own insert and surfaced as a raw
  `UniqueViolation` on `client_event_id` instead of a clean no-op. Fixed
  with a single-flight guard in `outbox.ts` (concurrent callers await the
  same in-flight sync) and, for defense in depth against genuinely
  concurrent clients (two tabs, two devices), a catch in
  `macenplast.api.events.apply_event` that treats a unique-constraint
  violation on commit as "the other request already applied this" and
  returns its cached result instead of raising.
- **BASELINE mode's "don't block on a mismatch" rule lives in
  `operator/baselineMode.ts`, not in the shared `pickMachine`** —
  intentional, not a shortcut: VOICE mode's blocking behavior is the
  audited Poka-Yoke contract the shared cross-language test vectors pin
  down, and BASELINE's override is a presentation-layer policy on top of
  the same machine. `baselineMode.ts` re-runs `transition()` as if the
  scan/qty had matched whenever the real result would have been
  BLOCKED/NEEDS_OVERRIDE, tagging the outcome with a `MISMATCH_UNBLOCKED`
  alert. Has its own Vitest suite (`baselineMode.test.ts`), separate from
  `pickMachine.test.ts`'s shared vectors.
- **Correction to the above, found live-testing the Vercel deployment**:
  the offline PWA queues the *actual* mismatched event for the audit
  trail (not a synthesized "corrected" one), and that event gets replayed
  server-side by `macenplast.api.events.apply_event` — which had no idea
  the session was BASELINE and always ran the strict, blocking
  `transition()`. A wrong location scan pushed the server's copy of the
  line into BLOCKED while the client had already moved on; the next
  queued event (a QTY submission, a different event type than what
  BLOCKED(LOCATION) accepts) then 500'd with `InvalidTransitionError` —
  and since `submit_event_batch` didn't catch that exception, the crash
  killed the whole batch response, so the offline outbox retried the same
  poisoned event forever ("Pendientes por sincronizar" stuck non-zero).
  Fixed by porting `baselineMode.ts` to Python
  (`macenplast.domain.baseline_mode.apply_baseline_event`), used whenever
  `apply_event` finds the session's `mode` is BASELINE, plus catching
  `InvalidTransitionError` in both event endpoints so one bad event can't
  crash a whole batch regardless of mode. `PLAN.md`'s original framing —
  "presentation-layer policy on top of the same machine" — was right
  about the pick machine itself, just wrong about which layers need it:
  both the client's local state AND the server's authoritative replay are
  presentation over the same machine. Regression-tested through the real
  `/events/batch` endpoint (`test_baseline_mode_mismatches_never_block_the_server_either`),
  not just the ported function in isolation — a wiring mistake in
  `events.py` wouldn't have shown up in a unit test of
  `baseline_mode.py` alone.
- **The `INSTRUCTION` effect's args are assembled by the caller, not
  taken from the pick-machine effect itself** — `PickContext` has no
  aisle/bay/level/reference (only barcodes and quantity), so
  `Speak('INSTRUCTION')` carries no args from the pure machine by design.
  `PickingScreen.tsx` fills them in from the cached line, exactly the
  same way `apps/api/src/macenplast/api/orders.py`'s `next-line` endpoint
  already did server-side. Found via the e2e test failing with "Missing
  arg 'aisle'" — a good example of why an actual browser-driven e2e test
  earns its keep over unit tests alone.
- **Service worker is a hand-written plain-JS file in `public/`**, not a
  Vite-bundled TypeScript module (which would need a second Rollup build
  entry) or `vite-plugin-pwa` (a heavier dependency+config surface than
  this phase needs). It precaches the app shell only; voice clips are
  cached directly by the page via the Cache Storage API
  (`operator/clipPlayer.ts`), which doesn't need the service worker's
  involvement at all.
- **Reports/KPI comparisons stay out of scope** (Phase 6, per the chosen
  MVP boundary) — the mode indicator and BASELINE's non-blocking mismatch
  logging exist so Phase 6 has something to report on later, not to
  report on themselves yet.
- Playwright's `webServer` needed `--host 127.0.0.1` for the Vite dev
  server explicitly: this machine's Vite 8 binds `localhost` to IPv6
  loopback (`::1`) only, so a health check against `127.0.0.1:5173`
  (IPv4) failed until the host was pinned explicitly — worth knowing if
  `make e2e`/CI ever mysteriously times out waiting for the dev server.

**Open questions for later phases**

- Device selection at shift start always picks the first active device —
  fine for the single seeded demo device, but a real deployment with
  multiple handhelds needs an actual picker (scan the device's own
  barcode, most likely). Flag before a multi-device pilot.
- The manual scanner-input fallback and the two exception buttons
  (empty location / damaged) are present but not e2e-tested — the e2e
  suite only covers the golden path plus one in-progress line, per the
  acceptance criterion's wording. Worth a follow-up test if exception
  handling becomes pilot-critical.
- This is the last phase in the chosen MVP scope (Phases 0-5). Phases 6-9
  (supervisor dashboard/KPI reporting, pilot protocol, feature-flagged
  voice input, production hardening) remain per `PLAN.md`, to be picked up
  as separate sessions per the plan's own phase-by-phase workflow.
