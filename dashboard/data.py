"""
dashboard_data.py — cached data loaders and staleness helpers for PulseEngine.

All st.cache_data functions live here so dashboard.py stays free of caching
boilerplate.  Heavy computation (scan, metrics) remains in scan.py / app.py.
"""

from __future__ import annotations

import datetime as dt
import logging

import pandas as pd
import streamlit as st

from config.settings import NEWS_CACHE_TTL, PRICE_CACHE_TTL
from app.analysis import fetch_news_articles, fetch_price_history
from src.errors import DataFetchError

log = logging.getLogger(__name__)

try:
    from app.scan import load_last_scan_summary
except ImportError:
    log.warning(
        "app.scan could not be imported; load_last_scan_summary will return {}. "
        "Ensure app/scan.py exists and all its dependencies are installed."
    )
    def load_last_scan_summary() -> dict:  # noqa: E731
        return {}


# caching: because hammering Yahoo Finance 300 times a minute would get us
# banned and is antisocial
@st.cache_data(ttl=NEWS_CACHE_TTL, show_spinner="Fetching news feeds ...")
def cached_news() -> list[dict]:
    return fetch_news_articles()


@st.cache_data(ttl=PRICE_CACHE_TTL, show_spinner="Fetching prices ...")
def cached_history(symbol: str) -> pd.DataFrame:
    try:
        result = fetch_price_history(symbol)
    except DataFetchError as exc:
        log.warning("Price fetch failed for %s: %s", symbol, exc)
        return pd.DataFrame()
    return result if result is not None else pd.DataFrame()


@st.cache_data(ttl=3600)
def cached_scan_summary(cache_token: int = 0) -> dict:
    """Load the latest scan summary from disk — no network calls."""
    _ = cache_token  # cache-buster only; kept out of the return value on purpose
    return load_last_scan_summary()


def is_data_stale(summary: dict, ttl_hours: float = 1.0) -> bool:
    """Return True if the scan summary is older than *ttl_hours*, or missing."""
    scan_time = summary.get("scan_time")
    if not scan_time:
        return True
    try:
        last = dt.datetime.fromisoformat(scan_time)
        if last.tzinfo is None:
            last = last.replace(tzinfo=dt.timezone.utc)
        return dt.datetime.now(dt.timezone.utc) - last > dt.timedelta(hours=ttl_hours)
    except (ValueError, TypeError):
        return True
