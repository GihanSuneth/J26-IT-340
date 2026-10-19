"""Product catalogue endpoints for Component 4."""
from pathlib import Path
from functools import lru_cache

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()
REPO_ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = REPO_ROOT / "data" / "catalogues" / "sri_lankan_grocery_dataset.xlsx"

REQUIRED_COLUMNS = {
    "Item_ID", "Item_Name", "Category", "Price_LKR", "Stock_Status"
}


@lru_cache(maxsize=1)
def load_catalogue():
    if not CATALOG_PATH.exists():
        raise RuntimeError(
            f"Catalogue file not found: {CATALOG_PATH}. "
            "Place sri_lankan_grocery_dataset.xlsx in data/catalogues/."
        )

    frame = pd.read_excel(CATALOG_PATH, sheet_name="Grocery Dataset")
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise RuntimeError(f"Catalogue is missing required columns: {sorted(missing)}")

    frame = frame.copy()
    frame["Item_ID"] = frame["Item_ID"].astype(str).str.strip()
    frame["Item_Name"] = frame["Item_Name"].fillna("").astype(str).str.strip()
    frame["Category"] = frame["Category"].fillna("Uncategorized").astype(str).str.strip()
    frame["Stock_Status"] = frame["Stock_Status"].fillna("Unknown").astype(str).str.strip()
    frame["Price_LKR"] = pd.to_numeric(frame["Price_LKR"], errors="coerce")
    frame = frame.drop_duplicates(subset=["Item_ID"], keep="first")
    return frame


def product_record(row):
    price = None if pd.isna(row["Price_LKR"]) else float(row["Price_LKR"])
    return {
        "id": row["Item_ID"],
        "name": row["Item_Name"],
        "category": row["Category"],
        "price": price,
        "brand": str(row.get("Brand", "") or ""),
        "aisle": str(row.get("Aisle", "") or ""),
        "stock_status": row["Stock_Status"],
        "available": row["Stock_Status"].strip().lower() == "available",
    }


@router.get("/catalog/categories")
def get_categories():
    frame = load_catalogue()
    categories = sorted(
        category for category in frame["Category"].dropna().unique().tolist()
        if str(category).strip()
    )
    return {"categories": categories}


@router.get("/catalog/products")
def get_products(
    category: str | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    available_only: bool = Query(default=False),
):
    frame = load_catalogue()
    if category:
        frame = frame[frame["Category"].str.casefold() == category.strip().casefold()]
    if search:
        needle = search.strip().casefold()
        frame = frame[
            frame["Item_Name"].str.casefold().str.contains(needle, regex=False)
            | frame["Item_ID"].str.casefold().str.contains(needle, regex=False)
        ]
    if available_only:
        frame = frame[frame["Stock_Status"].str.casefold() == "available"]
    products = [product_record(row) for _, row in frame.sort_values("Item_Name").iterrows()]
    return {"count": len(products), "products": products}


@router.get("/catalog/products/{product_id}")
def get_product(product_id: str):
    frame = load_catalogue()
    matches = frame[frame["Item_ID"].str.casefold() == product_id.strip().casefold()]
    if matches.empty:
        raise HTTPException(status_code=404, detail="Product not found in catalogue")
    return product_record(matches.iloc[0])
