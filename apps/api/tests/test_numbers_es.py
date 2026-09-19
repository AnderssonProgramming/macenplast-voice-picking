"""Tests for the Spanish number-to-speech module."""

from __future__ import annotations

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from macenplast.domain.numbers_es import MAX_SUPPORTED, MIN_SUPPORTED, number_to_es

_SPANISH_WORD_RE = re.compile(r"^[a-záéíóúñ]+( y [a-záéíóúñ]+)*( [a-záéíóúñ]+( y [a-záéíóúñ]+)*)*$")

KNOWN_VALUES = {
    0: "cero",
    1: "uno",
    10: "diez",
    15: "quince",
    16: "dieciséis",
    20: "veinte",
    21: "veintiuno",
    22: "veintidós",
    23: "veintitrés",
    26: "veintiséis",
    30: "treinta",
    31: "treinta y uno",
    45: "cuarenta y cinco",
    99: "noventa y nueve",
    100: "cien",
    101: "ciento uno",
    115: "ciento quince",
    200: "doscientos",
    201: "doscientos uno",
    999: "novecientos noventa y nueve",
}


@pytest.mark.parametrize(("n", "expected"), sorted(KNOWN_VALUES.items()))
def test_known_values(n: int, expected: str) -> None:
    assert number_to_es(n) == expected


@pytest.mark.parametrize("n", [-1, 1000, -100, 5000])
def test_out_of_range_raises(n: int) -> None:
    with pytest.raises(ValueError, match="0-999"):
        number_to_es(n)


def test_every_value_in_range_is_unique() -> None:
    words = [number_to_es(n) for n in range(MIN_SUPPORTED, MAX_SUPPORTED + 1)]
    assert len(words) == len(set(words))


@given(st.integers(min_value=MIN_SUPPORTED, max_value=MAX_SUPPORTED))
def test_output_is_lowercase_spanish_words_only(n: int) -> None:
    word = number_to_es(n)
    assert word == word.lower()
    assert not any(char.isdigit() for char in word)
    assert _SPANISH_WORD_RE.match(word), f"{n} -> {word!r} doesn't look like nominal Spanish"


@given(st.integers(min_value=MIN_SUPPORTED, max_value=MAX_SUPPORTED))
def test_output_is_deterministic(n: int) -> None:
    assert number_to_es(n) == number_to_es(n)
