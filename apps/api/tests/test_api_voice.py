"""Integration tests for the voice API router (dynamic SKU clip, manifest,
and clip audio serving). TTS is mocked; requires a reachable Postgres."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from macenplast.db import seed
from macenplast.db.base import Base
from macenplast.db.models import PickLine, PickOrder, Sku
from macenplast.db.session import SessionLocal, engine
from macenplast.main import app

client = TestClient(app)


@pytest.fixture
def seeded_db() -> Iterator[None]:
    try:
        with engine.connect():
            pass
    except OperationalError:
        pytest.skip("Postgres not reachable; start it with `docker compose up -d postgres`")

    Base.metadata.create_all(bind=engine)
    seed.main()
    yield


@pytest.fixture
def mock_tts() -> Iterator[MagicMock]:
    with patch("macenplast.voice.clip_cache.synthesize") as mock_synthesize:
        mock_synthesize.return_value = b"fake-audio-bytes"
        yield mock_synthesize


def test_sku_clip_returns_descriptor_and_is_cached_on_second_call(
    seeded_db: None, mock_tts: MagicMock
) -> None:
    with SessionLocal() as session:
        sku = session.query(Sku).first()
        assert sku is not None
        sku_id = sku.id

    first = client.get(f"/voice/skus/{sku_id}/clip")
    assert first.status_code == 200
    body = first.json()
    assert body["content_hash"]
    assert body["url"] == f"/voice/clips/{body['content_hash']}"

    calls_after_first = mock_tts.call_count

    second = client.get(f"/voice/skus/{sku_id}/clip")
    assert second.status_code == 200
    assert second.json()["content_hash"] == body["content_hash"]
    assert mock_tts.call_count == calls_after_first


def test_sku_clip_404_for_unknown_sku(seeded_db: None, mock_tts: MagicMock) -> None:
    response = client.get(f"/voice/skus/{uuid.uuid4()}/clip")
    assert response.status_code == 404


def test_clip_audio_is_served(seeded_db: None, mock_tts: MagicMock) -> None:
    with SessionLocal() as session:
        sku = session.query(Sku).first()
        assert sku is not None
        sku_id = sku.id

    descriptor = client.get(f"/voice/skus/{sku_id}/clip").json()

    audio_response = client.get(descriptor["url"])

    assert audio_response.status_code == 200
    assert audio_response.content == b"fake-audio-bytes"
    assert audio_response.headers["content-type"].startswith("audio/")


def test_clip_audio_404_for_unknown_hash(seeded_db: None, mock_tts: MagicMock) -> None:
    response = client.get("/voice/clips/does-not-exist")
    assert response.status_code == 404


def test_voice_manifest_covers_fixed_phrases_and_pending_lines(
    seeded_db: None, mock_tts: MagicMock
) -> None:
    with SessionLocal() as session:
        order = session.query(PickOrder).first()
        assert order is not None
        order_id = order.id
        pending_line_count = session.query(PickLine).filter(PickLine.order_id == order_id).count()

    response = client.get(f"/voice/orders/{order_id}/manifest")

    assert response.status_code == 200
    body = response.json()
    assert body["order_id"] == str(order_id)
    # 4 fixed phrases + (INSTRUCTION, QTY_PROMPT) per line, deduplicated
    # by content hash — so this is an upper bound, not an exact count.
    assert len(body["clips"]) <= 4 + 2 * pending_line_count
    assert len(body["clips"]) >= 4


def test_voice_manifest_second_call_is_fully_cached(seeded_db: None, mock_tts: MagicMock) -> None:
    with SessionLocal() as session:
        order = session.query(PickOrder).first()
        assert order is not None
        order_id = order.id

    client.get(f"/voice/orders/{order_id}/manifest")
    mock_tts.reset_mock()

    client.get(f"/voice/orders/{order_id}/manifest")

    mock_tts.assert_not_called()


def test_voice_manifest_404_for_unknown_order(seeded_db: None, mock_tts: MagicMock) -> None:
    response = client.get(f"/voice/orders/{uuid.uuid4()}/manifest")
    assert response.status_code == 404
