"""
torchledger-py — Python SDK for the TorchLedger API.

Usage:
    from torchledger import TorchLedger

    client = TorchLedger(api_key="tl_live_...")
    report = client.risk.get("0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045")
    print(report.score, report.label)

    # Batch
    reports = client.risk.batch(["0xabc...", "0xdef..."])

    # Trace
    trace = client.trace.from_address("0xabc...", max_hops=4)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import httpx


class RiskLabel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    SEVERE = "severe"
    SANCTIONED = "sanctioned"


@dataclass
class RiskReport:
    address: str
    chain: str
    score: int
    label: RiskLabel
    exposures: list[dict[str, Any]]
    cluster_id: str | None
    entity_name: str | None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RiskReport":
        return cls(
            address=d["address"],
            chain=d["chain"],
            score=d["score"],
            label=RiskLabel(d["label"]),
            exposures=d.get("exposures", []),
            cluster_id=d.get("cluster_id"),
            entity_name=d.get("entity_name"),
        )

    @property
    def is_high_risk(self) -> bool:
        return self.score >= 50


@dataclass
class TraceResult:
    origin: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    hop_count: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TraceResult":
        return cls(
            origin=d["origin"],
            nodes=d.get("nodes", []),
            edges=d.get("edges", []),
            hop_count=d.get("hop_count", 0),
        )


class RiskClient:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def get(
        self,
        address: str,
        chain: str = "evm",
        explain: bool = False,
    ) -> RiskReport:
        r = self._http.get(
            f"/v1/risk/{address}",
            params={"chain": chain, "explain": explain},
        )
        r.raise_for_status()
        return RiskReport.from_dict(r.json())

    def batch(
        self,
        addresses: list[str],
        chain: str = "evm",
    ) -> list[RiskReport]:
        r = self._http.post(
            "/v1/risk/batch",
            params={"chain": chain},
            json=addresses,
        )
        r.raise_for_status()
        return [RiskReport.from_dict(item) for item in r.json()]


class TraceClient:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def from_address(
        self,
        address: str,
        chain: str = "evm",
        max_hops: int = 4,
        follow_bridges: bool = True,
    ) -> TraceResult:
        r = self._http.post(
            "/v1/trace/",
            json={
                "origin": address,
                "chain": chain,
                "max_hops": max_hops,
                "follow_bridges": follow_bridges,
            },
        )
        r.raise_for_status()
        return TraceResult.from_dict(r.json())


class TorchLedger:
    """
    TorchLedger API client.

    Args:
        api_key: Your TorchLedger API key (env: TORCHLEDGER_API_KEY)
        base_url: API base URL (default: https://api.torchledger.io)
        timeout: Request timeout in seconds
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.torchledger.io",
        timeout: float = 30.0,
    ) -> None:
        key = api_key or os.environ.get("TORCHLEDGER_API_KEY")
        if not key:
            raise ValueError(
                "api_key is required. Set TORCHLEDGER_API_KEY env var or pass api_key="
            )
        self._http = httpx.Client(
            base_url=base_url,
            headers={"X-API-Key": key, "User-Agent": "torchledger-py/0.1.0"},
            timeout=timeout,
        )
        self.risk = RiskClient(self._http)
        self.trace = TraceClient(self._http)

    def __enter__(self) -> "TorchLedger":
        return self

    def __exit__(self, *args: Any) -> None:
        self._http.close()
