"""Real historical transaction popularity and Keells-oriented grocery taxonomy.

This module computes genuine product popularity metrics directly from the local POS
transaction dataset (Retail_pos_basket_data.csv) without modifying frozen model artifacts.
It organizes catalog items under the departmental taxonomy used by major Sri Lankan
supermarket chains like Keells Super.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

COMPONENT_ROOT = Path(__file__).resolve().parents[2]
RAW_POS_PATH = COMPONENT_ROOT / "data/raw/Retail_pos_basket_data.csv"
CLEANED_BASKETS_PATH = COMPONENT_ROOT / "data/derived/recommendation_phase8a/cleaned_baskets.jsonl"
CATALOG_RECONCILIATION_PATH = COMPONENT_ROOT / "data/derived/recommendation_phase8a/catalog_reconciliation.csv"
DEMO_STORE_PATH = COMPONENT_ROOT / "data/demo_store/v1/demo_store.json"

KEELLS_DEPARTMENT_TAXONOMY = {
    "Produce": {
        "department": "Fresh Produce",
        "sub_category": "Fresh Fruits & Vegetables",
        "keells_aisle": "Aisle 1 — Fresh Market",
    },
    "Bakery": {
        "department": "Bakery & Confectionery",
        "sub_category": "Fresh Breads & Baked Goods",
        "keells_aisle": "Aisle 2 — In-Store Bakery",
    },
    "Dairy": {
        "department": "Dairy & Chilled",
        "sub_category": "Milk, Butter & Eggs",
        "keells_aisle": "Aisle 3 — Chilled Dairy",
    },
    "Pantry": {
        "department": "Grocery & Staples",
        "sub_category": "Pasta, Grains & Pulses",
        "keells_aisle": "Aisle 4 — Dry Goods & Staples",
    },
    "Cereal": {
        "department": "Breakfast & Spreads",
        "sub_category": "Breakfast Cereals & Oats",
        "keells_aisle": "Aisle 5 — Breakfast Foods",
    },
    "Frozen": {
        "department": "Frozen Foods",
        "sub_category": "Frozen Vegetables & Meats",
        "keells_aisle": "Aisle 6 — Frozen Cabinets",
    },
}


@dataclass(frozen=True, slots=True)
class ProductPopularity:
    """Genuine transaction statistics from historical POS data."""

    product_name: str
    transaction_count: int
    total_transactions: int
    popularity_share: float
    data_source_description: str
    is_available: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RetailCatalogPopularityService:
    """Computes transparent, data-backed popularity and Keells taxonomy."""

    def __init__(
        self,
        pos_path: Path = RAW_POS_PATH,
        reconciliation_path: Path = CATALOG_RECONCILIATION_PATH,
    ) -> None:
        self.pos_path = Path(pos_path)
        self.reconciliation_path = Path(reconciliation_path)
        self.total_orders = 0
        self.product_order_counts: Counter[str] = Counter()
        self.normalized_reconciliation: dict[str, dict[str, str]] = {}
        self._load_reconciliation()
        self._compute_popularity()

    def _load_reconciliation(self) -> None:
        if not self.reconciliation_path.exists():
            return
        with self.reconciliation_path.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                demo_id = row.get("demo_product_id")
                if demo_id:
                    self.normalized_reconciliation[demo_id] = row

    def _compute_popularity(self) -> None:
        if not self.pos_path.exists():
            return
        orders: dict[str, set[str]] = defaultdict(set)
        with self.pos_path.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                order_id = row.get("order_id")
                product_name = (row.get("product_name") or "").strip()
                if order_id and product_name:
                    orders[order_id].add(product_name.lower())
        self.total_orders = len(orders)
        for products in orders.values():
            self.product_order_counts.update(products)

    def get_product_popularity(self, demo_product_id: str, display_name: str) -> ProductPopularity:
        """Return genuine transaction frequency for a demo product."""
        name_keys = [display_name.lower()]
        if display_name.lower() == "bananas":
            name_keys.append("banana")
        elif display_name.lower() == "bread loaf":
            name_keys.extend(["bread", "bread loaf"])
        elif display_name.lower() == "milk carton":
            name_keys.extend(["milk", "milk carton"])
        elif display_name.lower() == "pasta":
            name_keys.append("pasta")
        elif display_name.lower() == "frozen peas":
            name_keys.extend(["peas", "frozen peas"])
        elif display_name.lower() == "cereal box":
            name_keys.extend(["cereal", "cereal box"])

        count = 0
        for key in name_keys:
            if key in self.product_order_counts:
                count = max(count, self.product_order_counts[key])

        is_available = count > 0 and self.total_orders > 0
        share = count / self.total_orders if is_available else 0.0

        return ProductPopularity(
            product_name=display_name,
            transaction_count=count,
            total_transactions=self.total_orders,
            popularity_share=round(share, 5),
            data_source_description=(
                f"Synthetic POS transaction dataset (Retail_pos_basket_data.csv, {self.total_orders} baskets)"
                if is_available
                else "Not recorded in historical retail POS basket dataset"
            ),
            is_available=is_available,
        )

    def get_keells_metadata(self, category: str) -> dict[str, str]:
        """Return research-pilot Keells supermarket taxonomy details."""
        return KEELLS_DEPARTMENT_TAXONOMY.get(
            category,
            {
                "department": "General Groceries",
                "sub_category": category,
                "keells_aisle": "Main Grocery Floor",
            },
        )

    def get_enriched_product(self, raw_product: dict[str, Any]) -> dict[str, Any]:
        """Enrich demo store product with popularity and Keells taxonomy."""
        demo_id = raw_product["demo_product_id"]
        display_name = raw_product.get("display_name") or raw_product.get("name", demo_id)
        category = raw_product.get("category", "General")
        pop = self.get_product_popularity(demo_id, display_name)
        keells_info = self.get_keells_metadata(category)
        recon = self.normalized_reconciliation.get(demo_id)

        return {
            **raw_product,
            "display_name": display_name,
            "popularity": pop.to_dict(),
            "keells_pilot": {
                "research_pilot_partner": "Keells Supermarket (Sri Lanka) Research Pilot Concept",
                "department": keells_info["department"],
                "sub_category": keells_info["sub_category"],
                "keells_aisle": keells_info["keells_aisle"],
                "retailer_sku_format": f"KEELLS-PILOT-{demo_id}",
                "notes": "Organized under Keells departmental taxonomy for research pilot demonstrations; not official retailer stock.",
            },
            "ml_mapping": {
                "mapped_to_ml_model": recon is not None,
                "normalized_model_key": recon.get("source_item_key") if recon else None,
                "mapping_status": recon.get("mapping_status") if recon else "unmapped_in_ml_model",
                "navigation_eligible": recon.get("navigation_eligible", "").lower() == "true" if recon else False,
                "gate_contribution": "recognized_distinct_cart_item",
                "model_contribution": "active_model_input" if recon else "excluded_from_model_input",
            },
        }

    def get_all_enriched_products(self, products: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return all catalog products sorted by genuine transaction popularity."""
        enriched = [self.get_enriched_product(p) for p in products]
        # Sort by transaction_count descending (popular items first), then by name
        return sorted(
            enriched,
            key=lambda item: (-item["popularity"]["transaction_count"], item["display_name"]),
        )


_POPULARITY_SERVICE: RetailCatalogPopularityService | None = None


def get_catalog_popularity_service() -> RetailCatalogPopularityService:
    global _POPULARITY_SERVICE
    if _POPULARITY_SERVICE is None:
        _POPULARITY_SERVICE = RetailCatalogPopularityService()
    return _POPULARITY_SERVICE
