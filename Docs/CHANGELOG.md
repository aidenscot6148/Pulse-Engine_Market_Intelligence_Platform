# Changelog

All notable changes to this project will be documented in this file.

---

# Changelog

All notable changes to this project will be documented in this file.

---

## [0.2.0] - 2026-04-04
### "UI Overhaul + Performance & Scalability Improvements"

## Added
- Easter egg functionality in the UI.

### Changed
- Complete dashboard UI redesign with a retro financial aesthetic (cards, typography, layout, sidebar, and visual hierarchy)
- Improved structure of signal, explanation, contradiction, and news sections for faster readability

### Improved
- Reduced load times via parallel data fetching and scan-level reuse of news data
- Improved performance under higher user load through more efficient execution and reduced redundant processing
- Optimized storage layer with compressed snapshots, atomic writes, and noise-threshold updates
- Improved stability when price or news data is missing

### Technical
- Centralized configuration handling to reduce repeated computation and improve consistency
- Internal optimizations to support better scalability during peak usage


## [0.1.1] — 2026-04-03

### Added
- Minimal `pytest` test suite (`tests/test_core.py`, `tests/test_pipeline.py`) — 14 tests covering core function invariants and pipeline smoke tests
- `requirements-dev.txt` for test dependencies (`pytest`, `pytest-mock`)
- `tests/MAINTENANCE.md` — guide for when and how to update the test suite

### Changed
- `tests/conftest.py` rewritten — removed import facade and future-proofing logic; now contains only fixtures and shared setup
- `pytest.ini` simplified — removed stale `hyper` marker and filter
- `CONTRIBUTING.md` — Testing section updated to reflect the live pytest suite; dev setup now includes `requirements-dev.txt` install step; "Automated tests" removed from open contribution areas and replaced with "Test suite expansion"
- `README.md` — Project Structure updated to include `tests/` directory and `requirements-dev.txt`

### Removed
- 9 over-engineered placeholder test files (`test_backtest.py`, `test_dedup_and_clustering.py`, `test_hyper.py`, `test_integration.py`, `test_momentum.py`, `test_price_metrics.py`, `test_sentiment.py`, `test_signal_score.py`, `test_storage.py`)
- Unused dependencies from `requirements.txt`: `beautifulsoup4`, `soupsieve`, `GitPython`, `gitdb`, `smmap`, `peewee`
- Dev dependencies duplicated at the bottom of `requirements.txt` (`freezegun`, `pytest`, `pytest-mock`)
- `freezegun` from `requirements-dev.txt` — no tests use time-freezing

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


## [0.1.1] — 2026-04-03

### Added
- Minimal `pytest` test suite (`tests/test_core.py`, `tests/test_pipeline.py`) — 14 tests covering core function invariants and pipeline smoke tests
- `requirements-dev.txt` for test dependencies (`pytest`, `pytest-mock`)
- `tests/MAINTENANCE.md` — guide for when and how to update the test suite

### Changed
- `tests/conftest.py` rewritten — removed import facade and future-proofing logic; now contains only fixtures and shared setup
- `pytest.ini` simplified — removed stale `hyper` marker and filter
- `CONTRIBUTING.md` — Testing section updated to reflect the live pytest suite; dev setup now includes `requirements-dev.txt` install step; "Automated tests" removed from open contribution areas and replaced with "Test suite expansion"
- `README.md` — Project Structure updated to include `tests/` directory and `requirements-dev.txt`

### Removed
- 9 over-engineered placeholder test files (`test_backtest.py`, `test_dedup_and_clustering.py`, `test_hyper.py`, `test_integration.py`, `test_momentum.py`, `test_price_metrics.py`, `test_sentiment.py`, `test_signal_score.py`, `test_storage.py`)
- Unused dependencies from `requirements.txt`: `beautifulsoup4`, `soupsieve`, `GitPython`, `gitdb`, `smmap`, `peewee`
- Dev dependencies duplicated at the bottom of `requirements.txt` (`freezegun`, `pytest`, `pytest-mock`)
- `freezegun` from `requirements-dev.txt` — no tests use time-freezing

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
