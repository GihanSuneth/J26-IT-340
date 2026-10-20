"""Reproducible Phase 8C functional integration evaluation."""

from __future__ import annotations

import csv
from itertools import combinations
import json
from pathlib import Path
from statistics import mean
import time

from component3.backend.comp3_reco_navigation.recommendation.live_service import LiveRecommendationService
from component3.simulations.navigation_dashboard.shared_session import SharedNavigationSession
from component3.simulations.navigation_dashboard.spatial_simulation import SpatialNavigationSimulation


COMPONENT = Path(__file__).resolve().parents[2]
ARCHIVE = COMPONENT / "evaluation/research_archive/03_integrated_system"


def _complete(simulation: SpatialNavigationSimulation) -> dict[str, object]:
    if simulation.status == "ready":
        simulation.start()
    for _ in range(4000):
        if simulation.status == "complete":
            return simulation.snapshot()
        if simulation.status == "awaiting_product_confirmation":
            simulation.confirm_product(
                expected_shopping_revision=simulation.shopping_session.revision
            )
        elif simulation.running:
            simulation.step()
        else:
            raise RuntimeError(f"journey stopped unexpectedly in {simulation.status}")
    raise RuntimeError("journey did not complete within the fixed-step bound")


def run(output_directory: Path = ARCHIVE) -> dict[str, object]:
    output_directory.mkdir(parents=True, exist_ok=True)
    scenario_rows: list[dict[str, object]] = []
    mapped = ("SIM-P-001", "SIM-P-002", "SIM-P-003", "SIM-P-004")
    scenario_inputs = [combo for size in range(0, 5) for combo in combinations(mapped, size)]
    for index, products in enumerate(scenario_inputs, start=1):
        simulation = SpatialNavigationSimulation(speed_m_s=1.6)
        simulation.set_products(products)
        state = simulation.snapshot()
        diagnostics = state["recommendation_diagnostics"]
        scenario_rows.append({
            "scenario_id": f"AVAIL-{index:02d}",
            "selected_products": "|".join(products),
            "shopping_revision": state["shopping_list_revision"],
            "recommendation_available": bool(state["recommendations"]),
            "navigable_suggestion": bool(state["recommendations"] and state["recommendations"][0]["navigation_eligible"]),
            "candidate_count": diagnostics["candidate_count"],
            "eligible_candidate_count": diagnostics["eligible_candidate_count"],
            "inference_latency_ms": diagnostics["inference_latency_ms"],
            "filtering_latency_ms": diagnostics["eligibility_filtering_latency_ms"],
            "response_latency_ms": diagnostics["end_to_end_latency_ms"],
            "fallback_state": diagnostics["fallback_state"] or "none",
        })

    integrated = SpatialNavigationSimulation(speed_m_s=1.6)
    integrated.set_products(("SIM-P-001", "SIM-P-002"))
    before = integrated.snapshot()
    suggestion = before["recommendations"][0]
    accepted = integrated.accept_recommendation(suggestion["recommendation_id"], 0)
    acceptance_event = accepted["recommendation_events"][-1]
    final = _complete(integrated)

    dismissed_sim = SpatialNavigationSimulation()
    dismissed_sim.set_products(("SIM-P-001",))
    dismissed_before = dismissed_sim.snapshot()
    dismissed_suggestion = dismissed_before["recommendations"][0]
    dismissed = dismissed_sim.reject_recommendation(dismissed_suggestion["recommendation_id"], 0)

    stale_rejected = False
    stale_sim = SpatialNavigationSimulation()
    stale_sim.set_products(("SIM-P-001",))
    stale_suggestion = stale_sim.snapshot()["recommendations"][0]
    try:
        stale_sim.accept_recommendation(stale_suggestion["recommendation_id"], 9)
    except ValueError:
        stale_rejected = True

    duplicate_sim = SpatialNavigationSimulation()
    duplicate_sim.set_products(("SIM-P-001",))
    duplicate_suggestion = duplicate_sim.snapshot()["recommendations"][0]
    shared = SharedNavigationSession(duplicate_sim)
    command = {
        "action": "accept_recommendation", "client_id": "phase8c-eval",
        "command_id": "phase8c-accept-once",
        "recommendation_id": duplicate_suggestion["recommendation_id"],
        "expected_shopping_revision": 0,
    }
    dispatch = lambda action, body: duplicate_sim.accept_recommendation(
        body["recommendation_id"], body["expected_shopping_revision"]
    )
    shared.apply(command, dispatch)
    shared.apply(command, dispatch)

    unavailable = SpatialNavigationSimulation(
        recommendation_service=LiveRecommendationService(Path("/nonexistent/phase8c-model.json"))
    ).snapshot()
    no_eligible_sim = SpatialNavigationSimulation()
    no_eligible_sim.set_products(tuple(no_eligible_sim.products_by_id))
    no_eligible = no_eligible_sim.snapshot()

    available = sum(bool(row["recommendation_available"]) for row in scenario_rows)
    suggested = [row for row in scenario_rows if row["recommendation_available"]]
    metrics = {
        "scenario_count": len(scenario_rows),
        "recommendation_available_count": available,
        "recommendation_availability_fraction": available / len(scenario_rows),
        "navigable_suggestion_fraction": (
            sum(bool(row["navigable_suggestion"]) for row in suggested) / len(suggested)
            if suggested else 0.0
        ),
        "mean_model_inference_latency_ms": mean(float(row["inference_latency_ms"]) for row in scenario_rows),
        "mean_eligibility_filtering_latency_ms": mean(float(row["filtering_latency_ms"]) for row in scenario_rows),
        "mean_end_to_end_response_latency_ms": mean(float(row["response_latency_ms"]) for row in scenario_rows),
        "acceptance_to_route_update_latency_ms": acceptance_event["reroute_latency_ms"],
        "route_revision_correct": accepted["route_revision"] == before["route_revision"] + 1,
        "shopping_revision_correct": accepted["shopping_list_revision"] == 1,
        "duplicate_mutation_rate": 0.0 if duplicate_sim.shopping_session.revision == 1 else 1.0,
        "additional_route_distance_after_acceptance_m": (
            acceptance_event["new_remaining_route_cost_m"] - acceptance_event["previous_remaining_route_cost_m"]
        ),
        "integrated_journey_completed": final["status"] == "complete",
        "accepted_product_collected": suggestion["product_id"] in final["collected_product_ids"],
        "dismissal_preserved_revision": dismissed["shopping_list_revision"] == dismissed_before["shopping_list_revision"],
        "dismissed_product_not_immediately_repeated": all(
            item["product_id"] != dismissed_suggestion["product_id"] for item in dismissed["recommendations"]
        ),
        "stale_revision_rejected": stale_rejected,
        "model_unavailable_navigation_preserved": bool(unavailable["planned_route"]),
        "no_eligible_candidate_handled": not no_eligible["recommendations"],
        "claims_scope": "functional synthetic integration only; not offline accuracy, personalization, satisfaction, or commercial impact",
    }
    raw = {
        "protocol": "demonstration-selected basket uses only live frozen-model inference; scores and artifacts are unchanged",
        "availability_scenarios": scenario_rows,
        "integrated_journey": {
            "initial_products": ["SIM-P-001", "SIM-P-002"],
            "recommendation": suggestion,
            "acceptance_event": acceptance_event,
            "final_status": final["status"],
            "final_collected_product_ids": final["collected_product_ids"],
            "final_shopping_revision": final["shopping_list_revision"],
            "final_route_revision": final["route_revision"],
        },
        "negative_cases": metrics,
    }
    (output_directory / "phase_8c_raw_scenario_results.json").write_text(
        json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_directory / "phase_8c_aggregated_metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (output_directory / "phase_8c_availability_scenarios.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(scenario_rows[0]))
        writer.writeheader()
        writer.writerows(scenario_rows)
    return {"metrics": metrics, "raw": raw}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
