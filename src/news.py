"""
src/news.py — News fetching, deduplication, and clustering.

Single responsibility: acquire and pre-process raw article data from RSS feeds.

Pipeline role (steps 2 and 2.5 of the full engine):
  - fetch_news_articles   : pull recent articles from all configured RSS feeds in parallel
  - deduplicate_articles  : remove near-duplicates via Jaccard title similarity
  - cluster_articles      : group articles by dominant detected event type
  - get_display_clusters  : filtered, summarised cluster view for UI consumption

This module does NOT score sentiment or match articles to assets — those
responsibilities belong to src/sentiment.py and src/signals.py respectively.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import feedparser

from config.settings import (
    DEDUP_SIMILARITY_THRESHOLD,
    MAX_WORKERS,
    NEWS_FEEDS,
    NEWS_MAX_AGE_HOURS,
    NEWS_MAX_ARTICLES,
    RELEVANCE_MEDIUM,
)

log = logging.getLogger(__name__)


# ── Fetching ─────────────────────────────────────────────────────────────────

def fetch_news_articles() -> list[dict]:
    """
    Pull recent articles from every configured RSS feed in parallel,
    then deduplicate the combined result.
    """
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


# ── Deduplication ─────────────────────────────────────────────────────────────

def deduplicate_articles(articles: list[dict]) -> list[dict]:
    """
    Remove near-duplicate articles using Jaccard similarity on title tokens.

    When two titles exceed the similarity threshold, the one that appears
    earlier in the list (higher relevance / more recent) is kept.
    """
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


# ── Clustering ────────────────────────────────────────────────────────────────

def cluster_articles(articles: list[dict]) -> dict[str, list[dict]]:
    """
    Group matched articles into topic clusters by dominant event type.

    Articles with no detected event go into the "General News" cluster.
    Clusters are returned sorted by descending size.
    """
    clusters: dict[str, list[dict]] = {}
    for article in articles:
        events = article.get("events_detected", [])
        key    = events[0]["label"] if events else "General News"
        clusters.setdefault(key, []).append(article)

    return dict(sorted(clusters.items(), key=lambda kv: len(kv[1]), reverse=True))


def get_display_clusters(
    news: list[dict],
    max_clusters: int = 2,
    min_relevance: Optional[float] = None,
) -> dict:
    """
    Return top N topic clusters for display, filtering low-relevance noise.

    Each cluster entry contains:
      label             — topic name (e.g. "Central Bank Policy")
      articles          — filtered article list
      count             — number of articles in cluster
      avg_sentiment     — average compound sentiment score
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
            "label":             label,
            "articles":          articles,
            "count":             len(articles),
            "avg_sentiment":     round(avg_sent, 3),
            "sentiment_summary": f"{sent_word} ({avg_sent:+.2f})",
        })

    return {
        "clusters":        clusters_out,
        "suppressed_count": suppressed,
        "total_shown":     len(shown),
    }


# ── Private helpers ───────────────────────────────────────────────────────────

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


def _normalize_title(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", "", text.lower())


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
