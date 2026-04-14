# Changelog

All notable changes to this project will be documented in this file.

---

## [Unreleased] — v0.3 development

- No entries yet.

---

## [0.2.3] - 2026-04-14
### "Ticker Keyword Intelligence + Correlation Reliability"

### Added
- `generate_keywords(ticker)` in `src/news.py` — auto-builds a keyword list for any ticker from Yahoo Finance metadata (company name tokens, executive surnames). Uses a daemon thread bounded by `REQUEST_TIMEOUT` so a hung network call never blocks the pipeline. Falls back to `[ticker]` on timeout, network failure, or unknown ticker. Part of #35 (v0.3 arbitrary ticker support).
- `Docs/CONTRIBUTORS.md` — acknowledgement list for all project contributors.
- 5 new unit tests in `tests/test_core.py`: `generate_keywords` known ticker, unknown ticker, network failure, timeout, and `correlate_news` false-positive regression. Total test count: 42.

### Fixed
- `correlate_news` in `src/signals.py` now uses word-boundary regex matching (`\b{kw}\b` via `_kw_re`) instead of plain Python substring containment (`kw in blob`). Previously, short keywords such as `"gold"` matched unrelated articles where the word appeared as a substring (e.g. *Goldman Sachs* articles appearing in the Gold section, *S&P 500* articles matching via broad terms).

### Technical
- `_KW_PATTERN_CACHE` added to `src/signals.py` — module-level dict caching compiled `re.Pattern` objects so keyword patterns are compiled once per process rather than on every article scored.
- Industry and sector fields intentionally excluded from `generate_keywords` output — terms like `"Technology"` are too broad to use as correlation keywords without causing noise across unrelated assets.

---

## [0.2.2] - 2026-04-12
### "Dashboard Stability + Security + Test Expansion"

### Added
- `tests/test_logic_coverage.py` — edge case coverage for signal scoring, sentiment, deduplication, and contradiction detection
- `tests/test_storage_and_scan.py` — storage round-trip, retention policy, dry-run scan, and synthetic backtest tests
- Signal score legend added to the sidebar for quick reference
- Loading spinner shown in the dashboard while live analysis is running

### Changed
- Pinned runtime dependencies tightened after `pip audit` security review; no vulnerable packages remain in `requirements.txt`
- Dashboard cache invalidation logic reduced to avoid unnecessary reruns on stale data
- Dashboard stale-refresh handling tightened — refresh now triggers only when data is genuinely outdated
- Signal legend copy in sidebar clarified for readability
- Changelog housekeeping updated on `main` after sync

### Technical
- Total test count increased from 14 to 37
- All test files use package-based imports consistent with the v0.2.1 modular restructure

---

## [0.2.1] - 2026-04-07
### "Modular Package Restructure + Asset Organisation"
> Partial progress toward v0.3. Arbitrary ticker support, local installer, and open issue backlog (#10, #11, #12) remain outstanding before v0.3.0 is reached.

### Changed
- Reorganized all top-level Python files into proper packages with `__init__.py` files:
  - `app.py` → `app/analysis.py`
  - `scan.py` → `app/scan.py`
  - `backtest.py` → `app/backtest.py`
  - `dashboard.py` → `dashboard/main.py`
  - `ui_components.py` → `dashboard/components.py`
  - `styles.py` → `dashboard/styles.py`
  - `dashboard_data.py` → `dashboard/data.py`
  - `storage.py` → `storage/storage.py`
  - `config.py` → `config/settings.py`
- All import statements updated to use absolute package-based imports (e.g. `from config.settings import X`, `from storage.storage import X`)
- `config/settings.py` `BASE_DIR` updated to use `.parent.parent` to correctly resolve the project root from the new subdirectory location
- Moved image assets out of the project root into dedicated subdirectories:
  - `favicon.ico` → `assets/icons/favicon.ico`
  - `pulseengine_logo.png` → `assets/logo/pulseengine_logo.png`
- Dashboard entry point changed from `streamlit run dashboard.py` to `streamlit run dashboard/main.py`
- Scan CLI entry point changed from `python scan.py` to `python -m app.scan`

### Fixed
- Added `sys.path.insert(0, ...)` at the top of `dashboard/main.py` to ensure the project root is on `sys.path` when Streamlit is launched, resolving `ModuleNotFoundError: No module named 'config'` that occurred because Streamlit adds the script directory (`dashboard/`) to `sys.path` rather than the project root

### Technical
- No logic, function names, arguments, or behaviour changed — pure structural reorganization
- `src/` package (engine, price, news, signals, context, explanation, sentiment) remains unchanged in location; only its `from config import` statements updated to `from config.settings import`

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
