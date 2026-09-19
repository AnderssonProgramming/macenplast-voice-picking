"""Tests for the content-hash clip cache. TTS is always mocked; requires a
reachable Postgres for the DB row (skips otherwise, see test_seed.py)."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from macenplast.db.base import Base
from macenplast.db.session import SessionLocal, engine
from macenplast.voice.clip_cache import content_hash, get_or_synthesize


@pytest.fixture
def db() -> Iterator[Session]:
    try:
        with engine.connect():
            pass
    except OperationalError:
        pytest.skip("Postgres not reachable; start it with `docker compose up -d postgres`")

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_content_hash_differs_by_voice_and_format() -> None:
    a = content_hash("Correcto.", "voice-1", "eleven_flash_v2_5", "mp3_44100_128")
    b = content_hash("Correcto.", "voice-2", "eleven_flash_v2_5", "mp3_44100_128")
    c = content_hash("Correcto.", "voice-1", "eleven_flash_v2_5", "wav_44100")
    assert len({a, b, c}) == 3


@patch("macenplast.voice.clip_cache.synthesize")
def test_first_request_synthesizes_and_stores_audio(
    mock_synthesize: MagicMock, db: Session
) -> None:
    mock_synthesize.return_value = b"fake-audio-bytes"

    clip = get_or_synthesize(db, "Correcto.", voice_id="voice-1")

    mock_synthesize.assert_called_once()
    assert clip.audio_data == b"fake-audio-bytes"


@patch("macenplast.voice.clip_cache.synthesize")
def test_second_request_is_a_cache_hit(mock_synthesize: MagicMock, db: Session) -> None:
    mock_synthesize.return_value = b"fake-audio-bytes"

    first = get_or_synthesize(db, "Correcto.", voice_id="voice-1")
    second = get_or_synthesize(db, "Correcto.", voice_id="voice-1")

    mock_synthesize.assert_called_once()
    assert first.id == second.id
    assert first.content_hash == second.content_hash


@patch("macenplast.voice.clip_cache.synthesize")
def test_different_text_is_a_different_clip(mock_synthesize: MagicMock, db: Session) -> None:
    mock_synthesize.return_value = b"fake-audio-bytes"

    first = get_or_synthesize(db, "Correcto.", voice_id="voice-1")
    second = get_or_synthesize(db, "Incorrecto.", voice_id="voice-1")

    assert mock_synthesize.call_count == 2
    assert first.content_hash != second.content_hash
