"""Pure customer-facing recommendation display policy.

The policy deliberately does not rank products.  It only decides whether one
already-ranked, navigation-eligible candidate may be shown to a customer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from typing import Iterable, Mapping, Protocol


class ShoppingLineLike(Protocol):
    """Small structural type used by the distinct-item counter."""

    product_id: str
    requested_quantity: int


@dataclass(frozen=True, slots=True)
class RecommendationPolicyConfig:
    """Configurable limits for passive customer suggestions."""

    min_distinct_items: int = 1
    max_suggestions_per_trip: int = 2
    debounce_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.min_distinct_items < 0:
            raise ValueError("min_distinct_items must be zero or greater")
        if self.max_suggestions_per_trip < 0:
            raise ValueError("max_suggestions_per_trip must be zero or greater")
        if self.debounce_seconds < 0:
            raise ValueError("debounce_seconds must be zero or greater")

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> "RecommendationPolicyConfig":
        """Load the customer gate without changing model configuration."""
        source = os.environ if environment is None else environment
        raw = source.get("COMP3_RECO_MIN_ITEMS", "1")
        try:
            minimum = int(raw)
        except ValueError as exc:
            raise ValueError("COMP3_RECO_MIN_ITEMS must be an integer") from exc
        raw_debounce = source.get("COMP3_RECO_DEBOUNCE_SECONDS", "0")
        try:
            debounce = float(raw_debounce)
        except ValueError as exc:
            raise ValueError("COMP3_RECO_DEBOUNCE_SECONDS must be numeric") from exc
        return cls(min_distinct_items=minimum, debounce_seconds=debounce)


@dataclass(frozen=True, slots=True)
class RecommendationPolicyDecision:
    """Explainable output from one policy evaluation."""

    allowed: bool
    reasons: tuple[str, ...]
    min_distinct_items: int
    distinct_items: int
    suggestions_shown: int
    max_suggestions_per_trip: int

    @property
    def gate_message(self) -> str:
        return (
            f"Suggestions unlock at {self.min_distinct_items} distinct items - "
            f"you have {self.distinct_items}"
        )

    def to_dict(self) -> dict[str, object]:
        return {**asdict(self), "reasons": list(self.reasons), "gate_message": self.gate_message}


def count_distinct_requested_items(lines: Iterable[ShoppingLineLike]) -> int:
    """Count unique cart products whose requested quantity is positive."""
    return len({line.product_id for line in lines if line.requested_quantity > 0})


def evaluate_recommendation_policy(
    config: RecommendationPolicyConfig,
    *,
    distinct_items: int,
    candidate_product_id: str | None,
    dismissed_product_ids: Iterable[str] = (),
    suggestions_shown: int = 0,
    candidate_previously_offered: bool = False,
    product_arrival_pending: bool = False,
    active_suggestion: bool = False,
    debounce_active: bool = False,
) -> RecommendationPolicyDecision:
    """Return all applicable reasons without mutating session state."""
    reasons: list[str] = []
    if distinct_items < config.min_distinct_items:
        reasons.append("below_minimum_distinct_items")
    if (
        suggestions_shown >= config.max_suggestions_per_trip
        and not candidate_previously_offered
    ):
        reasons.append("max_suggestions_per_trip_reached")
    if product_arrival_pending:
        reasons.append("product_arrival_decision_pending")
    if active_suggestion:
        reasons.append("one_suggestion_already_active")
    if debounce_active:
        reasons.append("rapid_list_edit_debounce")
    if candidate_product_id is None:
        reasons.append("no_eligible_candidate")
    elif candidate_product_id in set(dismissed_product_ids):
        reasons.append("dismissed_for_session")
    return RecommendationPolicyDecision(
        allowed=not reasons,
        reasons=tuple(reasons),
        min_distinct_items=config.min_distinct_items,
        distinct_items=distinct_items,
        suggestions_shown=suggestions_shown,
        max_suggestions_per_trip=config.max_suggestions_per_trip,
    )
