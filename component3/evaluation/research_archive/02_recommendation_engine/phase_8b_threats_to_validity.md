# Phase 8B threats to validity

The dataset has unknown source/license and synthetic-like properties. Product IDs are
invalid as SKUs, so normalized names collapse variants. There is no verified currency,
store, branch, cancellation, return, stock or customer-identity semantics. The 68-item
catalog is small; timestamps may not reflect real chronology. One deterministic hidden
item per basket tests completion, not next-item prediction or customer acceptance.

Bootstrap intervals quantify basket-sampling variation only and do not correct provenance,
temporal drift, hyperparameter search, or catalog mismatch. The selected model's test
degradation and small absolute hit counts limit conclusions. Latency excludes integration
overhead. Four demo mappings are lexical, not verified SKU identity. No result establishes
Sri Lankan supermarket behavior, causal value, user satisfaction, physical navigation
accuracy, or production readiness.
