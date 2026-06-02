"""
Risk scoring pipeline.

Combines:
 - LightGBM model trained on labeled entity-level features
 - Deterministic OFAC / FATF rule overlay
 - SHAP explainability
"""
from __future__ import annotations

import asyncio
import hashlib
from functools import lru_cache
from pathlib import Path

import lightgbm as lgb
import numpy as np
import structlog

from api.schemas.risk import ExposureItem, RiskLabel, RiskReport, RiskSummary, ShapFeature

logger = structlog.get_logger()

MODEL_PATH = Path(__file__).parent / "ml" / "risk_model.lgb"

# Sanctioned addresses (stub — production loads from OFAC SDN list + TRM feed)
SANCTIONED_ADDRESSES: frozenset[str] = frozenset(
    [
        "0x7f268357a8c2552623316e2562d90e642bb538e5",  # example
        "0xd882cfc20f52f2599d84b8e8d58c7fb62cfe344b",
    ]
)

RISK_THRESHOLDS = {
    RiskLabel.LOW: 25,
    RiskLabel.MEDIUM: 50,
    RiskLabel.HIGH: 75,
    RiskLabel.SEVERE: 100,
}


def _label_from_score(score: int) -> RiskLabel:
    if score < 25:
        return RiskLabel.LOW
    if score < 50:
        return RiskLabel.MEDIUM
    if score < 75:
        return RiskLabel.HIGH
    return RiskLabel.SEVERE


@lru_cache(maxsize=1)
def _load_model() -> lgb.Booster | None:
    if MODEL_PATH.exists():
        return lgb.Booster(model_file=str(MODEL_PATH))
    logger.warning("risk_model_not_found", path=str(MODEL_PATH))
    return None


class RiskScorer:
    """
    Scores an address 0–100 using ML + hard rules.

    Feature vector (18 features):
     [0]  tx_count_30d
     [1]  unique_counterparties_30d
     [2]  mixer_exposure_ratio       # 0–1, fraction of volume through mixers
     [3]  cex_deposit_ratio          # 0–1
     [4]  darknet_hop_count          # integer, hops to darknet market
     [5]  bridge_usage_count         # cross-chain bridge calls
     [6]  ofac_direct                # 1 if direct interaction with sanctioned
     [7]  ofac_1hop                  # 1 if 1-hop from sanctioned
     [8]  cluster_size               # size of entity cluster
     [9]  cluster_risk_max           # max risk in cluster
     [10] timing_entropy             # Shannon entropy of tx timing
     [11] value_variance_log         # log-variance of tx values
     [12] fee_anomaly_score          # deviation from normal fee pattern
     [13] contract_deploy_count      # number of deployed contracts
     [14] nft_volume_ratio           # NFT vol / total vol
     [15] defi_protocol_count        # unique DeFi protocols interacted with
     [16] account_age_days           # age of account
     [17] dormancy_score             # recent activity after long dormancy
    """

    def __init__(self) -> None:
        self._model = _load_model()

    async def score(
        self,
        address: str,
        chain: str = "evm",
        explain: bool = False,
    ) -> RiskReport:
        address_lower = address.lower()

        # Hard override: sanctioned address
        if address_lower in SANCTIONED_ADDRESSES:
            return RiskReport(
                address=address,
                chain=chain,
                score=99,
                label=RiskLabel.SANCTIONED,
                exposures=[
                    ExposureItem(
                        entity_name="OFAC SDN List",
                        category="sanctions",
                        direction="self",
                        hop_distance=0,
                    )
                ],
            )

        # Fetch features (stub — production fetches from ClickHouse + Neo4j)
        features = await self._fetch_features(address_lower, chain)
        score = self._predict(features)

        shap_features = None
        if explain and self._model is not None:
            shap_features = self._explain(features)

        return RiskReport(
            address=address,
            chain=chain,
            score=score,
            label=_label_from_score(score),
            exposures=await self._fetch_exposures(address_lower, chain),
            shap_features=shap_features,
        )

    async def batch_score(
        self, addresses: list[str], chain: str = "evm"
    ) -> list[RiskSummary]:
        results = await asyncio.gather(
            *[self.score(addr, chain=chain) for addr in addresses],
            return_exceptions=True,
        )
        summaries = []
        for addr, result in zip(addresses, results, strict=True):
            if isinstance(result, Exception):
                summaries.append(RiskSummary(address=addr, score=0, label=RiskLabel.LOW))
            else:
                summaries.append(
                    RiskSummary(address=addr, score=result.score, label=result.label)
                )
        return summaries

    def _predict(self, features: np.ndarray) -> int:
        if self._model is None:
            # Fallback: simple rule-based score when model not loaded
            return self._rule_score(features)

        raw = float(self._model.predict(features.reshape(1, -1))[0])
        return max(0, min(100, int(raw * 100)))

    def _rule_score(self, features: np.ndarray) -> int:
        """Deterministic fallback using hard rules."""
        score = 0
        if features[6] > 0:   # ofac_direct
            score += 60
        if features[7] > 0:   # ofac_1hop
            score += 25
        if features[2] > 0.3: # mixer_exposure > 30%
            score += 20
        if features[4] > 2:   # darknet hops
            score += 15
        return min(score, 99)

    def _explain(self, features: np.ndarray) -> list[ShapFeature]:
        import shap  # lazy import
        explainer = shap.TreeExplainer(self._model)
        shap_vals = explainer.shap_values(features.reshape(1, -1))[0]
        feature_names = [
            "tx_count_30d", "unique_counterparties_30d", "mixer_exposure_ratio",
            "cex_deposit_ratio", "darknet_hop_count", "bridge_usage_count",
            "ofac_direct", "ofac_1hop", "cluster_size", "cluster_risk_max",
            "timing_entropy", "value_variance_log", "fee_anomaly_score",
            "contract_deploy_count", "nft_volume_ratio", "defi_protocol_count",
            "account_age_days", "dormancy_score",
        ]
        return [
            ShapFeature(feature=name, contribution=float(val), value=float(features[i]))
            for i, (name, val) in enumerate(zip(feature_names, shap_vals, strict=True))
        ]

    async def _fetch_features(self, address: str, chain: str) -> np.ndarray:
        """Fetch 18-dim feature vector. Stub returns deterministic mock."""
        seed = int(hashlib.md5(address.encode()).hexdigest()[:8], 16)  # noqa: S324
        rng = np.random.default_rng(seed)
        return rng.uniform(0, 1, 18).astype(np.float32)

    async def _fetch_exposures(self, address: str, chain: str) -> list[ExposureItem]:
        """Fetch known exposure items from Neo4j. Stub returns empty list."""
        return []
