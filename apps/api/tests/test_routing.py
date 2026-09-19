"""Tests for `plan_route`'s default serpentine heuristic and, when the
optional `ortools` dependency is installed, the `or_tools` strategy."""

from __future__ import annotations

import builtins
import uuid
from collections.abc import Mapping, Sequence
from types import ModuleType

import pytest

from macenplast.domain.routing import RouteLocation, plan_route


def loc(pos_x: float, pos_y: float, level: str = "1") -> RouteLocation:
    return RouteLocation(id=uuid.uuid4(), pos_x=pos_x, pos_y=pos_y, level=level)


def test_single_aisle_visits_in_ascending_bay_order() -> None:
    locations = [loc(0, 3), loc(0, 1), loc(0, 2)]

    route = plan_route(locations, strategy="serpentine")

    assert [item.pos_y for item in route] == [1, 2, 3]


def test_multi_aisle_zigzags_without_backtracking() -> None:
    # Aisle 0: bays 1,2,3. Aisle 1: bays 1,2,3. A naive "always ascending"
    # route would end aisle 0 at bay 3 then jump back to bay 1 of aisle 1 —
    # the serpentine heuristic should instead walk aisle 1 in descending
    # bay order, so the route never backtracks along the bay axis.
    locations = [
        loc(0, 1),
        loc(0, 2),
        loc(0, 3),
        loc(1, 1),
        loc(1, 2),
        loc(1, 3),
    ]

    route = plan_route(locations, strategy="serpentine")

    assert [(item.pos_x, item.pos_y) for item in route] == [
        (0, 1),
        (0, 2),
        (0, 3),
        (1, 3),
        (1, 2),
        (1, 1),
    ]


def test_tie_break_by_level_then_id() -> None:
    # Same (pos_x, pos_y) slot — different shelf levels of the same bay.
    lower = loc(0, 0, level="1")
    upper = loc(0, 0, level="2")

    route = plan_route([upper, lower], strategy="serpentine")

    assert route == [lower, upper]


def test_unknown_strategy_raises() -> None:
    with pytest.raises(ValueError, match="Unknown routing strategy"):
        plan_route([loc(0, 0)], strategy="bogus")


def test_or_tools_strategy_visits_every_location() -> None:
    pytest.importorskip("ortools", reason="optional 'routing' extra not installed")
    locations = [loc(0, 0), loc(0, 5), loc(3, 0), loc(3, 5)]

    route = plan_route(locations, strategy="or_tools")

    assert {item.id for item in route} == {item.id for item in locations}
    assert len(route) == len(locations)


def test_or_tools_strategy_without_dependency_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def fake_import(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> ModuleType:
        if name == "ortools.constraint_solver":
            raise ImportError("simulated missing dependency")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError, match="optional 'ortools' dependency"):
        plan_route([loc(0, 0), loc(1, 1), loc(2, 2)], strategy="or_tools")
