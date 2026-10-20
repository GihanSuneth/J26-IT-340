
"""Local FastAPI entry point for Component 4."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router_reco import router as recommendation_router
from api.router_catalog import router as catalogue_router

from auth_database import Base, engine
from auth_models import User
from auth_router import router as auth_router

app = FastAPI(title="Component 4 - Smart Shopping Recommendations")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create missing authentication tables.
# This does not delete existing data.
Base.metadata.create_all(bind=engine)

# Existing Component 4 APIs — preserved.
app.include_router(recommendation_router, prefix="/c4")
app.include_router(catalogue_router, prefix="/c4")

# New authentication APIs.
app.include_router(auth_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "component": "comp4"}
