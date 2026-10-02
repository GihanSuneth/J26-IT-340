# backend/comp3_reco_navigation/recommendation

**Owner:** comp3

## Responsibility
Recommendation engine: three-signal fusion plus detour filter.

## What lives here
preprocess, tfidf_category, knn_cooccurrence, fusion, detour_filter.

## Rules
No individual user data: preprocess.py must drop user_id. Do not use product_id as a join key (one id maps to many names in the dataset); use cleaned product names or rebuilt ids. Parameters come from ml/configs/comp3_reco.yaml.

## Files in this folder
- `__init__.py` - Package marker.
- `preprocess.py` - Cleans the POS CSV: drops user_id, fixes product keys, filters non-grocery categories, builds baskets.
- `tfidf_category.py` - sklearn TF-IDF + cosine similarity over category/product text (signal 1).
- `knn_cooccurrence.py` - KNN over basket co-occurrence vectors (signal 2).
- `fusion.py` - Fuses the three signals into one ranked candidate list.
- `detour_filter.py` - Relevance-vs-detour-cost filter: the novelty. Keeps a candidate only if its relevance justifies the extra route length.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Implement preprocess.py (read data/raw CSV, drop user_id, drop non-grocery categories, build baskets, write data/processed), tfidf_category.py (sklearn TfidfVectorizer + cosine similarity), knn_cooccurrence.py (sklearn NearestNeighbors on basket vectors), fusion.py (weighted fusion of the signals described in docs/components/comp3-reco-navigation.md) and detour_filter.py (keep a candidate only when fused relevance justifies the added route length versus the current Held-Karp route; threshold configurable).
```
