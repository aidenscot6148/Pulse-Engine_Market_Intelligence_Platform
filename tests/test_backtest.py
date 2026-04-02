"""
THIS TEST FOLDER IS AI GENERATED AND A PLACEHOLDER. IT WILL BE IMPROVED AND IMPLEMENTED AS IT GOES ON MANUALLY.
test_backtest.py — Contract tests for evaluate_signal_accuracy().

All tests use the storage_dir fixture (hermetic tmp_path storage).
Snapshots are created via save_snapshot() + freeze_time, not by
writing .gz files manually.
"""

from __future__ import annotations

import pytest
from freezegun import freeze_time

from storage import save_snapshot
from backtest import evaluate_signal_accuracy

# Required keys in every non-empty evaluate_signal_accuracy() result.
MINIMUM_RESULT_KEYS = frozenset({
    "hit_rate",
    "num_evaluated",
    "details",
    "avg_signal_score",
    "message",
    "by_signal_strength",
    "by_label",
    "label_summaries",
})


# ── helpers ───────────────────────────────────────────────────────────────────

def _save_snap(asset: str, date_str: str, price: float, score: float, label: str) -> None:
    with freeze_time(date_str):
        save_snapshot(
            asset,
            {"latest_price": price, "change_1d": 0.5, "trend": "uptrend",
             "volatility": 0.3, "change_7d": 1.0, "change_30d": 2.0},
            {"rsi": 55.0, "roc_10d": 2.0, "trend_strength": 1.0, "momentum_accel": 0.1},
            {"score": score, "label": label, "components": {}, "raw_components": {}},
            [],
        )


# ── evaluate_signal_accuracy ──────────────────────────────────────────────────

class TestEvaluateSignalAccuracyInsufficientData:
    def test_returns_graceful_result_with_no_snapshots(self, storage_dir):
        result = evaluate_signal_accuracy("NonExistentAsset")
        assert isinstance(result, dict)
        assert MINIMUM_RESULT_KEYS.issubset(result.keys())
        assert result["num_evaluated"] == 0

    def test_returns_graceful_result_with_one_snapshot(self, storage_dir):
        _save_snap("Gold", "2026-04-01", price=1850.0, score=3.0, label="Bullish")
        result = evaluate_signal_accuracy("Gold")
        assert MINIMUM_RESULT_KEYS.issubset(result.keys())
        assert result["num_evaluated"] == 0

    def test_does_not_raise_when_storage_empty(self, storage_dir):
        result = evaluate_signal_accuracy("Gold")
        assert isinstance(result, dict)


class TestEvaluateSignalAccuracyWithData:
    def test_returns_required_keys_with_two_snapshots(self, storage_dir):
        _save_snap("Gold", "2026-03-31", price=1800.0, score=3.0, label="Bullish")
        _save_snap("Gold", "2026-04-01", price=1850.0, score=4.0, label="Bullish")
        result = evaluate_signal_accuracy("Gold")
        assert MINIMUM_RESULT_KEYS.issubset(result.keys())

    def test_hit_rate_invariant_in_0_to_1(self, storage_dir):
        """INVARIANT: hit_rate is always in [0.0, 1.0] when data exists."""
        _save_snap("Gold", "2026-03-31", price=1800.0, score=3.0, label="Bullish")
        _save_snap("Gold", "2026-04-01", price=1850.0, score=4.0, label="Bullish")
        result = evaluate_signal_accuracy("Gold")
        if result["hit_rate"] is not None:
            assert 0.0 <= result["hit_rate"] <= 1.0

    def test_correct_prediction_gives_hit_rate_1(self, storage_dir):
        """
        Day 1: score=3.0 (predicted up). Day 2: price rose → correct.
        hit_rate should be 1.0.
        """
        _save_snap("Silver", "2026-03-31", price=25.0, score=3.0, label="Bullish")
        _save_snap("Silver", "2026-04-01", price=26.0, score=2.0, label="Slightly Bullish")
        result = evaluate_signal_accuracy("Silver")
        assert result["num_evaluated"] == 1
        assert result["hit_rate"] == pytest.approx(1.0)

    def test_wrong_prediction_gives_hit_rate_0(self, storage_dir):
        """
        Day 1: score=3.0 (predicted up). Day 2: price fell → wrong.
        hit_rate should be 0.0.
        """
        _save_snap("Copper", "2026-03-31", price=4.0, score=3.0, label="Bullish")
        _save_snap("Copper", "2026-04-01", price=3.8, score=-1.0, label="Slightly Bearish")
        result = evaluate_signal_accuracy("Copper")
        assert result["num_evaluated"] == 1
        assert result["hit_rate"] == pytest.approx(0.0)

    def test_message_is_non_empty_string(self, storage_dir):
        _save_snap("Bitcoin", "2026-03-31", price=80000.0, score=5.0, label="Bullish")
        _save_snap("Bitcoin", "2026-04-01", price=82000.0, score=4.5, label="Bullish")
        result = evaluate_signal_accuracy("Bitcoin")
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0

    def test_details_list_newest_first(self, storage_dir):
        """details is sorted newest-first."""
        _save_snap("Ethereum", "2026-03-30", price=2000.0, score=2.0, label="Slightly Bullish")
        _save_snap("Ethereum", "2026-03-31", price=2100.0, score=3.0, label="Bullish")
        _save_snap("Ethereum", "2026-04-01", price=2050.0, score=1.5, label="Slightly Bullish")
        result = evaluate_signal_accuracy("Ethereum")
        if result["num_evaluated"] >= 2:
            dates = [d["date"] for d in result["details"]]
            assert dates == sorted(dates, reverse=True)

    def test_by_signal_strength_values_in_range(self, storage_dir):
        """Each bucket's hit_rate in by_signal_strength must be in [0.0, 1.0]."""
        _save_snap("Gold", "2026-03-31", price=1800.0, score=7.0, label="Strong Bullish")
        _save_snap("Gold", "2026-04-01", price=1850.0, score=6.0, label="Strong Bullish")
        result = evaluate_signal_accuracy("Gold")
        for bucket_data in result["by_signal_strength"].values():
            assert 0.0 <= bucket_data["hit_rate"] <= 1.0

    def test_num_evaluated_matches_details_length(self, storage_dir):
        _save_snap("Gold", "2026-03-31", price=1800.0, score=3.0, label="Bullish")
        _save_snap("Gold", "2026-04-01", price=1850.0, score=4.0, label="Bullish")
        result = evaluate_signal_accuracy("Gold")
        assert result["num_evaluated"] == len(result["details"])
