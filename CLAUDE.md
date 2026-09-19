# Project rules — Macenplast Voice Picking

Generated from `PLAN.md` section 2. This file is the source of truth for how
Claude Code (and anyone else) should work in this repository. If `PLAN.md`
section 2 changes, regenerate this file to match.

## Language

- Code, comments, commit messages, README, ADRs: English.
- Everything the operator hears or reads on screen: Spanish (Colombia), kept
  in catalog files (`phrases.es.yaml`, `i18n/es.json`) — never hard-coded
  inside logic.

## Python

- 3.12, `src/` layout, `pathlib` for all paths, PEP 8 via ruff, full type
  hints checked by mypy strict, Google-style docstrings, pytest (hypothesis
  for property-based tests on the state machine and number-to-speech logic).

## TypeScript

- Strict mode, ESLint + Prettier, Vitest for unit tests, Playwright for e2e.

## Repo

- Conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`), small
  commits, one branch per phase (`phase/03-voice-service`), merged to `main`
  via PR.
- Mermaid diagrams in the README.
- GitHub Actions CI.
- SonarCloud config can go in during Phase 0 but should never block a build.

## Working rules for Claude Code

- Tests first for anything with logic (state machine, routing,
  number-to-speech, offline sync). Implementation after.
- Never call the live ElevenLabs API from automated tests — mock it. Live
  smoke tests are marked `@pytest.mark.live` and skipped by default.
- Never commit secrets. `.env` is git-ignored; `.env.example` is committed.
- The ElevenLabs API key lives only on the backend. The browser never sees
  it — client-side STT uses a short-lived token minted by the backend, not
  the key itself.
- Don't persist operator audio. Only parsed commands and transcripts of
  committed voice commands are stored, and only when voice input (Phase 8)
  is enabled.
- Before coding against ElevenLabs, verify current model IDs, endpoints, and
  output formats against their docs — names in `PLAN.md` were correct when
  written and may have moved since.
- Definition of done for every phase: lint, type check, and tests pass;
  every acceptance criterion in that phase is demonstrably met; the README
  gets a short update; `docs/PROGRESS.md` gets an entry (what was built,
  deviations from this plan, open questions for the next phase).

## How to use PLAN.md

1. Work one phase per Claude Code session: start in plan mode, review the
   plan, approve, build, verify against that phase's acceptance criteria,
   then `/clear` before starting the next phase.
2. Don't skip or reorder phases; each one lists what it depends on.
3. When a decision in `PLAN.md` section 3 seems wrong, stop, ask, and record
   the resolution as an ADR in `docs/adr/`.
