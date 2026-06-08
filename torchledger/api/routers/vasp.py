"""VASP attribution router — /v1/vasp"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel

from ingestion.vasp.attribution import VASPAttribution, VASPAttributionEngine

router = APIRouter()
_engine = VASPAttributionEngine()


class VASPResponse(BaseModel):
    address: str
    vasp_name: str | None
    vasp_type: str
    confidence: float
    method: str
    evidence: list[str]
    jurisdiction: str | None
    risk_flags: list[str]
    is_regulated: bool


class ClusterFingerprintRequest(BaseModel):
    addresses: list[str]
    chain: str = "evm"


def _to_response(attr: VASPAttribution) -> VASPResponse:
    return VASPResponse(
        address=attr.address, vasp_name=attr.vasp_name,
        vasp_type=str(attr.vasp_type), confidence=round(attr.confidence, 4),
        method=str(attr.method), evidence=attr.evidence,
        jurisdiction=attr.jurisdiction, risk_flags=attr.risk_flags,
        is_regulated=attr.is_regulated,
    )


@router.get("/{address}", response_model=VASPResponse)
async def get_vasp_attribution(
    address: str = Path(description="EVM / Solana / BTC address"),
    chain: str = Query(default="evm"),
) -> VASPResponse:
    """
    Identify which VASP an address belongs to.
    4-layer pipeline: known DB → deposit pattern → withdrawal pattern → ML classifier.
    """
    try:
        return _to_response(await _engine.attribute(address, chain=chain))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/batch", response_model=list[VASPResponse])
async def batch_vasp_attribution(
    addresses: list[str], chain: str = "evm"
) -> list[VASPResponse]:
    """Attribute up to 1000 addresses in one call."""
    if len(addresses) > 1000:
        raise HTTPException(status_code=400, detail="Max 1000 addresses per batch")
    return [_to_response(r) for r in await _engine.batch_attribute(addresses, chain=chain)]


@router.post("/fingerprint-cluster")
async def fingerprint_cluster(req: ClusterFingerprintRequest) -> dict:
    """Determine if a cluster of addresses collectively forms a known exchange entity."""
    if len(req.addresses) > 1000:
        raise HTTPException(status_code=400, detail="Max 1000 addresses")
    return await _engine.fingerprint_exchange(req.addresses, chain=req.chain)