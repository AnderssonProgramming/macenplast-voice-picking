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
  content-hash-keyed cache (`voice_clips` DB row + file under
  `VOICE_CLIP_DIR`). Hash covers `(text, voice_id, model_id,
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
