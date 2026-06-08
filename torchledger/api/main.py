"""TorchLedger API — entry point."""
from __future__ import annotations

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from api.routers import address, alert, risk, trace, vasp
from api.routers.graphql import graphql_router

logger = structlog.get_logger()

app = FastAPI(
    title="TorchLedger",
    description="On-chain behavioral clustering & cross-chain risk tracing engine",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Metrics ───────────────────────────────────────────────────────────────────
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(address.router, prefix="/v1/address", tags=["address"])
app.include_router(trace.router, prefix="/v1/trace", tags=["trace"])
app.include_router(risk.router, prefix="/v1/risk", tags=["risk"])
app.include_router(alert.router, prefix="/v1/alert", tags=["alert"])
app.include_router(graphql_router, prefix="/graphql")
app.include_router(vasp.router, prefix="/v1/vasp", tags=["vasp"])


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}
