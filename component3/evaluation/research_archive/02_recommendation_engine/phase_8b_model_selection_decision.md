# Phase 8B model selection decision

Association rules were selected by the predeclared primary criterion, maximum validation
NDCG@5 (0.058075). Validation HitRate@5, coverage, and simplicity were tie-breakers but
were not needed. The model uses minimum support count 5 and confidence×lift ranking,
with 3,502 directed rules and deterministic popularity fallback.

Before test evaluation, the Phase 8A preprocessing, 68-item vocabulary (SHA-256
`f2f5255acf97b565da80acf38ef9bb5ed980e40df364a0f2fa0e5ff9e4f2a839`), family,
hyperparameters, observed-item filtering, score/tie logic, and seed were frozen. The
test set was not used for selection. The item-item result was close enough that this is
a protocol-based selection, not proof of superiority.
