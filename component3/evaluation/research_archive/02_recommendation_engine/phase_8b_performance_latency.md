# Phase 8B latency benchmark

Validation inference p95 latency was 0.0145 ms global, 0.0225 ms category, 0.0380 ms
association, 0.4735 ms item-item, and 0.0249 ms linear. Frozen-test association latency
over 299 calls was mean 0.03075 ms, median 0.03083 ms, and p95 0.03783 ms.

Calls ran sequentially in-process after model fitting on the local development machine.
They exclude disk loading, HTTP, UI, routing and network time. The dataset is only 68
items; values are useful for relative prototype comparison and must not be generalized
to deployment scale. Raw per-call measurements are in the prediction JSONL files.
