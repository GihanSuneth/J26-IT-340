# Phase 8B training handoff

Before training, resolve or formally accept the unknown provenance/license limitation.
Then reproduce Phase 8A, verify all hashes, and freeze the split assignments.

1. Fit four prepared baselines on the 1,393 training baskets only.
2. Select minimum support, scoring variants, and K using 297 validation baskets.
3. If justified, fit a regularized bag-of-items linear completion model and compare it
   with the strongest baseline; avoid user/sequential features.
4. Freeze preprocessing, hyperparameters, dependency versions, model artifact hash,
   and model card before the single 299-basket test evaluation.
5. Report relevance, coverage/diversity, cold-start, observed-item violations and
   latency with basket-level uncertainty. Do not claim customer acceptance quality.
6. Export only candidates passing the catalog contract. Four source names are currently
   navigation-eligible; category-only/unmapped candidates must be blocked.
7. Keep suggestions pending until explicit customer acceptance. Send acceptance through
   the existing `accept_recommendation` command with the current shopping revision;
   its atomic mutation performs route reoptimization or fails without partial state.

The contract requires product ID, model version, score, candidate source
(`recommendation_source`), optional explanation, mapping status, shelf availability,
navigation eligibility, optional detour cost, and acceptance status. Phase 8B must add
experiment result artifacts; Phase 8A contains no accuracy number.
