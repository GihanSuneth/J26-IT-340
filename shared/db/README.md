# shared/db

**Owner:** develop (shared - all four members review)

## Responsibility
Database definition shared by all services.

## What lives here
schema.sql, migrations/ (numbered SQL or Alembic), seed/ (products.csv, store_locations.csv).

## Rules
Migrations are append-only. Never edit a migration that has been merged.

## Files in this folder
- `schema.sql` - Authoritative relational schema (products, carts, cart_items, bills, history, sessions).

## Subfolders
- `migrations/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write schema.sql for PostgreSQL: products, aisles, store_locations, sessions, carts, cart_items, bills, purchase_history, with primary/foreign keys and indexes, plus an initial numbered migration that creates them.
```
