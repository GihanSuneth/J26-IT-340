# backend/comp4_pattern_billing/services

**Owner:** comp4

## Responsibility
Business logic of Component 4.

## What lives here
history, billing, shopping_list, recipe, notification, sync services.

## Rules
Database access through shared/db schema only.

## Files in this folder
- `__init__.py` - Package marker.
- `history_service.py` - Stores and queries per-customer purchase history.
- `billing_service.py` - Totals the confirmed cart, applies prices/discounts, creates the bill.
- `shopping_list_service.py` - Builds and edits the monthly shopping list.
- `recipe_service.py` - Recipe-to-ingredient mapping used to extend shopping lists.
- `notification_service.py` - Sends reminders/alerts to the mobile app.
- `sync_service.py` - Two-way sync of lists and bills between backend and mobile app.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Implement BillingService (sum cart_items, apply prices, create bill row), HistoryService (append purchases per customer), ShoppingListService (monthly list from predictions) using SQLAlchemy against shared/db/schema.sql.
```
