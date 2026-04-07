"""
dashboard_data.py — cached data loaders and staleness helpers for PulseEngine.

All st.cache_data functions live here so dashboard.py stays free of caching
boilerplate.  Heavy computation (scan, metrics) remains in scan.py / app.py.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from config.settings import NEWS_CACHE_TTL, PRICE_CACHE_TTL
from app.analysis import fetch_news_articles, fetch_price_history

try:
    from app.scan import load_last_scan_summary
except ImportError:
    def load_last_scan_summary() -> dict:  # noqa: E731
        return {}


# caching: because hammering Yahoo Finance 300 times a minute would get us
# banned and is antisocial
@st.cache_data(ttl=NEWS_CACHE_TTL, show_spinner="Fetching news feeds ...")
def cached_news() -> list[dict]:
    return fetch_news_articles()


@st.cache_data(ttl=PRICE_CACHE_TTL, show_spinner="Fetching prices ...")
def cached_history(symbol: str) -> pd.DataFrame:
    result = fetch_price_history(symbol)
    return result if result is not None else pd.DataFrame()


@st.cache_data(ttl=3600)
def cached_scan_summary() -> dict:
    """Load the latest scan summary from disk — no network calls."""
    return load_last_scan_summary()


def is_data_stale(summary: dict, ttl_hours: float = 1.0) -> bool:
    """Return True if the scan summary is older than *ttl_hours*, or missing."""
    scan_time = summary.get("scan_time")
    if not scan_time:
        return True
    try:
        last = dt.datetime.fromisoformat(scan_time)
        return dt.datetime.now() - last > dt.timedelta(hours=ttl_hours)
    except (ValueError, TypeError):
        return True
