"""Unit tests for risk scorer."""
from __future__ import annotations

import numpy as np
import pytest

from api.schemas.risk import RiskLabel
from risk.scorer import SANCTIONED_ADDRESSES, RiskScorer, _label_from_score


class TestLabelFromScore:
    def test_low(self) -> None:
        assert _label_from_score(0) == RiskLabel.LOW
        assert _label_from_score(24) == RiskLabel.LOW

    def test_medium(self) -> None:
        assert _label_from_score(25) == RiskLabel.MEDIUM
        assert _label_from_score(49) == RiskLabel.MEDIUM

    def test_high(self) -> None:
        assert _label_from_score(50) == RiskLabel.HIGH
        assert _label_from_score(74) == RiskLabel.HIGH

    def test_severe(self) -> None:
        assert _label_from_score(75) == RiskLabel.SEVERE
        assert _label_from_score(100) == RiskLabel.SEVERE


class TestRiskScorer:
    @pytest.fixture
    def scorer(self) -> RiskScorer:
        return RiskScorer()

    @pytest.mark.asyncio
    async def test_sanctioned_address_returns_99(self, scorer: RiskScorer) -> None:
        sanctioned = next(iter(SANCTIONED_ADDRESSES))
        report = await scorer.score(sanctioned)
        assert report.score == 99
        assert report.label == RiskLabel.SANCTIONED

    @pytest.mark.asyncio
    async def test_normal_address_returns_report(self, scorer: RiskScorer) -> None:
        address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
        report = await scorer.score(address)
        assert 0 <= report.score <= 100
        assert report.label in list(RiskLabel)
        assert report.address == address

    @pytest.mark.asyncio
    async def test_batch_score(self, scorer: RiskScorer) -> None:
        addresses = [
            "0xabc0000000000000000000000000000000000001",
            "0xabc0000000000000000000000000000000000002",
            "0xabc0000000000000000000000000000000000003",
        ]
        results = await scorer.batch_score(addresses)
        assert len(results) == 3
        for r in results:
            assert 0 <= r.score <= 100

    @pytest.mark.asyncio
    async def test_batch_max_500(self, scorer: RiskScorer) -> None:
        addresses = [f"0x{i:040x}" for i in range(501)]
        # Should not raise; individual scores will return even if some fail
        results = await scorer.batch_score(addresses[:500])
        assert len(results) == 500

    def test_rule_score_sanctioned_flags(self, scorer: RiskScorer) -> None:
        features = np.zeros(18, dtype=np.float32)
        features[6] = 1.0  # ofac_direct
        score = scorer._rule_score(features)
        assert score >= 60

    def test_rule_score_mixer_exposure(self, scorer: RiskScorer) -> None:
        features = np.zeros(18, dtype=np.float32)
        features[2] = 0.5  # mixer_exposure_ratio = 50%
        score = scorer._rule_score(features)
        assert score >= 20

    def test_rule_score_clean_address(self, scorer: RiskScorer) -> None:
        features = np.zeros(18, dtype=np.float32)
        score = scorer._rule_score(features)
        assert score == 0
