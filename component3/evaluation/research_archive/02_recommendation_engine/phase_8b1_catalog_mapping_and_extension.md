# Phase 8B.1 catalog mapping audit and extension proposal

The active synthetic demo-store catalog contains six products. All 68 normalized
research names were rechecked against that catalog, each referenced shelf, and the
active graph pickup nodes. The evidence-backed navigation coverage remains **4/68
(5.88%) before and 4/68 (5.88%) after reconciliation**:

- Banana → Bananas (`SIM-P-001`, `DEMO-SHELF-01`, `N1_1`)
- Bread → Bread loaf (`SIM-P-002`, `DEMO-SHELF-02`, `N1_2`)
- Milk → Milk carton (`SIM-P-003`, `DEMO-SHELF-03`, `N1_4`)
- Pasta → Pasta (`SIM-P-004`, `DEMO-SHELF-04`, `N2_1`)

All four references pass active graph validation. No additional mapping is approved.
Category/section similarity is not product identity, and the demo Cereal box and
Frozen peas entries have no equivalent normalized research product. The row-level
evidence and status for every source name are in `phase_8b1_catalog_mapping_audit.csv`.

## Separate synthetic extension proposal

For each non-eligible source item, a future demo-data change may create a clearly
synthetic product record only after a human reviews product identity and availability,
allocates a shelf/section/bay/level, supplies an adjacent pickup node, and validates
the revised graph and geometry. The proposal deliberately assigns no SKU, shelf, or
pickup node today. It must be versioned separately from the validated research maps;
this audit made no map change.
