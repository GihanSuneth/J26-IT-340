"""Quantity, revision, pickup and recommendation contract tests."""

from __future__ import annotations

import unittest

from component3.simulations.navigation_dashboard.shopping_session import (
    Recommendation,
    ShoppingSession,
)


class ShoppingSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = ShoppingSession(("A", "B", "C"), ("A",))

    def apply(self, action: str, product: str, quantity: int = 1):
        mutation = self.session.propose(
            action, product, quantity, self.session.revision
        )
        return self.session.commit(mutation, 1.25)

    def test_add_increase_and_decrease_track_quantities_and_revision(self) -> None:
        self.apply("add", "B", 2)
        self.apply("increase", "B", 1)
        line = self.apply("decrease_remaining", "B", 1)
        self.assertEqual((line.requested_quantity, line.collected_quantity), (2, 0))
        self.assertEqual(self.session.revision, 3)
        self.assertEqual(len(self.session.events), 3)

    def test_pickup_is_monotonic_and_collected_line_cannot_be_removed(self) -> None:
        self.apply("increase", "A", 1)
        first = self.apply("pickup", "A")
        self.assertEqual((first.collected_quantity, first.remaining_quantity), (1, 1))
        with self.assertRaisesRegex(ValueError, "confirmed pickups"):
            self.session.propose("remove", "A", 1, self.session.revision)
        second = self.apply("pickup", "A")
        self.assertEqual(second.collection_status, "collected")
        with self.assertRaisesRegex(ValueError, "exceeds"):
            self.session.propose("pickup", "A", 1, self.session.revision)

    def test_invalid_or_stale_mutations_do_not_change_state(self) -> None:
        before = self.session.snapshot({"A": {}, "B": {}, "C": {}})
        cases = (
            ("add", "UNKNOWN", 1, 0),
            ("add", "B", 0, 0),
            ("increase", "B", 1, 0),
            ("add", "B", 1, 9),
        )
        for action, product, quantity, revision in cases:
            with self.assertRaises(ValueError):
                self.session.propose(action, product, quantity, revision)
        self.assertEqual(self.session.snapshot({"A": {}, "B": {}, "C": {}}), before)

    def test_decrease_cannot_erase_confirmed_pickup(self) -> None:
        self.apply("increase", "A", 2)
        self.apply("pickup", "A", 2)
        line = self.apply("decrease_remaining", "A", 1)
        self.assertEqual((line.requested_quantity, line.collected_quantity), (2, 2))
        self.assertEqual(line.collection_status, "collected")

    def test_recommendation_contract_has_no_fabricated_score(self) -> None:
        recommendation = Recommendation(
            "DEMO-R-001", "B", "demonstration_suggestion", None, None,
            "Clearly labelled integration suggestion.",
        )
        self.assertEqual(recommendation.acceptance_status, "pending")
        self.assertIsNone(recommendation.score)
        self.assertIsNone(recommendation.model_version)


if __name__ == "__main__":
    unittest.main()
