"""
THIS TEST FOLDER IS AI GENERATED AND A PLACEHOLDER. IT WILL BE IMPROVED AND IMPLEMENTED AS IT GOES ON MANUALLY.
test_signal_score.py — Contract tests for compute_signal_score() and
_detect_contradictions().

Key invariants:
  - score is always in [-10.0, 10.0]
  - label is always from the known label set
  - label and score are consistent with each other
  - Adding new components does not break tests (issubset checks)
"""

from __future__ import annotations

import pytest

from conftest import compute_signal_score, _detect_contradictions
from config import TRACKED_ASSETS, SIGNAL_THRESHOLDS

# Required keys in every non-empty compute_signal_score() result.
MINIMUM_REQUIRED_KEYS = frozenset({"score", "label", "components", "raw_components"})

# All valid labels the function may return — derived from source + "No Data".
# If labels are renamed, this set catches the change.
VALID_SIGNAL_LABELS = frozenset({
    "Strong Bullish", "Bullish", "Slightly Bullish", "Neutral",
    "Slightly Bearish", "Bearish", "Strong Bearish", "No Data",
})

# Required keys in every _detect_contradictions() item.
MINIMUM_CONTRADICTION_KEYS = frozenset({"type", "description"})


# ── compute_signal_score ──────────────────────────────────────────────────────

class TestComputeSignalScoreNoData:
    def test_empty_metrics_returns_no_data(self):
        result = compute_signal_score({}, {}, [])
        assert result["score"] == 0.0
        assert result["label"] == "No Data"

    def test_empty_metrics_has_required_keys(self):
        result = compute_signal_score({}, {}, [])
        assert MINIMUM_REQUIRED_KEYS.issubset(result.keys())


class TestComputeSignalScoreContract:
    def test_minimum_keys_present(self, synthetic_metrics, synthetic_momentum):
        result = compute_signal_score(synthetic_metrics, synthetic_momentum, [])
        assert MINIMUM_REQUIRED_KEYS.issubset(result.keys())

    def test_score_invariant_in_range(self, synthetic_metrics, synthetic_momentum):
        """INVARIANT: score is always clamped to [-10.0, 10.0]."""
        result = compute_signal_score(synthetic_metrics, synthetic_momentum, [])
        assert -10.0 <= result["score"] <= 10.0

    def test_score_is_float(self, synthetic_metrics, synthetic_momentum):
        result = compute_signal_score(synthetic_metrics, synthetic_momentum, [])
        assert isinstance(result["score"], float)

    def test_label_is_in_valid_set(self, synthetic_metrics, synthetic_momentum):
        result = compute_signal_score(synthetic_metrics, synthetic_momentum, [])
        assert result["label"] in VALID_SIGNAL_LABELS

    def test_label_consistent_with_score(self, synthetic_metrics, synthetic_momentum):
        """Label must match the score's numeric bracket per SIGNAL_THRESHOLDS."""
        result = compute_signal_score(synthetic_metrics, synthetic_momentum, [])
        score = result["score"]
        label = result["label"]

        if score >= SIGNAL_THRESHOLDS["strong_bullish"]:
            assert label == "Strong Bullish"
        elif score >= SIGNAL_THRESHOLDS["bullish"]:
            assert label == "Bullish"
        elif score >= SIGNAL_THRESHOLDS["slightly_bullish"]:
            assert label == "Slightly Bullish"
        elif score > SIGNAL_THRESHOLDS["neutral"]:
            assert label == "Neutral"
        elif score >= SIGNAL_THRESHOLDS["slightly_bearish"]:
            assert label == "Slightly Bearish"
        elif score >= SIGNAL_THRESHOLDS["bearish"]:
            assert label == "Bearish"
        else:
            assert label == "Strong Bearish"

    def test_score_invariant_with_extreme_inputs(self):
        """INVARIANT: extreme component values are still clamped to [-10, 10]."""
        metrics = {
            "latest_price": 1.0,
            "change_1d": 50.0,   # extreme positive
            "trend": "uptrend",
            "volatility": 0.5,
        }
        momentum = {"rsi": 15.0, "roc_10d": 100.0, "trend_strength": 50.0, "momentum_accel": 0.0}
        result = compute_signal_score(metrics, momentum, [])
        assert -10.0 <= result["score"] <= 10.0

        metrics["trend"] = "downtrend"
        metrics["change_1d"] = -50.0
        momentum["roc_10d"] = -100.0
        result = compute_signal_score(metrics, momentum, [])
        assert -10.0 <= result["score"] <= 10.0

    @pytest.mark.parametrize("category", list(TRACKED_ASSETS.keys()))
    def test_no_key_error_for_tracked_categories(self, synthetic_metrics, synthetic_momentum,
                                                   category):
        """
        Every category in TRACKED_ASSETS must not cause a KeyError.
        Catches missing entries when new asset classes are added to config.
        """
        result = compute_signal_score(
            synthetic_metrics,
            synthetic_momentum,
            [],
            category=category,
        )
        assert MINIMUM_REQUIRED_KEYS.issubset(result.keys())

    def test_score_higher_for_bullish_metrics(self, synthetic_momentum):
        """Uptrend metrics should score higher than downtrend metrics."""
        bullish_metrics = {
            "latest_price": 100.0, "change_1d": 3.0, "trend": "uptrend",
            "volatility": 0.5, "change_7d": 5.0, "change_30d": 10.0,
            "high_30d": 110.0, "low_30d": 90.0,
        }
        bearish_metrics = {
            "latest_price": 100.0, "change_1d": -3.0, "trend": "downtrend",
            "volatility": 0.5, "change_7d": -5.0, "change_30d": -10.0,
            "high_30d": 110.0, "low_30d": 90.0,
        }
        bullish_result = compute_signal_score(bullish_metrics, synthetic_momentum, [])
        bearish_result = compute_signal_score(bearish_metrics, synthetic_momentum, [])
        assert bullish_result["score"] > bearish_result["score"]


# ── _detect_contradictions ────────────────────────────────────────────────────

class TestDetectContradictions:
    def test_returns_empty_for_benign_inputs(self):
        """No thresholds crossed → no contradictions."""
        result = _detect_contradictions(
            metrics={"change_1d": 0.5, "trend": "sideways"},
            momentum={"rsi": 50.0, "roc_10d": 3.0},
            factors=[],
            signal={"score": 1.0},
        )
        assert result == []

    def test_does_not_raise_with_empty_dicts(self):
        """FRAGILE-SAFE: all optional keys have defaults; empty dicts must not raise."""
        result = _detect_contradictions({}, {}, [], {})
        assert isinstance(result, list)

    def test_each_item_has_required_keys(self):
        """Each contradiction dict has at minimum 'type' and 'description'."""
        # trigger overbought_surge: change_1d > 2 AND rsi > 70
        result = _detect_contradictions(
            metrics={"change_1d": 3.0, "trend": "sideways"},
            momentum={"rsi": 75.0, "roc_10d": 0.0},
            factors=[],
            signal={"score": 0.0},
        )
        assert len(result) >= 1
        for item in result:
            assert MINIMUM_CONTRADICTION_KEYS.issubset(item.keys())

    def test_overbought_surge_triggered(self):
        """change_1d > 2 AND rsi > 70 → 'overbought_surge' contradiction."""
        result = _detect_contradictions(
            metrics={"change_1d": 3.0, "trend": "sideways"},
            momentum={"rsi": 75.0, "roc_10d": 0.0},
            factors=[],
            signal={"score": 0.0},
        )
        types = [c["type"] for c in result]
        assert "overbought_surge" in types

    def test_overbought_surge_not_triggered_at_exact_boundary(self):
        """Boundary: change_1d == 2.0 (not > 2) should NOT trigger overbought_surge."""
        result = _detect_contradictions(
            metrics={"change_1d": 2.0, "trend": "sideways"},
            momentum={"rsi": 75.0, "roc_10d": 0.0},
            factors=[],
            signal={"score": 0.0},
        )
        types = [c["type"] for c in result]
        assert "overbought_surge" not in types

    def test_oversold_drop_triggered(self):
        """change_1d < -2 AND rsi < 30 → 'oversold_drop' contradiction."""
        result = _detect_contradictions(
            metrics={"change_1d": -3.0, "trend": "sideways"},
            momentum={"rsi": 25.0, "roc_10d": 0.0},
            factors=[],
            signal={"score": 0.0},
        )
        types = [c["type"] for c in result]
        assert "oversold_drop" in types

    def test_oversold_drop_not_triggered_at_exact_boundary(self):
        """Boundary: change_1d == -2.0 (not < -2) should NOT trigger oversold_drop."""
        result = _detect_contradictions(
            metrics={"change_1d": -2.0, "trend": "sideways"},
            momentum={"rsi": 25.0, "roc_10d": 0.0},
            factors=[],
            signal={"score": 0.0},
        )
        types = [c["type"] for c in result]
        assert "oversold_drop" not in types

    def test_trend_sentiment_conflict_triggered(self):
        """uptrend + sentiment_diverged factor → 'trend_sentiment_conflict'."""
        factors = [{"type": "sentiment_diverged", "label": "Sentiment diverges", "detail": ""}]
        result = _detect_contradictions(
            metrics={"change_1d": 1.0, "trend": "uptrend"},
            momentum={"rsi": 55.0, "roc_10d": 2.0},
            factors=factors,
            signal={"score": 2.0},
        )
        types = [c["type"] for c in result]
        assert "trend_sentiment_conflict" in types

    def test_trend_signal_conflict_triggered(self):
        """downtrend + signal score > 3 → 'trend_signal_conflict'."""
        result = _detect_contradictions(
            metrics={"change_1d": -1.0, "trend": "downtrend"},
            momentum={"rsi": 45.0, "roc_10d": -2.0},
            factors=[],
            signal={"score": 4.0},
        )
        types = [c["type"] for c in result]
        assert "trend_signal_conflict" in types

    def test_trend_signal_conflict_not_triggered_at_exact_boundary(self):
        """Boundary: score == 3.0 (not > 3) should NOT trigger trend_signal_conflict."""
        result = _detect_contradictions(
            metrics={"change_1d": -1.0, "trend": "downtrend"},
            momentum={"rsi": 45.0, "roc_10d": -2.0},
            factors=[],
            signal={"score": 3.0},
        )
        types = [c["type"] for c in result]
        assert "trend_signal_conflict" not in types

    def test_momentum_no_catalyst_triggered(self):
        """abs(roc) > 10 with no 'event' factor → 'momentum_no_catalyst'."""
        result = _detect_contradictions(
            metrics={"change_1d": 1.0, "trend": "sideways"},
            momentum={"rsi": 55.0, "roc_10d": 15.0},
            factors=[],   # no "event" factor
            signal={"score": 2.0},
        )
        types = [c["type"] for c in result]
        assert "momentum_no_catalyst" in types

    def test_momentum_no_catalyst_not_triggered_with_event_factor(self):
        """Strong momentum + event factor present → no 'momentum_no_catalyst'."""
        factors = [{"type": "event", "label": "Central Bank Policy", "detail": ""}]
        result = _detect_contradictions(
            metrics={"change_1d": 1.0, "trend": "sideways"},
            momentum={"rsi": 55.0, "roc_10d": 15.0},
            factors=factors,
            signal={"score": 2.0},
        )
        types = [c["type"] for c in result]
        assert "momentum_no_catalyst" not in types

    def test_momentum_no_catalyst_not_triggered_at_exact_boundary(self):
        """Boundary: abs(roc) == 10.0 (not > 10) should NOT trigger momentum_no_catalyst."""
        result = _detect_contradictions(
            metrics={"change_1d": 1.0, "trend": "sideways"},
            momentum={"rsi": 55.0, "roc_10d": 10.0},
            factors=[],
            signal={"score": 2.0},
        )
        types = [c["type"] for c in result]
        assert "momentum_no_catalyst" not in types
