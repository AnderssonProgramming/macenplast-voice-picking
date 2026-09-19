#!/usr/bin/env python
"""Pre-synthesizes the voice clips needed to run the current seeded
warehouse with zero dynamic-clip fallbacks at pick time.

Run with the API's virtualenv active (it needs the `macenplast` package
and a reachable Postgres + `ELEVENLABS_API_KEY`):

    cd apps/api && python ../../tools/voice-clips/build_static_clips.py

Safe to re-run — `macenplast.voice.clip_cache.get_or_synthesize` is
idempotent by content hash, so a second run only fills in anything new
(e.g. a SKU or pick line added since the last run).

What this builds:

1. Every spoken number 0-999 (`macenplast.domain.numbers_es`) — the
   bounded, reusable vocabulary described in ADR 0001's "Audio strategy"
   row as the "static clip library".
2. Every fixed (no-placeholder) phrase in the catalog: LOCATION_CORRECT,
   CORRECT, CALL_SUPERVISOR, MISMATCH.
3. Every SKU's `voice_alias` (falling back to `description`) — ADR 0001's
   "dynamic per-SKU clips", pre-warmed here rather than left to first use,
   so a demo/pilot run never hits the dynamic path.
4. The INSTRUCTION and QTY_PROMPT phrases for every currently-PENDING
   pick line, using that line's actual location/SKU/quantity.

What this deliberately does NOT pre-build: ASK_CONFIRM_SHORT, because the
shortage quantity it speaks isn't known until an operator actually reports
one. That's the one phrase this system still expects to synthesize
dynamically (or fall back to `speechSynthesis`, per ADR 0001) — by design,
not an oversight.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from macenplast.config import get_settings
from macenplast.db.models import PickLine, PickOrder, Sku
from macenplast.db.session import SessionLocal
from macenplast.domain.numbers_es import MAX_SUPPORTED, MIN_SUPPORTED, number_to_es
from macenplast.domain.pick_machine import PickState
from macenplast.voice.clip_cache import get_or_synthesize
from macenplast.voice.phrases import render_phrase

FIXED_PHRASES = ("LOCATION_CORRECT", "CORRECT", "CALL_SUPERVISOR", "MISMATCH")


def build_numbers(session: Session, voice_id: str) -> int:
    count = 0
    for n in range(MIN_SUPPORTED, MAX_SUPPORTED + 1):
        get_or_synthesize(session, number_to_es(n), voice_id=voice_id)
        count += 1
    return count


def build_fixed_phrases(session: Session, voice_id: str) -> int:
    for key in FIXED_PHRASES:
        get_or_synthesize(session, render_phrase(key), voice_id=voice_id)
    return len(FIXED_PHRASES)


def build_sku_aliases(session: Session, voice_id: str) -> int:
    skus = session.query(Sku).all()
    for sku in skus:
        text = sku.voice_alias or sku.description
        get_or_synthesize(session, text, voice_id=voice_id)
    return len(skus)


def build_pending_line_instructions(session: Session, voice_id: str) -> int:
    lines = (
        session.query(PickLine)
        .join(PickOrder, PickLine.order_id == PickOrder.id)
        .filter(PickLine.state == PickState.PENDING)
        .all()
    )
    for line in lines:
        location = line.location
        sku = line.sku
        get_or_synthesize(
            session,
            render_phrase(
                "INSTRUCTION",
                aisle=location.aisle,
                bay=int(location.bay),
                level=int(location.level),
                reference=sku.voice_alias or sku.description,
                quantity=line.expected_qty,
            ),
            voice_id=voice_id,
        )
        get_or_synthesize(
            session,
            render_phrase("QTY_PROMPT", quantity=line.expected_qty),
            voice_id=voice_id,
        )
    return len(lines)


def main() -> None:
    voice_id = get_settings().elevenlabs_voice_id
    with SessionLocal() as session:
        numbers = build_numbers(session, voice_id)
        fixed = build_fixed_phrases(session, voice_id)
        skus = build_sku_aliases(session, voice_id)
        lines = build_pending_line_instructions(session, voice_id)
        session.commit()

    print(f"Numbers: {numbers}")
    print(f"Fixed phrases: {fixed}")
    print(f"SKU aliases: {skus}")
    print(f"Pending pick lines (INSTRUCTION + QTY_PROMPT): {lines}")


if __name__ == "__main__":
    main()
