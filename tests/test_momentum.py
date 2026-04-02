"""
THIS TEST FOLDER IS AI GENERATED AND A PLACEHOLDER. IT WILL BE IMPROVED AND IMPLEMENTED AS IT GOES ON MANUALLY
test_momentum.py — Contract tests for _compute_rsi(), _compute_roc(),
and compute_momentum_metrics().

Invariants tested here survive weight changes and series-size changes.
"""

from __future__ import annotations

import pandas as pd
import pytest

from conftest import _compute_rsi, _compute_roc, compute_momentum_metrics

MINIMUM_REQUIRED_KEYS = frozenset({"rsi", "roc_10d", "trend_strength", "momentum_accel"})


# ── _compute_rsi ─────────────────────────────────────────────────────────────

class TestComputeRsi:
    def test_returns_neutral_when_insufficient_data(self, price_series_short):
        """len(series) < period+1 → 50.0 (neutral default)."""
        assert _compute_rsi(price_series_short) == 50.0

    def test_returns_100_for_all_gains(self):
        """All positive diffs → avg_loss == 0 → RSI == 100.0."""
        series = pd.Series([float(i) for i in range(1, 41)])  # 40 strictly increasing values
        assert _compute_rsi(series) == 100.0

    def test_returns_0_for_all_losses(self):
        """All negative diffs → avg_gain == 0 → RSI == 0.0."""
        series = pd.Series([float(40 - i) for i in range(41)])  # 41 strictly decreasing values
        assert _compute_rsi(series) == 0.0

    def test_invariant_always_in_0_to_100(self, price_series_rising, price_series_falling,
                                           price_series_flat, price_series_short):
        """INVARIANT: RSI ∈ [0.0, 100.0] for any input."""
        for series in (price_series_rising, price_series_falling,
                       price_series_flat, price_series_short):
            result = _compute_rsi(series)
            assert 0.0 <= result <= 100.0, "RSI out of range: " + str(result)

    def test_above_50_for_rising_series(self, price_series_rising):
        assert _compute_rsi(price_series_rising) > 50.0

    def test_below_50_for_falling_series(self, price_series_falling):
        assert _compute_rsi(price_series_falling) < 50.0

    def test_returns_float(self, price_series_rising):
        assert isinstance(_compute_rsi(price_series_rising), float)

    def test_custom_period_respected(self):
        """Explicitly passing period=5 triggers the < period+1 guard at len==5."""
        short = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])  # exactly 5 = period, not period+1
        assert _compute_rsi(short, period=5) == 50.0

    def test_one_over_period_does_not_return_neutral(self):
        """len == period+1 is the boundary where real RSI computation begins."""
        series = pd.Series([float(i) for i in range(1, 16)])  # len=15, period+1=15
        result = _compute_rsi(series, period=14)
        assert result != 50.0  # real computation was triggered


# ── _compute_roc ─────────────────────────────────────────────────────────────

class TestComputeRoc:
    def test_returns_zero_when_not_enough_data(self, price_series_short):
        """len(series) <= period → 0.0."""
        assert _compute_roc(price_series_short, period=10) == 0.0

    def test_returns_zero_when_exactly_period_length(self):
        """Boundary: len == period → 0.0 (strict: len must be > period)."""
        series = pd.Series([100.0] * 10)
        assert _compute_roc(series, period=10) == 0.0

    def test_returns_zero_when_reference_price_is_zero(self):
        """Zero-division guard: old price == 0 → 0.0."""
        # len=11 > period=10, and iloc[-11] = iloc[0] = 0.0
        series = pd.Series([0.0] + [float(i) for i in range(1, 11)])
        assert _compute_roc(series, period=10) == 0.0

    def test_positive_for_rising_series(self, price_series_rising):
        result = _compute_roc(price_series_rising)
        assert result > 0.0

    def test_negative_for_falling_series(self, price_series_falling):
        result = _compute_roc(price_series_falling)
        assert result < 0.0

    def test_zero_for_flat_series(self, price_series_flat):
        assert _compute_roc(price_series_flat) == pytest.approx(0.0)

    def test_returns_float(self, price_series_rising):
        assert isinstance(_compute_roc(price_series_rising), float)


# ── compute_momentum_metrics ─────────────────────────────────────────────────

class TestComputeMomentumMetrics:
    def test_returns_defaults_for_none(self):
        """None input → neutral defaults dict (not an empty dict)."""
        result = compute_momentum_metrics(None)
        assert MINIMUM_REQUIRED_KEYS.issubset(result.keys())
        assert result["rsi"] == 50.0
        assert result["roc_10d"] == 0.0

    def test_returns_defaults_for_empty_dataframe(self):
        result = compute_momentum_metrics(pd.DataFrame())
        assert MINIMUM_REQUIRED_KEYS.issubset(result.keys())

    def test_minimum_keys_present_for_valid_data(self, ohlcv_df, price_series_rising):
        result = compute_momentum_metrics(ohlcv_df(price_series_rising))
        assert MINIMUM_REQUIRED_KEYS.issubset(result.keys())

    def test_rsi_invariant_in_range(self, ohlcv_df, price_series_rising,
                                     price_series_falling, price_series_flat, price_series_short):
        """INVARIANT: rsi key always in [0.0, 100.0]."""
        for series in (price_series_rising, price_series_falling,
                       price_series_flat, price_series_short):
            result = compute_momentum_metrics(ohlcv_df(series))
            assert 0.0 <= result["rsi"] <= 100.0

    def test_defaults_for_short_series(self, ohlcv_df, price_series_short):
        """Short series triggers guard paths; result still has required keys."""
        result = compute_momentum_metrics(ohlcv_df(price_series_short))
        assert MINIMUM_REQUIRED_KEYS.issubset(result.keys())

    def test_rsi_above_50_for_rising_data(self, ohlcv_df, price_series_rising):
        result = compute_momentum_metrics(ohlcv_df(price_series_rising))
        assert result["rsi"] > 50.0

    def test_rsi_below_50_for_falling_data(self, ohlcv_df, price_series_falling):
        result = compute_momentum_metrics(ohlcv_df(price_series_falling))
        assert result["rsi"] < 50.0

    def test_roc_positive_for_rising_data(self, ohlcv_df, price_series_rising):
        result = compute_momentum_metrics(ohlcv_df(price_series_rising))
        assert result["roc_10d"] > 0.0

    def test_roc_negative_for_falling_data(self, ohlcv_df, price_series_falling):
        result = compute_momentum_metrics(ohlcv_df(price_series_falling))
        assert result["roc_10d"] < 0.0
