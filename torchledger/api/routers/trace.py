"""Cross-chain trace router — /v1/trace"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.schemas.trace import TraceRequest, TraceResult
from tracing.engine import TraceEngine

router = APIRouter()
_engine = TraceEngine()


@router.post("/", response_model=TraceResult)
async def trace_funds(req: TraceRequest) -> TraceResult:
    """
    Trace fund flow from a source address or tx hash across chains.

    Follows bridges (Wormhole, LayerZero, Axelar, Stargate),
    mixers (Tornado Cash, Railgun), and DEX hops.
    Returns a path graph with hop-level metadata.
    """
    try:
        return await _engine.trace(
            origin=req.origin,
            chain=req.chain,
            max_hops=req.max_hops,
            follow_bridges=req.follow_bridges,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/entity/{entity_id}", response_model=TraceResult)
async def trace_entity(
    entity_id: str,
    depth: int = Query(default=3, le=6),
) -> TraceResult:
    """Trace all known addresses associated with a clustered entity."""
    return await _engine.trace_entity(entity_id, depth=depth)
