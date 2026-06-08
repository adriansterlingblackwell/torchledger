"""Unit tests for VASP attribution engine."""
from __future__ import annotations
import pytest
from ingestion.vasp.attribution import (
    KNOWN_VASP_ADDRESSES,
    AttributionMethod,
    BehavioralFeatures,
    DepositPatternDetector,
    VASPAttributionEngine,
    VASPType,
    WithdrawalPatternDetector,
)


def _feat(
    address: str = "0xtest",
    daily_tx_count: float = 10.0,
    unique_senders_ratio: float = 0.5,
    unique_receivers_ratio: float = 0.5,
    round_amount_ratio: float = 0.2,
    consolidation_ratio: float = 0.3,
    tx_hour_entropy: float = 2.0,
    weekend_activity: float = 0.3,
    address_reuse_rate: float = 0.5,
    contract_interaction_ratio: float = 0.3,
    erc20_transfer_ratio: float = 0.5,
    native_transfer_ratio: float = 0.5,
    betweenness_centrality: float = 0.3,
) -> BehavioralFeatures:
    return BehavioralFeatures(
        address=address,
        daily_tx_count=daily_tx_count,
        unique_senders_ratio=unique_senders_ratio,
        unique_receivers_ratio=unique_receivers_ratio,
        round_amount_ratio=round_amount_ratio,
        consolidation_ratio=consolidation_ratio,
        tx_hour_entropy=tx_hour_entropy,
        weekend_activity=weekend_activity,
        address_reuse_rate=address_reuse_rate,
        contract_interaction_ratio=contract_interaction_ratio,
        erc20_transfer_ratio=erc20_transfer_ratio,
        native_transfer_ratio=native_transfer_ratio,
        betweenness_centrality=betweenness_centrality,
    )


class TestDepositPatternDetector:
    def test_cex_deposit_detected(self) -> None:
        d = DepositPatternDetector()
        match, conf, ev = d.detect(_feat(
            unique_senders_ratio=0.92,
            consolidation_ratio=0.75,
            address_reuse_rate=0.05,
            daily_tx_count=200.0,
        ))
        assert match is True
        assert conf >= 0.55
        assert len(ev) >= 2

    def test_normal_not_detected(self) -> None:
        d = DepositPatternDetector()
        match, _, _ = d.detect(_feat(
            unique_senders_ratio=0.3,
            consolidation_ratio=0.2,
        ))
        assert match is False


class TestWithdrawalPatternDetector:
    def test_cex_withdrawal_detected(self) -> None:
        d = WithdrawalPatternDetector()
        match, conf, _ = d.detect(_feat(
            unique_receivers_ratio=0.90,
            round_amount_ratio=0.55,
            erc20_transfer_ratio=0.80,
            tx_hour_entropy=4.2,
        ))
        assert match is True
        assert conf >= 0.55

    def test_low_ratio_not_detected(self) -> None:
        d = WithdrawalPatternDetector()
        match, _, _ = d.detect(_feat(
            unique_receivers_ratio=0.20,
            round_amount_ratio=0.10,
        ))
        assert match is False


class TestVASPAttributionEngine:
    @pytest.fixture
    def engine(self) -> VASPAttributionEngine:
        return VASPAttributionEngine()

    @pytest.mark.asyncio
    async def test_binance_known(self, engine: VASPAttributionEngine) -> None:
        r = await engine.attribute("0x28c6c06298d514db089934071355e5743bf21d60")
        assert r.vasp_name == "Binance"
        assert r.vasp_type == VASPType.CEX
        assert r.confidence >= 0.99
        assert r.method == AttributionMethod.KNOWN_ADDRESS

    @pytest.mark.asyncio
    async def test_tornado_flags(self, engine: VASPAttributionEngine) -> None:
        r = await engine.attribute("0xd90e2f925da726b50c4ed8d0fb90ad053324f31b")
        assert r.vasp_type == VASPType.MIXER
        assert "OFAC_SANCTIONED" in r.risk_flags

    @pytest.mark.asyncio
    async def test_unknown_returns_result(self, engine: VASPAttributionEngine) -> None:
        r = await engine.attribute("0xdeadbeef00000000000000000000000000000001")
        assert 0.0 <= r.confidence <= 1.0
        assert r.vasp_type in list(VASPType)

    @pytest.mark.asyncio
    async def test_batch_limit(self, engine: VASPAttributionEngine) -> None:
        with pytest.raises(ValueError, match="Max 1000"):
            await engine.batch_attribute([f"0x{i:040x}" for i in range(1001)])

    @pytest.mark.asyncio
    async def test_uniswap_is_dex(self, engine: VASPAttributionEngine) -> None:
        r = await engine.attribute("0xe592427a0aece92de3edee1f18e0157c05861564")
        assert r.vasp_type == VASPType.DEX
        assert r.vasp_name == "Uniswap v3"

    @pytest.mark.asyncio
    async def test_coinbase_is_regulated(self, engine: VASPAttributionEngine) -> None:
        r = await engine.attribute("0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43")
        assert r.is_regulated is True

    @pytest.mark.asyncio
    async def test_cluster_fingerprint(self, engine: VASPAttributionEngine) -> None:
        fp = await engine.fingerprint_exchange([
            "0x28c6c06298d514db089934071355e5743bf21d60",
            "0xdfd5293d8e347dfe59e90efd55b2956a1343963d",
        ])
        assert fp["dominant_vasp_name"] == "Binance"
        assert fp["avg_confidence"] >= 0.99