"""Pick-route planning.

Pure functions: `plan_route` takes plain location data and returns a
visiting order. It never touches the database — callers load `Location`
rows and build `RouteLocation` values from them (a conversion helper
belongs in the API layer once Phase 4 assembles routes for an order, not
here — this module has no dependency on `macenplast.db`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class RouteLocation:
    """The subset of a `Location` row the router needs."""

    id: uuid.UUID
    pos_x: float
    pos_y: float
    level: str = "0"


def plan_route(locations: list[RouteLocation], strategy: str = "serpentine") -> list[RouteLocation]:
    """Order `locations` into a pick route.

    Args:
        locations: Locations to visit, in any order.
        strategy: `"serpentine"` (default, no extra dependencies) or
            `"or_tools"` (exact/near-exact TSP solve for larger orders;
            requires the optional `ortools` dependency — see
            `_plan_route_or_tools`).

    Returns:
        The same locations, reordered.
    """
    if strategy == "serpentine":
        return _plan_route_serpentine(locations)
    if strategy == "or_tools":
        return _plan_route_or_tools(locations)
    raise ValueError(f"Unknown routing strategy: {strategy!r}")


def _plan_route_serpentine(locations: list[RouteLocation]) -> list[RouteLocation]:
    """S-shape (serpentine) heuristic: walk aisles in a zigzag.

    Locations are grouped by `pos_x` (the aisle axis) in ascending order.
    Within each aisle group, locations are visited in ascending `pos_y`
    order if the aisle's position in the walk is even, descending if odd —
    so the picker reaches the end of one aisle and immediately enters the
    next without walking back to the start. This never backtracks along
    the aisle axis, which is what makes it a reasonable default without
    solving a full TSP.

    Tie-break: within the same `(pos_x, pos_y)` slot (e.g. different
    shelf levels of the same bay), locations are ordered by `level`
    (ascending, lexical) and then by `id`, so the result is fully
    deterministic even with degenerate/duplicate coordinates.
    """
    distinct_x = sorted({loc.pos_x for loc in locations})
    aisle_index = {x: i for i, x in enumerate(distinct_x)}

    def sort_key(loc: RouteLocation) -> tuple[float, float, str, str]:
        index = aisle_index[loc.pos_x]
        y = loc.pos_y if index % 2 == 0 else -loc.pos_y
        return (loc.pos_x, y, loc.level, str(loc.id))

    return sorted(locations, key=sort_key)


def _plan_route_or_tools(locations: list[RouteLocation]) -> list[RouteLocation]:
    """Near-optimal TSP solve using Google OR-Tools.

    Requires the optional `ortools` dependency
    (`pip install ".[routing]"` in `apps/api`). Minimizes total Euclidean
    travel distance over `pos_x`/`pos_y`, starting from the first location
    in the input list.
    """
    try:
        from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    except ImportError as exc:
        raise RuntimeError(
            "The 'or_tools' routing strategy requires the optional 'ortools' "
            'dependency. Install it with `pip install ".[routing]"` in '
            "apps/api, or use ROUTING_STRATEGY=serpentine instead."
        ) from exc

    if len(locations) <= 2:
        return list(locations)

    manager = pywrapcp.RoutingIndexManager(len(locations), 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index: int, to_index: int) -> int:
        a = locations[manager.IndexToNode(from_index)]
        b = locations[manager.IndexToNode(to_index)]
        # Scaled to integers: OR-Tools' solver requires integer costs.
        distance = ((a.pos_x - b.pos_x) ** 2 + (a.pos_y - b.pos_y) ** 2) ** 0.5
        return int(round(distance * 1000))

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )

    solution = routing.SolveWithParameters(search_parameters)
    if solution is None:
        raise RuntimeError("OR-Tools failed to find a route")

    ordered: list[RouteLocation] = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        ordered.append(locations[manager.IndexToNode(index)])
        index = solution.Value(routing.NextVar(index))
    return ordered
