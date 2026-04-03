"""
scan.py — Full-market snapshot pipeline.

Processes and saves snapshots for ALL tracked assets independently
of the dashboard.  Each run saves per-asset compressed JSON snapshots
and writes a hierarchical scan summary.

Usage:
    python scan.py              # process all assets, verbose
    python scan.py --quiet      # suppress per-asset log lines
    python scan.py --dry-run    # show what would run, save nothing

Structure of the scan summary (market_data/_scan_summary.json.gz):
    {
      "scan_date":  "2026-03-31",
      "scan_time":  "2026-03-31T14:00:00",
      "total":      24,
      "succeeded":  24,
      "errors":     [],
      "results": {
        "Commodities": {
          "Gold": {
            "ticker":       "GC=F",
            "signal_score": 4.5,
            "signal_label": "Bullish",
            "price":        2150.43,
            "change_1d":    1.25,
            "change_7d":    3.45,
            "trend":        "uptrend",
            "rsi":          65.3,
            "roc_10d":      3.45,
            "confidence":   "high",
            "verdict":      "Gold is up 1.25% today ..."
          },
          ...
        },
        "Cryptocurrency": { ... },
        ...
      }
    }
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import logging
from pathlib import Path

from config import TRACKED_ASSETS, STORAGE_DIR
from app import fetch_news_articles, analyse_asset

log = logging.getLogger(__name__)

_SUMMARY_FILE = Path(STORAGE_DIR) / "_scan_summary.json.gz"


def run_scan(verbose: bool = True, dry_run: bool = False) -> dict:
    """
    Run the full pipeline for every tracked asset.

    Returns a hierarchical dict:
        {category: {asset_name: scalar_summary_dict}}
    plus top-level meta fields (scan_date, errors, etc.).
    """
    started = dt.datetime.now().isoformat()
    log.info("Full market scan started at %s", started)

    if dry_run:
        log.info("DRY RUN — no snapshots will be written.")

    # fetch news once, reuse for every asset. work smarter not harder
    articles = fetch_news_articles()
    log.info("Fetched %d deduplicated articles for correlation.", len(articles))

    total   = sum(len(v) for v in TRACKED_ASSETS.values())
    done    = 0
    errors: list[dict] = []  # the hall of shame
    results: dict      = {}

    # processing all 24 assets. this takes a while. go make a coffee. seriously
    for category, asset_map in TRACKED_ASSETS.items():
        results[category] = {}
        for asset_name, ticker in asset_map.items():
            done += 1
            try:
                # crunch crunch crunch
                r = analyse_asset(
                    asset_name, ticker, category, articles,
                    with_market_ctx=False,   # keep scan fast; context optional
                    save=True,               # scan pipeline is the sole snapshot writer
                )
                sig     = r["signal"]
                metrics = r["metrics"]
                mom     = r["momentum"]
                expl    = r["explanation"]

                entry = {
                    "ticker":       ticker,
                    "signal_score": sig.get("score"),
                    "signal_label": sig.get("label"),
                    "price":        metrics.get("latest_price"),
                    "change_1d":    metrics.get("change_1d"),
                    "change_7d":    metrics.get("change_7d"),
                    "trend":        metrics.get("trend"),
                    "rsi":          mom.get("rsi"),
                    "roc_10d":      mom.get("roc_10d"),
                    "confidence":   expl.get("confidence"),
                    "verdict":      expl.get("verdict", ""),
                }
                results[category][asset_name] = entry

                if verbose:
                    chg       = metrics.get("change_1d") or 0.0
                    sig_score = sig.get("score", 0.0)
                    log.info(
                        "[%d/%d] %-22s %-20s %+.1f  (%+.2f%%)",
                        done, total, asset_name, sig.get("label", ""), sig_score, chg,
                    )

            except Exception as exc:
                log.error(
                    "[%d/%d] FAILED %-22s: %s", done, total, asset_name, exc
                )
                errors.append({"asset": asset_name, "category": category, "error": str(exc)})
                results.setdefault(category, {})[asset_name] = {}

    scan_result = {
        "scan_date": dt.date.today().isoformat(),
        "scan_time": started,
        "total":     total,
        "succeeded": total - len(errors),
        "errors":    errors,
        "results":   results,
    }

    if not dry_run:
        _save_summary(scan_result)  # seal it in a zip. like embarrassment in a jar
        # Apply retention policy on stored per-asset snapshots
        try:
            from storage import apply_retention_policy, cleanup_old_snapshots
            apply_retention_policy()
            deleted = cleanup_old_snapshots()
            if deleted:
                log.info("Retention cleanup: removed %d old snapshot(s).", deleted)
        except Exception as exc:
            log.warning("Retention policy failed: %s", exc)

    log.info(
        "Scan complete: %d/%d assets processed, %d error(s).",
        scan_result["succeeded"], total, len(errors),
    )
    return scan_result


def load_last_scan_summary() -> dict:
    """
    Load the most recent scan summary written by run_scan().
    Returns an empty dict if no summary exists or it cannot be read.
    """
    if not _SUMMARY_FILE.exists():
        return {}
    try:
        with gzip.open(_SUMMARY_FILE, "rb") as fh:
            return json.loads(fh.read().decode("utf-8"))
    except Exception as exc:
        log.warning("Could not load scan summary: %s", exc)
        return {}


# ── Internal ─────────────────────────────────────────────────────

def _save_summary(payload: dict) -> None:
    """Write hierarchical scan summary to compressed JSON."""
    try:
        _SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        with gzip.open(_SUMMARY_FILE, "wb", compresslevel=6) as fh:
            fh.write(raw)
        log.info("Scan summary saved: %s", _SUMMARY_FILE)
    except Exception as exc:
        log.warning("Could not save scan summary: %s", exc)


# ── CLI entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="PulseEngine — Full Market Scan"
    )
    parser.add_argument(
        "--quiet",   action="store_true",
        help="Suppress per-asset log lines (errors still shown)",
        # --quiet: for when you're embarrassed by your own logs
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run the pipeline but do not write any files",
    )
    args = parser.parse_args()

    scan_summary = run_scan(verbose=not args.quiet, dry_run=args.dry_run)

    print()
    print("=" * 65)
    print(f"  Market Scan — {scan_summary['scan_date']}")
    print(f"  Assets processed: {scan_summary['succeeded']}/{scan_summary['total']}")
    if scan_summary["errors"]:
        print(f"  Errors ({len(scan_summary['errors'])}):")
        for e in scan_summary["errors"]:
            print(f"    [{e['category']}] {e['asset']}: {e['error']}")
    print()
    print("  Top signals by magnitude:")
    all_sigs: list[tuple] = []
    for cat, assets in scan_summary["results"].items():
        for name, data in assets.items():
            score = data.get("signal_score")
            if score is not None:
                all_sigs.append((name, cat, score, data.get("signal_label", "")))
    all_sigs.sort(key=lambda x: -abs(x[2]))
    for name, cat, score, label in all_sigs[:10]:
        print(f"    {name:<22s} {label:<20s} {score:+.1f}")
    print("=" * 65)
