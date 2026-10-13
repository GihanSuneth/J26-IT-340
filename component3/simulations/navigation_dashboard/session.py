"""Client-side demonstration state model used by the dashboard adapter tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from component3.backend.comp3_reco_navigation.navigation.store_graph import StoreGraph

from .adapter import RoutePlan, calculate_dashboard_route
from .config import DEFAULT_DESTINATION_IDS


@dataclass(slots=True)
class DashboardSession:
    """One browser demonstration's selected destinations and calculated route."""

    map_data: dict[str, Any]
    graph: StoreGraph
    selected_destination_ids: tuple[str, ...] = DEFAULT_DESTINATION_IDS
    route_plan: RoutePlan | None = None

    def calculate(self, destination_ids: Sequence[str] | None = None) -> RoutePlan:
        """Calculate a route and update this session only after success."""
        selected = (
            self.selected_destination_ids
            if destination_ids is None
            else tuple(destination_ids)
        )
        plan = calculate_dashboard_route(self.map_data, selected, self.graph)
        self.selected_destination_ids = plan.selected_destination_ids
        self.route_plan = plan
        return plan

    def reset(self) -> None:
        """Restore the deterministic default shopping scenario."""
        self.selected_destination_ids = DEFAULT_DESTINATION_IDS
        self.route_plan = None
