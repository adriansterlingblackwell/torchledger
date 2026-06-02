"""Pydantic schemas for trace API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TraceRequest(BaseModel):
    origin: str = Field(description="Source address or tx hash")
    chain: str = Field(default="evm", description="evm|solana|btc")
    max_hops: int = Field(default=4, ge=1, le=8)
    follow_bridges: bool = Field(default=True)
    min_value_usd: float = Field(default=0.0, ge=0)


class TraceResult(BaseModel):
    origin: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    hop_count: int
    crossed_chains: list[str] = []
    touched_mixer: bool = False
    touched_bridge: bool = False
