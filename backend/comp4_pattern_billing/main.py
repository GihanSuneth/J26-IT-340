
"""Local FastAPI entry point for Component 4."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router_reco import router as recommendation_router

app = FastAPI(
    title="Component 4 - Smart Shopping Recommendations"
)

# Allow the local React development server to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(
    recommendation_router,
    prefix="/c4",
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "component": "comp4",
    }
