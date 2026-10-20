"""Quantity-aware, auditable shopping state for the shared navigation session."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import asdict, dataclass
import math
from typing import Literal, Mapping, Sequence


ProductSource = Literal["customer_selection", "accepted_recommendation"]
MutationAction = Literal["add", "remove", "increase", "decrease_remaining", "pickup"]


class ShoppingRevisionConflictError(ValueError):
    """Raised when a valid mutation was prepared against stale shopping state."""


@dataclass(frozen=True, slots=True)
class ShoppingLine:
    """One catalog product with monotonic confirmed collection state."""

    product_id: str
    requested_quantity: int
    collected_quantity: int
    source: ProductSource

    @property
    def remaining_quantity(self) -> int:
        return self.requested_quantity - self.collected_quantity

    @property
    def collection_status(self) -> str:
        if self.remaining_quantity == 0:
            return "collected"
        if self.collected_quantity:
            return "partially_collected"
        return "remaining"

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["remaining_quantity"] = self.remaining_quantity
        result["collection_status"] = self.collection_status
        return result


@dataclass(frozen=True, slots=True)
class ShoppingMutation:
    """Validated proposed state; commit occurs only after route calculation succeeds."""

    action: MutationAction
    product_id: str
    quantity: int
    source: ProductSource
    expected_revision: int
    proposed_lines: tuple[ShoppingLine, ...]


@dataclass(frozen=True, slots=True)
class Recommendation:
    """Future-compatible inert recommendation contract."""

    recommendation_id: str
    product_id: str
    recommendation_source: str
    model_version: str | None
    score: float | None
    display_explanation: str
    acceptance_status: Literal["pending", "accepted", "rejected"] = "pending"
    mapping_status: Literal[
        "exact_verified_mapping", "normalized_name_mapping",
        "category_level_mapping", "unmapped_product",
    ] = "unmapped_product"
    shelf_availability: Literal["available", "unavailable", "unknown"] = "unknown"
    shelf_id: str | None = None
    pickup_node_id: str | None = None
    navigation_eligible: bool = False
    route_detour_cost_m: float | None = None
    shopping_revision: int = 0
    model_artifact_sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.recommendation_id or not self.product_id or not self.recommendation_source:
            raise ValueError("recommendation identifiers and source must be non-empty")
        if self.score is not None and (
            isinstance(self.score, bool)
            or not isinstance(self.score, (int, float))
            or not math.isfinite(self.score)
        ):
            raise ValueError("recommendation score must be finite or null")
        if self.navigation_eligible and (
            self.mapping_status not in {"exact_verified_mapping", "normalized_name_mapping"}
            or self.shelf_availability != "available"
            or not self.shelf_id
            or not self.pickup_node_id
        ):
            raise ValueError("navigable recommendation requires a mapped available shelf and pickup node")
        if self.route_detour_cost_m is not None and (
            not math.isfinite(self.route_detour_cost_m) or self.route_detour_cost_m < 0
        ):
            raise ValueError("route detour cost must be finite and nonnegative or null")
        if isinstance(self.shopping_revision, bool) or self.shopping_revision < 0:
            raise ValueError("recommendation shopping revision must be nonnegative")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class ShoppingSession:
    """Own quantities, revisioning and append-only shopping event history."""

    def __init__(self, catalog_product_ids: Sequence[str], initial_product_ids: Sequence[str]) -> None:
        catalog = tuple(catalog_product_ids)
        if len(set(catalog)) != len(catalog) or not all(
            isinstance(product_id, str) and product_id for product_id in catalog
        ):
            raise ValueError("catalog_product_ids must contain unique non-empty IDs")
        self._catalog = frozenset(catalog)
        self._lines: OrderedDict[str, ShoppingLine] = OrderedDict()
        for product_id in initial_product_ids:
            self._validate_product(product_id)
            if product_id not in self._lines:
                self._lines[product_id] = ShoppingLine(
                    product_id, 1, 0, "customer_selection"
                )
        self.revision = 0
        self.events: list[dict[str, object]] = []

    @staticmethod
    def _quantity(value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("quantity must be a positive integer")
        return value

    @staticmethod
    def _revision(value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("expected_shopping_revision must be a nonnegative integer")
        return value

    def _validate_product(self, product_id: object) -> str:
        if not isinstance(product_id, str) or product_id not in self._catalog:
            raise ValueError(f"Unknown synthetic demo product: {product_id!r}")
        return product_id

    @property
    def lines(self) -> tuple[ShoppingLine, ...]:
        return tuple(self._lines.values())

    @property
    def requested_product_ids(self) -> tuple[str, ...]:
        return tuple(self._lines)

    @property
    def remaining_product_ids(self) -> tuple[str, ...]:
        return tuple(
            product_id for product_id, line in self._lines.items()
            if line.remaining_quantity > 0
        )

    @property
    def collected_product_ids(self) -> tuple[str, ...]:
        return tuple(
            product_id for product_id, line in self._lines.items()
            if line.collected_quantity > 0
        )

    def line(self, product_id: str) -> ShoppingLine | None:
        return self._lines.get(product_id)

    def defer_to_end(self, product_id: str, timestamp_s: float) -> None:
        """Keep an uncollected line but explicitly defer it behind other products."""
        line = self._lines.get(product_id)
        if line is None or line.remaining_quantity <= 0:
            raise ValueError("Only a remaining shopping line can be deferred")
        self._lines.move_to_end(product_id)
        self.revision += 1
        self.events.append({
            "shopping_revision": self.revision,
            "timestamp_s": float(timestamp_s),
            "action": "skip_keep_for_later",
            "product_id": product_id,
            "quantity": line.remaining_quantity,
            "source": line.source,
            "result": line.to_dict(),
        })

    def clone_for_new_run(self, timestamp_s: float) -> "ShoppingSession":
        """Create an explicit new-run state while retaining demand and audit history."""
        clone = ShoppingSession(tuple(self._catalog), ())
        clone._lines = OrderedDict(
            (
                line.product_id,
                ShoppingLine(line.product_id, line.requested_quantity, 0, line.source),
            )
            for line in self._lines.values()
        )
        clone.revision = self.revision + 1
        clone.events = deepcopy(self.events)
        clone.events.append(
            {
                "shopping_revision": clone.revision,
                "timestamp_s": float(timestamp_s),
                "action": "explicit_new_run_reset",
                "product_id": None,
                "quantity": None,
                "source": None,
                "result": None,
            }
        )
        return clone

    def propose(
        self,
        action: MutationAction,
        product_id: object,
        quantity: object,
        expected_revision: object,
        *,
        source: ProductSource = "customer_selection",
    ) -> ShoppingMutation:
        product = self._validate_product(product_id)
        amount = self._quantity(quantity)
        expected = self._revision(expected_revision)
        if expected != self.revision:
            raise ShoppingRevisionConflictError(
                f"Stale shopping-list revision {expected}; current revision is {self.revision}"
            )
        if source not in {"customer_selection", "accepted_recommendation"}:
            raise ValueError("invalid product source")
        if action not in {"add", "remove", "increase", "decrease_remaining", "pickup"}:
            raise ValueError(f"Unknown shopping mutation: {action!r}")
        proposed = OrderedDict(self._lines)
        current = proposed.get(product)
        if action == "add":
            if current is None:
                proposed[product] = ShoppingLine(product, amount, 0, source)
            else:
                proposed[product] = ShoppingLine(
                    product, current.requested_quantity + amount,
                    current.collected_quantity, current.source,
                )
        elif action == "increase":
            if current is None:
                raise ValueError("Cannot increase a product that is not on the shopping list")
            proposed[product] = ShoppingLine(
                product, current.requested_quantity + amount,
                current.collected_quantity, current.source,
            )
        elif action == "remove":
            if amount != 1:
                raise ValueError("remove uses quantity 1 and removes the complete uncollected line")
            if current is None:
                raise ValueError("Product is not on the shopping list")
            if current.collected_quantity:
                raise ValueError("A product with confirmed pickups cannot be removed")
            del proposed[product]
        elif action == "decrease_remaining":
            if current is None:
                raise ValueError("Product is not on the shopping list")
            if amount > current.remaining_quantity:
                raise ValueError("Cannot decrease more than the remaining requested quantity")
            requested = current.requested_quantity - amount
            if requested == 0:
                del proposed[product]
            else:
                proposed[product] = ShoppingLine(
                    product, requested, current.collected_quantity, current.source
                )
        else:
            if current is None or amount > current.remaining_quantity:
                raise ValueError("Pickup quantity exceeds the remaining requested quantity")
            proposed[product] = ShoppingLine(
                product, current.requested_quantity,
                current.collected_quantity + amount, current.source,
            )
        return ShoppingMutation(
            action, product, amount, source, expected, tuple(proposed.values())
        )

    def commit(self, mutation: ShoppingMutation, timestamp_s: float) -> ShoppingLine | None:
        """Commit exactly one previously validated mutation."""
        if mutation.expected_revision != self.revision:
            raise ValueError("Shopping mutation revision changed before commit")
        if not math.isfinite(timestamp_s) or timestamp_s < 0:
            raise ValueError("shopping mutation timestamp must be finite and nonnegative")
        self._lines = OrderedDict((line.product_id, line) for line in mutation.proposed_lines)
        self.revision += 1
        line = self._lines.get(mutation.product_id)
        self.events.append(
            {
                "shopping_revision": self.revision,
                "timestamp_s": float(timestamp_s),
                "action": mutation.action,
                "product_id": mutation.product_id,
                "quantity": mutation.quantity,
                "source": mutation.source,
                "result": line.to_dict() if line else None,
            }
        )
        return line

    def snapshot(self, product_catalog: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
        lines: list[dict[str, object]] = []
        for line in self._lines.values():
            item = line.to_dict()
            product = product_catalog[line.product_id]
            item.update(
                {
                    "name": product.get("display_name", product.get("name")),
                    "shelf_id": product.get("shelf_id"),
                    "shelf_section": product.get("shelf_section"),
                    "shelf_bay": product.get("shelf_bay"),
                    "shelf_level": product.get("shelf_level"),
                    "pickup_node_id": product.get("pickup_node_id"),
                }
            )
            lines.append(item)
        return {
            "revision": self.revision,
            "items": lines,
            "requested_units": sum(line.requested_quantity for line in self._lines.values()),
            "collected_units": sum(line.collected_quantity for line in self._lines.values()),
            "remaining_units": sum(line.remaining_quantity for line in self._lines.values()),
            "events": deepcopy(self.events[-100:]),
        }
