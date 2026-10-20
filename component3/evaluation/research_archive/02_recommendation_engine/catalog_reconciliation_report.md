# Catalog reconciliation report

The source vocabulary was compared with the synthetic six-product catalog at
`component3/data/demo_store/v1/demo_store.json`. No shared, verified SKU exists, so
**exact verified mapping count is zero**.

| Status | Source names | Navigation policy |
|---|---:|---|
| Normalized-name mapping | 4 | Eligible only because the demo product also has shelf and pickup node |
| Category-level mapping | 22 | Not navigable; section-level association is insufficient |
| Unmapped product | 42 | Not navigable |
| Exact verified mapping | 0 | None available |

The four conservative mappings are Banana→Bananas, Bread→Bread loaf,
Milk→Milk carton, and Pasta→Pasta. These cover 4/68 source names (5.88%) and 4/6 demo
products (66.67%); lexical mapping does not prove SKU equivalence. Cereal box and Frozen
peas have no source-name counterpart. The complete crosswalk is
`component3/data/derived/recommendation_phase8a/catalog_reconciliation.csv`.

Only a product-level mapping with a known available shelf and valid pickup node can set
`navigation_eligible=true`. Category-only and unmapped candidates may be studied
offline but must not appear as navigable customer suggestions.
