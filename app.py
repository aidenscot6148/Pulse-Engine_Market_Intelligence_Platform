"""
app.py — Core engine for the Market Intelligence Platform.

Pipeline:
  1. Fetch price data (Yahoo Finance)
  2. Fetch news from public RSS feeds in parallel (feedparser)
  3. Deduplicate and cluster articles
  4. Score sentiment with VADER + financial lexicon
  5. Correlate news to assets via source-weighted keyword matching
  6. Detect event triggers (Fed, OPEC, earnings, ...)
  7. Compute momentum indicators (RSI, ROC, trend strength)
  8. Score composite bullish/bearish signal (-10 to +10)
  9. Analyse market context (asset-specific vs sector vs market-wide)
 10. Build a multi-factor explanation with contradiction detection
     and confidence reasoning
 11. Generate a concise "why it matters" insight
 12. Save lightweight compressed snapshot for backtesting

All configurable values come from config.py.
"""

from __future__ import annotations
# so many imports I, actually might get taxed
import datetime as dt
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import feedparser
import pandas as pd
import yfinance as yf

try:
    # VADER said "I am your father." here lol
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _vader = SentimentIntensityAnalyzer()
    VADER_AVAILABLE = True
except ImportError:
    SentimentIntensityAnalyzer = None
    _vader = None
    VADER_AVAILABLE = False

try:
    from storage import save_snapshot as _save_snapshot
    STORAGE_AVAILABLE = True
except ImportError:
    STORAGE_AVAILABLE = False
    def _save_snapshot(*_a, **_kw): pass  # noqa: E731

from config import (
    TRACKED_ASSETS,
    NEWS_FEEDS,
    ASSET_KEYWORDS,
    SECTOR_PEERS,
    MARKET_BENCHMARK,
    EVENT_TRIGGERS,
    SOURCE_WEIGHTS,
    LOOKBACK_DAYS,
    PRICE_CHANGE_THRESHOLD,
    NEWS_MAX_AGE_HOURS,
    NEWS_MAX_ARTICLES,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RELEVANCE_HIGH,
    RELEVANCE_MEDIUM,
    MOMENTUM_PERIOD,
    RSI_PERIOD,
    SIGNAL_THRESHOLDS,
    DEDUP_SIMILARITY_THRESHOLD,
    MAX_WORKERS,
    ASSET_CLASS_WEIGHTS,
)

# ── Logging ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Behold, my great work, the sentiment robot to understand money words
# I am teaching a machine to sin!
_FINANCE_LEXICON = {
    "surge": 2.5, "surges": 2.5, "surging": 2.5, "rally": 2.2,
    "rallies": 2.2, "rallying": 2.2, "bullish": 2.5, "soar": 2.8,
    "soars": 2.8, "soaring": 2.8, "breakout": 2.0, "upbeat": 1.8,
    "outperform": 2.0, "outperforms": 2.0, "beat": 1.5, "beats": 1.5,
    "upgrade": 2.0, "upgraded": 2.0, "boom": 2.5, "booming": 2.5,
    "recovery": 1.8, "rebound": 2.0, "rebounds": 2.0, "uptick": 1.5,
    "momentum": 1.3, "expansion": 1.5,
    "crash": -3.0, "crashes": -3.0, "crashing": -3.0, "plunge": -2.8,
    "plunges": -2.8, "plunging": -2.8, "bearish": -2.5, "slump": -2.2,
    "slumps": -2.2, "selloff": -2.5, "sell-off": -2.5, "tumble": -2.5,
    "tumbles": -2.5, "downturn": -2.2, "recession": -2.5,
    "downgrade": -2.0, "downgraded": -2.0, "contraction": -2.0,
    "misses": -1.8, "underperform": -2.0, "underperforms": -2.0,
}

if VADER_AVAILABLE and _vader is not None:
    _vader.lexicon.update(_FINANCE_LEXICON)


#  SECTION 1 - Price Data

def fetch_price_history(
    ticker: str,
    days: int = LOOKBACK_DAYS,
) -> Optional[pd.DataFrame]:
    """Download OHLCV history for *ticker*. Returns None on failure."""
    # politely asking yahoo finance for data. they might say no. they often do
    end   = dt.datetime.now()
    start = end - dt.timedelta(days=days)
    for attempt in range(1, MAX_RETRIES + 1):  # MAX_RETRIES = 2. i tried twice and gave up. classic
        try:
            data = yf.download(
                ticker,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                progress=False,
                timeout=REQUEST_TIMEOUT,
            )
            if data is None or data.empty:
                log.warning("Empty data for %s (attempt %d/%d)",
                            ticker, attempt, MAX_RETRIES)
                continue
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            return data
        except Exception as exc:
            log.error("Fetch error for %s (attempt %d/%d): %s",
                      ticker, attempt, MAX_RETRIES, exc)
    return None


def compute_price_metrics(df: Optional[pd.DataFrame]) -> dict:
    """Return a dict of price analytics for a price DataFrame."""
    if df is None or df.empty:
        return {}

    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    if not isinstance(close, pd.Series):
        close = pd.Series([float(close)])

    latest = float(close.iloc[-1])

    def safe_pct(n: int) -> Optional[float]:
        if len(close) > n:
            old = float(close.iloc[-(n + 1)])
            if old != 0:
                return round(((latest - old) / old) * 100, 2)
        return None

    # how violently is your money thrashing around today tell me computer
    vol = (
        round(float(close.pct_change(fill_method=None).std() * 100), 4)
        if len(close) > 1 else 0.0
    )

    return {
        "latest_price": round(latest, 4),
        "change_1d":    safe_pct(1),
        "change_7d":    safe_pct(7),
        "change_30d":   safe_pct(min(30, len(close) - 1)),
        "high_30d":     round(float(close.max()), 4),
        "low_30d":      round(float(close.min()), 4),
        "volatility":   vol,
        "trend":        _classify_trend(close),
    }


def _classify_trend(series: pd.Series) -> str:
    # GENIUS!!!!! is the short line above the long line? yes? uptrend. you're welcome
    if len(series) < 8:
        return "insufficient data"
    ma7    = float(series.rolling(7).mean().iloc[-1])
    window = min(30, len(series))
    ma30   = float(series.rolling(window).mean().iloc[-1])
    if ma7 > ma30 * 1.01:
        return "uptrend"
    if ma7 < ma30 * 0.99:
        return "downtrend"
    return "sideways"  # neither. we shrug.


#  SECTION 1.5 - Momentum Metrics

def compute_momentum_metrics(df: Optional[pd.DataFrame]) -> dict:
    """
    Return RSI, rate-of-change, trend strength, and momentum acceleration.
    Falls back to neutral defaults when data is insufficient.
    """
    # RSI 50 is the Switzerland of momentum - neutral, does nothing, get swized
    defaults = {"rsi": 50.0, "roc_10d": 0.0, "trend_strength": 0.0, "momentum_accel": 0.0}
    if df is None or df.empty:
        return defaults

    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = close.dropna()

    if len(close) < 2:
        return defaults

    rsi = _compute_rsi(close, RSI_PERIOD)
    roc = _compute_roc(close, MOMENTUM_PERIOD)

    # Trend strength: how far the 7-day MA is from the long-term MA (%)
    trend_strength = 0.0
    window = min(30, len(close))
    if len(close) >= 7:
        ma7    = float(close.rolling(7).mean().iloc[-1])
        ma_ref = float(close.rolling(window).mean().iloc[-1])
        if ma_ref != 0:
            trend_strength = round(((ma7 - ma_ref) / ma_ref) * 100, 2)

    # momentum acceleration: the derivative of the derivative.
    momentum_accel = 0.0
    if len(close) > 10:
        recent_roc = _compute_roc(close.iloc[-6:], 5)
        prior_roc  = _compute_roc(close.iloc[-11:-5], 5) if len(close) >= 11 else 0.0
        momentum_accel = round(recent_roc - prior_roc, 2)

    return {
        "rsi":            rsi,
        "roc_10d":        roc,
        "trend_strength": trend_strength,
        "momentum_accel": momentum_accel,
    }


def _compute_rsi(series: pd.Series, period: int = 14) -> float:
    # RSI > 70: the market is sweating. RSI < 30: the market is weeping. 50: fine i guess
    if len(series) < period + 1:
        return 50.0  # not enough data, here's a 50
    delta    = series.diff().dropna()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean().iloc[-1]
    avg_loss = loss.rolling(period).mean().iloc[-1]
    if pd.isna(avg_gain) or pd.isna(avg_loss):
        return 50.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(float(100 - (100 / (1 + rs))), 1)


def _compute_roc(series: pd.Series, period: int = 10) -> float:
    if len(series) <= period:
        return 0.0
    old = float(series.iloc[-(period + 1)])
    new = float(series.iloc[-1])
    if old == 0:
        return 0.0
    return round(((new - old) / old) * 100, 2)


# ================================================================
#  SECTION 2 — News Fetching  (parallel across feeds)
# ================================================================

def fetch_news_articles() -> list[dict]:
    """
    Pull recent articles from every configured RSS feed in parallel,
    then deduplicate the combined result.
    """
    # STEP 2: vacuum up the internet's opinions about money. all of them. even the bad ones
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=NEWS_MAX_AGE_HOURS)

    def _fetch_feed(source_name: str, feed_url: str) -> list[dict]:
        feed_articles: list[dict] = []
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                pub = _parse_pub_date(entry)
                if pub and pub < cutoff:
                    continue
                title   = entry.get("title", "").strip()
                summary = _strip_html(entry.get("summary", ""))
                if not title:
                    continue
                feed_articles.append({
                    "title":     title,
                    "summary":   summary,
                    "link":      entry.get("link", ""),
                    "source":    source_name,
                    "published": pub,
                })
        except Exception as exc:
            log.warning("RSS error (%s): %s", source_name, exc)
        return feed_articles

    articles: list[dict] = []
    # unleash the threads. MAX_WORKERS = 8 gremlins, all fetching simultaneously
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_fetch_feed, name, url): name
            for name, url in NEWS_FEEDS
        }
        for future in as_completed(futures):
            articles.extend(future.result())

    articles.sort(
        key=lambda a: a["published"] or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
        reverse=True,
    )
    articles = articles[:NEWS_MAX_ARTICLES]

    before = len(articles)
    articles = deduplicate_articles(articles)
    log.info(
        "Fetched %d articles from %d feeds (%d removed as duplicates)",
        len(articles), len(NEWS_FEEDS), before - len(articles),
    )
    return articles


def _parse_pub_date(entry) -> Optional[dt.datetime]:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return dt.datetime(*parsed[:6], tzinfo=dt.timezone.utc)
            except (ValueError, OverflowError, TypeError):
                pass
    return None


def _strip_html(raw: str) -> str:
    return re.sub(r"<[^>]+>", "", raw).strip()[:600]


#  SECTION 2.5 — News Deduplication and Clustering

def deduplicate_articles(articles: list[dict]) -> list[dict]:
    """
    Remove near-duplicate articles using Jaccard similarity on title tokens.
    When two titles are above the similarity threshold, the one that arrived
    earlier in the list (usually higher relevance or more recent) is kept.
    """
    # journalism has a cloning problem. Reuters writes it, everyone else copies it. we fix that here
    seen_token_sets: list[set] = []
    deduped: list[dict] = []

    for article in articles:
        tokens = set(_normalize_title(article["title"]).split())
        if not tokens:
            deduped.append(article)
            continue
        is_dup = any(
            _jaccard(tokens, prev) >= DEDUP_SIMILARITY_THRESHOLD
            for prev in seen_token_sets
        )
        if not is_dup:
            seen_token_sets.append(tokens)
            deduped.append(article)

    return deduped


def cluster_articles(articles: list[dict]) -> dict[str, list[dict]]:
    """
    Group matched articles into topic clusters by dominant event type.
    Articles with no detected event go into the "General News" cluster.
    Clusters are returned sorted by descending size.
    """
    # grouping by vibes essentially. very scientific
    clusters: dict[str, list[dict]] = {}
    for article in articles:
        events = article.get("events_detected", [])
        key    = events[0]["label"] if events else "General News"
        clusters.setdefault(key, []).append(article)

    # Sort clusters by size descending
    return dict(sorted(clusters.items(), key=lambda kv: len(kv[1]), reverse=True))


def get_display_clusters(
    news: list[dict],
    max_clusters: int = 2,
    min_relevance: Optional[float] = None,
) -> dict:
    """
    Return top N topic clusters for display, filtering low-relevance noise.

    Each cluster entry contains:
      label            — topic name (e.g. "Central Bank Policy")
      articles         — filtered article list
      count            — number of articles in cluster
      avg_sentiment    — average compound sentiment score
      sentiment_summary — human-readable summary (e.g. "mostly positive (+0.23)")

    Also returns:
      suppressed_count — articles filtered below min_relevance
      total_shown      — articles remaining after filter
    """
    cutoff = min_relevance if min_relevance is not None else float(RELEVANCE_MEDIUM)

    shown      = [a for a in news if a.get("relevance_score", 0) >= cutoff]
    suppressed = len(news) - len(shown)

    if not shown:
        return {"clusters": [], "suppressed_count": suppressed, "total_shown": 0}

    raw_clusters = cluster_articles(shown)

    clusters_out: list[dict] = []
    for label, articles in list(raw_clusters.items())[:max_clusters]:
        compounds = [a["sentiment"]["compound"] for a in articles]
        avg_sent  = sum(compounds) / len(compounds) if compounds else 0.0

        if avg_sent > 0.15:
            sent_word = "mostly positive"
        elif avg_sent < -0.15:
            sent_word = "mostly negative"
        elif avg_sent > 0.05:
            sent_word = "slightly positive"
        elif avg_sent < -0.05:
            sent_word = "slightly negative"
        else:
            sent_word = "neutral"

        clusters_out.append({
            "label":            label,
            "articles":         articles,
            "count":            len(articles),
            "avg_sentiment":    round(avg_sent, 3),
            "sentiment_summary": f"{sent_word} ({avg_sent:+.2f})",
        })

    return {
        "clusters":        clusters_out,
        "suppressed_count": suppressed,
        "total_shown":     len(shown),
    }


def _normalize_title(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", "", text.lower())


def _jaccard(a: set, b: set) -> float:
    # set theory walked so we could deduplicate Reuters articles. respect the ancestors
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


#  SECTION 3 — Sentiment Analysis  (VADER + financial words)

_POS_WORDS = frozenset([
    "surge", "rally", "gain", "rise", "jump", "climb", "boom", "bullish",
    "record", "high", "profit", "growth", "recovery", "optimism", "strong",
    "upgrade", "beat", "exceed", "soar", "breakout", "expansion", "upbeat",
])
_NEG_WORDS = frozenset([
    "crash", "drop", "fall", "plunge", "sink", "decline", "slump", "bearish",
    "low", "loss", "recession", "fear", "crisis", "panic", "weak", "downgrade",
    "miss", "risk", "sell-off", "tumble", "contraction", "downturn", "collapse",
])


def score_sentiment(text: str) -> dict:
    """
    Return {"compound": float, "pos": float, "neg": float, "neu": float}.
    Uses VADER with the injected financial lexicon; falls back to keyword
    counting if VADER is unavailable.
    """
    # at this point therapy would have been cheaper
    if VADER_AVAILABLE and _vader is not None:
        s = _vader.polarity_scores(text)
        return {"compound": s["compound"], "pos": s["pos"], "neg": s["neg"], "neu": s["neu"]}
    return _fallback_sentiment(text)


def _fallback_sentiment(text: str) -> dict:
    # VADER is on vacation so we're literally just counting mean words. very peer-reviewed
    words   = set(text.lower().split())
    p       = len(words & _POS_WORDS)
    n       = len(words & _NEG_WORDS)
    total   = p + n or 1
    return {"compound": round((p - n) / total, 4), "pos": p, "neg": n, "neu": 0}



#  SECTION 4 — News-Asset Correlation  (source-weighted)

def correlate_news(asset_name: str, articles: list[dict]) -> list[dict]:
    """
    Match articles to *asset_name* using weighted keywords, recency bonus,
    and a source credibility multiplier.
    """
    kw_pairs = ASSET_KEYWORDS.get(asset_name, []) + [(asset_name.lower(), 2)]

    matched: list[dict] = []
    for article in articles:
        blob  = (article["title"] + " " + article["summary"]).lower()
        score = sum(w for kw, w in kw_pairs if kw in blob)

        if score <= 0:
            continue  # article is blissfully unaware our asset exists. skip

        # recency bonus — yesterday's news is yesterday's problem
        recency_bonus = 0
        if article.get("published"):
            age_h = (
                dt.datetime.now(dt.timezone.utc) - article["published"]
            ).total_seconds() / 3600
            if age_h < 24:
                recency_bonus = 2
            elif age_h < 48:
                recency_bonus = 1

        # Source credibility multiplier
        src_weight   = SOURCE_WEIGHTS.get(article.get("source", ""), 1.0)
        final_score  = round((score + recency_bonus) * src_weight, 2)

        sentiment = score_sentiment(article["title"] + " " + article["summary"])
        events    = detect_events(article["title"] + " " + article["summary"])

        matched.append({
            **article,
            "relevance_score": final_score,
            "base_score":      score,
            "source_weight":   src_weight,
            "sentiment":       sentiment,
            "events_detected": events,
        })

    matched.sort(key=lambda a: a["relevance_score"], reverse=True)
    return matched


#  SECTION 5 — Event Trigger Detection

def detect_events(text: str) -> list[dict]:
    """Scan *text* for known event patterns from config.EVENT_TRIGGERS."""
    # CSI: Financial Markets. who done it this time, Fed? OPEC? Elon tweeted again?
    text_lower = text.lower()
    found: list[dict] = []
    for key, info in EVENT_TRIGGERS.items():
        hits = [kw for kw in info["keywords"] if kw in text_lower]
        if hits:
            found.append({
                "event_key":  key,
                "label":      info["label"],
                "icon":       info["icon"],
                "matched_kw": hits,
            })
    return found


#  SECTION 5.5 — Signal Scoring  (-10 to +10 composite score)

def compute_signal_score(
    metrics: dict,
    momentum: dict,
    news: list[dict],
    market_ctx: Optional[dict] = None,
    category: Optional[str] = None,
) -> dict:
    """
    Compute a composite bullish/bearish signal for an asset.

    Raw component max contributions (before per-class weighting):
      trend          +/- 2.0   (7d vs 30d MA direction)
      momentum       +/- 2.0   (10-day rate of change, normalised)
      rsi            +/- 1.0   (overbought/oversold positioning)
      sentiment      +/- 2.0   (news sentiment average)
      trend_strength +/- 1.0   (magnitude of MA divergence)
      context        +/- 1.0   (sector/market alignment)

    Per-class weights from ASSET_CLASS_WEIGHTS scale each component.
    Weak signals between -1.0 and +1.0 are labelled "Neutral".
    Total clamped to -10 to +10.
    """
    if not metrics:
        return {"score": 0.0, "label": "No Data", "components": {}, "raw_components": {}}
        # AHHHHHHHHH

    # 6 ingredients, one number. Gordon Ramsay would absolutely roast this recipe
    raw: dict[str, float] = {}

    # 1. Price trend - line goes up: +2. line goes down: -2. i built this in 10 minutes
    trend = metrics.get("trend", "sideways")
    raw["trend"] = {"uptrend": 2.0, "downtrend": -2.0, "sideways": 0.0}.get(trend, 0.0)

    # 2. ROC momentum - Rate Of (Cash burning)
    roc = momentum.get("roc_10d", 0.0)
    raw["momentum"] = round(max(-2.0, min(2.0, roc / 5.0)), 2)

    # 3. RSI positioning - above 70 the market is sweating, below 30 it is openly sobbing
    rsi = momentum.get("rsi", 50.0)
    if rsi > 70:
        raw["rsi"] = -1.0       # overbought, sir this is a Wendy's
    elif rsi < 30:
        raw["rsi"] = 1.0        # oversold (mean-reversion bullish) bargain bin, maybe
    elif rsi > 55:
        raw["rsi"] = 0.5
    elif rsi < 45:
        raw["rsi"] = -0.5
    else:
        raw["rsi"] = 0.0

    # 4. News sentiment — we multiply vibes by 4. nothing could possibly go wrong
    if news:
        avg_sent = sum(a["sentiment"]["compound"] for a in news) / len(news)
        raw["sentiment"] = round(max(-2.0, min(2.0, avg_sent * 4.0)), 2)
    else:
        raw["sentiment"] = 0.0  # no news. the void stares back

    # 5. Trend strength (3% MA divergence = full 1.0 score)
    ts = momentum.get("trend_strength", 0.0)
    raw["trend_strength"] = round(max(-1.0, min(1.0, ts / 3.0)), 2)

    # 6. Market context alignment
    ctx_score = 0.0
    if market_ctx:
        chg_1d = metrics.get("change_1d")
        if chg_1d is not None:
            direction = 1.0 if chg_1d > 0 else -1.0
            if market_ctx.get("is_market_wide"):
                ctx_score += direction * 0.5
            if market_ctx.get("is_sector_wide"):
                ctx_score += direction * 0.5
    raw["context"] = round(ctx_score, 2)

    # apply per-class multipliers - giving the robot a personality
    class_weights = ASSET_CLASS_WEIGHTS.get(category, {}) if category else {}
    components: dict[str, float] = {
        k: round(v * class_weights.get(k, 1.0), 2)
        for k, v in raw.items()
    }

    total = round(max(-10.0, min(10.0, sum(components.values()))), 2)

    # determine label — weak signals get called Neutral. diplomatic cowardice
    if total >= SIGNAL_THRESHOLDS["strong_bullish"]:
        label = "Strong Bullish"
    elif total >= SIGNAL_THRESHOLDS["bullish"]:
        label = "Bullish"
    elif total >= SIGNAL_THRESHOLDS["slightly_bullish"]:
        label = "Slightly Bullish"
    elif total > SIGNAL_THRESHOLDS["neutral"]:
        label = "Neutral"
    elif total >= SIGNAL_THRESHOLDS["slightly_bearish"]:
        label = "Slightly Bearish"
    elif total >= SIGNAL_THRESHOLDS["bearish"]:
        label = "Bearish"
    else:
        label = "Strong Bearish"

    return {
        "score":          total,
        "label":          label,
        "components":     components,     # weighted — used for total
        "raw_components": raw,            # before per-class weights
        "category":       category,
    }


#  SECTION 6 — Market Context Analysis

def analyse_market_context(
    asset_name: str,
    category: str,
    asset_change: Optional[float],
) -> dict:
    """
    Compare the asset's move against sector peers and the broad market
    benchmark to determine whether the move is asset-specific or systemic.
    """
    # is Gold falling or is EVERYTHING falling? let's call 8 friends and find out
    context: dict = {
        "peer_moves":       {},
        "benchmark_change": None,
        "is_sector_wide":   False,
        "is_market_wide":   False,
        "is_asset_specific": False,
    }

    if asset_change is None:
        return context

    direction = 1 if asset_change > 0 else -1

    # Peer comparison (parallel)
    peers = SECTOR_PEERS.get(asset_name, [])
    peer_data: dict[str, Optional[float]] = {}

    def _fetch_peer(peer_name: str):
        peer_ticker = _find_ticker(peer_name)
        if not peer_ticker:
            return peer_name, None
        peer_hist = fetch_price_history(peer_ticker, days=5)
        if peer_hist is None or peer_hist.empty:
            return peer_name, None
        peer_m = compute_price_metrics(peer_hist)
        return peer_name, peer_m.get("change_1d")

    if peers:
        with ThreadPoolExecutor(max_workers=min(len(peers), MAX_WORKERS)) as ex:
            for name, chg in ex.map(lambda p: _fetch_peer(p), peers):
                peer_data[name] = chg

    same_dir = sum(
        1 for chg in peer_data.values()
        if chg is not None and chg * direction > 0
    )
    context["peer_moves"] = peer_data
    if peers and same_dir / max(len(peers), 1) >= 0.6:
        context["is_sector_wide"] = True

    # Benchmark comparison
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


def _find_ticker(asset_name: str) -> Optional[str]:
    # plays "match the asset to the ticker". i should be doing something more productive
    for _cat, assets in TRACKED_ASSETS.items():
        if asset_name in assets:
            return assets[asset_name]
    return None


def find_category(asset_name: str) -> Optional[str]:
    for cat, assets in TRACKED_ASSETS.items():
        if asset_name in assets:
            return cat
    return None


#  SECTION 7 — Explanation Engine

def build_explanation(
    asset_name: str,
    metrics: dict,
    related_news: list[dict],
    market_ctx: Optional[dict] = None,
    momentum: Optional[dict] = None,
    signal: Optional[dict] = None,
) -> dict:
    """
    Produce a structured explanation with:
      verdict          — one-line summary
      factors          — contributing factor dicts
      detail           — long-form markdown
      confidence       — "high"/"medium"/"low" (backward-compat)
      confidence_info  — dict with score + reasoning
      contradictions   — detected signal contradictions
      why_it_matters   — concise actionable insight
    """
    if not metrics:
        return {
            "verdict":         f"No price data available for {asset_name}.",
            "factors":         [],
            "detail":          "",
            "confidence":      "none",
            "confidence_info": {"level": "none", "score": 0, "reasons": []},
            "contradictions":  [],
            "why_it_matters":  "",
        }

    momentum = momentum or {}
    signal   = signal   or {}

    price   = metrics["latest_price"]
    chg_1d  = metrics.get("change_1d")
    chg_7d  = metrics.get("change_7d")
    trend   = metrics.get("trend", "unknown")
    vol     = metrics.get("volatility", 0)
    rsi     = momentum.get("rsi", 50.0)
    roc     = momentum.get("roc_10d", 0.0)
    ts      = momentum.get("trend_strength", 0.0)

    is_significant = chg_1d is not None and abs(chg_1d) >= PRICE_CHANGE_THRESHOLD

    if chg_1d is None:
        direction_word, direction_sign = "unchanged", 0
    elif chg_1d > 0:
        direction_word, direction_sign = "up", 1
    elif chg_1d < 0:
        direction_word, direction_sign = "down", -1
    else:
        direction_word, direction_sign = "flat", 0

    factors: list[dict] = []

    # A. Price overview
    detail_parts: list[str] = [
        f"## {asset_name} — Price Analysis\n",
        (
            f"**Current price:** ${price:,.4f}  \n"
            f"**24-hour change:** {_fmt_pct(chg_1d)}  \n"
            f"**7-day change:** {_fmt_pct(chg_7d)}  \n"
            f"**30-day trend:** {trend}  \n"
            f"**Daily volatility:** {vol:.2f}%\n"
        ),
    ]

    if is_significant and vol > 0:
        z_score = abs(chg_1d) / vol
        if z_score > 2:  # z > 2 means something statistically weird happened. or it's just crypto Tuesday
            detail_parts.append(
                f"> This move is **{z_score:.1f}x** the normal daily volatility"
                f" — a statistically unusual event.\n"
            )
            factors.append({
                "type": "volatility",
                "label": "Abnormal move size",
                "detail": f"{z_score:.1f}x normal daily volatility",
            })

    # B. Momentum indicators
    detail_parts.append("## Momentum Indicators\n")
    rsi_note = ""
    if rsi > 70:
        rsi_note = f" — overbought territory"
        factors.append({
            "type": "rsi_overbought",
            "label": f"RSI overbought ({rsi:.0f})",
            "detail": "RSI above 70 suggests overextension; watch for pullback",
        })
    elif rsi < 30:
        rsi_note = f" — oversold territory"
        factors.append({
            "type": "rsi_oversold",
            "label": f"RSI oversold ({rsi:.0f})",
            "detail": "RSI below 30 suggests potential mean-reversion bounce",
        })

    detail_parts.append(
        f"**RSI ({RSI_PERIOD}-day):** {rsi:.1f}{rsi_note}  \n"
        f"**10-day Rate of Change:** {roc:+.2f}%  \n"
        f"**Trend strength (MA divergence):** {ts:+.2f}%  \n"
        f"**Momentum acceleration:** {momentum.get('momentum_accel', 0.0):+.2f}% (recent vs prior 5d ROC)\n"
    )

    if signal:
        detail_parts.append(
            f"**Signal score:** {signal.get('score', 0):+.1f} / 10 "
            f"— **{signal.get('label', 'Neutral')}**\n"
        )

    # C. Market context
    if market_ctx:
        detail_parts.append("## Market Context\n")

        if market_ctx.get("is_market_wide"):
            bench = market_ctx.get("benchmark_change")
            detail_parts.append(
                f"The **broad market also moved {_fmt_pct(bench)}**, "
                f"suggesting this is part of a **market-wide shift** rather than "
                f"something specific to {asset_name}.\n"
            )
            factors.append({
                "type": "market_wide",
                "label": "Market-wide movement",
                "detail": f"Benchmark also moved {_fmt_pct(bench)}",
            })

        if market_ctx.get("is_sector_wide"):
            peers = market_ctx.get("peer_moves", {})
            peer_strs = [
                f"{n} ({_fmt_pct(c)})" for n, c in peers.items() if c is not None
            ]
            if peer_strs:
                detail_parts.append(
                    f"**Sector peers moved in the same direction:** "
                    f"{', '.join(peer_strs)}.  \n"
                    f"This points to a **sector-wide catalyst** rather than "
                    f"an {asset_name}-specific event.\n"
                )
            factors.append({
                "type": "sector_wide",
                "label": "Sector-wide movement",
                "detail": f"Peers: {', '.join(peer_strs)}",
            })

        if market_ctx.get("is_asset_specific"):
            detail_parts.append(
                f"Peers and the broad market did **not** move similarly. "
                f"This move appears **specific to {asset_name}**.\n"
            )
            factors.append({
                "type": "asset_specific",
                "label": f"{asset_name}-specific movement",
                "detail": "Peers/market did not move in the same direction",
            })

    # D. News & event analysis
    if related_news:
        detail_parts.append(
            f"## News Analysis ({len(related_news)} matched articles)\n"
        )

        compounds  = [a["sentiment"]["compound"] for a in related_news]
        avg_sent   = sum(compounds) / len(compounds)
        pos_count  = sum(1 for c in compounds if c > 0.05)
        neg_count  = sum(1 for c in compounds if c < -0.05)
        neu_count  = len(compounds) - pos_count - neg_count

        if avg_sent > 0.15:
            sent_label = "predominantly positive"
        elif avg_sent < -0.15:
            sent_label = "predominantly negative"
        else:
            sent_label = "mixed / neutral"

        detail_parts.append(
            f"**Overall news sentiment:** {sent_label} (avg score: {avg_sent:+.2f})  \n"
            f"Positive: {pos_count}  Negative: {neg_count}  Neutral: {neu_count}\n"
        )

        if direction_sign != 0:
            if (direction_sign > 0 and avg_sent > 0.1) or (direction_sign < 0 and avg_sent < -0.1):
                detail_parts.append(
                    "News sentiment **aligns with price direction** — "
                    "the move is likely news-driven.\n"
                )
                factors.append({
                    "type": "sentiment_aligned",
                    "label": "Sentiment matches price",
                    "detail": f"News is {sent_label} while price is {direction_word}",
                })
            elif (direction_sign > 0 and avg_sent < -0.1) or (direction_sign < 0 and avg_sent > 0.1):
                detail_parts.append(
                    "**News sentiment diverges from price direction.** "
                    "Possible explanations: the news was already priced in, "
                    "contrarian trading, or technical/algorithmic factors.\n"
                )
                factors.append({
                    "type": "sentiment_diverged",
                    "label": "Sentiment diverges from price",
                    "detail": f"News is {sent_label} but price is {direction_word}",
                })

        # Event triggers
        all_events: dict[str, list[str]] = {}
        for article in related_news:
            for ev in article.get("events_detected", []):
                all_events.setdefault(ev["label"], []).append(ev["icon"])

        if all_events:
            detail_parts.append("### Detected Catalysts\n")
            for label, icons in all_events.items():
                count = len(icons)
                detail_parts.append(
                    f"- {icons[0]} **{label}** ({count} mention{'s' if count > 1 else ''})"
                )
                factors.append({
                    "type": "event",
                    "label": label,
                    "detail": f"Mentioned in {count} article(s)",
                })
            detail_parts.append("")

        # Top headlines
        detail_parts.append("### Key Headlines\n")
        for article in related_news[:7]:
            sent = article["sentiment"]["compound"]
            tag  = "[+]" if sent > 0.05 else "[-]" if sent < -0.05 else "[ ]"

            rel = article["relevance_score"]
            rel_tag = (
                "HIGH" if rel >= RELEVANCE_HIGH
                else "MED" if rel >= RELEVANCE_MEDIUM
                else "LOW"
            )

            pub = ""
            if article.get("published"):
                pub = article["published"].strftime("%b %d %H:%M")

            src_w = article.get("source_weight", 1.0)
            detail_parts.append(
                f"- {tag} **[{rel_tag}]** {article['title']}  \n"
                f"  _{article['source']}_ (weight {src_w:.2f}) · {pub} · "
                f"sentiment: {sent:+.2f}"
            )
        detail_parts.append("")

    else:
        detail_parts.append("## News Analysis\n")
        detail_parts.append("No recent news articles matched this asset.\n")
        if is_significant:
            detail_parts.append(
                "Without clear news catalysts this move may be driven by:\n"
                "- Algorithmic / high-frequency trading\n"
                "- Large institutional order flow\n"
                "- Technical breakout or breakdown\n"
                "- Broader sector rotation\n"
                "- Macro factors not captured in current feeds\n"
            )
            factors.append({
                "type": "no_news",
                "label": "No clear news catalyst",
                "detail": "Move may be technical or flow-driven",
            })

    # E. Contradiction detection
    contradictions = _detect_contradictions(metrics, momentum, factors, signal)
    if contradictions:
        detail_parts.append("## Signal Contradictions\n")
        for c in contradictions:
            detail_parts.append(f"- **{c['type'].replace('_', ' ').title()}:** {c['description']}")
        detail_parts.append("")

    # F. Verdict, confidence, why-it-matters
    verdict         = _build_verdict(asset_name, direction_word, chg_1d, factors, related_news)
    confidence_data = _assess_confidence(
        factors, related_news, market_ctx,
        metrics=metrics,
        contradictions=contradictions,
    )
    why_it_matters  = _build_why_it_matters(asset_name, momentum, factors, signal)

    # Append confidence reasoning to detail
    if confidence_data["reasons"]:
        detail_parts.append(
            f"## Confidence Assessment: {confidence_data['level'].upper()}\n"
        )
        for reason in confidence_data["reasons"]:
            detail_parts.append(f"- {reason}")
        detail_parts.append("")

    return {
        "verdict":         verdict,
        "factors":         factors,
        "detail":          "\n".join(detail_parts),
        "confidence":      confidence_data["level"],
        "confidence_info": confidence_data,
        "contradictions":  contradictions,
        "why_it_matters":  why_it_matters,
    }


def _detect_contradictions(
    metrics: dict,
    momentum: dict,
    factors: list[dict],
    signal: dict,
) -> list[dict]:
    """Identify tensions between different signal components."""
    contradictions: list[dict] = []
    chg_1d = metrics.get("change_1d")
    rsi    = momentum.get("rsi", 50.0)
    roc    = momentum.get("roc_10d", 0.0)
    trend  = metrics.get("trend", "sideways")

    # strong price surge + overbought RSI — up 2% AND RSI over 70? calm down
    if chg_1d and chg_1d > 2 and rsi > 70:
        contradictions.append({
            "type": "overbought_surge",
            "description": (
                f"Price surged {chg_1d:+.2f}% but RSI ({rsi:.0f}) is in "
                f"overbought territory. Near-term momentum may be unsustainable."
            ),
        })

    # Price drop + oversold RSI
    if chg_1d and chg_1d < -2 and rsi < 30:
        contradictions.append({
            "type": "oversold_drop",
            "description": (
                f"Price dropped {chg_1d:+.2f}% and RSI ({rsi:.0f}) signals "
                f"oversold conditions. Technical bounce is possible despite negative news flow."
            ),
        })

    # Uptrend + diverging negative sentiment
    if trend == "uptrend" and any(f["type"] == "sentiment_diverged" for f in factors):
        contradictions.append({
            "type": "trend_sentiment_conflict",
            "description": (
                "Price trend is upward but news sentiment is predominantly negative. "
                "This divergence may indicate the news is lagging, already priced in, "
                "or being overridden by technical buying."
            ),
        })

    # Downtrend + bullish signal score
    sig_score = signal.get("score", 0)
    if trend == "downtrend" and sig_score > 3:
        contradictions.append({
            "type": "trend_signal_conflict",
            "description": (
                f"Signal score is bullish ({sig_score:+.1f}) but the underlying trend "
                f"is downward. A potential reversal is indicated but unconfirmed by price action."
            ),
        })

    # Strong momentum with no news catalyst
    if abs(roc) > 10 and not any(f["type"] == "event" for f in factors):
        mv = "upward" if roc > 0 else "downward"
        contradictions.append({
            "type": "momentum_no_catalyst",
            "description": (
                f"Strong {mv} momentum ({roc:+.1f}% over 10 days) with no identifiable "
                f"news catalyst. Possible algorithmic, institutional, or technical driver."
            ),
        })

    return contradictions


def _build_why_it_matters(
    asset_name: str,
    momentum: dict,
    factors: list[dict],
    signal: dict,
) -> str:
    """Generate a concise 1-2 sentence actionable insight."""
    # final boss: say something useful in two sentences. no pressure
    parts: list[str] = []
    rsi       = momentum.get("rsi", 50.0)
    ts        = momentum.get("trend_strength", 0.0)
    sig_label = signal.get("label", "Neutral")

    if any(f["type"] == "market_wide" for f in factors):
        parts.append(
            f"This is a broad market event, not specific to {asset_name}. "
            "Portfolio-wide exposure matters more than single-asset positioning right now."
        )
    elif any(f["type"] == "asset_specific" for f in factors):
        parts.append(
            f"{asset_name} is diverging from its peers, suggesting an asset-specific "
            f"catalyst. Current signal is {sig_label}."
        )
    elif any(f["type"] == "sector_wide" for f in factors):
        parts.append(
            "The move is sector-wide. "
            "Watch peer assets for convergence or divergence as a leading signal."
        )

    if any(f["type"] == "sentiment_diverged" for f in factors):
        parts.append(
            "Caution: news sentiment and price direction diverge. "
            "This may indicate noise-driven trading or a news lag."
        )

    if rsi > 70:
        parts.append(
            f"RSI at {rsi:.0f} flags overbought conditions. "
            "Watch for short-term mean reversion."
        )
    elif rsi < 30:
        parts.append(
            f"RSI at {rsi:.0f} flags oversold conditions. "
            "A technical bounce is possible."
        )

    if not parts:
        if abs(ts) > 2:
            direction = "positive" if ts > 0 else "negative"
            parts.append(
                f"Trend momentum is {direction} ({ts:+.1f}%). "
                "Monitor for continuation or reversal in the next 24-48 hours."
            )
        else:
            parts.append(
                f"{asset_name} is showing limited directional signal. "
                "Wait for clearer momentum before acting on a directional view."
            )

    return " ".join(parts[:2])


def _build_verdict(
    name: str,
    direction: str,
    change: Optional[float],
    factors: list[dict],
    news: list[dict],
) -> str:
    if change is None:
        return f"{name} — no recent price data."

    parts = [f"{name} is **{direction} {abs(change):.2f}%** today"]

    event_factors = [f for f in factors if f["type"] == "event"]
    if event_factors:
        parts.append(f"likely driven by **{event_factors[0]['label']}**")
    elif any(f["type"] == "market_wide" for f in factors):
        parts.append("as part of a **broad market move**")
    elif any(f["type"] == "sector_wide" for f in factors):
        parts.append("in line with a **sector-wide shift**")
    elif any(f["type"] == "sentiment_aligned" for f in factors):
        if news:
            parts.append(
                f"supported by **{len(news)} related news article"
                f"{'s' if len(news) > 1 else ''}**"
            )
    elif any(f["type"] == "no_news" for f in factors):
        parts.append("with **no clear news catalyst** (possibly technical)")
    else:
        parts.append("with limited signal from available data")

    return ", ".join(parts) + "."


def _assess_confidence(
    factors: list[dict],
    news: list[dict],
    ctx: Optional[dict],
    metrics: Optional[dict] = None,
    contradictions: Optional[list[dict]] = None,
) -> dict:
    """
    Return a dict: {level, score, reasons, increases, decreases}.

    Score increases when:
      - Multiple high-quality sources agree (weight >= 1.2, at least 2)
      - Sentiment aligns with price direction
      - Event trigger detected
      - Strong price move (|change_1d| >= 2%)
      - Market or sector context confirms direction

    Score decreases when:
      - Contradictions detected
      - Low news coverage (< 2 articles)
      - Weak price move (|change_1d| < 0.5%)
      - Sentiment contradicts price direction
    """
    score     = 0
    increases: list[str] = []
    decreases: list[str] = []

    # === INCREASES ===

    # High-quality sources agreeing (credibility weight >= 1.2)
    if news:
        hq = [a for a in news if a.get("source_weight", 1.0) >= 1.2]
        if len(hq) >= 2:
            score += 3
            increases.append(
                f"{len(hq)} high-quality sources agree "
                f"(credibility weight >= 1.2x)"
            )
        else:
            n = min(len(news), 3)
            score += n
            increases.append(
                f"{len(news)} matched news article{'s' if len(news) != 1 else ''}"
            )

    # Sentiment aligns with price
    if any(f["type"] == "sentiment_aligned" for f in factors):
        score += 2
        increases.append("news sentiment aligns with price direction")

    # Event trigger detected
    event_factors = [f for f in factors if f["type"] == "event"]
    if event_factors:
        score += 3
        labels = [f["label"] for f in event_factors[:2]]
        increases.append(
            f"event trigger detected: {', '.join(labels)}"
        )

    # Strong price move provides clearer signal
    chg_1d = metrics.get("change_1d") if metrics else None
    if chg_1d is not None and abs(chg_1d) >= 2.0:
        score += 1
        increases.append(f"strong price move ({chg_1d:+.2f}%)")

    # Market or sector context confirms direction
    if ctx:
        if ctx.get("is_market_wide"):
            score += 2
            increases.append("broad market context confirms direction")
        elif ctx.get("is_sector_wide"):
            score += 1
            increases.append("sector context confirms direction")

    # === DECREASES ===

    # Contradictions detected
    if contradictions:
        penalty = min(len(contradictions) * 2, 3)
        score -= penalty
        decreases.append(
            f"{len(contradictions)} signal contradiction(s) detected "
            f"(-{penalty})"
        )

    # Low news coverage
    if not news:
        score -= 2
        decreases.append("no matched news articles (-2)")
    elif len(news) < 2:
        score -= 1
        decreases.append("very few matched news articles (-1)")

    # Weak price move — limited signal strength
    if chg_1d is not None and abs(chg_1d) < 0.5:
        score -= 1
        decreases.append(
            f"weak price move ({chg_1d:+.2f}%) — limited signal clarity (-1)"
        )

    # Sentiment contradicts price direction
    if any(f["type"] == "sentiment_diverged" for f in factors):
        score -= 2
        decreases.append("news sentiment contradicts price direction (-2)")

    # No event catalyst despite significant move
    if chg_1d is not None and abs(chg_1d) >= 2.0 and not event_factors and not news:
        score -= 1
        decreases.append("significant move with no identifiable catalyst (-1)")

    reasons = increases + decreases
    if not reasons:
        reasons = ["limited signal data available"]

    if score >= 7:
        level = "high"
    elif score >= 4:
        level = "medium"
    else:
        level = "low"

    return {
        "level":     level,
        "score":     score,
        "reasons":   reasons,
        "increases": increases,
        "decreases": decreases,
    }


def _fmt_pct(val: Optional[float]) -> str:
    if val is None:
        return "N/A"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.2f}%"



#  SECTION 8 — Orchestration

def analyse_asset(
    asset_name: str,
    ticker: str,
    category: str,
    articles: list[dict],
    with_market_ctx: bool = False,
) -> dict:
    """Full analysis pipeline for a single asset."""
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

    # Persist lightweight snapshot (fails silently)
    if STORAGE_AVAILABLE:
        try:
            _save_snapshot(asset_name, metrics, momentum, signal, news[:5])
        except Exception as exc:
            log.debug("Snapshot not saved for %s: %s", asset_name, exc)

    # Load historical context features from stored snapshots
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

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {
            ex.submit(_fetch_one_asset, cat, name, tkr, days): (cat, name)
            for cat, name, tkr in all_assets
        }
        for future in as_completed(futures):
            try:
                f_cat, f_name, f_metrics, f_mom = future.result()
                all_results.setdefault(f_cat, {})[f_name] = {"metrics": f_metrics, "momentum": f_mom}
            except Exception as exc:
                log.warning("Parallel fetch failed: %s", exc)

    return all_results


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

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {
            ex.submit(_run, name, tkr, cat): (cat, name)
            for name, tkr, cat in [(t[0], t[1], t[2]) for t in all_tasks]
        }
        for future in as_completed(futures):
            try:
                cat, name, res = future.result()
                results.setdefault(cat, {})[name] = res
            except Exception as exc:
                log.error("Analysis error: %s", exc)

    log.info("Full scan complete.")
    return results


#  CLI entry point

if __name__ == "__main__":
    print("=" * 60)
    print("  Market Intelligence Platform — CLI Test")
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

# coffee tracker cups now empty 7 -> 8