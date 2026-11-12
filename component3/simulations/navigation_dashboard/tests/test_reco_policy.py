"""Unit tests for the pure recommendation display policy."""

from __future__ import annotations

from dataclasses import dataclass
import json
import unittest

from component3.simulations.navigation_dashboard.build_reco_evidence import build_payload
from component3.simulations.navigation_dashboard.config import RECOMMENDATION_FRONTEND_ROOT
from component3.simulations.navigation_dashboard.reco_policy import (
    RecommendationPolicyConfig,
    count_distinct_requested_items,
    evaluate_recommendation_policy,
)


@dataclass(frozen=True)
class Line:
    product_id: str
    requested_quantity: int


class RecommendationPolicyTests(unittest.TestCase):
    def test_environment_override_and_default(self) -> None:
        self.assertEqual(RecommendationPolicyConfig.from_environment({}).min_distinct_items, 1)
        self.assertEqual(
            RecommendationPolicyConfig.from_environment({"COMP3_RECO_MIN_ITEMS": "3"}).min_distinct_items,
            3,
        )
        configured = RecommendationPolicyConfig.from_environment(
            {"COMP3_RECO_MIN_ITEMS": "3", "COMP3_RECO_DEBOUNCE_SECONDS": "0.35"}
        )
        self.assertEqual(configured.debounce_seconds, 0.35)

    def test_distinct_positive_cart_lines_drive_gate(self) -> None:
        lines = (Line("mapped", 1), Line("unmapped", 2), Line("ignored", 0), Line("mapped", 4))
        self.assertEqual(count_distinct_requested_items(lines), 2)

    def test_gate_blocks_below_minimum_and_explains_count(self) -> None:
        decision = evaluate_recommendation_policy(
            RecommendationPolicyConfig(min_distinct_items=3),
            distinct_items=2,
            candidate_product_id="SIM-P-003",
        )
        self.assertFalse(decision.allowed)
        self.assertIn("below_minimum_distinct_items", decision.reasons)
        self.assertEqual(decision.gate_message, "Suggestions unlock at 3 distinct items - you have 2")

    def test_safety_limits_are_independent(self) -> None:
        decision = evaluate_recommendation_policy(
            RecommendationPolicyConfig(max_suggestions_per_trip=2),
            distinct_items=3,
            candidate_product_id="SIM-P-003",
            dismissed_product_ids={"SIM-P-003"},
            suggestions_shown=2,
            product_arrival_pending=True,
            active_suggestion=True,
            debounce_active=True,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(
            set(decision.reasons),
            {
                "max_suggestions_per_trip_reached",
                "product_arrival_decision_pending",
                "one_suggestion_already_active",
                "rapid_list_edit_debounce",
                "dismissed_for_session",
            },
        )

    def test_one_candidate_is_allowed_when_all_guards_pass(self) -> None:
        decision = evaluate_recommendation_policy(
            RecommendationPolicyConfig(min_distinct_items=3),
            distinct_items=3,
            candidate_product_id="SIM-P-003",
            suggestions_shown=1,
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reasons, ())

    def test_trip_limit_does_not_hide_the_current_previously_counted_offer(self) -> None:
        decision = evaluate_recommendation_policy(
            RecommendationPolicyConfig(max_suggestions_per_trip=2),
            distinct_items=3,
            candidate_product_id="SIM-P-003",
            suggestions_shown=2,
            candidate_previously_offered=True,
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.suggestions_shown, 2)

    def test_static_disclosure_is_generated_from_preserved_archives(self) -> None:
        static_path = RECOMMENDATION_FRONTEND_ROOT / "reco_evidence.json"
        self.assertEqual(json.loads(static_path.read_text(encoding="utf-8")), build_payload())
        self.assertEqual(
            build_payload()["wording"],
            "Experimental baseline; offline HitRate@5 4.7% (CI ~2-7%) on 299 held-out baskets; validation 9.4%; popularity baseline scored higher on test",
        )


if __name__ == "__main__":
    unittest.main()
