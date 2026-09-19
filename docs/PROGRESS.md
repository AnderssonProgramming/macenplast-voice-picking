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
