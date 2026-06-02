"""Pydantic v2 schemas for risk scoring API."""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RiskLabel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    SEVERE = "severe"
    SANCTIONED = "sanctioned"


class ExposureItem(BaseModel):
    entity_name: str
    category: str  # e.g. "mixer", "exchange", "darknet"
    direction: str  # "sent_to" | "received_from"
    hop_distance: int
    value_usd: float | None = None


class ShapFeature(BaseModel):
    feature: str
    contribution: float
    value: Any


class RiskReport(BaseModel):
    address: str
    chain: str
    score: int = Field(ge=0, le=100)
    label: RiskLabel
    exposures: list[ExposureItem] = []
    cluster_id: str | None = None
    entity_name: str | None = None
    last_seen_block: int | None = None
    # SHAP explanation (only when explain=True)
    shap_features: list[ShapFeature] | None = None
    model_version: str = "v0.1"

    @property
    def is_high_risk(self) -> bool:
        return self.score >= 50


class RiskSummary(BaseModel):
    address: str
    score: int
    label: RiskLabel
