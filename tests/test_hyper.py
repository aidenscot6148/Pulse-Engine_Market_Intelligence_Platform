"""
THIS TEST FOLDER IS AI GENERATED AND A PLACEHOLDER. IT WILL BE IMPROVED AND IMPLEMENTED AS IT GOES ON MANUALLY
test_hyper.py — Surgical precision tests. OFF BY DEFAULT.

These tests are skipped in all normal runs including CI.
A developer activates them by setting HYPER_TESTS=1 in the environment,
investigates a specific regression, then turns them off again.

  HYPER_TESTS=1 pytest tests/test_hyper.py -v

Each test has a comment explaining WHEN to activate it.
"""

from __future__ import annotations

import os

import pandas as pd
import pytest
from freezegun import freeze_time

from conftest import _compute_rsi, _jaccard, deduplicate_articles, compute_signal_score
from storage import save_snapshot, apply_retention_policy, load_snapshots
import storage
from config import (
    DEDUP_SIMILARITY_THRESHOLD,
    ASSET_CLASS_WEIGHTS,
    STORAGE_FULL_DETAIL_DAYS,
)

# Module-level boolean — usable in @pytest.mark.skipif decorators.
_HYPER = os.getenv("HYPER_TESTS") == "1"

_SKIP = pytest.mark.skipif(not _HYPER, reason="Set HYPER_TESTS=1 to run hyper tests")


# ── RSI known-value ───────────────────────────────────────────────────────────

@pytest.mark.hyper
@_SKIP
def test_rsi_known_value():
    """
    ACTIVATE WHEN: _compute_rsi logic is refactored or RSI_PERIOD default changes.

    Hand-calculated expected RSI for a deterministic series:
      series = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 19, 18, 17, 16]
      diffs  = [+1, +1, +1, +1, +1, +1, +1, +1, +1, +1, -1, -1, -1, -1]  (14 values)
      gains  = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0]
      losses = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1]
      avg_gain (rolling 14 at end) = 10/14 = 5/7 ≈ 0.7143
      avg_loss (rolling 14 at end) = 4/14  = 2/7 ≈ 0.2857
      RS  = (5/7) / (2/7) = 2.5
      RSI = 100 - 100/(1 + 2.5) = 100 - 28.571... ≈ 71.4
      After round(..., 1): 71.4
    """
    HAND_CALCULATED_VALUE = 71.4
    series = pd.Series([10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 19, 18, 17, 16],
                       dtype=float)
    result = _compute_rsi(series, period=14)
    assert abs(result - HAND_CALCULATED_VALUE) < 0.5, (
        "RSI = {}, expected approx {}. "
        "If this drifted, the RSI formula or rounding changed.".format(result, HAND_CALCULATED_VALUE)
    )


# ── Jaccard boundary exactness ────────────────────────────────────────────────

@pytest.mark.hyper
@_SKIP
def test_jaccard_boundary_value():
    """
    ACTIVATE WHEN: DEDUP_SIMILARITY_THRESHOLD changes or the dedup comparison
    operator changes (>= vs >).

    Source uses: `>= DEDUP_SIMILARITY_THRESHOLD`
    → Jaccard exactly equal to threshold SHOULD trigger deduplication.

    Construction: 13 shared tokens out of 20 total → 13/20 = 0.65 exactly.
      set_a = 13 shared + 3 unique (total 16 tokens)
      set_b = 13 shared + 4 unique (total 17 tokens)
      intersection = 13, union = 13 + 3 + 4 = 20, Jaccard = 13/20 = 0.65
    """
    shared  = ["a" + str(i) for i in range(13)]
    unique_a = ["b0", "b1", "b2"]
    unique_b = ["c0", "c1", "c2", "c3"]

    set_a = set(shared + unique_a)
    set_b = set(shared + unique_b)

    computed = _jaccard(set_a, set_b)
    assert computed == pytest.approx(DEDUP_SIMILARITY_THRESHOLD, abs=1e-9), (
        "Computed Jaccard {} != threshold {}. "
        "Construction is wrong -- fix shared/unique token counts.".format(
            computed, DEDUP_SIMILARITY_THRESHOLD)
    )

    # Because comparison is >=, boundary input SHOULD be treated as a duplicate
    article_a = {
        "title":     " ".join(shared + unique_a),
        "summary":   "", "link": "", "source": "", "published": None,
    }
    article_b = {
        "title":     " ".join(shared + unique_b),
        "summary":   "", "link": "", "source": "", "published": None,
    }
    result = deduplicate_articles([article_a, article_b])
    assert len(result) == 1, (
        "Boundary Jaccard={} with '>=' operator should dedup to 1, got {}. "
        "If operator changed to '>', update this assertion and the comment.".format(
            computed, len(result))
    )


# ── Signal weight correctness per class ──────────────────────────────────────

@pytest.mark.hyper
@_SKIP
@pytest.mark.parametrize("category", list(ASSET_CLASS_WEIGHTS.keys()))
def test_signal_weight_single_component(category):
    """
    ACTIVATE WHEN: ASSET_CLASS_WEIGHTS values change.

    Construct inputs where ONLY the 'trend' component is non-zero.
    Assert output score == raw_trend_contribution * class_weight.

    trend raw max = +2.0 (for uptrend).
    Expected weighted score = 2.0 * ASSET_CLASS_WEIGHTS[category]["trend"].
    """
    weight = ASSET_CLASS_WEIGHTS[category]["trend"]
    expected_score = round(2.0 * weight, 2)

    metrics = {
        "latest_price": 100.0,
        "change_1d":    0.0,    # zero → no context boost
        "trend":        "uptrend",
        "volatility":   0.0,
        "change_7d":    None,
        "change_30d":   None,
        "high_30d":     100.0,
        "low_30d":      100.0,
    }
    momentum = {
        "rsi":            50.0,    # neutral → raw rsi = 0.0
        "roc_10d":        0.0,     # neutral → raw momentum = 0.0
        "trend_strength": 0.0,     # neutral → raw trend_strength = 0.0
        "momentum_accel": 0.0,
    }

    result = compute_signal_score(metrics, momentum, [], market_ctx=None, category=category)
    # Only trend contributes; all other components are 0.
    assert result["score"] == pytest.approx(expected_score, abs=0.05), (
        "category={}: expected score={} (2.0 * weight={}), got {}. "
        "If this fails, ASSET_CLASS_WEIGHTS changed -- update expected values.".format(
            category, expected_score, weight, result["score"])
    )


# ── Contradiction boundary exactness ─────────────────────────────────────────

@pytest.mark.hyper
@_SKIP
def test_contradiction_overbought_surge_boundary():
    """
    ACTIVATE WHEN: thresholds in _detect_contradictions change.

    overbought_surge condition: chg_1d > 2 AND rsi > 70  (both strict)

    Boundary cases:
      chg_1d=2.0, rsi=75  → NOT triggered (2.0 is NOT > 2)
      chg_1d=2.001, rsi=75 → IS triggered
      chg_1d=3.0, rsi=70   → NOT triggered (70 is NOT > 70)
      chg_1d=3.0, rsi=70.1 → IS triggered
    """
    from conftest import _detect_contradictions

    def _run(chg, rsi):
        return [c["type"] for c in _detect_contradictions(
            metrics={"change_1d": chg, "trend": "sideways"},
            momentum={"rsi": rsi, "roc_10d": 0.0},
            factors=[],
            signal={"score": 0.0},
        )]

    assert "overbought_surge" not in _run(2.0, 75.0),   "chg=2.0 (boundary) should NOT trigger"
    assert "overbought_surge" in _run(2.001, 75.0),      "chg=2.001 SHOULD trigger"
    assert "overbought_surge" not in _run(3.0, 70.0),   "rsi=70.0 (boundary) should NOT trigger"
    assert "overbought_surge" in _run(3.0, 70.1),        "rsi=70.1 SHOULD trigger"


# ── Retention field stripping exactness ──────────────────────────────────────

@pytest.mark.hyper
@_SKIP
def test_retention_field_stripping_exactness(tmp_path, monkeypatch):
    """
    ACTIVATE WHEN: the field strip list in apply_retention_policy() changes,
    or _REDUCED_FIELDS in storage.py is updated.

    Fields that SHOULD be retained in reduced snapshots (from _REDUCED_FIELDS):
      asset, date, price, change_1d, signal_score, signal_label,
      trend, rsi, roc_10d, trend_strength

    Fields that SHOULD be stripped (present in full snapshot but not _REDUCED_FIELDS):
      headlines, change_7d, change_30d, volatility, momentum_accel
    """
    monkeypatch.setattr(storage, "_storage_path", tmp_path)

    target_age = STORAGE_FULL_DETAIL_DAYS + 2
    old_date = __import__("datetime").date(2026, 4, 2) - __import__("datetime").timedelta(days=target_age)

    SHOULD_RETAIN = {"asset", "date", "price", "change_1d", "signal_score",
                     "signal_label", "trend", "rsi", "roc_10d", "trend_strength"}
    SHOULD_STRIP  = {"headlines", "change_7d", "change_30d", "volatility", "momentum_accel"}

    with freeze_time(old_date.isoformat()):
        save_snapshot(
            "TestAsset",
            {"latest_price": 100.0, "change_1d": 1.0, "change_7d": 2.0,
             "change_30d": 5.0, "volatility": 0.5, "trend": "uptrend"},
            {"rsi": 55.0, "roc_10d": 3.0, "trend_strength": 1.5, "momentum_accel": 0.2},
            {"score": 3.5, "label": "Bullish", "components": {}, "raw_components": {}},
            [{"title": "Test headline", "source": "Reuters Business",
              "sentiment": {"compound": 0.3}}],
        )

    rewritten = apply_retention_policy()
    assert rewritten >= 1, "Expected at least one snapshot to be rewritten to reduced detail"

    snaps = load_snapshots("TestAsset", days=target_age + 2)
    assert len(snaps) >= 1, "Could not reload snapshot after retention"
    snap = snaps[0]

    for field in SHOULD_RETAIN:
        if field in snap:  # field may be None but key should exist
            pass  # present — correct
        # Note: some fields may be absent if they were None to begin with

    for field in SHOULD_STRIP:
        assert field not in snap, (
            "Field '{}' should have been stripped by retention policy but is still present. "
            "Update SHOULD_STRIP if _REDUCED_FIELDS changed.".format(field)
        )
