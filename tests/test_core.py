"""
test_core.py — Sanity and invariant tests for pure functions.

Goal: each function runs without crashing and its output is sane.
Not testing exact values — testing that outputs are usable.
"""

from __future__ import annotations

from app import (
    _compute_rsi,
    _compute_roc,
    compute_momentum_metrics,
    compute_price_metrics,
    compute_signal_score,
    score_sentiment,
    deduplicate_articles,
)


# ── RSI ──────────────────────────────────────────────────────────────────────

def test_rsi_always_in_range(price_series_rising, price_series_falling, price_series_flat):
    """INVARIANT: RSI must always be between 0 and 100, no matter what."""
    for series in [price_series_rising, price_series_falling, price_series_flat]:
        result = _compute_rsi(series)
        assert 0.0 <= result <= 100.0


def test_rsi_direction(price_series_rising, price_series_falling):
    """Rising series → RSI above 50. Falling → RSI below 50."""
    assert _compute_rsi(price_series_rising) > 50
    assert _compute_rsi(price_series_falling) < 50


# ── ROC ──────────────────────────────────────────────────────────────────────

def test_roc_sign(price_series_rising, price_series_falling):
    """ROC should be positive for an uptrend and negative for a downtrend."""
    assert _compute_roc(price_series_rising) > 0
    assert _compute_roc(price_series_falling) < 0


# ── Momentum metrics ──────────────────────────────────────────────────────────

def test_momentum_metrics_runs(ohlcv_df, price_series_rising):
    """compute_momentum_metrics should return a dict with an 'rsi' key."""
    result = compute_momentum_metrics(ohlcv_df(price_series_rising))
    assert isinstance(result, dict)
    assert "rsi" in result


# ── Price metrics ─────────────────────────────────────────────────────────────

def test_price_metrics_runs(ohlcv_df, price_series_rising):
    """compute_price_metrics should return a dict with a usable latest_price."""
    result = compute_price_metrics(ohlcv_df(price_series_rising))
    assert isinstance(result, dict)
    assert result.get("latest_price") is not None
    assert result["latest_price"] > 0


# ── Signal score ─────────────────────────────────────────────────────────────

def test_signal_score_in_range(synthetic_metrics, synthetic_momentum):
    """INVARIANT: score must always be clamped to [-10, 10]."""
    result = compute_signal_score(synthetic_metrics, synthetic_momentum, [])
    assert -10.0 <= result["score"] <= 10.0


# ── Sentiment ─────────────────────────────────────────────────────────────────

def test_sentiment_compound_in_range():
    """INVARIANT: sentiment compound must always be in [-1, 1]."""
    result = score_sentiment("markets are crashing hard, major losses everywhere")
    assert -1.0 <= result["compound"] <= 1.0


# ── Deduplication ─────────────────────────────────────────────────────────────

def test_dedup_reduces_or_preserves_count(synthetic_articles):
    """Dedup should never produce more articles than it received."""
    result = deduplicate_articles(synthetic_articles)
    assert 0 < len(result) <= len(synthetic_articles)
