"""
VASP Attribution Engine
=======================
Identifies Virtual Asset Service Providers (VASPs) from on-chain behavioral
fingerprints — without relying solely on address allowlists.

Strategy layers (applied in order, first match wins):
  1. Known address database    — direct lookup against curated VASP address list
  2. Deposit pattern heuristic — high fan-in, consolidation to cold storage
  3. Withdrawal pattern heuristic — high fan-out, round-amount outputs
  4. ML classifier             — LightGBM on 12 behavioral features

Output: VASPAttribution with name, type, confidence, and evidence chain.
"""
from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger()


# ── VASP type taxonomy ────────────────────────────────────────────────────────

class VASPType(StrEnum):
    CEX           = "centralized_exchange"
    DEX           = "decentralized_exchange"
    BRIDGE        = "bridge"
    MIXER         = "mixer"
    GAMBLING      = "gambling"
    PAYMENT       = "payment_processor"
    DARKNET       = "darknet_market"
    DEFI_PROTOCOL = "defi_protocol"
    NFT_PLATFORM  = "nft_platform"
    MINING_POOL   = "mining_pool"
    OTC_DESK      = "otc_desk"
    UNKNOWN       = "unknown"


class AttributionMethod(StrEnum):
    KNOWN_ADDRESS    = "known_address_db"
    DEPOSIT_PATTERN  = "deposit_pattern"
    WITHDRAW_PATTERN = "withdrawal_pattern"
    CLUSTER_LINK     = "cluster_hotcold_link"
    ML_CLASSIFIER    = "ml_classifier"
    COMBINED         = "combined"


@dataclass
class VASPAttribution:
    address: str
    vasp_name: str | None
    vasp_type: VASPType
    confidence: float
    method: AttributionMethod
    evidence: list[str] = field(default_factory=list)
    related_addresses: list[str] = field(default_factory=list)
    jurisdiction: str | None = None
    risk_flags: list[str] = field(default_factory=list)

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.80

    @property
    def is_regulated(self) -> bool:
        return self.vasp_type == VASPType.CEX and self.confidence >= 0.70


# ── Known VASP address database ───────────────────────────────────────────────

KNOWN_VASP_ADDRESSES: dict[str, dict[str, Any]] = {
    "0x28c6c06298d514db089934071355e5743bf21d60": {
        "name": "Binance",
        "type": VASPType.CEX,
        "jurisdiction": "Cayman Islands",
        "confidence": 0.99,
    },
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": {
        "name": "Binance",
        "type": VASPType.CEX,
        "jurisdiction": "Cayman Islands",
        "confidence": 0.99,
    },
    "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43": {
        "name": "Coinbase",
        "type": VASPType.CEX,
        "jurisdiction": "United States",
        "confidence": 0.99,
    },
    "0x2910543af39aba0cd09dbb2d50200b3e800a63d2": {
        "name": "Kraken",
        "type": VASPType.CEX,
        "jurisdiction": "United States",
        "confidence": 0.98,
    },
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": {
        "name": "OKX",
        "type": VASPType.CEX,
        "jurisdiction": "Seychelles",
        "confidence": 0.97,
    },
    "0xe592427a0aece92de3edee1f18e0157c05861564": {
        "name": "Uniswap v3",
        "type": VASPType.DEX,
        "jurisdiction": None,
        "confidence": 0.99,
    },
    "0x3ee18b2214aff97000d974cf647e7c347e8fa585": {
        "name": "Wormhole Token Bridge",
        "type": VASPType.BRIDGE,
        "jurisdiction": None,
        "confidence": 0.99,
    },
    "0xd90e2f925da726b50c4ed8d0fb90ad053324f31b": {
        "name": "Tornado Cash 0.1 ETH",
        "type": VASPType.MIXER,
        "jurisdiction": None,
        "confidence": 0.99,
        "risk_flags": ["OFAC_SANCTIONED", "MIXER"],
    },
    "0x910cbd523d972eb0a6f4cae4618ad62622b39dbf": {
        "name": "Tornado Cash 1 ETH",
        "type": VASPType.MIXER,
        "jurisdiction": None,
        "confidence": 0.99,
        "risk_flags": ["OFAC_SANCTIONED", "MIXER"],
    },
    "0x4d37f028d6c5b0b007d5e2d5b7faa1e0a33c1bd8": {
        "name": "Rollbit",
        "type": VASPType.GAMBLING,
        "jurisdiction": "Curacao",
        "confidence": 0.92,
        "risk_flags": ["GAMBLING"],
    },
}


# ── Behavioral features ───────────────────────────────────────────────────────

@dataclass
class BehavioralFeatures:
    address: str
    daily_tx_count: float
    unique_senders_ratio: float
    unique_receivers_ratio: float
    round_amount_ratio: float
    consolidation_ratio: float
    tx_hour_entropy: float
    weekend_activity: float
    address_reuse_rate: float
    contract_interaction_ratio: float
    erc20_transfer_ratio: float
    native_transfer_ratio: float
    betweenness_centrality: float


# ── Heuristic detectors ───────────────────────────────────────────────────────

class DepositPatternDetector:
    """
    CEX deposit addresses receive from many unique senders,
    then consolidate to a smaller set of cold/hot wallets.
    """

    def detect(self, f: BehavioralFeatures) -> tuple[bool, float, list[str]]:
        evidence: list[str] = []
        score = 0.0

        if f.unique_senders_ratio > 0.80:
            score += 0.35
            evidence.append(f"High unique sender ratio: {f.unique_senders_ratio:.0%}")

        if f.consolidation_ratio > 0.60:
            score += 0.30
            evidence.append(f"High consolidation ratio: {f.consolidation_ratio:.0%}")

        if f.address_reuse_rate < 0.15:
            score += 0.20
            evidence.append("Low address reuse — deposit address rotation pattern")

        if f.daily_tx_count > 50:
            score += 0.15
            evidence.append(f"High daily tx volume: {f.daily_tx_count:.0f} tx/day")

        return score >= 0.55, min(score, 1.0), evidence


class WithdrawalPatternDetector:
    """
    CEX withdrawal addresses send to many unique receivers,
    often with round amounts and high ERC-20 transfer ratios.
    """

    def detect(self, f: BehavioralFeatures) -> tuple[bool, float, list[str]]:
        evidence: list[str] = []
        score = 0.0

        if f.unique_receivers_ratio > 0.75:
            score += 0.35
            evidence.append(f"High unique receiver ratio: {f.unique_receivers_ratio:.0%}")

        if f.round_amount_ratio > 0.40:
            score += 0.25
            evidence.append(f"Round amount ratio: {f.round_amount_ratio:.0%}")

        if f.erc20_transfer_ratio > 0.60:
            score += 0.20
            evidence.append("Predominantly ERC-20 transfers — exchange withdrawal pattern")

        if f.tx_hour_entropy > 3.5:
            score += 0.20
            evidence.append("24/7 activity — automated withdrawal queue")

        return score >= 0.55, min(score, 1.0), evidence


# ── ML classifier ─────────────────────────────────────────────────────────────

class VASPClassifier:
    """
    LightGBM multi-class classifier predicting VASPType.
    Falls back to heuristics when model file is not present.
    """

    VASP_TYPES = [
        VASPType.CEX, VASPType.DEX, VASPType.BRIDGE, VASPType.MIXER,
        VASPType.GAMBLING, VASPType.PAYMENT, VASPType.DARKNET,
        VASPType.DEFI_PROTOCOL, VASPType.NFT_PLATFORM,
        VASPType.MINING_POOL, VASPType.OTC_DESK, VASPType.UNKNOWN,
    ]

    def __init__(self) -> None:
        self._model: Any = None
        model_path = Path(__file__).parent / "vasp_classifier.lgb"
        if model_path.exists():
            import lightgbm as lgb
            self._model = lgb.Booster(model_file=str(model_path))

    def predict(self, f: BehavioralFeatures) -> tuple[VASPType, float]:
        if self._model is None:
            return self._fallback(f)

        vec = np.array([
            f.daily_tx_count, f.unique_senders_ratio, f.unique_receivers_ratio,
            f.round_amount_ratio, f.consolidation_ratio, f.tx_hour_entropy,
            f.weekend_activity, f.address_reuse_rate, f.contract_interaction_ratio,
            f.erc20_transfer_ratio, f.native_transfer_ratio, f.betweenness_centrality,
        ], dtype=np.float32)

        raw = self._model.predict(vec.reshape(1, -1))
        probs: np.ndarray = np.asarray(raw, dtype=np.float64)
        idx = int(np.argmax(probs[0]))
        return self.VASP_TYPES[idx], float(probs[0][idx])

    def _fallback(self, f: BehavioralFeatures) -> tuple[VASPType, float]:
        if f.unique_senders_ratio > 0.8 and f.consolidation_ratio > 0.6:
            return VASPType.CEX, 0.65
        if f.contract_interaction_ratio > 0.90:
            return VASPType.DEX, 0.60
        if f.betweenness_centrality > 0.85:
            return VASPType.BRIDGE, 0.55
        return VASPType.UNKNOWN, 0.30


# ── Main attribution engine ───────────────────────────────────────────────────

class VASPAttributionEngine:
    """
    Multi-layer VASP attribution engine.

    Usage:
        engine = VASPAttributionEngine()
        result = await engine.attribute("0xd8dA6BF26...")
        print(result.vasp_name, result.vasp_type, result.confidence)
    """

    def __init__(self) -> None:
        self._deposit = DepositPatternDetector()
        self._withdrawal = WithdrawalPatternDetector()
        self._classifier = VASPClassifier()

    async def attribute(
        self,
        address: str,
        chain: str = "evm",
    ) -> VASPAttribution:
        addr = address.lower()

        # Layer 1: Known address database
        if addr in KNOWN_VASP_ADDRESSES:
            e = KNOWN_VASP_ADDRESSES[addr]
            logger.info("vasp_known_address", address=addr, vasp=e["name"])
            return VASPAttribution(
                address=address,
                vasp_name=e["name"],
                vasp_type=e["type"],
                confidence=e["confidence"],
                method=AttributionMethod.KNOWN_ADDRESS,
                evidence=[f"Found in curated VASP database: {e['name']}"],
                jurisdiction=e.get("jurisdiction"),
                risk_flags=e.get("risk_flags", []),
            )

        # Fetch behavioral features
        features = await self._fetch_features(addr, chain)

        # Layer 2 & 3: Heuristic detectors
        dep_match, dep_conf, dep_ev = self._deposit.detect(features)
        wd_match, wd_conf, wd_ev = self._withdrawal.detect(features)

        # Layer 4: ML classifier
        ml_type, ml_conf = self._classifier.predict(features)

        # Combine signals
        if dep_match or wd_match:
            combined_conf = max(dep_conf, wd_conf) * 0.6 + ml_conf * 0.4
            vasp_type = ml_type if ml_conf > 0.5 else VASPType.CEX
            logger.info(
                "vasp_heuristic_match",
                address=addr,
                dep_conf=dep_conf,
                wd_conf=wd_conf,
                ml_type=ml_type,
            )
            return VASPAttribution(
                address=address,
                vasp_name=None,
                vasp_type=vasp_type,
                confidence=min(combined_conf, 0.95),
                method=AttributionMethod.COMBINED,
                evidence=dep_ev + wd_ev,
                risk_flags=self._risk_flags(vasp_type, combined_conf),
            )

        # Layer 4 only
        logger.info("vasp_ml_only", address=addr, ml_type=ml_type, ml_conf=ml_conf)
        return VASPAttribution(
            address=address,
            vasp_name=None,
            vasp_type=ml_type,
            confidence=ml_conf,
            method=AttributionMethod.ML_CLASSIFIER,
            evidence=[f"ML classifier: {ml_type} ({ml_conf:.0%})"],
            risk_flags=self._risk_flags(ml_type, ml_conf),
        )

    async def batch_attribute(
        self,
        addresses: list[str],
        chain: str = "evm",
    ) -> list[VASPAttribution]:
        """Attribute up to 1000 addresses concurrently."""
        if len(addresses) > 1000:
            raise ValueError("Max 1000 addresses per batch")

        results = await asyncio.gather(
            *[self.attribute(a, chain=chain) for a in addresses],
            return_exceptions=True,
        )
        out: list[VASPAttribution] = []
        for addr, r in zip(addresses, results, strict=True):
            if isinstance(r, BaseException):
                logger.error("vasp_attribution_failed", address=addr, error=str(r))
                out.append(VASPAttribution(
                    address=addr,
                    vasp_name=None,
                    vasp_type=VASPType.UNKNOWN,
                    confidence=0.0,
                    method=AttributionMethod.ML_CLASSIFIER,
                    evidence=["Attribution failed"],
                ))
            elif isinstance(r, VASPAttribution):
                out.append(r)
        return out

    async def fingerprint_exchange(
        self,
        cluster_addresses: list[str],
        chain: str = "evm",
    ) -> dict[str, Any]:
        """
        Given a cluster of addresses, determine if they collectively
        form a known exchange entity — exchange fingerprinting.
        """
        attributions = await self.batch_attribute(cluster_addresses, chain=chain)

        type_votes: dict[str, float] = {}
        name_votes: dict[str, float] = {}

        for a in attributions:
            k = str(a.vasp_type)
            type_votes[k] = type_votes.get(k, 0) + a.confidence
            if a.vasp_name:
                name_votes[a.vasp_name] = name_votes.get(a.vasp_name, 0) + a.confidence

        return {
            "cluster_size": len(cluster_addresses),
            "dominant_vasp_type": max(type_votes, key=lambda k: type_votes[k]),
            "dominant_vasp_name": (
                max(name_votes, key=lambda k: name_votes[k]) if name_votes else None
            ),
            "avg_confidence": sum(a.confidence for a in attributions) / len(attributions),
            "high_confidence_count": sum(1 for a in attributions if a.is_high_confidence),
            "risk_flags": list({f for a in attributions for f in a.risk_flags}),
        }

    def _risk_flags(self, vasp_type: VASPType, confidence: float) -> list[str]:
        flags: list[str] = []
        if vasp_type == VASPType.MIXER and confidence > 0.5:
            flags.append("MIXER")
        if vasp_type == VASPType.DARKNET and confidence > 0.5:
            flags.append("DARKNET")
        if vasp_type == VASPType.GAMBLING and confidence > 0.6:
            flags.append("GAMBLING")
        return flags

    async def _fetch_features(
        self,
        address: str,
        chain: str,
    ) -> BehavioralFeatures:
        """
        Production: queries ClickHouse for tx stats, Neo4j for graph metrics.
        Stub: deterministic mock based on address hash.
        """
        seed = int(hashlib.md5(address.encode()).hexdigest()[:8], 16)  # noqa: S324
        rng = np.random.default_rng(seed)
        v = rng.uniform(0, 1, 12).tolist()
        return BehavioralFeatures(
            address=address,
            daily_tx_count=float(v[0]) * 500,
            unique_senders_ratio=float(v[1]),
            unique_receivers_ratio=float(v[2]),
            round_amount_ratio=float(v[3]),
            consolidation_ratio=float(v[4]),
            tx_hour_entropy=float(v[5]) * 4.5,
            weekend_activity=float(v[6]),
            address_reuse_rate=float(v[7]),
            contract_interaction_ratio=float(v[8]),
            erc20_transfer_ratio=float(v[9]),
            native_transfer_ratio=float(v[10]),
            betweenness_centrality=float(v[11]),
        )