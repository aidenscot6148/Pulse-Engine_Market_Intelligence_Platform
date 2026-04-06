"""
src/engine.py — Pipeline orchestration.

Single responsibility: coordinate all other modules to produce per-asset
analysis results and drive the full market scan.

Pipeline role (steps 11 and 12 of the full engine):
  - analyse_asset            : run the complete pipeline for a single asset
  - run_full_scan            : run analyse_asset across every tracked asset in parallel
  - fetch_all_metrics_parallel : lightweight parallel price + momentum fetch
                                 (used by the dashboard heatmap / top-movers view)

This module owns no domain logic — it only wires together src/price, src/news,
src/signals, src/context, and src/explanation.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import (
    LOOKBACK_DAYS,
    PRICE_FETCH_WORKERS,
    TRACKED_ASSETS,
)
from src.context import analyse_market_context
from src.explanation import build_explanation
from src.news import cluster_articles, fetch_news_articles
from src.price import (
    compute_momentum_metrics,
    compute_price_metrics,
    fetch_price_history,
)
from src.signals import compute_signal_score, correlate_news

log = logging.getLogger(__name__)

try:
    from storage import save_snapshot as _save_snapshot
    STORAGE_AVAILABLE = True
except ImportError:
    STORAGE_AVAILABLE = False
    def _save_snapshot(*_a, **_kw): pass  # noqa: E731


# ── Single-asset analysis ─────────────────────────────────────────────────────

def analyse_asset(
    asset_name: str,
    ticker: str,
    category: str,
    articles: list[dict],
    with_market_ctx: bool = False,
    save: bool = False,
) -> dict:
    """Run the full analysis pipeline for a single asset."""
    log.info("Analysing %s (%s)", asset_name, ticker)
    history  = fetch_price_history(ticker)
    metrics  = compute_price_metrics(history)
    momentum = compute_momentum_metrics(history)
    news     = correlate_news(asset_name, articles)
    clusters = cluster_articles(news)

    market_ctx = None
    if with_market_ctx and metrics.get("change_1d") is not None:
        market_ctx = analyse_market_context(asset_name, category, metrics["change_1d"])

    signal      = compute_signal_score(metrics, momentum, news, market_ctx, category=category)
    explanation = build_explanation(
        asset_name, metrics, news, market_ctx, momentum, signal
    )

    # Only the batch pipeline should persist snapshots — dashboard stays read-only
    if save and STORAGE_AVAILABLE:
        try:
            _save_snapshot(asset_name, metrics, momentum, signal, news[:5])
        except Exception as exc:
            log.debug("Snapshot not saved for %s: %s", asset_name, exc)

    historical_features: dict = {}
    if STORAGE_AVAILABLE:
        try:
            from storage import get_historical_features
            historical_features = get_historical_features(asset_name)
        except Exception as exc:
            log.debug("Historical features unavailable for %s: %s", asset_name, exc)

    return {
        "ticker":              ticker,
        "history":             history,
        "metrics":             metrics,
        "momentum":            momentum,
        "news":                news,
        "clusters":            clusters,
        "market_ctx":          market_ctx,
        "signal":              signal,
        "explanation":         explanation,
        "historical_features": historical_features,
    }


# ── Parallel price/momentum fetch (dashboard helper) ──────────────────────────

def _fetch_one_asset(cat: str, name: str, tkr: str, days: int) -> tuple:
    """Worker used by fetch_all_metrics_parallel — module-level to avoid closure shadowing."""
    hist         = fetch_price_history(tkr, days=days)
    metrics_data = compute_price_metrics(hist)
    mom_data     = compute_momentum_metrics(hist)
    return cat, name, metrics_data, mom_data


def fetch_all_metrics_parallel(days: int = LOOKBACK_DAYS) -> dict:
    """
    Fetch price metrics and momentum for every tracked asset in parallel.

    Returns {category: {asset_name: {metrics: ..., momentum: ...}}}.
    Used by the dashboard for heatmaps and top-mover views.
    """
    all_results: dict = {}
    all_assets = [
        (cat, name, tkr)
        for cat, assets in TRACKED_ASSETS.items()
        for name, tkr in assets.items()
    ]

    with ThreadPoolExecutor(max_workers=PRICE_FETCH_WORKERS) as ex:
        futures = {
            ex.submit(_fetch_one_asset, cat, name, tkr, days): (cat, name)
            for cat, name, tkr in all_assets
        }
        for future in as_completed(futures):
            try:
                f_cat, f_name, f_metrics, f_mom = future.result()
                all_results.setdefault(f_cat, {})[f_name] = {
                    "metrics":  f_metrics,
                    "momentum": f_mom,
                }
            except Exception as exc:
                log.warning("Parallel fetch failed: %s", exc)

    return all_results


# ── Full market scan ──────────────────────────────────────────────────────────

def run_full_scan() -> dict:
    """Run the complete pipeline across every tracked asset in parallel."""
    log.info("Starting full market scan ...")
    articles = fetch_news_articles()
    results: dict = {}

    all_tasks = [
        (name, ticker, category)
        for category, assets in TRACKED_ASSETS.items()
        for name, ticker in assets.items()
    ]

    def _run(name: str, ticker: str, category: str) -> tuple:
        return (
            category,
            name,
            analyse_asset(name, ticker, category, articles, with_market_ctx=True),
        )

    with ThreadPoolExecutor(max_workers=PRICE_FETCH_WORKERS) as ex:
        futures = {
            ex.submit(_run, name, tkr, cat): (cat, name)
            for name, tkr, cat in all_tasks
        }
        for future in as_completed(futures):
            try:
                cat, name, res = future.result()
                results.setdefault(cat, {})[name] = res
            except Exception as exc:
                log.error("Analysis error: %s", exc)

    log.info("Full scan complete.")
    return results
