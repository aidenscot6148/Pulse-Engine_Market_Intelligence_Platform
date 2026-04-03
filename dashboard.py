"""
dashboard.py — Streamlit dashboard for PulseEngine.

Run with:  streamlit run dashboard.py

Decision flow (top to bottom):
  Signal  ->  Why it matters  ->  Primary driver  ->  Contradictions / risks
  ->  Metric cards  ->  Momentum  ->  Top news clusters  ->  Price chart
  ->  Backtest summary  ->  Full analysis  ->  Market heatmap
  ->  Category overview
"""

from __future__ import annotations

import datetime as dt
import threading
import time
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as st_components

from config import (
    TRACKED_ASSETS,
    DASHBOARD_TITLE,
    DASHBOARD_ICON,
    DASHBOARD_LAYOUT,
    CHART_HEIGHT,
    DEFAULT_CATEGORY,
    PRICE_CACHE_TTL,
    NEWS_CACHE_TTL,
    PRICE_CHANGE_THRESHOLD,
    RELEVANCE_HIGH,
    RELEVANCE_MEDIUM,
    SCAN_INTERVAL_MINUTES,
    STORAGE_DIR,
)
from app import (
    VADER_AVAILABLE,
    fetch_news_articles,
    fetch_price_history,
    compute_price_metrics,
    compute_momentum_metrics,
    correlate_news,
    cluster_articles,
    get_display_clusters,
    compute_signal_score,
    build_explanation,
    analyse_market_context,
)

try:
    from backtest import evaluate_signal_accuracy, get_signal_streak
    BACKTEST_AVAILABLE = True
except ImportError:
    BACKTEST_AVAILABLE = False
    def evaluate_signal_accuracy(*_a, **_kw): return {}  # noqa: E731
    def get_signal_streak(*_a, **_kw): return {"type": "none", "length": 0}  # noqa: E731

try:
    from storage import get_historical_features
    STORAGE_AVAILABLE = True
except ImportError:
    STORAGE_AVAILABLE = False
    def get_historical_features(*_a, **_kw): return {}  # noqa: E731

try:
    from scan import load_last_scan_summary
except ImportError:
    def load_last_scan_summary() -> dict: return {}  # noqa: E731

# Page configuration
st.set_page_config(
    page_title=DASHBOARD_TITLE,
    page_icon=DASHBOARD_ICON,
    layout=DASHBOARD_LAYOUT,  # type: ignore[arg-type]
)

# Theme / CSS
# yeah... i am chatpgting this part.
st.markdown("""
<style>
  :root {
    --bg-card: #0e1117;
    --border:  #1e2a3a;
    --accent:  #4fc3f7;
    --green:   #00e676;
    --red:     #ff5252;
    --orange:  #ffab40;
    --muted:   #8892a0;
  }

  div[data-testid="stMetric"] {
    background: linear-gradient(145deg, #0f1923 0%, #152238 100%);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 20px;
  }
  div[data-testid="stMetric"] label { color: var(--muted) !important; }
  div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #e8ecf1 !important; }

  section[data-testid="stSidebar"] { background: #080c14; }

  .signal-card {
    padding: 20px 28px;
    border-radius: 12px;
    margin-bottom: 4px;
  }
  .signal-label-text {
    font-size: 1.6rem;
    font-weight: 800;
    letter-spacing: 0.5px;
  }
  .signal-score-text {
    font-size: 1.1rem;
    font-weight: 500;
    opacity: 0.8;
    margin-top: 2px;
  }
  .signal-strong-bull { background:#00320070; border:1px solid #00e67660; color:var(--green); }
  .signal-bull        { background:#00280050; border:1px solid #00c85350; color:#69f0ae; }
  .signal-slight-bull { background:#00200040; border:1px solid #00a84040; color:#a5d6a7; }
  .signal-neutral     { background:#1a274450; border:1px solid #4fc3f750; color:var(--accent); }
  .signal-slight-bear { background:#30100030; border:1px solid #ff8a6540; color:#ffab91; }
  .signal-bear        { background:#40080040; border:1px solid #ff525250; color:#ef9a9a; }
  .signal-strong-bear { background:#4a000060; border:1px solid #ff525270; color:var(--red); }

  .confidence-badge {
    display: inline-block;
    padding: 3px 11px;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-left: 10px;
    vertical-align: middle;
  }
  .conf-high   { background:#004d2640; color:var(--green);  border:1px solid #00e67640; }
  .conf-medium { background:#4a350040; color:var(--orange); border:1px solid #ffab4040; }
  .conf-low    { background:#4a000040; color:var(--red);    border:1px solid #ff525240; }

  .why-box {
    background: #0a1628;
    border: 1px solid #253a5e;
    border-radius: 8px;
    padding: 14px 20px;
    margin: 10px 0 12px 0;
    font-size: 0.95rem;
    color: #b8c8d8;
    line-height: 1.65;
  }
  .why-label {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 6px;
  }

  .driver-box {
    background: #0d1f10;
    border-left: 3px solid var(--green);
    border-radius: 0 8px 8px 0;
    padding: 10px 16px;
    margin: 0 0 10px 0;
    font-size: 0.9rem;
    color: #b8d8b8;
  }
  .driver-label {
    font-size: 0.70rem;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    color: #69f0ae;
    margin-bottom: 4px;
  }

  .contra-box {
    background: #1a1000;
    border: 1px solid #ff8a6540;
    border-radius: 8px;
    padding: 10px 16px;
    margin: 6px 0;
    font-size: 0.87rem;
    color: #ffccbc;
    line-height: 1.5;
  }

  .cluster-card {
    background: #0c1a2e;
    border: 1px solid #1a3050;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 14px;
  }
  .cluster-header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid #1e3050;
  }
  .cluster-title {
    font-size: 0.82rem;
    font-weight: 700;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    color: var(--orange);
  }
  .cluster-meta {
    font-size: 0.78rem;
    color: var(--muted);
  }

  .news-row {
    background: #0f1923;
    border: 1px solid #1c2d42;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 8px;
    transition: border-color 0.2s;
  }
  .news-row:hover { border-color: var(--accent); }
  .news-meta { color: var(--muted); font-size: 0.81rem; }
  .rel-high  { color: var(--accent); font-weight: 700; }
  .rel-med   { color: var(--orange); font-weight: 600; }
  .rel-low   { color: var(--muted);  font-weight: 400; }

  .factor-pill {
    display: inline-block;
    background: #1a2744;
    border: 1px solid #2a3f66;
    border-radius: 20px;
    padding: 4px 12px;
    margin: 3px 4px;
    font-size: 0.83rem;
    color: #c8d6e5;
  }
  .factor-pill-warn {
    border-color: #ff525260;
    color: #ef9a9a;
  }

  .hist-box {
    background: #0d1825;
    border: 1px solid #1a2e45;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 0.85rem;
    color: #8892a0;
  }
  .hist-label {
    font-size: 0.70rem;
    font-weight: 700;
    letter-spacing: 0.7px;
    text-transform: uppercase;
    color: #4fc3f7;
    margin-bottom: 4px;
  }

  .mover-row {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
    border-bottom: 1px solid #12202e;
    font-size: 0.84rem;
  }

  .bt-hit  { color: var(--green); }
  .bt-miss { color: var(--red); }
</style>
""", unsafe_allow_html=True)


# Cached data loaders

# caching: because hammering Yahoo Finance 300 times a minute would get us banned and is antisocial
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
    """Return True if the scan summary is older than ttl_hours, or missing entirely."""
    scan_time = summary.get("scan_time")
    if not scan_time:
        return True
    try:
        last = dt.datetime.fromisoformat(scan_time)
        return dt.datetime.now() - last > dt.timedelta(hours=ttl_hours)
    except (ValueError, TypeError):
        return True


#  BACKGROUND FULL-MARKET SCAN
#
#  _get_scan_state() — @st.cache_resource singleton that survives Streamlit
#    reruns within the same process.  Streamlit re-executes the entire script
#    on every rerun, so plain module-level variables (e.g. threading.Lock())
#    are reset to fresh values each time — making the lock ineffective and
#    allowing multiple concurrent scan threads to collide.  Using
#    @st.cache_resource ensures the lock and status dict are created exactly
#    once per process and shared across all reruns and browser sessions.
#
#  Trigger logic (called on every rerun via _maybe_trigger_scan):
#    1. At most one check per 60 s per browser session (st.session_state guard).
#    2. Ground truth for "last scan time" is the mtime of _scan_summary.json.gz
#       so the schedule survives server restarts.
#    3. If the file is missing or older than SCAN_INTERVAL_MINUTES, a daemon
#       thread is started; the lock prevents a second thread from starting
#       while the first is still running.

@st.cache_resource
def _get_scan_state() -> dict:
    """
    Singleton scan state — created once per process, never reset by reruns.
    Contains the threading.Lock and all status fields so they are co-located
    and share the same lifecycle.
    """
    # one lock to rule them all. one lock to find them. one lock to bring them all and in the darkness not deadlock
    return {
        "lock":          threading.Lock(),
        "running":       False,
        "last_started":  0.0,
        "last_finished": 0.0,
        "error":         "",
        "assets_done":   0,
    }


def _scan_summary_mtime() -> float:
    """Return mtime of the scan summary file, or 0.0 when the file does not exist."""
    p = Path(STORAGE_DIR) / "_scan_summary.json.gz"
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def _run_background_scan() -> None:
    """
    Worker executed inside a daemon thread.
    Holds the singleton scan lock for its entire duration so a second
    invocation is rejected even across Streamlit reruns.
    """
    # off you go little thread. do not crash. i believe in you (nervously)
    state = _get_scan_state()
    state["running"]     = True
    state["error"]       = ""
    state["assets_done"] = 0
    try:
        from scan import run_scan
        summary = run_scan(verbose=False)
        state["assets_done"] = summary.get("succeeded", 0)
    except Exception as exc:
        state["error"] = str(exc)
    finally:
        state["running"]       = False
        state["last_finished"] = time.time()
        state["lock"].release()


def _maybe_trigger_scan() -> None:
    """
    Called on every dashboard rerun.  Starts a background scan when the last
    completed scan is older than SCAN_INTERVAL_MINUTES.  Non-blocking.
    """
    now   = time.time()
    state = _get_scan_state()

    # rate-limit: at most once per 60 s within one browser session. we are not animals
    if now - st.session_state.get("_scan_check_ts", 0.0) < 60.0:
        return
    st.session_state["_scan_check_ts"] = now

    # use scan summary file mtime as ground truth — clocks don't lie, but timestamps sometimes do
    if now - _scan_summary_mtime() < SCAN_INTERVAL_MINUTES * 60:
        return  # scan is recent enough. nothing to see here. go home

    # acquire(blocking=False) returns False immediately if another thread holds it.
    if not state["lock"].acquire(blocking=False):
        return  # scan already running

    state["last_started"] = now
    state["running"]      = True   # set before start so UI reflects it on the very next rerun
    st.session_state["_scan_rerun_done"] = False  # allow one rerun after this scan finishes
    t = threading.Thread(
        target=_run_background_scan,
        daemon=True,
        name="full-market-scan",
    )
    t.start()


# Trigger check runs on every rerun — the guards inside make it cheap.
_maybe_trigger_scan()

# Auto-rerun once after a background scan completes so the UI shows fresh data.
# The flag ensures this fires exactly once per completed scan — no infinite loops.
_scan_state = _get_scan_state()
if (
    not _scan_state["running"]
    and _scan_state.get("last_finished", 0) > 0
    and not st.session_state.get("_scan_rerun_done", False)
):
    st.session_state["_scan_rerun_done"] = True
    cached_scan_summary.clear()  # drop stale disk cache so rerun loads fresh summary
    st.rerun()


# Sidebar

st.sidebar.markdown(
    f"<h2 style='margin:0;color:#e8ecf1'>{DASHBOARD_ICON} {DASHBOARD_TITLE}</h2>",
    unsafe_allow_html=True,
)
st.sidebar.markdown("---")

categories      = list(TRACKED_ASSETS.keys())
default_cat_idx = categories.index(DEFAULT_CATEGORY) if DEFAULT_CATEGORY in categories else 0
selected_category: str = (
    st.sidebar.selectbox("Category", categories, index=default_cat_idx)
    or categories[0]
)

asset_names    = list(TRACKED_ASSETS[selected_category].keys())
selected_asset: str = st.sidebar.selectbox("Asset", asset_names) or asset_names[0]
ticker = TRACKED_ASSETS[selected_category][selected_asset]

st.sidebar.markdown("---")

run_context = st.sidebar.checkbox(
    "Enable market-context analysis",
    value=False,
    help="Compares against sector peers and benchmark. Slower but deeper.",
)

st.sidebar.markdown("---")
st.sidebar.caption(f"Ticker: `{ticker}`")
st.sidebar.caption(f"Prices refresh: every {PRICE_CACHE_TTL}s")
st.sidebar.caption(f"News refresh: every {NEWS_CACHE_TTL}s")
st.sidebar.caption(f"Sentiment engine: {'VADER' if VADER_AVAILABLE else 'Keyword fallback'}")
st.sidebar.caption(f"Last refresh: {dt.datetime.now().strftime('%H:%M:%S')}")

if st.sidebar.button("Refresh Data"):
    cached_scan_summary.clear()
    st.cache_data.clear()
    st.session_state.pop("_stale_refresh_triggered", None)
    st.rerun()

# Full-scan status + manual trigger
st.sidebar.markdown("---")

_scan_state = _get_scan_state()
_mtime = _scan_summary_mtime()
if _scan_state["running"]:
    _scan_label = "Full scan: running..."
    _scan_color = "#ffab40"
elif _mtime == 0.0:
    _scan_label = "Full scan: pending first run"
    _scan_color = "#8892a0"
else:
    _age_min = int((time.time() - _mtime) / 60)
    if _age_min < 1:
        _scan_label = "Full scan: just completed"
    elif _age_min < 60:
        _scan_label = f"Full scan: {_age_min} min ago"
    else:
        _scan_label = f"Full scan: {_age_min // 60}h {_age_min % 60}m ago"
    _scan_color = "#4fc3f7" if _age_min < SCAN_INTERVAL_MINUTES else "#8892a0"

st.sidebar.markdown(
    f'<span style="font-size:0.80rem;color:{_scan_color}">{_scan_label}</span>',
    unsafe_allow_html=True,
)
if _scan_state.get("assets_done"):
    st.sidebar.caption(f"{_scan_state['assets_done']} assets in last scan")
if _scan_state.get("error"):
    st.sidebar.caption(f"Scan error: {_scan_state['error'][:80]}")

if st.sidebar.button(
    "Run full scan now",
    disabled=_scan_state["running"],
    help=f"Scans all {sum(len(v) for v in TRACKED_ASSETS.values())} tracked assets and saves snapshots",
):
    if not _scan_state["running"] and _scan_state["lock"].acquire(blocking=False):
        _scan_state["last_started"] = time.time()
        _scan_state["running"]      = True   # mark before start so button disables on next rerun
        threading.Thread(
            target=_run_background_scan,
            daemon=True,
            name="full-market-scan-manual",
        ).start()
    st.rerun()

# Load scan summary once — used for Top Movers, Heatmap, and Category Overview.
# Disk read only, no network calls.
_summary         = cached_scan_summary()
_summary_results = _summary.get("results", {})
_summary_date    = _summary.get("scan_date", "")

# Top movers (sidebar)
st.sidebar.markdown("---")
st.sidebar.markdown("**Top Movers — 24h**")  # winners and losers. wall street in 10 rows

with st.sidebar:
    movers: list[dict] = []
    for cat, cat_assets in _summary_results.items():
        for name, data in cat_assets.items():
            chg = data.get("change_1d")
            if chg is not None:
                movers.append({"name": name, "cat": cat, "chg": chg})

    if not movers:
        st.caption("No scan data yet — run a full scan to see top movers.")
    else:
        movers_sorted = sorted(movers, key=lambda x: x["chg"], reverse=True)
        gainers = movers_sorted[:5]
        losers  = movers_sorted[-5:][::-1]

        def _mover_html(items: list[dict], color: str) -> str:
            return "".join(
                f'<div class="mover-row">'
                f'<span style="color:#c8d6e5">{mover["name"]}</span>'
                f'<span style="color:{color};font-weight:600">{mover["chg"]:+.2f}%</span>'
                f'</div>'
                for mover in items
            )

        if gainers:
            st.markdown(
                '<div style="margin-bottom:6px;font-size:0.75rem;color:#4fc3f7;'
                'font-weight:700;letter-spacing:0.5px">GAINERS</div>'
                + _mover_html(gainers, "#00e676"),
                unsafe_allow_html=True,
            )
        if losers:
            st.markdown(
                '<div style="margin-top:10px;margin-bottom:6px;font-size:0.75rem;'
                'color:#ff5252;font-weight:700;letter-spacing:0.5px">LOSERS</div>'
                + _mover_html(losers, "#ff5252"),
                unsafe_allow_html=True,
            )
        if _summary_date:
            st.caption(f"From scan: {_summary_date}")

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Data sources (free, public):**  \n"
    "Yahoo Finance · Reuters · CNBC  \n"
    "BBC · CoinDesk · Google News  \n"
    "NPR · MarketWatch · Al Jazeera"
)



#  MAIN PANEL - fetch data

# Stale data detection — runs once per session to avoid infinite rerun loops.
# If data is stale, the background scan is already triggered by _maybe_trigger_scan()
# above. We just need to clear the disk cache once so the next rerun picks up fresh data.
_stale = is_data_stale(_summary)
if _stale and not st.session_state.get("_stale_refresh_triggered", False):
    st.session_state["_stale_refresh_triggered"] = True
    cached_scan_summary.clear()  # invalidate disk cache so next rerun loads fresh summary

st.markdown(f"# {selected_asset}")
st.caption(f"{selected_category}  ·  `{ticker}`  ·  last 30 days")

# Stale / scan-running banners — shown once, do not block rendering
if _get_scan_state()["running"]:
    st.info("Updating market data in background — snapshot data shown below.", icon="🔄")
elif _stale:
    st.warning(
        "Market data may be outdated. A background refresh has been triggered. "
        "Use **Refresh Data** in the sidebar to reload immediately.",
        icon="⚠️",
    )

_scan_time = _summary.get("scan_time", "")
if _scan_time:
    try:
        _last_dt = dt.datetime.fromisoformat(_scan_time)
        st.caption(f"Market data last updated: {_last_dt.strftime('%Y-%m-%d %H:%M')}")
    except (ValueError, TypeError):
        pass

history  = cached_history(ticker)
articles = cached_news()

if history.empty:
    st.error(
        f"Could not load price data for **{selected_asset}** (`{ticker}`). "
        "Yahoo Finance may be temporarily unreachable. Try refreshing."
    )
    st.stop()

metrics    = compute_price_metrics(history)
momentum   = compute_momentum_metrics(history)
news       = correlate_news(selected_asset, articles)
clusters   = cluster_articles(news)
disp_clust = get_display_clusters(news, max_clusters=2)

market_ctx = None
if run_context and metrics.get("change_1d") is not None:
    with st.spinner("Analysing market context (peers + benchmark) ..."):
        market_ctx = analyse_market_context(
            selected_asset, selected_category, metrics["change_1d"]
        )

signal      = compute_signal_score(
    metrics, momentum, news, market_ctx, category=selected_category
)
explanation = build_explanation(
    selected_asset, metrics, news, market_ctx, momentum, signal
)

#  SECTION 1 — Signal (prominent, top of page)

sig_score = signal.get("score", 0.0)
sig_label = signal.get("label", "Neutral")
conf      = explanation["confidence"]
conf_class = {"high": "conf-high", "medium": "conf-medium"}.get(conf, "conf-low")
conf_label = conf.upper()

_signal_class_map = {
    "Strong Bullish":  "signal-strong-bull",
    "Bullish":         "signal-bull",
    "Slightly Bullish": "signal-slight-bull",
    "Neutral":         "signal-neutral",
    "Slightly Bearish": "signal-slight-bear",
    "Bearish":         "signal-bear",
    "Strong Bearish":  "signal-strong-bear",
}
sig_css = _signal_class_map.get(sig_label, "signal-neutral")

chg_1d         = metrics.get("change_1d")
is_significant = chg_1d is not None and abs(chg_1d) >= PRICE_CHANGE_THRESHOLD

sig_col, spacer = st.columns([2, 3])
with sig_col:
    st.markdown(
        f'<div class="signal-card {sig_css}">'
        f'<div class="signal-label-text">{sig_label}'
        f'<span class="confidence-badge {conf_class}">Confidence: {conf_label}</span>'
        f'</div>'
        f'<div class="signal-score-text">Score: {sig_score:+.1f} / 10'
        f'&nbsp;&nbsp;&middot;&nbsp;&nbsp;'
        f'<span style="font-size:0.9rem;opacity:0.7">{selected_category}</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

if is_significant:
    verb = "surged" if chg_1d > 0 else "dropped"
    st.warning(
        f"Significant move: {selected_asset} {verb} {abs(chg_1d):.2f}% in 24 hours."
    )



#  SECTION 2 — Why it matters

why = explanation.get("why_it_matters", "")
verdict = explanation.get("verdict", "")

if why or verdict:
    combined = verdict
    if why and why != verdict:
        combined = f"{verdict}  {why}"
    st.markdown(
        f'<div class="why-box">'
        f'<div class="why-label">Why it matters</div>'
        f'{combined}'
        f'</div>',
        unsafe_allow_html=True,
    )



#  SECTION 3 - Primary driver

factors = explanation.get("factors", [])
event_factors   = [f for f in factors if f["type"] == "event"]
context_factors = [f for f in factors if f["type"] in ("market_wide", "sector_wide", "asset_specific")]
primary_driver = next(iter(event_factors or context_factors or factors), None)

if primary_driver:
    st.markdown(
        f'<div class="driver-box">'
        f'<div class="driver-label">Primary driver</div>'
        f'<strong>{primary_driver["label"]}</strong>'
        + (f' — {primary_driver["detail"]}' if primary_driver.get("detail") else "")
        + f'</div>',
        unsafe_allow_html=True,
    )

# Factor pills (supporting factors)
if factors:
    warn_types  = {"rsi_overbought", "rsi_oversold", "sentiment_diverged", "volatility"}
    pills_html  = "".join(
        f'<span class="factor-pill'
        f'{" factor-pill-warn" if f["type"] in warn_types else ""}">'
        f'{f["label"]}</span>'
        for f in factors
    )
    st.markdown(f"**Contributing factors:** {pills_html}", unsafe_allow_html=True)


#  SECTION 4 — Contradictions / risks

contradictions = explanation.get("contradictions", [])
if contradictions:
    with st.expander(f"Risks and contradictions ({len(contradictions)})"):
        for c in contradictions:
            st.markdown(
                f'<div class="contra-box">'
                f'<strong>{c["type"].replace("_", " ").title()}:</strong> '
                f'{c["description"]}'
                f'</div>',
                unsafe_allow_html=True,
            )


#  SECTION 5 — Confidence reasoning

conf_info = explanation.get("confidence_info", {})
if conf_info.get("increases") or conf_info.get("decreases"):
    with st.expander("Confidence reasoning"):
        if conf_info.get("increases"):
            st.markdown("**Increases confidence:**")
            for r in conf_info["increases"]:
                st.markdown(f"- {r}")
        if conf_info.get("decreases"):
            st.markdown("**Decreases confidence:**")
            for r in conf_info["decreases"]:
                st.markdown(f"- {r}")
        st.caption(f"Confidence score: {conf_info.get('score', 0)} / 12")


#  SECTION 6 — Metric cards + Momentum row

st.markdown("---")

mc1, mc2, mc3, mc4, mc5 = st.columns(5)
with mc1:
    st.metric(
        "Price",
        f"${metrics.get('latest_price', 0):,.2f}",
        delta=(
            f"{metrics['change_1d']:+.2f}% (24h)"
            if metrics.get("change_1d") is not None else None
        ),
    )
with mc2:
    v7 = metrics.get("change_7d")
    st.metric("7-Day", f"{v7:+.2f}%" if v7 is not None else "N/A")
with mc3:
    v30 = metrics.get("change_30d")
    st.metric("30-Day", f"{v30:+.2f}%" if v30 is not None else "N/A")
with mc4:
    st.metric("Volatility", f"{metrics.get('volatility', 0):.2f}%")
with mc5:
    trend = metrics.get("trend", "sideways")
    st.metric("Trend", trend.title())

m1, m2, m3, m4 = st.columns(4)
rsi    = momentum.get("rsi", 50.0)
roc    = momentum.get("roc_10d", 0.0)
ts     = momentum.get("trend_strength", 0.0)
maccel = momentum.get("momentum_accel", 0.0)

with m1:
    rsi_delta = "Overbought" if rsi > 70 else "Oversold" if rsi < 30 else None
    st.metric("RSI (14-day)", f"{rsi:.1f}", delta=rsi_delta)
with m2:
    st.metric("10-day ROC", f"{roc:+.2f}%")
with m3:
    st.metric("Trend Strength", f"{ts:+.2f}%", help="MA7 vs MA30 divergence")
with m4:
    st.metric("Momentum Accel", f"{maccel:+.2f}%", help="Recent 5d ROC minus prior 5d ROC")


#  SECTION 7 — Top news clusters (1-2, prominent)

st.markdown("---")

def _render_article(item: dict) -> None:
    sent       = item["sentiment"]["compound"]
    sent_word  = "Positive" if sent > 0.05 else "Negative" if sent < -0.05 else "Neutral"
    sent_color = "#00e676" if sent > 0.05 else "#ff5252" if sent < -0.05 else "#8892a0"

    rel = item["relevance_score"]
    rel_html = (
        '<span class="rel-high">HIGH</span>'   if rel >= RELEVANCE_HIGH
        else '<span class="rel-med">MED</span>'  if rel >= RELEVANCE_MEDIUM
        else '<span class="rel-low">LOW</span>'
    )

    src_w = item.get("source_weight", 1.0)
    pub   = ""
    if item.get("published"):
        pub = item["published"].strftime("%b %d, %H:%M")

    events_html = ""
    if item.get("events_detected"):
        tags = " · ".join(f'{e["icon"]} {e["label"]}' for e in item["events_detected"])
        events_html = f'<br><span style="font-size:0.80rem;color:#8892a0">{tags}</span>'

    summary = item["summary"][:220]
    if len(item["summary"]) > 220:
        summary += " ..."

    st.markdown(
        f'<div class="news-row">'
        f'<strong>{item["title"]}</strong><br>'
        f'<span class="news-meta">'
        f'{item["source"]} (weight {src_w:.2f}) &middot; {pub} &middot; '
        f'<span style="color:{sent_color}">{sent_word} ({sent:+.2f})</span>'
        f' &middot; Relevance: {rel_html}'
        f'</span>'
        f'{events_html}'
        f'<br><span style="color:#a0aec0;font-size:0.87rem">{summary}</span>'
        f'<br><a href="{item["link"]}" target="_blank" '
        f'style="color:#4fc3f7;font-size:0.82rem">Read full article</a>'
        f'</div>',
        unsafe_allow_html=True,
    )


clusters_data = disp_clust["clusters"]
suppressed    = disp_clust["suppressed_count"]
total_news    = len(news)

if not news:
    st.markdown("## Related News")
    st.info("No recent articles matched this asset. Try a different one.")
elif clusters_data:
    cluster_count = len(clusters_data)
    st.markdown(
        f"## Related News — Top {cluster_count} Cluster{'s' if cluster_count > 1 else ''}"
        + (f" ({suppressed} low-relevance article(s) suppressed)" if suppressed > 0 else "")
    )

    for cluster in clusters_data:
        sent_summary = cluster["sentiment_summary"]
        sent_color_c = (
            "#00e676" if cluster["avg_sentiment"] > 0.05
            else "#ff5252" if cluster["avg_sentiment"] < -0.05
            else "#8892a0"
        )
        st.markdown(
            f'<div class="cluster-card">'
            f'<div class="cluster-header-row">'
            f'<span class="cluster-title">{cluster["label"]}</span>'
            f'<span class="cluster-meta">'
            f'{cluster["count"]} article{"s" if cluster["count"] != 1 else ""}'
            f' &middot; sentiment: '
            f'<span style="color:{sent_color_c}">{sent_summary}</span>'
            f'</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        for art in cluster["articles"][:3]:
            _render_article(art)

    # Remaining articles in an expander
    shown_set = {
        id(a)
        for c in clusters_data
        for a in c["articles"][:3]
    }
    remaining = [a for a in news if id(a) not in shown_set]
    if remaining:
        with st.expander(f"More articles ({len(remaining)} remaining)"):
            for art in remaining[:10]:
                _render_article(art)
else:
    # No meaningful clustering — render flat
    st.markdown(f"## Related News ({total_news} articles)")
    for article in news[:10]:
        _render_article(article)


#  SECTION 8 - Price chart

st.markdown("---")
st.markdown("### Price History")

close_col = history["Close"]
if isinstance(close_col, pd.DataFrame):
    close_col = close_col.iloc[:, 0]

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=history.index, y=close_col,
    mode="lines",
    line=dict(color="#4fc3f7", width=2.2),
    fill="tozeroy",
    fillcolor="rgba(79,195,247,0.07)",
    name="Close",
    hovertemplate="$%{y:,.4f}<br>%{x|%b %d}<extra></extra>",
))

if len(close_col) >= 7:
    ma7 = close_col.rolling(7).mean()
    fig.add_trace(go.Scatter(
        x=history.index, y=ma7,
        mode="lines",
        line=dict(color="#ffab40", width=1.4, dash="dash"),
        name="7d MA",
        hovertemplate="MA7: $%{y:,.4f}<extra></extra>",
    ))

if len(close_col) >= 20:
    ma20 = close_col.rolling(20).mean()
    fig.add_trace(go.Scatter(
        x=history.index, y=ma20,
        mode="lines",
        line=dict(color="#b39ddb", width=1.2, dash="dot"),
        name="20d MA",
        hovertemplate="MA20: $%{y:,.4f}<extra></extra>",
    ))

fig.update_layout(
    height=CHART_HEIGHT,
    margin=dict(l=0, r=0, t=10, b=0),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    xaxis=dict(showgrid=False, color="#8892a0", tickformat="%b %d"),
    yaxis=dict(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.05)",
        color="#8892a0",
        tickprefix="$",
    ),
    legend=dict(
        orientation="h", yanchor="bottom", y=1.02,
        xanchor="right", x=1, font=dict(size=11, color="#8892a0"),
    ),
    hovermode="x unified",
)
st.plotly_chart(fig, width="stretch")

with st.expander("Volume chart"):
    if "Volume" in history.columns:
        vol_col = history["Volume"]
        if isinstance(vol_col, pd.DataFrame):
            vol_col = vol_col.iloc[:, 0]
        vfig = go.Figure(go.Bar(
            x=history.index, y=vol_col,
            marker=dict(color="rgba(79,195,247,0.35)"),
            hovertemplate="%{y:,.0f}<extra></extra>",
        ))
        vfig.update_layout(
            height=200,
            margin=dict(l=0, r=0, t=0, b=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False, color="#8892a0"),
            yaxis=dict(showgrid=False, color="#8892a0"),
        )
        st.plotly_chart(vfig, width="stretch")
    else:
        st.info("Volume data not available.")


#  SECTION 9 — Signal component breakdown

with st.expander("Signal component breakdown"):
    comps     = signal.get("components", {})
    raw_comps = signal.get("raw_components", {})
    if comps:
        comp_names  = list(comps.keys())
        comp_values = [comps[k] for k in comp_names]
        colors      = ["#00e676" if v >= 0 else "#ff5252" for v in comp_values]
        cfig = go.Figure(go.Bar(
            x=comp_names,
            y=comp_values,
            marker=dict(color=colors),
            text=[f"{v:+.2f}" for v in comp_values],
            textposition="outside",
        ))
        cfig.update_layout(
            height=220,
            margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(color="#8892a0"),
            yaxis=dict(
                color="#8892a0",
                showgrid=True,
                gridcolor="rgba(255,255,255,0.05)",
                range=[-3.5, 3.5],
            ),
        )
        cfig.add_hline(y=0, line_color="#8892a0", line_width=1)
        st.plotly_chart(cfig, width="stretch")
        if signal.get("category"):
            st.caption(
                f"Per-class weights applied for {signal['category']}. "
                "Weighted values shown. Each component contributes to the -10 to +10 signal."
            )
        else:
            st.caption("Each component contributes to the -10 to +10 composite signal score.")


#  SECTION 10 — Backtest summary

if BACKTEST_AVAILABLE:
    st.markdown("---")
    bt = evaluate_signal_accuracy(selected_asset)

    if bt["num_evaluated"] == 0:
        with st.expander("Signal Backtest (no history yet)"):
            st.info(
                bt["message"] + "\n\n"
                "Snapshots are saved each time this app runs. "
                "Return after a few days to see backtest results."
            )
    else:
        st.markdown("### Signal Backtest")
        hit_rate = bt["hit_rate"]
        streak   = get_signal_streak(bt["details"])

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            pct = f"{hit_rate * 100:.1f}%" if hit_rate is not None else "N/A"
            st.metric("Directional Accuracy", pct)
        with c2:
            st.metric("Signals Evaluated", bt["num_evaluated"])
        with c3:
            avg_str = f"{bt['avg_signal_score']:+.2f}" if bt["avg_signal_score"] is not None else "N/A"
            st.metric("Avg Signal Score", avg_str)
        with c4:
            if streak["type"] != "none":
                st.metric("Current Streak", f"{streak['length']} {streak['type'].upper()}")

        st.caption(bt["message"])

        # Label-level accuracy summaries (e.g. "Strong Bullish -> 70% accuracy")
        if bt.get("label_summaries"):
            with st.expander("Accuracy by signal label"):
                for s in bt["label_summaries"]:
                    st.markdown(f"- {s}")

        # Accuracy by signal strength
        bss = bt.get("by_signal_strength", {})
        if bss:
            with st.expander("Accuracy by signal strength"):
                for bucket in ("strong", "moderate", "weak"):
                    if bucket in bss:
                        st.markdown(f"- {bss[bucket]['summary']}")

        # Detail table
        if bt["details"]:
            with st.expander("Signal history (last 15)"):
                detail_rows = [
                    {
                        "Date":      d["date"],
                        "Signal":    d["signal_label"],
                        "Score":     d["signal_score"],
                        "Predicted": d["predicted"],
                        "Actual":    f"{d['actual_change']:+.2f}% ({d['actual']})",
                        "Correct":   "Yes" if d["correct"] else "No",
                    }
                    for d in bt["details"][:15]
                ]
                bt_df     = pd.DataFrame(detail_rows)
                bt_styled = bt_df.style.map(
                    lambda v: "color:#00e676" if v == "Yes" else "color:#ff5252" if v == "No" else "",
                    subset=["Correct"],
                )
                st.dataframe(bt_styled, width="stretch", hide_index=True)



#  SECTION 11 - Historical context (signal consistency)
if STORAGE_AVAILABLE:
    hist_feat = get_historical_features(selected_asset)
    if hist_feat.get("available", 0) >= 2:
        with st.expander("Historical context"):
            consistency = hist_feat.get("signal_consistency")
            persistence = hist_feat.get("trend_persistence", 0)
            t_vs_y      = hist_feat.get("today_vs_yesterday", {})

            hf_parts = []
            if consistency is not None:
                hf_parts.append(
                    f"Signal consistency over last {hist_feat['available']} snapshots: "
                    f"**{consistency * 100:.0f}%** pointing same direction as today."
                )
            if persistence > 0:
                hf_parts.append(
                    f"Trend **{metrics.get('trend', 'unknown')}** has persisted "
                    f"for **{persistence}** consecutive snapshot(s)."
                )
            if t_vs_y.get("signal_score"):
                d = t_vs_y["signal_score"]
                direction = "higher" if d["change"] > 0 else "lower" if d["change"] < 0 else "unchanged"
                hf_parts.append(
                    f"Signal score today ({d['today']:+.2f}) is **{direction}** "
                    f"than yesterday ({d['yesterday']:+.2f}, change: {d['change']:+.2f})."
                )

            for part in hf_parts:
                st.markdown(part)

            st.caption(
                f"Based on {hist_feat['available']} stored snapshot(s). "
                "Snapshots accumulate as the app runs over multiple days."
            )


#  SECTION 12 — Full analysis expander

with st.expander("Full Analysis", expanded=is_significant):
    st.markdown(explanation["detail"])


#  SECTION 13 — Market heatmap

st.markdown("---")
st.markdown("## Market Heatmap — 24h Changes")

cats_for_heatmap = list(TRACKED_ASSETS.keys())
max_assets       = max(len(TRACKED_ASSETS[c]) for c in cats_for_heatmap)
z_matrix:    list[list] = []
text_matrix: list[list] = []

for cat in cats_for_heatmap:
    cat_asset_names = list(TRACKED_ASSETS[cat].keys())
    row_z:    list = []
    row_text: list = []
    for name in cat_asset_names:
        chg = _summary_results.get(cat, {}).get(name, {}).get("change_1d")
        if chg is not None:
            row_z.append(round(chg, 2))
            row_text.append(f"{name}<br>{chg:+.1f}%")
        else:
            row_z.append(0)
            row_text.append(name)
    while len(row_z) < max_assets:
        row_z.append(None)
        row_text.append("")
    z_matrix.append(row_z)
    text_matrix.append(row_text)

hm_fig = go.Figure(go.Heatmap(
    z=z_matrix,
    x=[f"#{i+1}" for i in range(max_assets)],
    y=cats_for_heatmap,
    text=text_matrix,
    texttemplate="%{text}",
    colorscale=[
        [0.0, "#b71c1c"], [0.2, "#e53935"], [0.4, "#ef9a9a"],
        [0.5, "#1a2744"],
        [0.6, "#a5d6a7"], [0.8, "#43a047"], [1.0, "#00e676"],
    ],
    zmid=0, zmin=-5, zmax=5,
    showscale=True,
    colorbar=dict(
        title=dict(text="24h %", font=dict(color="#8892a0")),
        tickfont=dict(color="#8892a0"),
        thickness=14,
    ),
    xgap=3, ygap=3,
    hovertemplate="%{text}<extra></extra>",
))
hm_fig.update_layout(
    height=220,
    margin=dict(l=120, r=80, t=10, b=10),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    xaxis=dict(showticklabels=False, showgrid=False),
    yaxis=dict(color="#8892a0", showgrid=False),
    font=dict(size=10, color="#c8d6e5"),
)
st.plotly_chart(hm_fig, width="stretch")
_hm_caption = "Clipped at +/- 5%. Cells with no data show 0%."
if _summary_date:
    _hm_caption += f"  ·  Data from scan: {_summary_date}"
st.caption(_hm_caption)


#  SECTION 14 — Category overview table

st.markdown("---")
with st.expander("Category Overview", expanded=False):
    _cat_summary = _summary_results.get(selected_category, {})
    rows = []

    for name, tkr in TRACKED_ASSETS[selected_category].items():
        snap = _cat_summary.get(name, {})

        if snap.get("price") is not None:
            # Fast path: use pre-computed scan summary — no network call
            rows.append({
                "Asset":   name,
                "Signal":  snap.get("signal_label", "—"),
                "Price":   snap.get("price", 0),
                "24h %":   snap.get("change_1d", 0) or 0,
                "7d %":    snap.get("change_7d", 0) or 0,
                "Trend":   snap.get("trend", "?"),
                "RSI":     snap.get("rsi", 50.0),
                "10d ROC": snap.get("roc_10d", 0.0),
                "News":    len(correlate_news(name, articles)),
            })
        else:
            # Slow path: live fetch for assets missing from summary
            hist = cached_history(tkr)
            if hist.empty:
                continue
            m   = compute_price_metrics(hist)
            mom = compute_momentum_metrics(hist)
            rows.append({
                "Asset":   name,
                "Signal":  "—",
                "Price":   m.get("latest_price", 0),
                "24h %":   m.get("change_1d", 0) or 0,
                "7d %":    m.get("change_7d", 0) or 0,
                "Trend":   m.get("trend", "?"),
                "RSI":     mom.get("rsi", 50.0),
                "10d ROC": mom.get("roc_10d", 0.0),
                "News":    len(correlate_news(name, articles)),
            })

    if rows:
        df = pd.DataFrame(rows)

        def _color_pct(val):
            if isinstance(val, (int, float)):
                if val > 0:
                    return "color: #00e676"
                if val < 0:
                    return "color: #ff5252"
            return ""

        def _color_rsi(val):
            if isinstance(val, (int, float)):
                if val > 70:
                    return "color: #ff5252"
                if val < 30:
                    return "color: #00e676"
            return ""

        styled = (
            df.style
            .format({
                "Price":   "${:,.2f}",
                "24h %":   "{:+.2f}%",
                "7d %":    "{:+.2f}%",
                "RSI":     "{:.1f}",
                "10d ROC": "{:+.2f}%",
            })
            .map(_color_pct, subset=["24h %", "7d %", "10d ROC"])
            .map(_color_rsi, subset=["RSI"])
        )
        st.dataframe(styled, width="stretch", hide_index=True)
        if _summary_date:
            st.caption(f"Data from scan: {_summary_date}. Open with live data via 'Refresh all data'.")
        else:
            st.caption("No scan summary found. Run a full scan for faster loads.")
    else:
        st.info("No data available for this category. Run a full scan first.")


# Auto-refresh

@st.fragment(run_every=PRICE_CACHE_TTL)
def _auto_refresher() -> None:
    st.rerun(scope="app")

_auto_refresher()

# Footer

st.markdown("---")
st.caption(
    "PulseEngine  ·  "
    "Yahoo Finance (prices) + Public RSS (news) + VADER (sentiment)  ·  "
    "This is not financial advice."
)

# ── Easter egg ───────────────────────────────────────────────────────────────
# a tiny "·" button hiding in the footer. clicking it 5 times fast does something.
# does not affect any real functionality. purely for the chaos goblins among us.

_EGG_LIMIT     = 5      # clicks needed
_EGG_WINDOW    = 2.0    # seconds; reset counter if gap exceeds this
_EGG_URL       = "https://www.youtube.com/watch?v=QDia3e12czc"

if "_egg_count" not in st.session_state:
    st.session_state["_egg_count"] = 0
if "_egg_ts" not in st.session_state:
    st.session_state["_egg_ts"] = 0.0

# the button itself: a grey mid-dot in the footer — looks like punctuation, acts like a trap
if st.button("·", key="_egg_btn", help="", type="tertiary"):
    _now = time.time()
    if _now - st.session_state["_egg_ts"] > _EGG_WINDOW:
        st.session_state["_egg_count"] = 1          # gap too long — restart sequence
    else:
        st.session_state["_egg_count"] += 1
    st.session_state["_egg_ts"] = _now

if st.session_state["_egg_count"] >= _EGG_LIMIT:
    st.session_state["_egg_count"] = 0              # reset so it doesn't loop
    st.toast("never gonna give you up 🎷", icon="🎷")
    st_components.html(
        f'<script>window.open("{_EGG_URL}", "_blank");</script>',
        height=0,
    )
