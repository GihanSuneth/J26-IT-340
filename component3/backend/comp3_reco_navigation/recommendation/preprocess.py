"""Deterministic POS audit, basket reconstruction and leakage-safe splitting.

The raw input is read-only. Source ``product_id`` values are retained as evidence,
but a normalized product-name key is used for modelling when the audit proves that
the source identifier is not semantically stable.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
from pathlib import Path
import re
from typing import Iterable, Sequence


REQUIRED_COLUMNS = (
    "order_id", "user_id", "order_date", "time", "order_hour_of_day",
    "product_name", "quantity", "price", "category", "product_id",
)
MODEL_ITEM_KEY = "normalized_product_name"


def normalized_name(value: str) -> str:
    """Return a conservative, reproducible name key without semantic guessing."""
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def item_key(product_name: str) -> str:
    return f"name:{normalized_name(product_name).replace(' ', '-')}"


@dataclass(frozen=True, slots=True)
class TransactionLine:
    order_id: str
    user_id: str
    timestamp: datetime
    product_name: str
    category: str
    source_product_id: str
    quantity: int
    price: float


@dataclass(frozen=True, slots=True)
class BasketItem:
    item_key: str
    product_name: str
    category: str
    quantity: int
    source_product_ids: tuple[str, ...]
    line_count: int


@dataclass(frozen=True, slots=True)
class Basket:
    basket_id: str
    timestamp: datetime
    source_user_id: str
    items: tuple[BasketItem, ...]
    source_line_count: int

    @property
    def signature(self) -> tuple[str, ...]:
        return tuple(sorted(item.item_key for item in self.items))

    def to_dict(self) -> dict[str, object]:
        return {
            "basket_id": self.basket_id,
            "timestamp": self.timestamp.isoformat(),
            "source_line_count": self.source_line_count,
            "items": [asdict(item) for item in self.items],
        }


@dataclass(frozen=True, slots=True)
class SplitResult:
    train: tuple[Basket, ...]
    validation: tuple[Basket, ...]
    test: tuple[Basket, ...]
    purged_duplicate_basket_ids: tuple[str, ...]
    train_end: str
    validation_end: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_transactions(path: Path) -> tuple[list[TransactionLine], list[dict[str, object]]]:
    """Parse valid rows and return explicit rejects; never mutate the source file."""
    lines: list[TransactionLine] = []
    rejects: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or tuple(reader.fieldnames) != REQUIRED_COLUMNS:
            raise ValueError(f"unexpected POS schema: {reader.fieldnames!r}")
        for row_number, row in enumerate(reader, start=2):
            missing = [name for name in REQUIRED_COLUMNS if not (row.get(name) or "").strip()]
            if missing:
                rejects.append({"row_number": row_number, "reason": "missing_required", "fields": missing})
                continue
            try:
                timestamp = datetime.strptime(
                    f"{row['order_date']} {row['time']}", "%Y-%m-%d %H:%M:%S"
                )
                quantity_float = float(row["quantity"])
                price = float(row["price"])
                hour = int(row["order_hour_of_day"])
                if not quantity_float.is_integer() or quantity_float <= 0:
                    raise ValueError("quantity must be a positive integer")
                if price <= 0:
                    raise ValueError("price must be positive")
                if hour != timestamp.hour:
                    raise ValueError("order hour disagrees with timestamp")
            except (TypeError, ValueError) as exc:
                rejects.append({"row_number": row_number, "reason": "invalid_value", "detail": str(exc)})
                continue
            lines.append(TransactionLine(
                order_id=row["order_id"].strip(), user_id=row["user_id"].strip(),
                timestamp=timestamp, product_name=row["product_name"].strip(),
                category=row["category"].strip(), source_product_id=row["product_id"].strip(),
                quantity=int(quantity_float), price=price,
            ))
    return lines, rejects


def audit_dataset(path: Path) -> dict[str, object]:
    lines, rejects = read_transactions(path)
    raw_rows: list[tuple[str, ...]] = []
    missing = Counter({column: 0 for column in REQUIRED_COLUMNS})
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            raw_rows.append(tuple(row.get(column, "") for column in REQUIRED_COLUMNS))
            missing.update(column for column in REQUIRED_COLUMNS if not (row.get(column) or "").strip())
    exact = Counter(raw_rows)
    by_order: dict[str, list[TransactionLine]] = defaultdict(list)
    id_names: dict[str, set[str]] = defaultdict(set)
    name_ids: dict[str, set[str]] = defaultdict(set)
    for line in lines:
        by_order[line.order_id].append(line)
        id_names[line.source_product_id].add(line.product_name)
        name_ids[line.product_name].add(line.source_product_id)
    repeated_source_pair = Counter((line.order_id, line.source_product_id) for line in lines)
    repeated_name_pair = Counter((line.order_id, item_key(line.product_name)) for line in lines)
    timestamps = [line.timestamp for line in lines]
    quantities = [line.quantity for line in lines]
    prices = [line.price for line in lines]
    return {
        "path": path.as_posix(), "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path), "row_count": len(raw_rows),
        "valid_row_count": len(lines), "rejected_row_count": len(rejects),
        "columns": list(REQUIRED_COLUMNS),
        "inferred_dtypes": {
            "order_id": "string", "user_id": "string", "order_date": "date",
            "time": "time", "order_hour_of_day": "integer", "product_name": "string",
            "quantity": "integer", "price": "decimal-like float", "category": "string",
            "product_id": "string",
        },
        "date_coverage": {
            "minimum": min(timestamps).isoformat() if timestamps else None,
            "maximum": max(timestamps).isoformat() if timestamps else None,
            "unique_calendar_dates": len({value.date() for value in timestamps}),
        },
        "identifier_coverage": {
            "unique_transactions": len(by_order),
            "unique_source_users": len({line.user_id for line in lines}),
            "unique_source_product_ids": len(id_names),
            "unique_product_names": len(name_ids),
            "product_ids_with_multiple_names": sum(len(names) > 1 for names in id_names.values()),
            "names_with_multiple_product_ids": sum(len(ids) > 1 for ids in name_ids.values()),
            "model_item_key": MODEL_ITEM_KEY,
        },
        "numeric_fields": {
            "quantity_min": min(quantities) if quantities else None,
            "quantity_max": max(quantities) if quantities else None,
            "quantity_total": sum(quantities),
            "nonpositive_quantities": sum(value <= 0 for value in quantities),
            "price_min": min(prices) if prices else None,
            "price_max": max(prices) if prices else None,
            "nonpositive_prices": sum(value <= 0 for value in prices),
        },
        "missing_counts": dict(missing),
        "missing_rates": {key: value / len(raw_rows) if raw_rows else 0.0 for key, value in missing.items()},
        "duplicates": {
            "exact_duplicate_extra_rows": sum(count - 1 for count in exact.values()),
            "repeated_order_source_product_pairs": sum(count > 1 for count in repeated_source_pair.values()),
            "repeated_order_normalized_name_pairs": sum(count > 1 for count in repeated_name_pair.values()),
            "repeated_order_normalized_name_extra_rows": sum(count - 1 for count in repeated_name_pair.values() if count > 1),
        },
        "provenance_classification": "unknown",
        "provenance_note": "No source, acquisition, generator, or license record was found in component3.",
        "reject_samples": rejects[:20],
    }


def reconstruct_baskets(lines: Iterable[TransactionLine]) -> tuple[list[Basket], list[dict[str, object]]]:
    """Group consistent orders and aggregate repeated normalized-name line items."""
    orders: dict[str, list[TransactionLine]] = defaultdict(list)
    for line in lines:
        orders[line.order_id].append(line)
    baskets: list[Basket] = []
    excluded: list[dict[str, object]] = []
    for order_id, order_lines in orders.items():
        users = {line.user_id for line in order_lines}
        timestamps = {line.timestamp for line in order_lines}
        if len(users) != 1 or len(timestamps) != 1:
            excluded.append({
                "basket_id": order_id, "reason": "inconsistent_order_identity_or_timestamp",
                "user_count": len(users), "timestamp_count": len(timestamps),
            })
            continue
        grouped: dict[str, list[TransactionLine]] = defaultdict(list)
        for line in order_lines:
            grouped[item_key(line.product_name)].append(line)
        items: list[BasketItem] = []
        for key, item_lines in sorted(grouped.items()):
            names = {line.product_name for line in item_lines}
            categories = {line.category for line in item_lines}
            if len(names) != 1 or len(categories) != 1:
                excluded.append({"basket_id": order_id, "item_key": key, "reason": "ambiguous_normalized_name"})
                items = []
                break
            items.append(BasketItem(
                item_key=key, product_name=next(iter(names)), category=next(iter(categories)),
                quantity=sum(line.quantity for line in item_lines),
                source_product_ids=tuple(sorted({line.source_product_id for line in item_lines})),
                line_count=len(item_lines),
            ))
        if len(items) < 2:
            excluded.append({"basket_id": order_id, "reason": "fewer_than_two_valid_items"})
            continue
        baskets.append(Basket(
            basket_id=order_id, timestamp=next(iter(timestamps)),
            source_user_id=next(iter(users)), items=tuple(items), source_line_count=len(order_lines),
        ))
    baskets.sort(key=lambda basket: (basket.timestamp, basket.basket_id))
    return baskets, excluded


def chronological_split(
    baskets: Sequence[Basket], train_fraction: float = 0.70, validation_fraction: float = 0.15,
) -> SplitResult:
    """Chronologically split baskets and purge later duplicate basket signatures."""
    if not baskets or not 0 < train_fraction < 1 or not 0 < validation_fraction < 1:
        raise ValueError("non-empty baskets and fractions between zero and one are required")
    if train_fraction + validation_fraction >= 1:
        raise ValueError("train and validation fractions must leave a test partition")
    ordered = sorted(baskets, key=lambda basket: (basket.timestamp, basket.basket_id))
    train_stop = int(len(ordered) * train_fraction)
    validation_stop = int(len(ordered) * (train_fraction + validation_fraction))
    raw_parts = [ordered[:train_stop], ordered[train_stop:validation_stop], ordered[validation_stop:]]
    seen: set[tuple[str, ...]] = set()
    clean_parts: list[list[Basket]] = []
    purged: list[str] = []
    for part in raw_parts:
        clean: list[Basket] = []
        for basket in part:
            if basket.signature in seen:
                purged.append(basket.basket_id)
            else:
                clean.append(basket)
        seen.update(basket.signature for basket in clean)
        clean_parts.append(clean)
    return SplitResult(
        train=tuple(clean_parts[0]), validation=tuple(clean_parts[1]), test=tuple(clean_parts[2]),
        purged_duplicate_basket_ids=tuple(purged),
        train_end=ordered[train_stop - 1].timestamp.isoformat(),
        validation_end=ordered[validation_stop - 1].timestamp.isoformat(),
    )


def basket_completion_case(basket: Basket, seed: int) -> tuple[tuple[str, ...], str]:
    """Hide exactly one deterministic target; it cannot occur in the observed input."""
    keys = list(basket.signature)
    if len(keys) < 2:
        raise ValueError("basket completion requires at least two distinct items")
    digest = hashlib.sha256(f"{seed}:{basket.basket_id}".encode()).digest()
    target_index = int.from_bytes(digest[:8], "big") % len(keys)
    target = keys.pop(target_index)
    return tuple(keys), target


def category_by_item(baskets: Sequence[Basket]) -> dict[str, str]:
    result: dict[str, str] = {}
    for basket in baskets:
        for item in basket.items:
            previous = result.setdefault(item.item_key, item.category)
            if previous != item.category:
                raise ValueError(f"item category changed for {item.item_key}")
    return result
