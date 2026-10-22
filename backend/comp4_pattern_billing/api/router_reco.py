"""Authenticated Component 4 recommendations endpoint."""

import importlib.util
from pathlib import Path
from functools import lru_cache

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from auth_router import current_user
from auth_models import User

router = APIRouter(tags=["Component 4 Recommendations"])
# router_reco.py is in <repo>/comp4_pattern_billing/api/.
REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_SCRIPT = REPO_ROOT / "ml" / "recommend_comp4.py"


@lru_cache(maxsize=1)
def load_recommender():
    """Load the repository's existing recommendation implementation on demand.

    Loading lazily lets authentication and catalogue endpoints start even when the
    model script is not present. The recommendation endpoint returns a clear 503
    until that implementation is supplied.
    """
    if not MODEL_SCRIPT.is_file():
        raise FileNotFoundError(
            f"Recommendation script not found: {MODEL_SCRIPT}. "
            "Restore ml/recommend_comp4.py or update MODEL_SCRIPT to your trained model's inference script."
        )
    spec = importlib.util.spec_from_file_location("comp4_recommendation_module", MODEL_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load recommendation script: {MODEL_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "recommend_products"):
        raise RuntimeError("The recommendation script must expose recommend_products(customer_id, recommendation_date, top_n).")
    return module.recommend_products


@router.get("/recommendations/{customer_id}")
def get_recommendations(
    customer_id: str,
    recommendation_date: str | None = Query(default=None, description="Optional date in YYYY-MM-DD format"),
    top_n: int = Query(default=5, ge=1, le=20),
    user: User = Depends(current_user),
):
    """Return recommendations only for the authenticated customer's own account."""
    if not user.customer_id or user.customer_id.casefold() != customer_id.casefold():
        raise HTTPException(status_code=403, detail="You can only access recommendations for your own customer account.")

    try:
        recommend_products = load_recommender()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="The recommendation model could not be loaded.") from exc

    try:
        results = recommend_products(
            customer_id=user.customer_id,
            recommendation_date=recommendation_date,
            top_n=top_n,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Recommendation generation failed. Check the backend terminal.") from exc

    if results is None or results.empty:
        raise HTTPException(status_code=404, detail="No purchase-history recommendations are available for this customer yet.")

    recommendations = results.astype(object).where(pd.notna(results), None).to_dict(orient="records")
    return {"customer_id": user.customer_id, "recommendations": recommendations}
