"""Runs the pick machine against the shared cross-language test vectors.

The vectors live in `packages/machine-vectors/pick_line_transitions.json` and
are also consumed by `apps/web/src/shared/pickMachine.test.ts`, so both
implementations are checked against exactly the same cases.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from macenplast.domain.pick_machine import PickState, transition
from macenplast.domain.pick_machine_json import (
    context_from_json,
    context_to_json,
    effect_to_json,
    event_from_json,
)

VECTORS_PATH = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "machine-vectors"
    / "pick_line_transitions.json"
)


def load_vectors() -> list[dict[str, Any]]:
    vectors: list[dict[str, Any]] = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
    return vectors


@pytest.mark.parametrize("vector", load_vectors(), ids=lambda v: v["name"])
def test_vector(vector: dict[str, Any]) -> None:
    state = PickState(vector["state"])
    context = context_from_json(vector["context"])
    event = event_from_json(vector["event"])

    result = transition(state, context, event)

    assert result.state.value == vector["expected"]["state"]
    assert context_to_json(result.context) == vector["expected"]["context"]
    assert [effect_to_json(e) for e in result.effects] == vector["expected"]["effects"]
