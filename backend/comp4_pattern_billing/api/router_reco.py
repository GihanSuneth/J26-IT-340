
"""Routes for Component 4 personalized recommendations."""

import importlib.util
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

# Find the repository root: J26-IT-340/
REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_SCRIPT = REPO_ROOT / "ml" / "recommend_comp4.py"

if not MODEL_SCRIPT.is_file():
    raise RuntimeError(f"Recommendation script not found: {MODEL_SCRIPT}")

# Load the existing recommendation script directly by file path.
spec = importlib.util.spec_from_file_location(
    "comp4_recommendation_module",
    MODEL_SCRIPT,
)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot load recommendation script: {MODEL_SCRIPT}")

recommendation_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recommendation_module)

recommend_products = recommendation_module.recommend_products

router = APIRouter(tags=["Component 4 Recommendations"])


@router.get("/recommendations/{customer_id}")
def get_recommendations(
    customer_id: str,
    recommendation_date: str | None = Query(
        default=None,
        description="Optional date in YYYY-MM-DD format",
    ),
    top_n: int = Query(default=5, ge=1, le=20),
):
    """Return history-based recommendations for a customer."""

    try:
        results = recommend_products(
            customer_id=customer_id,
            recommendation_date=recommendation_date,
            top_n=top_n,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Recommendation generation failed. Check the backend terminal.",
        ) from exc

    if results.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No purchase history found for customer {customer_id}.",
        )

    # Convert Pandas and NumPy values into JSON-compatible values.
    recommendations = results.astype(object).where(
        pd.notna(results), None
    ).to_dict(orient="records")

    return {
        "customer_id": customer_id,
        "recommendations": recommendations,
    }
