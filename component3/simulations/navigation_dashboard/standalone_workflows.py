"""Small state adapters for the two independent research demonstrations.

The adapters deliberately leave route planning and recommendation inference in the
existing simulation.  They only separate customer intent (wishlist/navigation
basket) from confirmed cart input and expose mode-appropriate snapshots.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Iterable

from .shared_session import SharedNavigationSession


class StandaloneDemoWorkflow:
    """Own UI/policy state that must not be shared between dashboard processes."""

    def __init__(self, mode: str, session: SharedNavigationSession) -> None:
        if mode not in {"navigation", "recommendation"}:
            raise ValueError("unsupported standalone demonstration mode")
        self.mode = mode
        self.session = session
        self.wishlist: OrderedDict[str, None] = OrderedDict()
        self.navigation_basket: OrderedDict[str, None] = OrderedDict()
        self.unresolved_products: list[dict[str, str]] = []
        self.recommendation_wishlist: OrderedDict[str, None] = OrderedDict()
        self.accepted_suggestions: OrderedDict[str, None] = OrderedDict()

    @property
    def simulation(self):
        return self.session.simulation

    def _product(self, product_id: object) -> tuple[str, dict[str, Any]]:
        if not isinstance(product_id, str) or product_id not in self.simulation.products_by_id:
            raise ValueError(f"Unknown verified demo product: {product_id!r}")
        return product_id, self.simulation.products_by_id[product_id]

    def _validated_ids(self, values: object) -> tuple[str, ...]:
        if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
            raise ValueError("product_ids must be a sequence")
        result: list[str] = []
        for value in values:
            product_id, _ = self._product(value)
            if product_id not in result:
                result.append(product_id)
        return tuple(result)

    def reset(self) -> dict[str, Any]:
        """Reset only the active standalone component."""
        self.wishlist.clear()
        self.navigation_basket.clear()
        self.unresolved_products.clear()
        self.recommendation_wishlist.clear()
        self.accepted_suggestions.clear()
        if self.mode == "navigation":
            return self.session.reset_demo()
        return self.session.reset_recommendation_demo()

    def navigation_action(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply wishlist, basket, and explicit planning actions."""
        if self.mode != "navigation":
            raise ValueError("Navigation workflow actions are unavailable in recommendation mode")
        if action in {"wishlist_add", "wishlist_remove", "navigation_basket_add", "navigation_basket_remove"}:
            product_id, _ = self._product(payload.get("product_id"))
            if action == "wishlist_add":
                self.wishlist[product_id] = None
            elif action == "wishlist_remove":
                self.wishlist.pop(product_id, None)
                self.navigation_basket.pop(product_id, None)
            elif action == "navigation_basket_add":
                if product_id not in self.wishlist:
                    raise ValueError("Add the product to the wishlist before selecting it for navigation")
                self.navigation_basket[product_id] = None
            else:
                self.navigation_basket.pop(product_id, None)
            return self.simulation.snapshot()
        if action == "navigation_basket_set":
            product_ids = self._validated_ids(payload.get("product_ids", []))
            missing = [item for item in product_ids if item not in self.wishlist]
            if missing:
                raise ValueError("Navigation basket products must already be in the wishlist")
            self.navigation_basket = OrderedDict((item, None) for item in product_ids)
            return self.simulation.snapshot()
        if action == "plan_navigation_route":
            return self.plan_navigation_route()
        raise ValueError(f"Unknown navigation workflow action: {action!r}")

    def _resolve_navigation_products(self) -> tuple[tuple[str, ...], list[dict[str, str]]]:
        valid: list[str] = []
        unresolved: list[dict[str, str]] = []
        for product_id in self.navigation_basket:
            product = self.simulation.products_by_id.get(product_id)
            pickup = product.get("pickup_node_id") if product else None
            shelf = self.simulation.shelves_by_id.get(str(product.get("shelf_id"))) if product else None
            reason = None
            if not product:
                reason = "product_not_in_verified_catalog"
            elif not pickup or pickup not in self.simulation.graph:
                reason = "pickup_node_not_in_active_graph"
            elif not shelf or shelf.get("pickup_node_id") != pickup:
                reason = "shelf_mapping_not_verified"
            if reason:
                unresolved.append({"product_id": product_id, "reason": reason})
            else:
                valid.append(product_id)
        return tuple(valid), unresolved

    def plan_navigation_route(self) -> dict[str, Any]:
        """Resolve verified destinations, then delegate to existing route planning."""
        valid, unresolved = self._resolve_navigation_products()
        self.unresolved_products = unresolved
        if not valid:
            raise ValueError("Select at least one product with a verified store location")
        current = set(self.simulation.shopping_session.requested_product_ids)
        desired = set(valid)
        if self.simulation.status == "idle" or not current:
            return self.simulation.set_products(valid)
        for product_id in tuple(current - desired):
            self.simulation.mutate_shopping_list(
                "remove", product_id, 1, self.simulation.shopping_session.revision,
                refresh_recommendations=False,
            )
        for product_id in valid:
            if product_id not in current:
                self.simulation.mutate_shopping_list(
                    "add", product_id, 1, self.simulation.shopping_session.revision,
                    refresh_recommendations=False,
                )
        return self.simulation.snapshot()

    def recommendation_action(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply simulated confirmed-cart and local recommendation decisions."""
        if self.mode != "recommendation":
            raise ValueError("Recommendation workflow actions are unavailable in navigation mode")
        if action in {"confirmed_cart_add", "confirmed_cart_remove"}:
            product_id, _ = self._product(payload.get("product_id"))
            line = self.simulation.shopping_session.line(product_id)
            if action == "confirmed_cart_add":
                mutation = "increase" if line else "add"
            else:
                if line is None:
                    raise ValueError("Product is not in the simulated confirmed cart")
                mutation = "remove"
            return self.simulation.mutate_shopping_list(
                mutation, product_id, 1, self.simulation.shopping_session.revision,
            )
        if action in {"standalone_accept_recommendation", "recommendation_add_wishlist"}:
            recommendation_id = payload.get("recommendation_id")
            result, product_id = self.simulation.resolve_standalone_recommendation(
                recommendation_id,
                payload.get("expected_shopping_revision"),
                "accepted" if action == "standalone_accept_recommendation" else "wishlist",
            )
            self.recommendation_wishlist[product_id] = None
            if action == "standalone_accept_recommendation":
                self.accepted_suggestions[product_id] = None
            return result
        raise ValueError(f"Unknown recommendation workflow action: {action!r}")

    def _product_summary(self, product_id: str) -> dict[str, Any]:
        product = self.simulation.products_by_id[product_id]
        return {
            "product_id": product_id,
            "name": product["display_name"],
            "category": product.get("category"),
            "shelf_id": product.get("shelf_id"),
            "pickup_node_id": product.get("pickup_node_id"),
        }

    def enrich(self, state: dict[str, Any]) -> dict[str, Any]:
        """Add explicit standalone collections without altering compatibility fields."""
        result = dict(state)
        result["standalone_mode"] = self.mode
        if self.mode == "navigation":
            destination_groups: OrderedDict[str, list[str]] = OrderedDict()
            for product_id in self.navigation_basket:
                product = self.simulation.products_by_id[product_id]
                node = product.get("pickup_node_id")
                if node and not any(row["product_id"] == product_id for row in self.unresolved_products):
                    destination_groups.setdefault(node, []).append(product_id)
            result.update({
                "wishlist_items": [self._product_summary(item) for item in self.wishlist],
                "navigation_basket_items": [self._product_summary(item) for item in self.navigation_basket],
                "navigation_destinations": [
                    {"checkpoint_node_id": node, "product_ids": products}
                    for node, products in destination_groups.items()
                ],
                "unresolved_products": list(self.unresolved_products),
                "found_items": [self._product_summary(item) for item in state.get("collected_product_ids", [])],
                "confirmed_cart_items": [],
                "recommendations": [],
                "recommendation_diagnostics": {"enabled": False, "reason": "standalone_navigation_mode"},
            })
        else:
            confirmed = [
                self._product_summary(line["product_id"]) | {
                    "confirmed_quantity": line["requested_quantity"]
                }
                for line in state.get("shopping_session", {}).get("items", [])
                if line.get("requested_quantity", 0) > 0
            ]
            result.update({
                "confirmed_cart_items": confirmed,
                "recommendation_wishlist_items": [
                    self._product_summary(item) for item in self.recommendation_wishlist
                ],
                "accepted_suggestion_items": [
                    self._product_summary(item) for item in self.accepted_suggestions
                ],
            })
        return result
