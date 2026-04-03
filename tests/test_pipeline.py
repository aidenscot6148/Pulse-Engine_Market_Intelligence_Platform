"""
test_pipeline.py — Smoke tests for analyse_asset() and run_full_scan().

Goal: pipelines execute without crashing and return minimally usable output.
Not testing exact structure — testing that the output is there and in range.

All network calls are mocked via conftest fixtures.
"""

from __future__ import annotations

from app import analyse_asset, run_full_scan


# ── analyse_asset ─────────────────────────────────────────────────────────────

def test_analyse_asset_runs(mock_price_history, storage_dir, synthetic_articles):
    """Happy path: pipeline completes and returns a dict."""
    result = analyse_asset("Gold", "GC=F", "Commodities", synthetic_articles,
                           with_market_ctx=False)
    assert isinstance(result, dict)


def test_analyse_asset_has_signal_in_range(mock_price_history, storage_dir, synthetic_articles):
    """Result must contain a 'signal' key with a score inside [-10, 10]."""
    result = analyse_asset("Gold", "GC=F", "Commodities", synthetic_articles,
                           with_market_ctx=False)
    score = result.get("signal", {}).get("score")
    assert score is not None
    assert -10.0 <= score <= 10.0


def test_analyse_asset_no_price_data_does_not_crash(mocker, storage_dir, synthetic_articles):
    """When price fetch returns None, the pipeline must still return a dict (not raise)."""
    mocker.patch("app.fetch_price_history", return_value=None)
    result = analyse_asset("Gold", "GC=F", "Commodities", synthetic_articles,
                           with_market_ctx=False)
    assert isinstance(result, dict)
    assert "signal" in result


def test_analyse_asset_empty_articles_does_not_crash(mock_price_history, storage_dir):
    """Empty news list must not crash the pipeline."""
    result = analyse_asset("Gold", "GC=F", "Commodities", articles=[],
                           with_market_ctx=False)
    assert "signal" in result


# ── run_full_scan ─────────────────────────────────────────────────────────────

def test_run_full_scan_returns_dict(mock_price_history, mock_news_articles,
                                    mock_market_context, storage_dir):
    """Full scan must return a dict without crashing."""
    result = run_full_scan()
    assert isinstance(result, dict)


def test_run_full_scan_assets_have_signal(mock_price_history, mock_news_articles,
                                          mock_market_context, storage_dir):
    """Every asset result in the scan must contain a 'signal' key."""
    result = run_full_scan()
    for cat_results in result.values():
        for asset_result in cat_results.values():
            assert "signal" in asset_result
