"""Read-only terminal demonstration of the frozen live recommendation service."""

from __future__ import annotations

import argparse
import re
from typing import Sequence

from component3.backend.recommendation.live_service import (
    get_live_recommendation_service,
)

from .reco_policy import RecommendationPolicyConfig
from .spatial_simulation import SpatialNavigationSimulation


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _resolve_basket(
    simulation: SpatialNavigationSimulation, names: Sequence[str]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    service = get_live_recommendation_service()
    lookup: dict[str, str] = {}
    for product_id, product in simulation.products_by_id.items():
        lookup[_key(product_id)] = product_id
        lookup[_key(str(product["name"]))] = product_id
    if service.inference:
        for source, mapping in service.inference.mappings.items():
            demo_id = mapping.get("demo_product_id")
            if demo_id:
                lookup[_key(source)] = demo_id
                lookup[_key(mapping["source_product_name"])] = demo_id
                lookup[_key(mapping["demo_product_name"])] = demo_id
    resolved: list[str] = []
    unknown: list[str] = []
    for name in names:
        product_id = lookup.get(_key(name))
        if product_id is None:
            unknown.append(name)
        elif product_id not in resolved:
            resolved.append(product_id)
    return tuple(resolved), tuple(unknown)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--basket", nargs="+", required=True,
        help='Demo catalog names, for example --basket Bananas "Bread loaf" Pasta',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    service = get_live_recommendation_service()
    simulation = SpatialNavigationSimulation(
        recommendation_service=service,
        recommendation_policy=RecommendationPolicyConfig(min_distinct_items=0),
    )
    product_ids, unknown = _resolve_basket(simulation, args.basket)
    if unknown:
        raise SystemExit(f"Unknown demo basket name(s): {', '.join(unknown)}")
    state = simulation.set_products(product_ids)
    diagnostics = state["recommendation_diagnostics"]
    status = service.status()

    print("Component 3 frozen recommendation engine demo")
    print("=============================================")
    print(f"Basket names: {', '.join(args.basket)}")
    print(f"Resolved demo IDs: {', '.join(product_ids) or '(empty)'}")
    print(
        "Model input (verified mappings only): "
        + (", ".join(diagnostics["normalized_basket_input"]) or "(none)")
    )
    print(
        "Unmapped demo items excluded from model input: "
        + (", ".join(diagnostics["unmapped_demo_product_ids"]) or "(none)")
    )
    print(f"model_version: {status['model_version']}")
    checksum_ok = status["artifact_sha256"] == status["expected_artifact_sha256"]
    print(f"checksum_status: {'VERIFIED' if checksum_ok else 'FAILED'}")
    print(f"artifact_sha256: {status['artifact_sha256']}")
    print("\nRanked analysis (full engine output):")
    for candidate in diagnostics["candidate_ranking"]:
        reasons = ",".join(candidate["filter_reasons"]) or "none"
        detour = (
            "n/a" if candidate["route_detour_cost_m"] is None
            else f"{candidate['route_detour_cost_m']:.2f}m"
        )
        print(
            f"{candidate['rank']:>2}. {candidate['normalized_product']} "
            f"score={candidate['model_score']:.6f} "
            f"eligible={str(candidate['eligible']).lower()} "
            f"filter_reasons={reasons} detour_cost={detour}"
        )
    return 0 if service.ready and checksum_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
