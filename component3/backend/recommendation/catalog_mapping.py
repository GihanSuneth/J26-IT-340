"""Auditable POS-to-demo-catalog reconciliation without fabricated SKU matches."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Sequence

from .preprocess import Basket, item_key, normalized_name


# Reviewed lexical aliases only; these are name matches, never verified SKU matches.
NAME_ALIASES = {
    "bananas": "banana",
    "bread loaf": "bread",
    "milk carton": "milk",
}
CATEGORY_SECTION = {
    "Bakery": "Bakery",
    "Dairy & Eggs": "Dairy",
    "Fruits & Vegetables": "Produce",
    "Grains & Staples": "Pantry",
}


@dataclass(frozen=True, slots=True)
class CatalogMapping:
    source_item_key: str
    source_product_name: str
    source_category: str
    mapping_status: str
    demo_product_id: str | None
    demo_product_name: str | None
    shelf_section: str | None
    shelf_id: str | None
    pickup_node_id: str | None
    navigation_eligible: bool
    rationale: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def reconcile_catalog(baskets: Sequence[Basket], catalog_path: Path) -> list[CatalogMapping]:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    products = catalog.get("products", [])
    by_name = {normalized_name(product["display_name"]): product for product in products}
    source_items = {
        item.item_key: (item.product_name, item.category)
        for basket in baskets for item in basket.items
    }
    mappings: list[CatalogMapping] = []
    for source_key, (source_name, category) in sorted(source_items.items()):
        normalized_source = normalized_name(source_name)
        matches = [
            product for demo_name, product in by_name.items()
            if normalized_source == demo_name or NAME_ALIASES.get(demo_name) == normalized_source
        ]
        if len(matches) == 1:
            product = matches[0]
            has_route = bool(product.get("shelf_id") and product.get("pickup_node_id"))
            mappings.append(CatalogMapping(
                source_key, source_name, category, "normalized_name_mapping",
                product["product_id"], product["display_name"], product.get("shelf_section"),
                product.get("shelf_id"), product.get("pickup_node_id"), has_route,
                "Conservative normalized-name or reviewed singular/packaging alias; no shared SKU was verified.",
            ))
        elif category in CATEGORY_SECTION:
            mappings.append(CatalogMapping(
                source_key, source_name, category, "category_level_mapping", None, None,
                CATEGORY_SECTION[category], None, None, False,
                "Category can be associated with a demo section, but no product-specific shelf destination is verified.",
            ))
        else:
            mappings.append(CatalogMapping(
                source_key, source_name, category, "unmapped_product", None, None, None,
                None, None, False, "No defensible demo-catalog name or category mapping.",
            ))
    return mappings


def navigable_item_keys(mappings: Sequence[CatalogMapping]) -> tuple[str, ...]:
    return tuple(mapping.source_item_key for mapping in mappings if mapping.navigation_eligible)
