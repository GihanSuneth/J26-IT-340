
"""Local FastAPI entry point for Component 4."""

from fastapi import FastAPI
from api.router_reco import router as recommendation_router

app = FastAPI(title="Component 4 - Smart Shopping Recommendations")

app.include_router(
    recommendation_router,
    prefix="/c4",
)


@app.get("/health")
def health_check():
    return {"status": "ok", "component": "comp4"}
