"""Runs `tools/voice-clips/build_static_clips.py` end-to-end against the
seeded warehouse (TTS mocked) and checks Phase 3's acceptance criterion:
after the build, every clip a pending seeded pick line needs is already
cached — rendering it again is a pure cache hit, not a new synthesis call.

Requires a reachable Postgres; skips otherwise (see test_seed.py).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

from macenplast.db.models import Location, PickLine, PickOrder, Sku
from macenplast.db.session import SessionLocal
from macenplast.domain.pick_machine import PickState
from macenplast.voice.phrases import render_phrase

SCRIPT_PATH = (
    Path(__file__).resolve().parents[3] / "tools" / "voice-clips" / "build_static_clips.py"
)


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_static_clips", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@patch("macenplast.voice.clip_cache.synthesize")
def test_build_static_clips_is_idempotent_and_fully_warms_the_cache(
    mock_synthesize: MagicMock, seeded_db: None
) -> None:
    """Running the build twice must make zero synthesis calls the second
    time — that's what "zero dynamic-clip fallbacks at runtime" means:
    once built, nothing about the seeded warehouse needs a fresh call.

    (This intentionally doesn't assert on the *first* run's call count:
    the fixture reuses a persistent dev DB across test sessions, so a
    prior run may have already warmed some or all of the cache.)
    """
    mock_synthesize.return_value = b"fake-audio-bytes"
    module = _load_script_module()

    module.main()
    mock_synthesize.reset_mock()

    module.main()

    mock_synthesize.assert_not_called()

    with SessionLocal() as session:
        sku_count = session.query(Sku).count()
        pending_line_count = (
            session.query(PickLine).filter(PickLine.state == PickState.PENDING).count()
        )
    assert sku_count >= 30
    assert pending_line_count >= 1


@patch("macenplast.voice.clip_cache.synthesize")
def test_after_build_a_pending_lines_instruction_is_a_cache_hit(
    mock_synthesize: MagicMock, seeded_db: None
) -> None:
    mock_synthesize.return_value = b"fake-audio-bytes"

    module = _load_script_module()
    module.main()
    mock_synthesize.reset_mock()

    from macenplast.voice.clip_cache import get_or_synthesize

    with SessionLocal() as session:
        line = (
            session.query(PickLine)
            .join(PickOrder, PickLine.order_id == PickOrder.id)
            .filter(PickLine.state == PickState.PENDING)
            .first()
        )
        assert line is not None
        location = session.get(Location, line.location_id)
        sku = session.get(Sku, line.sku_id)
        assert location is not None and sku is not None

        text = render_phrase(
            "INSTRUCTION",
            aisle=location.aisle,
            bay=int(location.bay),
            level=int(location.level),
            reference=sku.voice_alias or sku.description,
            quantity=line.expected_qty,
        )
        get_or_synthesize(session, text, voice_id=module.get_settings().elevenlabs_voice_id)

    mock_synthesize.assert_not_called()
