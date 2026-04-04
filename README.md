# PulseEngine

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![pandas](https://img.shields.io/badge/pandas-2.0%2B-150458?style=flat-square&logo=pandas&logoColor=white)](https://pandas.pydata.org/)
[![Plotly](https://img.shields.io/badge/Plotly-5.18%2B-3F4F75?style=flat-square&logo=plotly&logoColor=white)](https://plotly.com/)
[![Data: Yahoo Finance](https://img.shields.io/badge/Data-Yahoo%20Finance-6001D2?style=flat-square)](https://finance.yahoo.com/)
[![News: RSS Feeds](https://img.shields.io/badge/News-12%20RSS%20Feeds-FFA500?style=flat-square)](https://en.wikipedia.org/wiki/RSS)
[![Assets: 24 Tracked](https://img.shields.io/badge/Assets-24%20Tracked-0ea5e9?style=flat-square)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen?style=flat-square)](CONTRIBUTING.md)
[![Disclaimer](https://img.shields.io/badge/Disclaimer-Not%20Financial%20Advice-red?style=flat-square)](DISCLAIMER.md)

_LINK TO LIVE DEPLOYMENT: [HERE!!!](https://lemarketintelligenceplatform-vsr4ernrtqqduydam2onapp.streamlit.app/)_

![dashboard1](https://github.com/user-attachments/assets/efe48c7c-8acb-40c7-8cea-2ece6d4ab30c)

---

A real-time market analysis dashboard that combines technical price indicators, multi-source news sentiment, and event-driven signal generation into a single composite score for 24 tracked assets across commodities, cryptocurrencies, technology equities, and market indices.

All data is sourced from free, publicly available feeds. No proprietary APIs, no paid data subscriptions, and no trading execution. The platform is an analytical tool only.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Asset Coverage](#asset-coverage)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Running the Dashboard](#running-the-dashboard)
- [Running a Full Scan](#running-a-full-scan)
- [Configuration](#configuration)
- [Data Storage](#data-storage)
- [Backtesting](#backtesting)
- [Project Structure](#project-structure)
- [Documentation](#documentation)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Disclaimer](#disclaimer)
- [License](#license)

---

## Overview

The platform processes data from two independent sources on each analysis cycle:

- **Price data** — 30-day OHLCV history fetched from Yahoo Finance via `yfinance`
- **News data** — up to 300 articles ingested in parallel from 12 curated RSS feeds, deduplicated using Jaccard similarity, and scored using VADER sentiment analysis augmented with a financial lexicon

These two streams are merged into a composite signal score ranging from -10 (Strong Bearish) to +10 (Strong Bullish) using weighted contributions from six sub-components: trend direction, price momentum, RSI oscillator reading, news sentiment, trend strength, and market/sector context. Each asset class applies its own weighting profile to reflect how different market types respond to different signal types.

Historical snapshots are persisted to compressed JSON files on disk. A background scan thread processes all 24 assets every 30 minutes without blocking the dashboard UI.

---

## Features

| Feature | Detail |
|---|---|
| Signal scoring | Composite score -10 to +10 across 6 weighted components |
| Asset classes | Commodities, Cryptocurrency, Tech Stocks, Market Indices |
| News ingestion | 12 public RSS feeds, parallel fetch, Jaccard deduplication |
| Sentiment engine | VADER with injected financial lexicon, keyword fallback |
| Event detection | 8 event categories (central bank, geopolitical, earnings, etc.) |
| Market context | Sector peer comparison and benchmark alignment analysis |
| Background scan | Full 24-asset scan every 30 minutes via daemon thread |
| Historical storage | Compressed per-asset JSON snapshots with tiered retention |
| Backtesting | Hit-rate evaluation by signal strength and label |
| Retention policy | Full detail 7 days, reduced detail 30 days, deleted after 60 days |
| Dashboard | Streamlit wide-layout with auto-refresh every 90 seconds |
| Top movers | Live 24h gainers and losers in sidebar |
| Market heatmap | Category-level 24h change heatmap |
| Category overview | Tabular summary of all assets in selected category |

---

## Architecture

```mermaid
flowchart TD
    A([Dashboard Start]) --> B[_maybe_trigger_scan]
    B --> C{Scan due?}
    C -->|No| D[Serve cached data]
    C -->|Yes| E[Acquire singleton lock]
    E --> F{Lock free?}
    F -->|No| D
    F -->|Yes| G[Spawn daemon thread]
    G --> H[run_scan — all 24 assets]
    D --> I[User selects asset]
    H --> J[fetch_news_articles]
    I --> K[cached_history]
    J --> L[analyse_asset loop]
    K --> M[compute_price_metrics]
    M --> N[compute_momentum_metrics]
    N --> O[correlate_news]
    O --> P[compute_signal_score]
    P --> Q[build_explanation]
    Q --> R[save_snapshot]
    L --> R
    R --> S[Dashboard renders]
    S --> T{Auto-refresh 90s}
    T --> B
```

---

## Asset Coverage

[![Commodities](https://img.shields.io/badge/Commodities-8%20Assets-a16207?style=flat-square)]()
[![Cryptocurrency](https://img.shields.io/badge/Cryptocurrency-5%20Assets-7c3aed?style=flat-square)]()
[![Tech%20Stocks](https://img.shields.io/badge/Tech%20Stocks-7%20Assets-0284c7?style=flat-square)]()
[![Market%20Indices](https://img.shields.io/badge/Market%20Indices-4%20Assets-059669?style=flat-square)]()

| Category | Assets |
|---|---|
| Commodities | Gold, Silver, Crude Oil, Natural Gas, Copper, Platinum, Wheat, Corn |
| Cryptocurrency | Bitcoin, Ethereum, Monero, Solana, Litecoin |
| Tech Stocks | Apple, Microsoft, NVIDIA, Google, Amazon, Meta, Tesla |
| Market Indices | S&P 500, NASDAQ, Dow Jones, VIX (Fear Index) |

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Codex-Crusader/le_Market_Intelligence_Platform.git
cd le_Market_Intelligence_Platform

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the dashboard
streamlit run dashboard.py
```

The dashboard opens at `http://localhost:8501`. A full-market background scan starts automatically on first load and repeats every 30 minutes.

---

## Quick Start (Docker)

```bash
docker build -t market-intel .
docker run -p 8501:8501 market-intel
```

Dashboard available at `http://localhost:8501`.

---

## Installation

### Requirements

- Python 3.9 or later
- Internet connection (Yahoo Finance and RSS feeds)

### Dependencies

| Package | Minimum Version | Purpose |
|---|---|---|
| streamlit | 1.30.0 | Dashboard framework |
| yfinance | 0.2.30 | Price history via Yahoo Finance |
| pandas | 2.0.0 | DataFrame operations |
| plotly | 5.18.0 | Interactive charts and heatmap |
| feedparser | 6.0.0 | RSS feed ingestion |
| vaderSentiment | 3.3.2 | Sentiment analysis |

Install all dependencies in one command:

```bash
pip install -r requirements.txt
```

---

## Running the Dashboard

```bash
streamlit run dashboard.py
```

On startup the dashboard:

1. Renders the sidebar with category and asset selectors
2. Checks whether a full-market scan is due
3. Launches a background daemon thread to scan all 24 assets if the last scan summary is missing or older than 30 minutes
4. Displays `System initializing — full market scan running in background...` while the scan is active
5. Fetches price and news data for the currently selected asset and renders the full analysis panel

The sidebar shows the scan status (running / N minutes ago / pending first run) and a manual `Run full scan now` button.

---

## Running a Full Scan

The scan pipeline can be executed independently of the dashboard:

```bash
# Full verbose scan — saves snapshots and summary
python scan.py

# Suppress per-asset log lines
python scan.py --quiet

# Validate pipeline without writing any files
python scan.py --dry-run
```

Output is written to:
- `market_data/<AssetName>_YYYYMMDD.json.gz` — per-asset daily snapshot
- `market_data/_scan_summary.json.gz` — hierarchical summary of latest scan

---

## Configuration

All tunable values are in `config.py`. No magic numbers exist anywhere else in the codebase.

| Constant | Default | Description |
|---|---|---|
| `LOOKBACK_DAYS` | 30 | Price history window in days |
| `NEWS_MAX_AGE_HOURS` | 96 | Maximum article age accepted |
| `NEWS_MAX_ARTICLES` | 300 | Article pool cap before correlation |
| `PRICE_CACHE_TTL` | 90 s | Dashboard price cache lifetime |
| `NEWS_CACHE_TTL` | 300 s | Dashboard news cache lifetime |
| `SCAN_INTERVAL_MINUTES` | 30 | Background scan frequency |
| `MAX_WORKERS` | 8 | Parallel threads for data fetching |
| `RSI_PERIOD` | 14 | RSI calculation window |
| `MOMENTUM_PERIOD` | 10 | Rate-of-change calculation window |
| `DEDUP_SIMILARITY_THRESHOLD` | 0.65 | Jaccard cutoff for deduplication |
| `PRICE_CHANGE_THRESHOLD` | 2.0 % | Threshold for significant move alert |
| `RELEVANCE_HIGH` | 6 | Score threshold for high-relevance news |
| `RELEVANCE_MEDIUM` | 3 | Score threshold for medium-relevance news |
| `STORAGE_FULL_DETAIL_DAYS` | 7 | Days to retain full snapshots |
| `STORAGE_REDUCED_DETAIL_DAYS` | 30 | Days to retain reduced snapshots |
| `STORAGE_MAX_DAYS` | 60 | Days before snapshot deletion |

### Signal Thresholds

| Label | Score Range |
|---|---|
| Strong Bullish | >= 6.0 |
| Bullish | >= 3.0 |
| Slightly Bullish | >= 1.0 |
| Neutral | -1.0 to 1.0 |
| Slightly Bearish | >= -3.0 |
| Bearish | >= -6.0 |
| Strong Bearish | < -6.0 |

### Per-Asset-Class Signal Weights

| Component | Crypto | Tech Stocks | Commodities | Indices |
|---|---|---|---|---|
| Trend | 1.2x | 1.2x | 1.3x | 1.5x |
| Momentum | 1.8x | 1.0x | 1.0x | 1.2x |
| RSI | 0.8x | 1.0x | 0.8x | 0.5x |
| Sentiment | 1.2x | 1.6x | 1.2x | 1.0x |
| Trend Strength | 1.2x | 1.0x | 1.0x | 1.2x |
| Context | 0.5x | 1.2x | 1.2x | 1.5x |

---

## Data Storage

Snapshots are stored as gzip-compressed JSON files under `market_data/`:

```
market_data/
  Gold_20260401.json.gz
  Bitcoin_20260401.json.gz
  ...
  _scan_summary.json.gz
```

### Retention Tiers

| Age | Fields Retained |
|---|---|
| 0 – 7 days | Full snapshot including top 5 headlines |
| 8 – 30 days | Reduced: price, change_1d, signal_score, signal_label, trend, rsi, roc_10d, trend_strength |
| > 60 days | Deleted automatically after each scan |

---

## Backtesting

The backtesting module evaluates historical signal accuracy by comparing the signal score on day N with the actual price direction from day N to day N+1.

```python
from backtest import evaluate_signal_accuracy
result = evaluate_signal_accuracy("Gold", lookback=20)
print(result["hit_rate"])
```

Results are broken down by:
- Overall hit rate
- Accuracy by signal strength (strong / moderate / weak)
- Accuracy per signal label
- Current win or loss streak

---

## Project Structure

```
market-intelligence-platform/
  app.py              Core analysis engine (price, news, signals, explanation)
  dashboard.py        Streamlit dashboard with background scan management
  config.py           All configuration constants
  scan.py             Full-market batch scan pipeline
  storage.py          Compressed snapshot persistence and retention
  backtest.py         Historical signal accuracy evaluation
  requirements.txt    Python dependencies
  requirements-dev.txt  Test dependencies (pytest, pytest-mock)
  README.md           This file
  CONTRIBUTING.md     Contribution guidelines
  LICENSE             MIT License
  .gitignore          Git ignore rules
  Docs/
    code_flow.md      Detailed execution flow diagrams
    variable_list.md  Complete variable and constant reference
    ROADMAP.md        Project direction, milestones, and contributor lanes
    CHANGELOG.md      All notable changes by version
    DISCLAIMER.md       Legal and financial disclaimer
  tests/
    conftest.py       Import facade and shared fixtures
    test_core.py      Sanity and invariant tests for pure functions
    test_pipeline.py  Smoke tests for end-to-end pipelines
    MAINTENANCE.md    Guide for updating the test suite
  market_data/        Runtime snapshot directory (git-ignored)
  pulseengine_logo.png
  Favicon.ico
```

---

## Documentation

| Document | Description |
|---|---|
| [Docs/code_flow.md](Docs/code_flow.md) | Step-by-step execution flow for every pipeline with Mermaid diagrams |
| [Docs/variable_list.md](Docs/variable_list.md) | Complete reference of all variables, constants, and return structures |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to report issues, propose changes, and submit pull requests |
| [DISCLAIMER.md](Docs/DISCLAIMER.md) | Financial, legal, and data accuracy disclaimers |
| [CHANGELOG.md](Docs/CHANGELOG.md) | Financial, legal, and data accuracy disclaimers |
| [Docs/ROADMAP.md](Docs/ROADMAP.md) | Project direction, milestones, and contributor lanes |

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. All contributors must follow the code style and testing requirements described there.

[![Open Issues](https://img.shields.io/github/issues/Codex-Crusader/le_Market_Intelligence_Platform?style=flat-square)](https://github.com/Codex-Crusader/le_Market_Intelligence_Platform/issues)
[![Pull Requests](https://img.shields.io/github/issues-pr/Codex-Crusader/le_Market_Intelligence_Platform?style=flat-square)](https://github.com/Codex-Crusader/le_Market_Intelligence_Platform/pulls)

---

## Roadmap

PulseEngine is being built toward a local-first desktop application — a full-power EXE that runs entirely on your machine with no cloud dependency, no accounts, and no data leaving your device. The Streamlit deployment is a live demo with restricted features.

Planned milestones:
- **v0.3** — Repo restructure, arbitrary ticker support, local installer
- **v0.4** — Desktop EXE via PyInstaller, GitHub Actions build pipeline
- **v0.5** — FinBERT running locally, offline mode, export features
- **v1.0** — Full market coverage, dynamic asset discovery, all stocks

See [Docs/ROADMAP.md](Docs/ROADMAP.md) for the full breakdown including what's out of scope and how to contribute to specific milestones.

---

## Disclaimer

This software is provided for informational and educational purposes only. It does not constitute financial advice, investment advice, trading advice, or any other form of advice. See [DISCLAIMER.md](Docs/DISCLAIMER.md) for the full disclaimer.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for the full text.

[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)
