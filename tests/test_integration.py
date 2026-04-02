"""
THIS TEST FOLDER IS AI GENERATED AND A PLACEHOLDER. IT WILL BE IMPROVED AND IMPLEMENTED AS IT GOES ON MANUALLY
test_integration.py — Integration tests for analyse_asset() and run_full_scan().

All network calls are mocked via the pre-built conftest fixtures.
Patch paths go through APP_MODULE — update that one variable when #4 lands.

IMPORTANT: Never add inline mocker.patch() calls here. Use conftest fixtures
so that APP_MODULE changes propagate automatically.
"""

from __future__ import annotations

from conftest import analyse_asset, run_full_scan
from config import TRACKED_ASSETS

# Required top-level keys in every analyse_asset() result.
MINIMUM_RESULT_KEYS = frozenset({
    "ticker",
    "history",
    "metrics",
    "momentum",
    "news",
    "clusters",
    "market_ctx",
    "signal",
    "explanation",
    "historical_features",
})

# Required keys in the explanation sub-dict.
MINIMUM_EXPLANATION_KEYS = frozenset({
    "verdict",
    "factors",
    "detail",
    "confidence",
    "contradictions",
    "why_it_matters",
})


# ── analyse_asset — happy path ────────────────────────────────────────────────

class TestAnalyseAssetHappyPath:
    def test_returns_required_keys(self, mock_price_history, synthetic_articles, storage_dir):
        result = analyse_asset(
            asset_name="Gold",
            ticker="GC=F",
            category="Commodities",
            articles=synthetic_articles,
            with_market_ctx=False,
        )
        assert MINIMUM_RESULT_KEYS.issubset(result.keys())

    def test_signal_score_in_range(self, mock_price_history, synthetic_articles, storage_dir):
        result = analyse_asset(
            asset_name="Gold",
            ticker="GC=F",
            category="Commodities",
            articles=synthetic_articles,
            with_market_ctx=False,
        )
        assert -10.0 <= result["signal"]["score"] <= 10.0

    def test_explanation_verdict_is_non_empty_string(self, mock_price_history,
                                                       synthetic_articles, storage_dir):
        result = analyse_asset(
            asset_name="Gold",
            ticker="GC=F",
            category="Commodities",
            articles=synthetic_articles,
            with_market_ctx=False,
        )
        assert isinstance(result["explanation"]["verdict"], str)
        assert len(result["explanation"]["verdict"]) > 0

    def test_explanation_has_required_keys(self, mock_price_history, synthetic_articles,
                                            storage_dir):
        result = analyse_asset(
            asset_name="Gold",
            ticker="GC=F",
            category="Commodities",
            articles=synthetic_articles,
            with_market_ctx=False,
        )
        assert MINIMUM_EXPLANATION_KEYS.issubset(result["explanation"].keys())

    def test_does_not_raise_with_market_ctx_false(self, mock_price_history,
                                                   synthetic_articles, storage_dir):
        """Explicit keyword arg — must not raise."""
        analyse_asset(
            asset_name="Gold",
            ticker="GC=F",
            category="Commodities",
            articles=synthetic_articles,
            with_market_ctx=False,
        )

    def test_does_not_raise_with_market_ctx_true(self, mock_price_history, mock_market_context,
                                                  synthetic_articles, storage_dir):
        """with_market_ctx=True triggers analyse_market_context (mocked to None)."""
        result = analyse_asset(
            asset_name="Gold",
            ticker="GC=F",
            category="Commodities",
            articles=synthetic_articles,
            with_market_ctx=True,
        )
        assert MINIMUM_RESULT_KEYS.issubset(result.keys())

    def test_signal_has_label(self, mock_price_history, synthetic_articles, storage_dir):
        result = analyse_asset(
            asset_name="Gold",
            ticker="GC=F",
            category="Commodities",
            articles=synthetic_articles,
            with_market_ctx=False,
        )
        assert isinstance(result["signal"]["label"], str)
        assert len(result["signal"]["label"]) > 0

    def test_ticker_echoed_in_result(self, mock_price_history, synthetic_articles, storage_dir):
        result = analyse_asset(
            asset_name="Gold",
            ticker="GC=F",
            category="Commodities",
            articles=synthetic_articles,
            with_market_ctx=False,
        )
        assert result["ticker"] == "GC=F"


# ── analyse_asset — degraded path ─────────────────────────────────────────────

class TestAnalyseAssetDegradedPath:
    def test_handles_none_price_history(self, mocker, synthetic_articles, storage_dir):
        """
        When fetch_price_history returns None, analyse_asset returns a dict
        with score=0.0 and label='No Data'.

        WATCH: if issue #6 changes this from returning {} to raising a specific
        FetchError, update this test to use pytest.raises(FetchError) instead.
        """
        from conftest import APP_MODULE
        mocker.patch(APP_MODULE + ".fetch_price_history", return_value=None)
        result = analyse_asset(
            asset_name="Gold",
            ticker="GC=F",
            category="Commodities",
            articles=synthetic_articles,
            with_market_ctx=False,
        )
        assert result["signal"]["score"] == 0.0
        assert result["signal"]["label"] == "No Data"

    def test_returns_dict_not_raise_when_no_articles(self, mock_price_history, storage_dir):
        """Empty article list must not crash the pipeline."""
        result = analyse_asset(
            asset_name="Gold",
            ticker="GC=F",
            category="Commodities",
            articles=[],
            with_market_ctx=False,
        )
        assert MINIMUM_RESULT_KEYS.issubset(result.keys())


# ── run_full_scan ─────────────────────────────────────────────────────────────

class TestRunFullScan:
    def test_all_tracked_categories_present(self, mock_price_history, mock_news_articles,
                                             mock_market_context, storage_dir):
        """All categories from TRACKED_ASSETS appear as top-level keys."""
        result = run_full_scan()
        assert set(TRACKED_ASSETS.keys()).issubset(result.keys())

    def test_every_leaf_has_signal_key(self, mock_price_history, mock_news_articles,
                                        mock_market_context, storage_dir):
        """Every asset result dict must contain a 'signal' key."""
        result = run_full_scan()
        for cat_results in result.values():
            for asset_result in cat_results.values():
                assert "signal" in asset_result, (
                    "Asset result missing 'signal' key: " + str(list(asset_result.keys()))
                )

    def test_does_not_write_snapshot_files(self, mock_price_history, mock_news_articles,
                                            mock_market_context, storage_dir):
        """
        run_full_scan() calls analyse_asset without save=True.
        No .json.gz files should appear in the storage dir.
        """
        run_full_scan()
        gz_files = list(storage_dir.glob("*.json.gz"))
        assert len(gz_files) == 0

    def test_returns_dict(self, mock_price_history, mock_news_articles,
                           mock_market_context, storage_dir):
        result = run_full_scan()
        assert isinstance(result, dict)
