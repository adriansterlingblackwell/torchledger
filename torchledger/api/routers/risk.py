"""Risk scoring router — /v1/risk/{address}"""
from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Path, Query

from api.schemas.risk import RiskReport, RiskSummary
from risk.scorer import RiskScorer

logger = structlog.get_logger()
router = APIRouter()
_scorer = RiskScorer()


@router.get("/{address}", response_model=RiskReport)
async def get_risk(
    address: Annotated[str, Path(description="EVM/Solana/BTC address or tx hash")],
    chain: Annotated[str, Query(description="evm|solana|btc")] = "evm",
    explain: bool = False,
) -> RiskReport:
    """
    Return FATF-aligned risk score (0–100) for an address.

    - **0–24**: Low risk — no exposure to illicit counterparties
    - **25–49**: Medium — indirect hops to flagged entities
    - **50–74**: High — direct interaction with sanctioned / mixer addresses
    - **75–100**: Severe — address IS sanctioned or is a known exploit wallet
    """
    log = logger.bind(address=address, chain=chain)
    try:
        report = await _scorer.score(address, chain=chain, explain=explain)
        log.info("risk_scored", score=report.score, label=report.label)
        return report
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        log.error("risk_score_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Scoring failed") from exc


@router.post("/batch", response_model=list[RiskSummary])
async def batch_risk(
    addresses: list[str],
    chain: str = "evm",
) -> list[RiskSummary]:
    """Score up to 500 addresses in one call."""
    if len(addresses) > 500:
        raise HTTPException(status_code=400, detail="Max 500 addresses per batch")
    return await _scorer.batch_score(addresses, chain=chain)
