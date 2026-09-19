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
