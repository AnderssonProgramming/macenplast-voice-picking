"""Tests for the Spanish phrase catalog renderer."""

from __future__ import annotations

import pytest

from macenplast.domain.pick_machine import Speak
from macenplast.voice.phrases import UnknownPhraseError, phrase_keys, render_phrase


def test_render_instruction_converts_numeric_args_to_words() -> None:
    text = render_phrase(
        "INSTRUCTION", aisle="A", bay=12, level=1, reference="Producto uno", quantity=21
    )
    assert text == (
        "Pasillo A. Estante doce. Nivel uno. Referencia, Producto uno. Cantidad, veintiuno."
    )


def test_render_fixed_phrase_needs_no_args() -> None:
    assert render_phrase("CORRECT") == "Correcto."


def test_render_qty_prompt() -> None:
    assert render_phrase("QTY_PROMPT", quantity=5) == "Cantidad, cinco."


def test_unknown_phrase_raises() -> None:
    with pytest.raises(UnknownPhraseError):
        render_phrase("NOT_A_REAL_PHRASE")


def test_every_pick_machine_speak_phrase_is_in_the_catalog() -> None:
    # Guards against the catalog drifting from the phrase keys the state
    # machine actually emits (see the vectors in
    # packages/machine-vectors/pick_line_transitions.json).
    used_in_vectors = {
        "INSTRUCTION",
        "LOCATION_CORRECT",
        "QTY_PROMPT",
        "CORRECT",
        "CALL_SUPERVISOR",
        "ASK_CONFIRM_SHORT",
    }
    assert used_in_vectors.issubset(set(phrase_keys()))
    # And a sanity check that Speak's `phrase` field is just a plain str,
    # so any catalog key is a valid value for it.
    assert isinstance(Speak("CORRECT").phrase, str)
