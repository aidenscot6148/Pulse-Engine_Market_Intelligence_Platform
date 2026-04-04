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

import base64
import datetime as dt
import threading
import time
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

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

# ── Theme / CSS — Retro Financial Broadsheet ──────────────────────────────────
st.markdown("""
<style>

/* ── Google Fonts ─────────────────────────────────────────────────────────── */
/* Lora: screen-optimised serif, heavier strokes — readable on dark bg        */
/* Playfair Display: display headings only                                     */
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;1,600&family=Lora:ital,wght@0,400;0,500;0,600;1,400;1,500&display=swap');

/* ── Design tokens ────────────────────────────────────────────────────────── */
:root {
  --bg-main:      #0d0c0a;
  --bg-card:      #141210;
  --bg-card-alt:  #111009;
  --bg-sidebar:   #0a0908;
  --bg-input:     #1c1a16;

  --border:       #2c2820;
  --border-mid:   #3d3630;
  --border-rule:  #524840;

  --gold:         #d4b06a;      /* slightly brighter for dark bg contrast     */
  --gold-dim:     #9a8050;
  --gold-faint:   #3a3020;

  /* Text — higher contrast than before for readability */
  --text-primary:   #f0e6cc;   /* warm ivory, clearly legible                 */
  --text-secondary: #c0aa88;   /* medium warm — body copy                     */
  --text-muted:     #7a6e58;   /* captions / ghost text                       */

  --green:      #4a7a52;
  --green-text: #8acc96;       /* bumped up for contrast                      */
  --green-bg:   #0b1c0e;

  --red:      #7a3a3a;
  --red-text: #d09090;         /* bumped up for contrast                      */
  --red-bg:   #180c0c;

  --amber:      #a07840;
  --amber-text: #e0b878;       /* bumped up for contrast                      */
  --amber-bg:   #1a1308;

  --font-body:    'Lora','Georgia','Times New Roman',serif;
  --font-display: 'Playfair Display','Georgia','Times New Roman',serif;
}

/* ── Global reset ─────────────────────────────────────────────────────────── */
html, body, [class*="css"], .stApp, .main {
  background-color: var(--bg-main) !important;
  color: var(--text-primary) !important;
  font-family: var(--font-body) !important;
  font-size: 16px;
  line-height: 1.75;
  -webkit-font-smoothing: antialiased;
}

/* ── Headings ─────────────────────────────────────────────────────────────── */
h1, h2, h3, h4, h5, h6,
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
  font-family: var(--font-display) !important;
  color: var(--text-primary) !important;
  font-weight: 700;
}
.stMarkdown h1 {
  font-size: 2.2rem !important;
  font-weight: 700 !important;
  color: var(--gold) !important;
  border-bottom: 1px solid var(--border-rule);
  padding-bottom: 10px;
  margin-bottom: 2px !important;
}
.stMarkdown h2 {
  font-size: 1.2rem !important;
  font-weight: 600 !important;
  color: var(--text-primary) !important;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border-bottom: 1px solid var(--border);
  padding-bottom: 6px;
  margin-top: 8px !important;
}
.stMarkdown h3 {
  font-size: 1.0rem !important;
  font-weight: 600 !important;
  color: var(--gold-dim) !important;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

/* ── Caption ──────────────────────────────────────────────────────────────── */
.stCaption, [data-testid="stCaptionContainer"] p {
  color: var(--text-muted) !important;
  font-family: var(--font-body) !important;
  font-size: 0.82rem !important;
  font-style: italic;
}

/* ── HR ───────────────────────────────────────────────────────────────────── */
hr {
  border: none !important;
  border-top: 1px solid var(--border-rule) !important;
  margin: 20px 0 !important;
  opacity: 0.6;
}

/* ── Sidebar ──────────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div {
  background-color: var(--bg-sidebar) !important;
  border-right: 1px solid var(--border-mid) !important;
}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stCaption {
  color: var(--text-secondary) !important;
  font-family: var(--font-body) !important;
  font-size: 0.88rem !important;
}
section[data-testid="stSidebar"] strong {
  color: var(--gold-dim) !important;
  font-weight: 600;
  letter-spacing: 0.05em;
  font-size: 0.80rem;
  text-transform: uppercase;
}

/* ── Metric cards ─────────────────────────────────────────────────────────── */
div[data-testid="stMetric"] {
  background: linear-gradient(160deg, #181510 0%, #111009 100%) !important;
  border: 1px solid var(--border-mid) !important;
  border-top: 2px solid var(--gold-faint) !important;
  border-radius: 4px !important;
  padding: 18px 22px 14px !important;
  box-shadow: 0 2px 8px rgba(0,0,0,0.4) !important;
  position: relative;
}
div[data-testid="stMetric"]::before {
  content: '';
  position: absolute;
  top: 0; left: 16px; right: 16px; height: 1px;
  background: linear-gradient(90deg, transparent, var(--gold-dim), transparent);
  opacity: 0.35;
}
div[data-testid="stMetric"] label {
  color: var(--text-muted) !important;
  font-family: var(--font-body) !important;
  font-size: 0.74rem !important;
  font-weight: 500 !important;
  letter-spacing: 0.12em !important;
  text-transform: uppercase !important;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
  color: var(--text-primary) !important;
  font-family: var(--font-display) !important;
  font-size: 1.6rem !important;
  font-weight: 700 !important;
}
div[data-testid="stMetric"] [data-testid="stMetricDelta"] svg { display: none; }
div[data-testid="stMetric"] [data-testid="stMetricDelta"] {
  font-family: var(--font-body) !important;
  font-size: 0.83rem !important;
  font-weight: 500 !important;
}

/* ── Signal card ─────────────────────────────────────────────────────────── */
.signal-card {
  padding: 22px 28px 18px;
  border-radius: 4px;
  margin-bottom: 4px;
  border-left: 3px solid;
  box-shadow: 0 2px 14px rgba(0,0,0,0.45);
}
.signal-label-text {
  font-family: var(--font-display) !important;
  font-size: 1.65rem;
  font-weight: 700;
}
.signal-score-text {
  font-family: var(--font-body);
  font-size: 0.90rem;
  font-weight: 400;
  font-style: italic;
  opacity: 0.75;
  margin-top: 5px;
}
.signal-strong-bull { background: linear-gradient(135deg,#0d2010,#0a1a0c); border-color: var(--green);   color: var(--green-text); }
.signal-bull        { background: linear-gradient(135deg,#0c1e0e,#091509); border-color: #3d6a44;        color: #7ab880; }
.signal-slight-bull { background: linear-gradient(135deg,#0c1a0e,#0a130c); border-color: #305038;        color: #9ac4a0; }
.signal-neutral     { background: linear-gradient(135deg,#181510,#121009); border-color: var(--gold-dim); color: var(--gold); }
.signal-slight-bear { background: linear-gradient(135deg,#1e1208,#170d06); border-color: #806030;        color: var(--amber-text); }
.signal-bear        { background: linear-gradient(135deg,#1e0e0e,#160909); border-color: var(--red);     color: var(--red-text); }
.signal-strong-bear { background: linear-gradient(135deg,#220e0e,#180808); border-color: #9a4040;        color: #d09090; }

/* ── Confidence badge ─────────────────────────────────────────────────────── */
.confidence-badge {
  display: inline-block;
  padding: 3px 11px;
  border-radius: 2px;
  font-family: var(--font-body);
  font-size: 0.70rem;
  font-weight: 600;
  font-style: normal;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  margin-left: 14px;
  vertical-align: middle;
  border: 1px solid;
}
.conf-high   { color: var(--green-text); border-color: var(--green); background: var(--green-bg); }
.conf-medium { color: var(--amber-text); border-color: var(--amber); background: var(--amber-bg); }
.conf-low    { color: var(--red-text);   border-color: var(--red);   background: var(--red-bg);   }

/* ── Why-it-matters box ───────────────────────────────────────────────────── */
.why-box {
  background: var(--bg-card-alt);
  border: 1px solid var(--border-mid);
  border-left: 3px solid var(--gold-dim);
  border-radius: 0 4px 4px 0;
  padding: 16px 22px;
  margin: 12px 0 14px;
  font-family: var(--font-body);
  font-size: 1.0rem;
  font-weight: 400;
  color: var(--text-secondary);
  line-height: 1.8;
}
.why-label {
  font-family: var(--font-body);
  font-size: 0.70rem;
  font-weight: 600;
  font-style: normal;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--gold-dim);
  margin-bottom: 8px;
}

/* ── Primary driver box ───────────────────────────────────────────────────── */
.driver-box {
  background: var(--green-bg);
  border-left: 3px solid var(--green);
  border-radius: 0 4px 4px 0;
  padding: 12px 18px;
  margin: 0 0 12px;
  font-family: var(--font-body);
  font-size: 0.95rem;
  color: #a8d8a8;
  line-height: 1.7;
}
.driver-label {
  font-family: var(--font-body);
  font-size: 0.70rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--green-text);
  margin-bottom: 5px;
}

/* ── Contradiction box ────────────────────────────────────────────────────── */
.contra-box {
  background: var(--red-bg);
  border: 1px solid #3a1818;
  border-radius: 4px;
  padding: 10px 16px;
  margin: 6px 0;
  font-family: var(--font-body);
  font-size: 0.92rem;
  color: #c8a0a0;
  line-height: 1.65;
}

/* ── Cluster cards ────────────────────────────────────────────────────────── */
.cluster-card {
  background: var(--bg-card-alt);
  border: 1px solid var(--border-mid);
  border-radius: 4px;
  padding: 14px 20px;
  margin-bottom: 14px;
}
.cluster-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}
.cluster-title {
  font-family: var(--font-body);
  font-size: 0.76rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--gold-dim);
}
.cluster-meta {
  font-family: var(--font-body);
  font-size: 0.80rem;
  font-style: italic;
  color: var(--text-muted);
}

/* ── News rows ────────────────────────────────────────────────────────────── */
.news-row {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 14px 18px;
  margin-bottom: 8px;
  transition: border-color 0.2s ease, background 0.2s ease;
}
.news-row:hover { border-color: var(--gold-dim); background: #181510; }
.news-meta {
  color: var(--text-muted);
  font-family: var(--font-body);
  font-size: 0.80rem;
  font-style: italic;
}
.rel-high { color: var(--gold);       font-weight: 600; }
.rel-med  { color: var(--amber-text); font-weight: 500; }
.rel-low  { color: var(--text-muted); font-weight: 400; }

/* ── Factor pills ─────────────────────────────────────────────────────────── */
.factor-pill {
  display: inline-block;
  background: #1c1910;
  border: 1px solid var(--border-mid);
  border-radius: 2px;
  padding: 3px 10px;
  margin: 3px 4px;
  font-family: var(--font-body);
  font-size: 0.82rem;
  color: var(--text-secondary);
}
.factor-pill-warn { border-color: #5a3030; color: var(--red-text); }

/* ── Historical context box ───────────────────────────────────────────────── */
.hist-box {
  background: var(--bg-card);
  border: 1px solid var(--border-mid);
  border-radius: 4px;
  padding: 12px 18px;
  font-family: var(--font-body);
  font-size: 0.90rem;
  color: var(--text-secondary);
}
.hist-label {
  font-family: var(--font-body);
  font-size: 0.70rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--gold-dim);
  margin-bottom: 5px;
}

/* ── Top movers row ───────────────────────────────────────────────────────── */
.mover-row {
  display: flex;
  justify-content: space-between;
  padding: 5px 0;
  border-bottom: 1px solid var(--border);
  font-family: var(--font-body);
  font-size: 0.85rem;
}

/* ── Backtest ─────────────────────────────────────────────────────────────── */
.bt-hit  { color: var(--green-text); }
.bt-miss { color: var(--red-text);   }

/* ── Buttons ──────────────────────────────────────────────────────────────── */
.stButton > button {
  font-family: var(--font-body) !important;
  font-size: 0.88rem !important;
  font-weight: 500 !important;
  letter-spacing: 0.06em !important;
  color: var(--gold) !important;
  background: transparent !important;
  border: 1px solid var(--gold-faint) !important;
  border-radius: 3px !important;
  padding: 7px 20px !important;
  transition: border-color 0.2s ease, background 0.2s ease !important;
}
.stButton > button:hover {
  border-color: var(--gold-dim) !important;
  background: var(--gold-faint) !important;
  color: var(--gold) !important;
}
.stButton > button:disabled { opacity: 0.35 !important; }

/* ── Selectbox ────────────────────────────────────────────────────────────── */
.stSelectbox > div > div,
[data-baseweb="select"] > div {
  background-color: var(--bg-input) !important;
  border-color: var(--border-mid) !important;
  border-radius: 3px !important;
  color: var(--text-primary) !important;
  font-family: var(--font-body) !important;
}
[data-baseweb="select"] span {
  color: var(--text-primary) !important;
  font-family: var(--font-body) !important;
  font-size: 0.95rem !important;
}

/* ── Checkbox ─────────────────────────────────────────────────────────────── */
.stCheckbox label,
.stCheckbox label p {
  color: var(--text-secondary) !important;
  font-family: var(--font-body) !important;
  font-size: 0.92rem !important;
}

/* ── Expanders ────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
  border: 1px solid var(--border) !important;
  border-radius: 4px !important;
  background: var(--bg-card) !important;
}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary p {
  font-family: var(--font-body) !important;
  font-size: 0.92rem !important;
  color: var(--text-secondary) !important;
  letter-spacing: 0.02em;
}
[data-testid="stExpander"] summary:hover,
[data-testid="stExpander"] summary:hover p { color: var(--gold) !important; }

/* ── Alerts — FULL OVERRIDE (covers all Streamlit alert variants) ─────────── */
/* Target every possible selector Streamlit uses across versions */
div[data-testid="stAlert"],
div[role="alert"],
.stAlert,
[data-baseweb="notification"] {
  font-family: var(--font-body) !important;
  font-size: 0.92rem !important;
  border-radius: 4px !important;
  border-width: 1px !important;
  border-style: solid !important;
}

/* Info banner — replace teal with slate-navy */
div[data-testid="stAlert"][kind="info"],
div[data-testid="stAlert"].st-emotion-cache-1clstc5,
[data-baseweb="notification"][kind="info"],
div[role="alert"]:has(svg[data-testid="stIconMaterial-info"]) {
  background: #0e1a2a !important;
  border-color: #1e3a5a !important;
  color: #a8c4dc !important;
}
div[data-testid="stAlert"][kind="info"] p,
div[data-testid="stAlert"][kind="info"] svg { color: #6a9abf !important; }

/* Warning banner — replace Streamlit's olive/yellow with warm amber */
div[data-testid="stAlert"][kind="warning"],
[data-baseweb="notification"][kind="warning"],
div[role="alert"]:has(svg[data-testid="stIconMaterial-warning"]) {
  background: var(--amber-bg) !important;
  border-color: #4a3010 !important;
  color: var(--amber-text) !important;
}
div[data-testid="stAlert"][kind="warning"] p,
div[data-testid="stAlert"][kind="warning"] svg { color: var(--amber-text) !important; }

/* Error banner */
div[data-testid="stAlert"][kind="error"],
[data-baseweb="notification"][kind="error"],
div[role="alert"]:has(svg[data-testid="stIconMaterial-error"]) {
  background: var(--red-bg) !important;
  border-color: #4a1818 !important;
  color: var(--red-text) !important;
}
div[data-testid="stAlert"][kind="error"] p,
div[data-testid="stAlert"][kind="error"] svg { color: var(--red-text) !important; }

/* Success banner */
div[data-testid="stAlert"][kind="success"],
[data-baseweb="notification"][kind="success"],
div[role="alert"]:has(svg[data-testid="stIconMaterial-check_circle"]) {
  background: var(--green-bg) !important;
  border-color: #1e4428 !important;
  color: var(--green-text) !important;
}

/* Nuclear override — catches any class-name Streamlit might generate */
div[data-testid="stAlert"] * {
  font-family: var(--font-body) !important;
}

/* ── Dataframe ────────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"],
[data-testid="stDataFrame"] * {
  font-family: var(--font-body) !important;
  font-size: 0.90rem !important;
}

/* ── Spinner ──────────────────────────────────────────────────────────────── */
[data-testid="stSpinner"] p {
  color: var(--text-muted) !important;
  font-family: var(--font-body) !important;
  font-style: italic;
}

/* ── Toast ────────────────────────────────────────────────────────────────── */
[data-testid="stToast"],
[data-testid="stToast"] * {
  background: var(--bg-card) !important;
  border: 1px solid var(--border-mid) !important;
  color: var(--text-primary) !important;
  font-family: var(--font-body) !important;
  border-radius: 4px !important;
}

/* ── Markdown body ────────────────────────────────────────────────────────── */
.stMarkdown p, .stMarkdown li {
  color: var(--text-secondary) !important;
  font-family: var(--font-body) !important;
  font-size: 0.97rem;
  font-weight: 400;
  line-height: 1.8;
}
.stMarkdown strong {
  color: var(--text-primary) !important;
  font-weight: 600;
}
.stMarkdown em { color: var(--text-secondary) !important; }
.stMarkdown a {
  color: var(--gold-dim) !important;
  text-decoration: underline;
  text-underline-offset: 3px;
}
.stMarkdown a:hover { color: var(--gold) !important; }
.stMarkdown code {
  background: #1e1c16 !important;
  color: var(--gold) !important;
  border: 1px solid var(--border-mid) !important;
  border-radius: 2px;
  padding: 1px 6px;
  font-size: 0.85em;
}

/* ── Scrollbars ───────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-main); }
::-webkit-scrollbar-thumb { background: var(--border-rule); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--gold-faint); }

</style>
""", unsafe_allow_html=True)


# ── Logo helper ───────────────────────────────────────────────────────────────
def _sidebar_logo_html() -> str:
    """Return an <img> tag with the logo as base64, or '' if not found."""
    logo_path = Path(__file__).parent / "pulseengine_logo.png"
    if logo_path.exists():
        data = base64.b64encode(logo_path.read_bytes()).decode()
        return (
            f'<img src="data:image/png;base64,{data}" '
            f'style="width:100%;max-width:190px;display:block;'
            f'margin:0 auto 4px auto;opacity:0.93;" />'
        )
    return f"<span style='font-size:1.4rem'>{DASHBOARD_ICON}</span>"


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

@st.cache_resource
def _get_scan_state() -> dict:
    """
    Singleton scan state — created once per process, never reset by reruns.
    """
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
    """Worker executed inside a daemon thread."""
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
    """Called on every dashboard rerun. Starts a background scan when stale."""
    now   = time.time()
    state = _get_scan_state()

    if now - st.session_state.get("_scan_check_ts", 0.0) < 60.0:
        return
    st.session_state["_scan_check_ts"] = now

    if now - _scan_summary_mtime() < SCAN_INTERVAL_MINUTES * 60:
        return

    if not state["lock"].acquire(blocking=False):
        return

    state["last_started"] = now
    state["running"]      = True
    st.session_state["_scan_rerun_done"] = False
    t = threading.Thread(
        target=_run_background_scan,
        daemon=True,
        name="full-market-scan",
    )
    t.start()


_maybe_trigger_scan()

_scan_state = _get_scan_state()
if (
    not _scan_state["running"]
    and _scan_state.get("last_finished", 0) > 0
    and not st.session_state.get("_scan_rerun_done", False)
):
    st.session_state["_scan_rerun_done"] = True
    cached_scan_summary.clear()
    st.rerun()


# Sidebar

st.sidebar.markdown(
    f"""
    <div style="text-align:center;padding:10px 0 6px 0;">
      {_sidebar_logo_html()}
      <div style="
        font-family:'EB Garamond','Georgia',serif;
        font-size:0.66rem;
        font-weight:400;
        letter-spacing:0.22em;
        text-transform:uppercase;
        color:#8a7650;
        margin-top:4px;
      ">Market Intelligence Platform</div>
    </div>
    """,
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
    _scan_color = "#a07840"
elif _mtime == 0.0:
    _scan_label = "Full scan: pending first run"
    _scan_color = "#635a48"
else:
    _age_min = int((time.time() - _mtime) / 60)
    if _age_min < 1:
        _scan_label = "Full scan: just completed"
    elif _age_min < 60:
        _scan_label = f"Full scan: {_age_min} min ago"
    else:
        _scan_label = f"Full scan: {_age_min // 60}h {_age_min % 60}m ago"
    _scan_color = "#8a7040" if _age_min < SCAN_INTERVAL_MINUTES else "#635a48"

st.sidebar.markdown(
    f'<span style="font-size:0.80rem;color:{_scan_color};font-style:italic">{_scan_label}</span>',
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
        _scan_state["running"]      = True
        threading.Thread(
            target=_run_background_scan,
            daemon=True,
            name="full-market-scan-manual",
        ).start()
    st.rerun()

# Load scan summary once
_summary         = cached_scan_summary()
_summary_results = _summary.get("results", {})
_summary_date    = _summary.get("scan_date", "")

# Top movers (sidebar)
st.sidebar.markdown("---")
st.sidebar.markdown("**Top Movers — 24h**")

with st.sidebar:
    _top_movers = _summary.get("top_movers", {})
    gainers     = _top_movers.get("gainers", [])
    losers      = _top_movers.get("losers", [])

    if not gainers and not losers:
        st.caption("No scan data yet — run a full scan to see top movers.")
    else:
        def _mover_html(items: list[dict], color: str) -> str:
            return "".join(
                f'<div class="mover-row">'
                f'<span style="color:#9e9078">{mover["name"]}</span>'
                f'<span style="color:{color};font-weight:600">{mover["chg"]:+.2f}%</span>'
                f'</div>'
                for mover in items
            )

        if gainers:
            st.markdown(
                '<div style="margin-bottom:6px;font-size:0.72rem;color:#8a7040;'
                'font-weight:600;letter-spacing:0.10em;text-transform:uppercase;font-style:italic">Gainers</div>'
                + _mover_html(gainers, "#7db888"),
                unsafe_allow_html=True,
            )
        if losers:
            st.markdown(
                '<div style="margin-top:10px;margin-bottom:6px;font-size:0.72rem;'
                'color:#7a3a3a;font-weight:600;letter-spacing:0.10em;text-transform:uppercase;font-style:italic">Losers</div>'
                + _mover_html(losers, "#c08080"),
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

_stale = is_data_stale(_summary)
if _stale and not st.session_state.get("_stale_refresh_triggered", False):
    st.session_state["_stale_refresh_triggered"] = True
    cached_scan_summary.clear()

st.markdown(f"# {selected_asset}")
st.caption(f"{selected_category}  ·  `{ticker}`  ·  last 30 days")

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

snap         = _summary_results.get(selected_category, {}).get(selected_asset, {})
_live_loaded = st.session_state.get("_live_for") == ticker
_news_loaded = st.session_state.get("_news_for") == ticker

#  SECTION 1 — Signal (from scan snapshot)

sig_score  = float(snap.get("signal_score") or 0.0)
sig_label  = snap.get("signal_label") or "Neutral"
conf       = snap.get("confidence") or "low"
conf_class = {"high": "conf-high", "medium": "conf-medium"}.get(conf, "conf-low")
conf_label = conf.upper()

_signal_class_map = {
    "Strong Bullish":   "signal-strong-bull",
    "Bullish":          "signal-bull",
    "Slightly Bullish": "signal-slight-bull",
    "Neutral":          "signal-neutral",
    "Slightly Bearish": "signal-slight-bear",
    "Bearish":          "signal-bear",
    "Strong Bearish":   "signal-strong-bear",
}
sig_css = _signal_class_map.get(sig_label, "signal-neutral")

chg_1d         = snap.get("change_1d")
is_significant = chg_1d is not None and abs(chg_1d) >= PRICE_CHANGE_THRESHOLD

sig_col, spacer = st.columns([2, 3])
with sig_col:
    if snap:
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
    else:
        st.info("No snapshot data yet — run a full scan from the sidebar.")

if is_significant:
    verb = "surged" if chg_1d > 0 else "dropped"
    st.warning(
        f"Significant move: {selected_asset} {verb} {abs(chg_1d):.2f}% in 24 hours."
    )


#  SECTION 2 — Why it matters (from scan snapshot)

verdict = snap.get("verdict", "")
if verdict:
    st.markdown(
        f'<div class="why-box">'
        f'<div class="why-label">Why it matters</div>'
        f'{verdict}'
        f'</div>',
        unsafe_allow_html=True,
    )


#  SECTION 3 — Metric cards + Momentum row (from scan snapshot)

st.markdown("---")

if snap:
    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    price = snap.get("price") or 0
    with mc1:
        st.metric(
            "Price",
            f"${price:,.2f}",
            delta=(f"{chg_1d:+.2f}% (24h)" if chg_1d is not None else None),
        )
    with mc2:
        v7 = snap.get("change_7d")
        st.metric("7-Day", f"{v7:+.2f}%" if v7 is not None else "N/A")
    with mc3:
        v30 = snap.get("change_30d")
        st.metric("30-Day", f"{v30:+.2f}%" if v30 is not None else "N/A")
    with mc4:
        vol = snap.get("volatility")
        st.metric("Volatility", f"{vol:.2f}%" if vol is not None else "N/A")
    with mc5:
        trend = snap.get("trend") or "sideways"
        st.metric("Trend", trend.title())

    m1, m2, m3, m4 = st.columns(4)
    rsi = float(snap.get("rsi") or 50.0)
    roc = float(snap.get("roc_10d") or 0.0)
    with m1:
        rsi_delta = "Overbought" if rsi > 70 else "Oversold" if rsi < 30 else None
        st.metric("RSI (14-day)", f"{rsi:.1f}", delta=rsi_delta)
    with m2:
        st.metric("10-day ROC", f"{roc:+.2f}%")
    with m3:
        ts = snap.get("trend_strength")
        st.metric("Trend Strength", f"{ts:+.2f}%" if ts is not None else "N/A", help="MA7 vs MA30 divergence")
    with m4:
        ma = snap.get("momentum_accel")
        st.metric("Momentum Accel", f"{ma:+.2f}%" if ma is not None else "N/A", help="Recent 5d ROC minus prior 5d ROC")
else:
    st.info("Run a full scan to populate metric data.")


#  SECTION 4 — News (deferred behind explicit user action)

st.markdown("---")

def _render_article(item: dict) -> None:
    sent       = item["sentiment"]["compound"]
    sent_word  = "Positive" if sent > 0.05 else "Negative" if sent < -0.05 else "Neutral"
    sent_color = "#7db888" if sent > 0.05 else "#c08080" if sent < -0.05 else "#635a48"

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
        events_html = f'<br><span style="font-size:0.80rem;color:#635a48">{tags}</span>'

    summary = item["summary"][:220]
    if len(item["summary"]) > 220:
        summary += " ..."

    st.markdown(
        f'<div class="news-row">'
        f'<strong style="color:#e4d9c4;font-family:var(--font-display)">{item["title"]}</strong><br>'
        f'<span class="news-meta">'
        f'{item["source"]} (weight {src_w:.2f}) &middot; {pub} &middot; '
        f'<span style="color:{sent_color}">{sent_word} ({sent:+.2f})</span>'
        f' &middot; Relevance: {rel_html}'
        f'</span>'
        f'{events_html}'
        f'<br><span style="color:#9e9078;font-size:0.87rem;font-style:italic">{summary}</span>'
        f'<br><a href="{item["link"]}" target="_blank" '
        f'style="color:#8a7040;font-size:0.82rem">Read full article →</a>'
        f'</div>',
        unsafe_allow_html=True,
    )


if not _news_loaded:
    st.markdown("### Related News")
    if st.button("Load news feed", key="_news_btn"):
        st.session_state["_news_for"] = ticker
        st.rerun()
    st.caption("News is not fetched on startup. Click above to load from 12 RSS feeds.")
else:
    articles   = cached_news()
    news       = correlate_news(selected_asset, articles)
    clusters   = cluster_articles(news)
    disp_clust = get_display_clusters(news, max_clusters=2)

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
                "#7db888" if cluster["avg_sentiment"] > 0.05
                else "#c08080" if cluster["avg_sentiment"] < -0.05
                else "#635a48"
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
        st.markdown(f"## Related News ({total_news} articles)")
        for article in news[:10]:
            _render_article(article)


#  SECTION 5 — Price chart & live analysis (deferred behind expander)

st.markdown("---")
with st.expander("Price Chart & Live Analysis", expanded=False):
    if not _live_loaded:
        st.caption(
            "Live price history and deep analysis are not fetched on startup. "
            "Loads 30-day OHLCV from Yahoo Finance and recomputes all signal components."
        )
        if st.button("Load live data", key="_live_btn"):
            st.session_state["_live_for"] = ticker
            st.rerun()
    else:
        history = cached_history(ticker)
        if history.empty:
            st.error(
                f"Could not load price data for **{selected_asset}** (`{ticker}`). "
                "Yahoo Finance may be temporarily unreachable. Try refreshing."
            )
        else:
            live_metrics  = compute_price_metrics(history)
            live_momentum = compute_momentum_metrics(history)

            _live_articles: list[dict] = cached_news() if _news_loaded else []
            live_news = correlate_news(selected_asset, _live_articles)

            market_ctx = None
            if run_context and live_metrics.get("change_1d") is not None:
                with st.spinner("Analysing market context (peers + benchmark) ..."):
                    market_ctx = analyse_market_context(
                        selected_asset, selected_category, live_metrics["change_1d"]
                    )

            live_signal      = compute_signal_score(
                live_metrics, live_momentum, live_news, market_ctx,
                category=selected_category,
            )
            live_explanation = build_explanation(
                selected_asset, live_metrics, live_news, market_ctx,
                live_momentum, live_signal,
            )

            live_factors    = live_explanation.get("factors", [])
            event_factors   = [f for f in live_factors if f["type"] == "event"]
            context_factors = [f for f in live_factors if f["type"] in ("market_wide", "sector_wide", "asset_specific")]
            primary_driver  = next(iter(event_factors or context_factors or live_factors), None)

            if primary_driver:
                st.markdown(
                    f'<div class="driver-box">'
                    f'<div class="driver-label">Primary driver</div>'
                    f'<strong>{primary_driver["label"]}</strong>'
                    + (f' — {primary_driver["detail"]}' if primary_driver.get("detail") else "")
                    + f'</div>',
                    unsafe_allow_html=True,
                )

            warn_types = {"rsi_overbought", "rsi_oversold", "sentiment_diverged", "volatility"}
            if live_factors:
                pills_html = "".join(
                    f'<span class="factor-pill'
                    f'{" factor-pill-warn" if f["type"] in warn_types else ""}">'
                    f'{f["label"]}</span>'
                    for f in live_factors
                )
                st.markdown(f"**Contributing factors:** {pills_html}", unsafe_allow_html=True)

            contradictions = live_explanation.get("contradictions", [])
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

            conf_info = live_explanation.get("confidence_info", {})
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

            # Price chart
            st.markdown("### Price History")
            close_col = history["Close"]
            if isinstance(close_col, pd.DataFrame):
                close_col = close_col.iloc[:, 0]

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=history.index, y=close_col,
                mode="lines",
                line=dict(color="#c4a35a", width=2.0),
                fill="tozeroy",
                fillcolor="rgba(196,163,90,0.06)",
                name="Close",
                hovertemplate="$%{y:,.4f}<br>%{x|%b %d}<extra></extra>",
            ))

            if len(close_col) >= 7:
                ma7 = close_col.rolling(7).mean()
                fig.add_trace(go.Scatter(
                    x=history.index, y=ma7,
                    mode="lines",
                    line=dict(color="#8a7040", width=1.4, dash="dash"),
                    name="7d MA",
                    hovertemplate="MA7: $%{y:,.4f}<extra></extra>",
                ))

            if len(close_col) >= 20:
                ma20 = close_col.rolling(20).mean()
                fig.add_trace(go.Scatter(
                    x=history.index, y=ma20,
                    mode="lines",
                    line=dict(color="#5a5040", width=1.2, dash="dot"),
                    name="20d MA",
                    hovertemplate="MA20: $%{y:,.4f}<extra></extra>",
                ))

            fig.update_layout(
                height=CHART_HEIGHT,
                margin=dict(l=0, r=0, t=10, b=0),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False, color="#635a48", tickformat="%b %d"),
                yaxis=dict(
                    showgrid=True,
                    gridcolor="rgba(82,72,64,0.2)",
                    color="#635a48",
                    tickprefix="$",
                ),
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1, font=dict(size=11, color="#9e9078"),
                ),
                hovermode="x unified",
                font=dict(family="Georgia, 'Times New Roman', serif"),
            )
            st.plotly_chart(fig, width="stretch")

            with st.expander("Volume chart"):
                if "Volume" in history.columns:
                    vol_col = history["Volume"]
                    if isinstance(vol_col, pd.DataFrame):
                        vol_col = vol_col.iloc[:, 0]
                    vfig = go.Figure(go.Bar(
                        x=history.index, y=vol_col,
                        marker=dict(color="rgba(196,163,90,0.25)"),
                        hovertemplate="%{y:,.0f}<extra></extra>",
                    ))
                    vfig.update_layout(
                        height=200,
                        margin=dict(l=0, r=0, t=0, b=0),
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(showgrid=False, color="#635a48"),
                        yaxis=dict(showgrid=False, color="#635a48"),
                        font=dict(family="Georgia, 'Times New Roman', serif"),
                    )
                    st.plotly_chart(vfig, width="stretch")
                else:
                    st.info("Volume data not available.")

            with st.expander("Signal component breakdown"):
                comps = live_signal.get("components", {})
                if comps:
                    comp_names  = list(comps.keys())
                    comp_values = [comps[k] for k in comp_names]
                    colors      = ["#4a7a52" if v >= 0 else "#7a3a3a" for v in comp_values]
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
                        xaxis=dict(color="#635a48"),
                        yaxis=dict(
                            color="#635a48",
                            showgrid=True,
                            gridcolor="rgba(82,72,64,0.2)",
                            range=[-3.5, 3.5],
                        ),
                        font=dict(family="Georgia, 'Times New Roman', serif", color="#9e9078"),
                    )
                    cfig.add_hline(y=0, line_color="#524840", line_width=1)
                    st.plotly_chart(cfig, width="stretch")
                    if live_signal.get("category"):
                        st.caption(
                            f"Per-class weights applied for {live_signal['category']}. "
                            "Weighted values shown. Each component contributes to the -10 to +10 signal."
                        )
                    else:
                        st.caption("Each component contributes to the -10 to +10 composite signal score.")

            if BACKTEST_AVAILABLE:
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

                    if bt.get("label_summaries"):
                        with st.expander("Accuracy by signal label"):
                            for s in bt["label_summaries"]:
                                st.markdown(f"- {s}")

                    bss = bt.get("by_signal_strength", {})
                    if bss:
                        with st.expander("Accuracy by signal strength"):
                            for bucket in ("strong", "moderate", "weak"):
                                if bucket in bss:
                                    st.markdown(f"- {bss[bucket]['summary']}")

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
                                lambda v: "color:#7db888" if v == "Yes" else "color:#c08080" if v == "No" else "",
                                subset=["Correct"],
                            )
                            st.dataframe(bt_styled, width="stretch", hide_index=True)

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
                                f"Trend **{snap.get('trend', 'unknown')}** has persisted "
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

            with st.expander("Full Analysis", expanded=is_significant):
                st.markdown(live_explanation["detail"])


#  SECTION 13 — Market heatmap

st.markdown("---")
st.markdown("## Market Heatmap — 24h Changes")

_heatmap         = _summary.get("heatmap", {})
cats_for_heatmap = _heatmap.get("categories", list(TRACKED_ASSETS.keys()))
max_assets       = _heatmap.get("max_assets", 1)
z_matrix         = _heatmap.get("z", [])
text_matrix      = _heatmap.get("text", [])

hm_fig = go.Figure(go.Heatmap(
    z=z_matrix,
    x=[f"#{i+1}" for i in range(max_assets)],
    y=cats_for_heatmap,
    text=text_matrix,
    texttemplate="%{text}",
    colorscale=[
        [0.0,  "#3d1010"],
        [0.2,  "#7a3a3a"],
        [0.4,  "#a06060"],
        [0.5,  "#1a1510"],
        [0.6,  "#4a6e50"],
        [0.8,  "#4a7a52"],
        [1.0,  "#5a9a62"],
    ],
    zmid=0, zmin=-5, zmax=5,
    showscale=True,
    colorbar=dict(
        title=dict(text="24h %", font=dict(color="#635a48", family="Georgia, serif")),
        tickfont=dict(color="#635a48", family="Georgia, serif"),
        thickness=12,
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
    yaxis=dict(color="#9e9078", showgrid=False),
    font=dict(size=10, color="#9e9078", family="Georgia, 'Times New Roman', serif"),
)
st.plotly_chart(hm_fig, width="stretch")
_hm_caption = "Clipped at ±5%. Cells with no data show 0%."
if _summary_date:
    _hm_caption += f"  ·  Data from scan: {_summary_date}"
st.caption(_hm_caption)


#  SECTION 14 — Category overview table

st.markdown("---")
with st.expander("Category Overview", expanded=False):
    _cat_data     = _summary.get("category_rows", {}).get(selected_category, {})
    rows          = _cat_data.get("rows", [])
    missing_names = _cat_data.get("missing", [])

    if rows:
        df = pd.DataFrame(rows)

        def _color_pct(val):
            if isinstance(val, (int, float)):
                if val > 0:
                    return "color: #7db888"
                if val < 0:
                    return "color: #c08080"
            return ""

        def _color_rsi(val):
            if isinstance(val, (int, float)):
                if val > 70:
                    return "color: #c08080"
                if val < 30:
                    return "color: #7db888"
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
        if missing_names:
            st.caption(f"No snapshot data for: {', '.join(missing_names)}. Run a full scan to populate.")
        elif _summary_date:
            st.caption(f"Data from scan: {_summary_date}.")
    else:
        st.info("No scan data for this category. Run a full scan first.")


# Footer

st.markdown("---")
st.caption(
    "PulseEngine  ·  "
    "Yahoo Finance (prices) + Public RSS (news) + VADER (sentiment)  ·  "
    "This is not financial advice."
)

# ── Easter egg ────────────────────────────────────────────────────────────────
_EGG_LIMIT  = 5
_EGG_WINDOW = 2.0
_EGG_URL    = "https://www.youtube.com/watch?v=QDia3e12czc"

if "_egg_clicks" not in st.session_state:
    st.session_state["_egg_clicks"] = []

clicked = st.button("·", key="_egg_btn", help="", type="tertiary")

_now = time.time()

if clicked:
    st.session_state["_egg_clicks"].append(_now)

st.session_state["_egg_clicks"] = [
    t for t in st.session_state["_egg_clicks"]
    if _now - t <= _EGG_WINDOW
]

if len(st.session_state["_egg_clicks"]) >= _EGG_LIMIT:
    st.session_state["_egg_clicks"] = []

    # Direct user-safe open (no popup blocker issues)
    st.link_button("Easter Egg Unlocked!", _EGG_URL)
