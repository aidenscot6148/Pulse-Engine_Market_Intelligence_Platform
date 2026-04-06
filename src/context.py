"""
src/context.py — Market and sector context analysis.

Single responsibility: determine whether an asset move is asset-specific,
sector-wide, or market-wide by comparing it against sector peers and a
broad market benchmark.

Pipeline role (step 6 of the full engine):
  - analyse_market_context : fetch peer and benchmark prices, classify the move
  - find_category          : resolve an asset name to its config category
  - _find_ticker           : internal helper to look up a ticker from TRACKED_ASSETS
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from config import (
    MARKET_BENCHMARK,
    PRICE_FETCH_WORKERS,
    SECTOR_PEERS,
    TRACKED_ASSETS,
)
from src.price import fetch_price_history, compute_price_metrics

log = logging.getLogger(__name__)


def analyse_market_context(
    asset_name: str,
    category: str,
    asset_change: Optional[float],
) -> dict:
    """
    Compare the asset's move against sector peers and the broad market
    benchmark to determine whether the move is asset-specific or systemic.

    Returns a dict with keys:
      peer_moves        — {peer_name: change_1d}
      benchmark_change  — float or None
      is_sector_wide    — bool (>= 60 % of peers moved in same direction)
      is_market_wide    — bool (benchmark moved same direction by > 0.5 %)
      is_asset_specific — bool (neither sector nor market wide)
    """
    context: dict = {
        "peer_moves":        {},
        "benchmark_change":  None,
        "is_sector_wide":    False,
        "is_market_wide":    False,
        "is_asset_specific": False,
    }

    if asset_change is None:
        return context

    direction = 1 if asset_change > 0 else -1

    # ── Peer comparison (parallel) ───────────────────────────────────────────
    peers = SECTOR_PEERS.get(asset_name, [])
    peer_data: dict[str, Optional[float]] = {}

    def _fetch_peer(peer_name: str) -> tuple[str, Optional[float]]:
        peer_ticker = _find_ticker(peer_name)
        if not peer_ticker:
            return peer_name, None
        peer_hist = fetch_price_history(peer_ticker, days=5)
        if peer_hist is None or peer_hist.empty:
            return peer_name, None
        peer_m = compute_price_metrics(peer_hist)
        return peer_name, peer_m.get("change_1d")

    if peers:
        with ThreadPoolExecutor(max_workers=min(len(peers), PRICE_FETCH_WORKERS)) as ex:
            for name, chg in ex.map(_fetch_peer, peers):
                peer_data[name] = chg

    same_dir = sum(
        1 for chg in peer_data.values()
        if chg is not None and chg * direction > 0
    )
    context["peer_moves"] = peer_data
    if peers and same_dir / max(len(peers), 1) >= 0.6:
        context["is_sector_wide"] = True

    # ── Benchmark comparison ─────────────────────────────────────────────────
    bench_ticker = MARKET_BENCHMARK.get(category)
    if bench_ticker:
        hist = fetch_price_history(bench_ticker, days=5)
        if hist is not None and not hist.empty:
            bm        = compute_price_metrics(hist)
            bench_chg = bm.get("change_1d")
            context["benchmark_change"] = bench_chg
            if (
                bench_chg is not None
                and bench_chg * direction > 0
                and abs(bench_chg) > 0.5
            ):
                context["is_market_wide"] = True

    context["is_asset_specific"] = (
        not context["is_sector_wide"] and not context["is_market_wide"]
    )
    return context


# ── Lookup helpers ────────────────────────────────────────────────────────────

def _find_ticker(asset_name: str) -> Optional[str]:
    """Return the ticker for *asset_name* by scanning TRACKED_ASSETS."""
    for _cat, assets in TRACKED_ASSETS.items():
        if asset_name in assets:
            return assets[asset_name]
    return None


def find_category(asset_name: str) -> Optional[str]:
    """Return the category string for *asset_name*, or None if not tracked."""
    for cat, assets in TRACKED_ASSETS.items():
        if asset_name in assets:
            return cat
    return None
