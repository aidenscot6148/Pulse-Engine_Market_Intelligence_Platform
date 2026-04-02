# Changelog

All notable changes to this project will be documented in this file.

---

## [Unreleased]

## [0.1.0] — 2026-04-02

### Added
- Core analysis engine (`app.py`) — price metrics, news correlation, composite signal scoring
- Streamlit dashboard (`dashboard.py`) — wide layout, 90s auto-refresh, background scan management
- Background scan daemon — full 24-asset scan every 30 minutes without blocking the UI
- Batch scan pipeline (`scan.py`) — supports `--dry-run` and `--quiet` flags
- Compressed snapshot storage (`storage.py`) — gzip JSON with tiered retention (7 / 30 / 60 days)
- Backtesting module (`backtest.py`) — hit-rate evaluation by signal strength and label
- Configuration module (`config.py`) — all tunable constants in one place
- 24 tracked assets across Commodities, Cryptocurrency, Tech Stocks, and Market Indices
- 12 RSS feed sources with parallel fetch and Jaccard deduplication
- VADER sentiment engine with injected financial lexicon
- 8 event category detection (central bank, geopolitical, earnings, etc.)
- Per-asset-class signal weighting profiles
- `Dockerfile` and `.dockerignore` for containerised deployment
- Fully pinned `requirements.txt` via `pip freeze`
