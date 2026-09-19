# ADR 0004 — Default voice ID changed off "Rachel": paid-plan-gated

- Status: Accepted
- Date: 2026-09-19

## Context

The Vercel MVP deployment returned `500` on every voice-manifest/clip
request. Backend logs showed the real cause was ElevenLabs itself:

```
402 Payment Required
{"detail": {"type": "payment_required", "code": "paid_plan_required",
 "message": "Free users cannot use library voices via the API. Please
 upgrade your subscription to use this voice."}}
```

This was reproduced locally too (same key, same result), which ruled out
anything Vercel-specific and pointed at the ElevenLabs account/voice
combination. `elevenlabs_voice_id`'s default, `21m00Tcm4TlvDq8ikWAM`
("Rachel"), was chosen ad hoc during Phase 3 as a well-known public
placeholder — it was never validated against a real account, since Phase 3
tests always mock `synthesize()` (per `CLAUDE.md`'s rule never to call the
live API from automated tests).

## What was confirmed

Against the project's real (free-tier) ElevenLabs key:

- `GET /v1/user/subscription` → `tier: "free"`,
  `can_use_instant_voice_cloning: false` — confirms the account has no paid
  plan and can't clone its own voice as an alternative.
- `POST /v1/text-to-speech/21m00Tcm4TlvDq8ikWAM` (Rachel) → `402`, the
  payment-required error above.
- `POST /v1/text-to-speech/hpp4J3VqNfWAUOO0d1Us` (Bella, also a premade/
  library voice per `GET /v2/voices`) → `200`, real audio bytes returned.

So the 402 is not "free accounts can never use library voices via the
API" as the error message's wording implies — it's specific to which
library voice is requested. Rachel is evidently one ElevenLabs has since
gated; Bella (and presumably others) are not. This can change again
without notice, which is exactly the risk `CLAUDE.md`'s "verify before
coding against ElevenLabs" rule is for.

## Decision

- `Settings.elevenlabs_voice_id`'s default becomes `hpp4J3VqNfWAUOO0d1Us`
  ("Bella"), verified working end-to-end (`synthesize()` → real MP3 bytes)
  against the project's actual key.
- `tests/test_tts_live.py` now synthesizes with
  `get_settings().elevenlabs_voice_id` instead of a hardcoded voice ID, so
  it always tests whatever voice the deployment is actually configured
  for, rather than a value that can silently drift from `config.py`.
- `.env.example` and this ADR both flag Rachel as a known-bad default so a
  future reader doesn't reintroduce it.

## Consequences

- Still just a placeholder voice — Macenplast picking/cloning a real voice
  (Phase 6+ concern) replaces this default regardless.
- Voice-gating policy is ElevenLabs' to change again; if `hpp4J3VqNfWAUOO0d1Us`
  ever starts 402ing too, re-run the same `GET /v1/user/subscription` +
  per-voice `POST /v1/text-to-speech/{id}` check against `GET /v2/voices`'
  list before picking a replacement, rather than guessing.
