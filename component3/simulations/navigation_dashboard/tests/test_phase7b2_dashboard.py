"""Phase 7B.2 dashboard contract tests that do not require physical hardware."""

from __future__ import annotations

import unittest

from component3.simulations.navigation_dashboard.dashboard import make_handler
from component3.simulations.navigation_dashboard.config import (
    NAVIGATION_FRONTEND_ROOT,
    RECOMMENDATION_FRONTEND_ROOT,
)


STATIC = NAVIGATION_FRONTEND_ROOT


class DashboardContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = (STATIC / "spatial.html").read_text(encoding="utf-8")
        cls.css = (STATIC / "spatial.css").read_text(encoding="utf-8")
        cls.javascript = (STATIC / "spatial.js").read_text(encoding="utf-8")

    def test_five_named_dashboard_sections_are_present(self) -> None:
        for heading in (
            "SHOPPING LIST", "NAVIGATION MAP", "CAMERA EVALUATION",
            "TURN-BY-TURN GUIDANCE", "EVALUATION RESULTS",
        ):
            self.assertIn(heading, self.html)

    def test_research_console_links_to_synchronized_customer_view(self) -> None:
        self.assertIn("AUTHORIZED OPERATOR VIEW", self.html)
        self.assertIn("Navigation Operations &amp; Diagnostics", self.html)
        self.assertIn('href="/customer"', self.html)

    def test_customer_view_exposes_required_navigation_contract(self) -> None:
        customer = (STATIC / "customer.html").read_text(encoding="utf-8")
        javascript = (STATIC / "customer.js").read_text(encoding="utf-8")
        for element_id in (
            "products", "instruction", "location", "checkpoint", "shelf",
            "confirm", "voice", "route", "session", "revision", "map",
            "direction-icon", "checkpoint-timeline", "camera-navigation",
        ):
            self.assertIn(f'id="{element_id}"', customer)
        self.assertIn("/api/session/state", javascript)
        self.assertIn("/api/session/control", javascript)
        self.assertIn("remaining_route", javascript)
        self.assertIn("detected_checkpoint_ids", javascript)
        self.assertIn("camera_evaluation", javascript)

    def test_customer_voice_is_immediate_visible_and_repeatable(self) -> None:
        customer = (STATIC / "customer.html").read_text(encoding="utf-8")
        javascript = (STATIC / "customer.js").read_text(encoding="utf-8")
        self.assertIn('id="voice-status"', customer)
        self.assertIn('id="voice-repeat"', customer)
        self.assertIn("speakGuidance(true)", javascript)
        self.assertIn("utterance.onstart", javascript)
        self.assertIn("utterance.onerror", javascript)
        self.assertIn("pendingVoice", javascript)
        self.assertNotIn("speechSynthesis.cancel();\n  speechSynthesis.speak(utterance)", javascript)

    def test_customer_route_and_trip_controls_are_stable_and_visible(self) -> None:
        customer = (STATIC / "customer.html").read_text(encoding="utf-8")
        css = (STATIC / "customer.css").read_text(encoding="utf-8")
        javascript = (STATIC / "customer.js").read_text(encoding="utf-8")
        self.assertIn('id="demo-speed"', customer)
        self.assertIn('value="0.5" selected', customer)
        self.assertIn('id="edit-items-button"', customer)
        self.assertIn("Pick up at shelf", customer)
        self.assertIn('data-mode="live"', css)
        self.assertNotIn("@keyframes route-flow", css)
        self.assertIn("setInterval(poll, 500)", javascript)
        self.assertNotIn('id="apply"', customer)
        self.assertIn('id="shopping-update-status"', customer)
        self.assertIn('"wishlist_remove" : "wishlist_add"', javascript)
        self.assertIn('control("plan_navigation_route")', javascript)

    def test_customer_can_add_items_before_selecting_navigation(self) -> None:
        """The wishlist action must remain visible while the basket is empty."""
        css = (STATIC / "customer.css").read_text(encoding="utf-8")
        javascript = (STATIC / "customer.js").read_text(encoding="utf-8")
        self.assertIn('"Add to wishlist"', javascript)
        self.assertNotIn(
            '.catalog[data-mode="planning"] .quantity-controls { display: none; }',
            css,
        )

    def test_customer_map_uses_live_position_not_a_static_road_illustration(self) -> None:
        javascript = (STATIC / "customer.js").read_text(encoding="utf-8")
        self.assertIn('"YOU ARE HERE"', javascript)
        self.assertIn('class: "route-line"', javascript)
        self.assertNotIn("Front-facing route preview", javascript)

    def test_operator_exposes_localization_health_and_active_layout_overlay(self) -> None:
        for element_id in (
            "localization-health-card", "health-last-confirmed", "health-raw-tag",
            "health-classification", "health-estimate", "health-uncertainty",
            "health-candidates", "health-camera", "health-sync", "show-checkpoints",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        self.assertIn("candidate_checkpoints", self.javascript)
        self.assertIn("apriltag_layouts", self.javascript)
        self.assertIn("uncertainty-marker", self.javascript)

    def test_phase7d_free_walk_controls_exist_in_both_views(self) -> None:
        customer = (STATIC / "customer.html").read_text(encoding="utf-8")
        for element_id in (
            "enter-free-walk", "free-walk-stop", "free-walk-resume",
            "free-walk-options", "request-navigation",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
            self.assertIn(f'id="{element_id}"', customer)
        for research_field in (
            "observation-classification", "route-revision", "replanning-reason",
            "free-walk-state",
        ):
            self.assertIn(f'id="{research_field}"', self.html)

    def test_camera_selection_and_preview_controls_are_present(self) -> None:
        for element_id in (
            "refresh-cameras", "select-camera", "start-camera", "stop-camera",
            "camera-preview", "camera-placeholder", "camera-error",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        self.assertIn("/api/camera/preview.jpg", self.javascript)
        self.assertIn("camera.scanning", self.javascript)

    def test_camera_selector_contains_only_refreshed_verified_devices(self) -> None:
        self.assertNotIn("built-in preference", self.html)
        self.assertNotIn("Continuity preference", self.html)
        self.assertIn("Refresh cameras to detect devices", self.html)
        self.assertIn("payload.devices.forEach", self.javascript)
        self.assertIn("state.selectedCameraIndex", self.javascript)
        self.assertIn("Not exposed by platform", self.javascript)

    def test_voice_is_optional_deduplicated_and_cancellable(self) -> None:
        self.assertIn("this.spoken.has(eventId)", self.javascript)
        self.assertIn("this.synth.cancel()", self.javascript)
        self.assertIn("Enable Voice", self.html)
        self.assertIn("Unavailable", self.javascript)
        self.assertIn('type="checkbox" hidden', self.html)

    def test_responsive_layout_has_desktop_tablet_and_mobile_rules(self) -> None:
        self.assertIn("grid-template-areas", self.css)
        self.assertIn("@media (min-width: 721px) and (max-width: 1180px)", self.css)
        self.assertIn("@media (max-width: 720px)", self.css)
        self.assertIn("overflow-x: hidden", self.css)

    def test_recommendation_subcomponent_separates_policy_and_analysis(self) -> None:
        html = (RECOMMENDATION_FRONTEND_ROOT / "recommendations.html").read_text(encoding="utf-8")
        javascript = (RECOMMENDATION_FRONTEND_ROOT / "recommendations.js").read_text(encoding="utf-8")
        self.assertIn("Backend Analysis", html)
        self.assertIn('id="gate-message"', html)
        self.assertIn("unmapped items were excluded", javascript)
        self.assertIn("candidate_ranking", javascript)
        self.assertIn("standalone_accept_recommendation", javascript)
        self.assertIn("reject_recommendation", javascript)

    def test_navigation_view_exposes_one_clear_reset_demo_action(self) -> None:
        customer = (STATIC / "customer.html").read_text(encoding="utf-8")
        javascript = (STATIC / "customer.js").read_text(encoding="utf-8")
        self.assertEqual(customer.count('id="reset-demo"'), 1)
        self.assertIn(">Reset Demo</button>", customer)
        self.assertIn('control("reset_demo")', javascript)
        self.assertIn('id="reset-status"', customer)

    def test_dashboard_modes_own_independent_sessions_and_navigation_starts_idle(self) -> None:
        navigation = make_handler(mode="navigation")
        recommendation = make_handler(mode="recommendation")
        try:
            navigation_state = navigation.shared_session.snapshot()
            recommendation_before = recommendation.shared_session.snapshot()
            self.assertEqual(navigation_state["status"], "idle")
            self.assertEqual(navigation_state["selected_product_ids"], [])
            navigation.shared_session.reset_demo()
            recommendation_after = recommendation.shared_session.snapshot()
            self.assertEqual(
                recommendation_after["shopping_session"],
                recommendation_before["shopping_session"],
            )
            self.assertEqual(
                recommendation_after["recommendations"],
                recommendation_before["recommendations"],
            )
        finally:
            navigation.camera_scanner.stop()
            recommendation.camera_scanner.stop()
            navigation.stop_background()
            recommendation.stop_background()


if __name__ == "__main__":
    unittest.main()
