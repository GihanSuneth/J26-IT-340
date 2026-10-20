# Dataset inventory

Search scope was all data directories under `component3/`; virtual-environment fixtures,
navigation telemetry, evidence indexes and AprilTag placement CSVs were not misclassified
as POS data.

| Candidate | Result |
|---|---|
| `component3/data/raw/Retail_pos_basket_data.csv` | Found; 660,339 bytes; 10,000 data rows |
| `Retail_pos_basket_data.csv.csv` | Not found |
| `srilanka_supermarket_raw_pos.csv` | Not found |

The found file has columns `order_id`, `user_id`, `order_date`, `time`,
`order_hour_of_day`, `product_name`, `quantity`, `price`, `category`, and `product_id`.
It covers 2024-01-01 06:23 through 2024-12-31 21:33, with 1,991 transaction IDs,
488 source user IDs, 900 source product IDs, 68 product names, quantity 1–3 and price
10.09–499.96. Exact inferred types and missing rates are in `dataset_inventory.json`.

SHA-256: `0cd3a4d7d66dec3e7ce6fb1031b095740fb180b9e5fa46ce8bbb9f26f763ae57`.
The file is Git-ignored local input. It was read only and its checksum was unchanged.
