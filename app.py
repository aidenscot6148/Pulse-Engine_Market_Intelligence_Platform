"""
app.py — Backward-compatible re-export shim.

All domain logic now lives in src/:
  src/price       — fetch_price_history, compute_price_metrics, compute_momentum_metrics
  src/sentiment   — score_sentiment, VADER_AVAILABLE
  src/news        — fetch_news_articles, deduplicate_articles, cluster_articles, get_display_clusters
  src/signals     — correlate_news, detect_events, compute_signal_score
  src/context     — analyse_market_context, find_category
  src/explanation — build_explanation
  src/engine      — analyse_asset, run_full_scan, fetch_all_metrics_parallel

This file re-exports every name that dashboard.py, scan.py, dashboard_data.py,
and the test suite currently import from app, so those files continue to work
without any changes.

New code should import directly from the src/ modules.
"""

# ── Logging (kept here so `python app.py` still configures it) ───────────────
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

# ── Re-exports ────────────────────────────────────────────────────────────────

from src.price import (  # noqa: F401
    fetch_price_history,
    compute_price_metrics,
    compute_momentum_metrics,
    _compute_rsi,
    _compute_roc,
    _classify_trend,
)

from src.sentiment import (  # noqa: F401
    VADER_AVAILABLE,
    score_sentiment,
    _FINANCE_LEXICON,
)

from src.news import (  # noqa: F401
    fetch_news_articles,
    deduplicate_articles,
    cluster_articles,
    get_display_clusters,
)

from src.signals import (  # noqa: F401
    correlate_news,
    detect_events,
    compute_signal_score,
)

from src.context import (  # noqa: F401
    analyse_market_context,
    find_category,
)

from src.explanation import (  # noqa: F401
    build_explanation,
)

from src.engine import (  # noqa: F401
    analyse_asset,
    run_full_scan,
    fetch_all_metrics_parallel,
    STORAGE_AVAILABLE,
)

# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    from config import TRACKED_ASSETS

    print("=" * 60)
    print("  PulseEngine — CLI Test")
    print("=" * 60)
    print(f"VADER available:   {VADER_AVAILABLE}")
    print(f"Storage available: {STORAGE_AVAILABLE}")

    _articles = fetch_news_articles()
    print(f"Fetched {len(_articles)} articles\n")

    first_cat   = list(TRACKED_ASSETS.keys())[0]
    first_asset = list(TRACKED_ASSETS[first_cat].keys())[0]
    first_tick  = TRACKED_ASSETS[first_cat][first_asset]

    result = analyse_asset(
        first_asset, first_tick, first_cat, _articles, with_market_ctx=False
    )
    print(result["explanation"]["verdict"])
    print()
    print(f"Signal: {result['signal']['label']} ({result['signal']['score']:+.1f})")
    print()
    print(f"Why it matters: {result['explanation']['why_it_matters']}")
    print()
    print(result["explanation"]["detail"][:800])
