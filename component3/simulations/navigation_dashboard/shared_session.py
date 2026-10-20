"""Authoritative server-owned state and deterministic command processing."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
import re
import time
from typing import Any, Callable
from uuid import uuid4

from .spatial_simulation import SpatialNavigationSimulation
from .engine import FIXED_TIMESTEP_S
from .workflow import contract as workflow_contract, public_state


CLIENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
COMMAND_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
MAX_REMEMBERED_COMMANDS = 256
CONTROLLER_LEASE_TIMEOUT_S = 2.0
CONTROL_TAKING_ACTIONS = {
    "start",
    "guided_demo",
    "camera_evaluation",
    "resume",
    "choose_free_walk_edge",
    "free_walk_resume",
    "request_navigation",
    "autoplay_start",
    "autoplay_resume",
}


class SessionConflictError(ValueError):
    """Raised when a valid command conflicts with session ownership or revision."""


class SharedNavigationSession:
    """Own one navigation run shared by every view connected to the server.

    Simulation time changes only through an accepted ``step`` command. Each command
    ID is applied at most once, and only the current controller may step. Reads are
    side-effect free.
    """

    def __init__(self, simulation: SpatialNavigationSimulation | None = None) -> None:
        self.simulation = simulation or SpatialNavigationSimulation()
        self.session_id = f"nav-{uuid4()}"
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.state_revision = 0
        self.controller_id: str | None = None
        self._controller_last_step_monotonic: float | None = None
        self._command_results: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self.autoplay_enabled = False
        self.autoplay_rate = 1.0
        self._next_autoplay_tick = time.monotonic()

    def set_autoplay(self, enabled: bool, rate: object | None = None) -> None:
        """Configure the single server-owned deterministic playback clock."""
        if rate is not None:
            if isinstance(rate, bool) or not isinstance(rate, (int, float)):
                raise ValueError("autoplay rate must be a number")
            if not 0.25 <= float(rate) <= 8.0:
                raise ValueError("autoplay rate must be between 0.25 and 8.0")
            self.autoplay_rate = float(rate)
        self.autoplay_enabled = bool(enabled)
        self._next_autoplay_tick = time.monotonic()

    def autoplay_tick(self, now: float | None = None) -> bool:
        """Advance at most one fixed step; return whether state changed."""
        current = time.monotonic() if now is None else now
        if not self.autoplay_enabled or not self.simulation.running:
            return False
        if current < self._next_autoplay_tick:
            return False
        self.simulation.step(1)
        self.state_revision += 1
        if self.simulation.status == "complete":
            self.autoplay_enabled = False
        interval = FIXED_TIMESTEP_S / self.autoplay_rate
        self._next_autoplay_tick = current + interval
        return True

    @staticmethod
    def _identifier(value: object, label: str, pattern: re.Pattern[str]) -> str:
        if not isinstance(value, str) or not pattern.fullmatch(value):
            raise ValueError(
                f"{label} must be 1-128 characters using letters, numbers, '.', ':', '_' or '-'"
            )
        return value

    def claim_control(self, client_id: object) -> dict[str, Any]:
        """Give the first browser a stable step lease; repeated claims are safe."""
        client = self._identifier(client_id, "client_id", CLIENT_ID_PATTERN)
        if self.controller_id not in {None, client} and not self._lease_expired():
            raise SessionConflictError(
                f"Simulation control is already held by {self.controller_id!r}"
            )
        if self.controller_id is None or self._lease_expired():
            self.controller_id = client
            self._controller_last_step_monotonic = time.monotonic()
            self.state_revision += 1
        return self.snapshot()

    def release_control(self, client_id: object) -> dict[str, Any]:
        """Release a lease without changing navigation or simulation time."""
        client = self._identifier(client_id, "client_id", CLIENT_ID_PATTERN)
        if self.controller_id == client:
            self.controller_id = None
            self._controller_last_step_monotonic = None
            self.state_revision += 1
        return self.snapshot()

    def _lease_expired(self) -> bool:
        """Return whether a silent controller may be replaced by another view."""
        return (
            self._controller_last_step_monotonic is not None
            and time.monotonic() - self._controller_last_step_monotonic
            > CONTROLLER_LEASE_TIMEOUT_S
        )

    def apply(
        self,
        payload: dict[str, Any],
        dispatcher: Callable[[str, dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        """Validate, deduplicate, and apply one backend action atomically."""
        action = payload.get("action")
        if not isinstance(action, str) or not action:
            raise ValueError("action must be a non-empty string")
        client = self._identifier(
            payload.get("client_id", "legacy-api"), "client_id", CLIENT_ID_PATTERN
        )
        command_id = self._identifier(
            payload.get("command_id", f"legacy-{uuid4()}"),
            "command_id",
            COMMAND_ID_PATTERN,
        )
        prior = self._command_results.get(command_id)
        if prior is not None:
            return deepcopy(prior)
        expected_revision = payload.get("expected_revision")
        if expected_revision is not None and expected_revision != self.state_revision:
            raise SessionConflictError(
                f"Stale state revision {expected_revision!r}; current revision is {self.state_revision}"
            )
        if action == "step":
            if self.controller_id is None or self._lease_expired():
                self.controller_id = client
            elif self.controller_id != client:
                raise SessionConflictError(
                    f"Only controller {self.controller_id!r} may advance simulation time"
                )
            self._controller_last_step_monotonic = time.monotonic()
        result = dispatcher(action, payload)
        # A deliberate movement command transfers the playback lease to the view
        # that issued it. Other tabs remain read-only observers until they issue
        # their own explicit movement command; GET polling never advances time.
        if action in CONTROL_TAKING_ACTIONS:
            self.controller_id = client
            self._controller_last_step_monotonic = time.monotonic()
        self.state_revision += 1
        enriched = self.snapshot(result)
        self._command_results[command_id] = deepcopy(enriched)
        self._command_results.move_to_end(command_id)
        while len(self._command_results) > MAX_REMEMBERED_COMMANDS:
            self._command_results.popitem(last=False)
        return enriched

    def external_mutation(self) -> None:
        """Record a validated camera callback mutation under the server lock."""
        self.state_revision += 1

    def snapshot(
        self, base: dict[str, Any] | None = None, *, camera_status: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Return the complete research session without advancing its clock."""
        state = dict(base if base is not None else self.simulation.snapshot())
        state.update(
            {
                "session_id": self.session_id,
                "session_created_at": self.created_at,
                "map_version": self.simulation.data.get("schema_version", "UNKNOWN"),
                "state_revision": self.state_revision,
                "controller_id": self.controller_id,
                "controller_lease_timeout_s": CONTROLLER_LEASE_TIMEOUT_S,
                "simulation_clock": {
                    "mode": "server_owned_autoplay" if self.autoplay_enabled else "manual_fixed_step",
                    "fixed_timestep_s": state["fixed_timestep_s"],
                    "current_time_s": state["simulation_time_s"],
                    "read_requests_advance_time": False,
                    "autoplay_enabled": self.autoplay_enabled,
                    "autoplay_rate": self.autoplay_rate,
                    "owner": "backend_singleton",
                },
                "current_shopping_list": list(state["selected_product_ids"]),
                "current_estimated_position": dict(state["estimate"]),
                "simulated_ground_truth_position": dict(state["ground_truth"]),
                "position_uncertainty_m": state["localization"]["uncertainty_m"],
                "last_verified_checkpoint": state["last_confirmed_checkpoint"],
                "navigation_status": state["status"],
                "evaluation_event_history": list(state["events"]),
                "camera_status": camera_status,
                "last_successful_sync_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        state["localization_health"] = self.simulation.localization_health(camera_status)
        state["navigation_state"] = public_state(
            str(state["status"]),
            has_remaining_products=bool(state.get("remaining_products")),
        ).value
        state["navigation_state_contract"] = workflow_contract()
        return state
