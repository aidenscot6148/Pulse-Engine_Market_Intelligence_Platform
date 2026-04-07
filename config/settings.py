"""
config.py — Central configuration for PulseEngine.

Every tunable value lives here. app.py and dashboard.py import from this
file only — no magic numbers or hardcoded strings elsewhere.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DASHBOARD_ICON = str(BASE_DIR / "assets" / "icons" / "favicon.ico")

#  1. TRACKED ASSETS  (Yahoo Finance tickers)

# 24 assets walk into a bar. the bartender says "what's your signal score?"
TRACKED_ASSETS = {
    "Commodities": {
        "Gold":          "GC=F",
        "Silver":        "SI=F",
        "Crude Oil":     "CL=F",
        "Natural Gas":   "NG=F",
        "Copper":        "HG=F",
        "Platinum":      "PL=F",
        "Wheat":         "ZW=F",
        "Corn":          "ZC=F",
    },
    "Cryptocurrency": {
        "Bitcoin":   "BTC-USD",
        "Ethereum":  "ETH-USD",
        "Monero":    "XMR-USD",   # for when you REALLY don't want anyone to know
        "Solana":    "SOL-USD",
        "Litecoin":  "LTC-USD",
    },
    "Tech Stocks": {
        "Apple":     "AAPL",
        "Microsoft": "MSFT",
        "NVIDIA":    "NVDA",
        "Google":    "GOOGL",
        "Amazon":    "AMZN",
        "Meta":      "META",
        "Tesla":     "TSLA",
    },
    "Market Indices": {
        "S&P 500":          "^GSPC",
        "NASDAQ":           "^IXIC",
        "Dow Jones":        "^DJI",
        "VIX (Fear Index)": "^VIX",  # the market's anxiety score. I genuinely did not know it existed
    },
}

#  2. SECTOR GROUPINGS  (cross-correlation analysis)

SECTOR_PEERS = {
    "Gold":        ["Silver", "Platinum"],
    "Silver":      ["Gold", "Platinum"],
    "Platinum":    ["Gold", "Silver"],
    "Crude Oil":   ["Natural Gas"],
    "Natural Gas": ["Crude Oil"],
    "Copper":      ["Gold", "Silver"],
    "Wheat":       ["Corn"],
    "Corn":        ["Wheat"],
    "Bitcoin":     ["Ethereum", "Monero", "Solana", "Litecoin"],
    "Ethereum":    ["Bitcoin", "Solana", "Litecoin"],
    "Monero":      ["Bitcoin", "Ethereum", "Litecoin"],
    "Solana":      ["Bitcoin", "Ethereum"],
    "Litecoin":    ["Bitcoin", "Ethereum"],
    "Apple":       ["Microsoft", "Google", "Amazon", "Meta", "Tesla"],
    "Microsoft":   ["Apple", "Google", "Amazon", "Meta"],
    "NVIDIA":      ["Apple", "Microsoft", "Google"],
    "Google":      ["Apple", "Microsoft", "Amazon", "Meta"],
    "Amazon":      ["Apple", "Microsoft", "Google", "Meta"],
    "Meta":        ["Apple", "Google", "Amazon", "Microsoft"],
    "Tesla":       ["Apple", "NVIDIA"],
}

MARKET_BENCHMARK = {
    "Commodities":     "^GSPC",
    "Cryptocurrency":  "BTC-USD",
    "Tech Stocks":     "^IXIC",
    "Market Indices":  "^GSPC",
}

#  3. NEWS RSS FEEDS  (all public, legal, free)

# 12 people shouting about money simultaneously. we listen to all of them. this is fine
NEWS_FEEDS = [
    ("Reuters Business",     "https://feeds.reuters.com/reuters/businessNews"),
    ("Reuters Tech",         "https://feeds.reuters.com/reuters/technologyNews"),
    ("CNBC Top News",        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
    ("BBC Business",         "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("MarketWatch",          "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ("CoinDesk",             "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Yahoo Finance",        "https://finance.yahoo.com/news/rssindex"),
    ("Al Jazeera",           "https://www.aljazeera.com/xml/rss/all.xml"),
    ("Google News Business", "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB"),
    ("Google News Tech",     "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRE41YXpBU0FtVnVHZ0pWVXlnQVAB"),
    ("NPR Business",         "https://feeds.npr.org/1006/rss.xml"),
    ("Economist Finance",    "https://www.economist.com/finance-and-economics/rss.xml"),
    # no r/wallstreetbets because it's just memes and pump talk, not actual news. also reddit has no rss feed, so there's that
]

#  4. KEYWORD MAP  — weighted terms linking assets to news
#     Format: "Asset": [(keyword, weight), ...]

ASSET_KEYWORDS = {
    "Gold": [
        ("gold", 3), ("bullion", 3), ("precious metal", 2),
        ("safe haven", 2), ("gold price", 3), ("xau", 2),
        ("central bank gold", 2), ("gold etf", 2),
    ],
    "Silver": [
        ("silver", 3), ("precious metal", 1), ("silver price", 3),
        ("industrial metal", 1),
    ],
    "Crude Oil": [
        ("oil", 2), ("crude", 3), ("opec", 3), ("brent", 3),
        ("wti", 3), ("petroleum", 2), ("energy price", 2),
        ("oil supply", 2), ("oil demand", 2), ("barrel", 2),
        ("opec+", 3), ("oil production", 2), ("refinery", 1),
    ],
    "Natural Gas": [
        ("natural gas", 3), ("lng", 3), ("gas price", 2),
        ("energy", 1), ("pipeline", 1), ("gas storage", 2),
    ],
    "Copper": [
        ("copper", 3), ("industrial metal", 1), ("mining", 1),
        ("copper demand", 2),
    ],
    "Platinum": [
        ("platinum", 3), ("precious metal", 1), ("catalytic", 1),
    ],
    "Wheat": [
        ("wheat", 3), ("grain", 2), ("agriculture", 1), ("crop", 1),
        ("food price", 2), ("drought", 2), ("harvest", 1),
    ],
    "Corn": [
        ("corn", 3), ("grain", 2), ("agriculture", 1), ("ethanol", 2),
        ("crop", 1), ("drought", 2),
    ],
    "Bitcoin": [
        ("bitcoin", 3), ("btc", 3), ("crypto", 2),
        ("cryptocurrency", 2), ("halving", 3), ("bitcoin etf", 3),
        ("digital currency", 2), ("crypto regulation", 2),
    ],
    "Ethereum": [
        ("ethereum", 3), ("eth", 2), ("crypto", 1), ("defi", 2),
        ("smart contract", 2), ("ethereum etf", 3), ("staking", 2),
    ],
    "Monero": [
        ("monero", 3), ("xmr", 3), ("privacy coin", 3), ("crypto", 1),
    ],
    "Solana": [
        ("solana", 3), ("sol", 2), ("crypto", 1),
    ],
    "Litecoin": [
        ("litecoin", 3), ("ltc", 2), ("crypto", 1),
    ],
    "Apple": [
        ("apple", 3), ("iphone", 3), ("aapl", 3), ("tim cook", 3),
        ("app store", 2), ("apple earnings", 3), ("cupertino", 1),
    ],
    "Microsoft": [
        ("microsoft", 3), ("msft", 3), ("azure", 3), ("windows", 2),
        ("satya nadella", 3), ("copilot", 2), ("microsoft earnings", 3),
    ],
    "NVIDIA": [
        ("nvidia", 3), ("nvda", 3), ("gpu", 3), ("ai chip", 3),
        ("jensen huang", 3), ("data center", 2), ("nvidia earnings", 3),
        ("h100", 3), ("blackwell", 3),
    ],
    "Google": [
        ("google", 3), ("alphabet", 3), ("googl", 3), ("youtube", 2),
        ("gemini", 2), ("google cloud", 2), ("alphabet earnings", 3),
    ],
    "Amazon": [
        ("amazon", 3), ("amzn", 3), ("aws", 3), ("bezos", 2),
        ("amazon earnings", 3), ("jassy", 2),
    ],
    "Meta": [
        ("meta", 3), ("facebook", 3), ("instagram", 2),
        ("zuckerberg", 3), ("meta earnings", 3), ("llama", 2),
    ],
    "Tesla": [
        ("tesla", 3), ("tsla", 3), ("elon musk", 3), ("ev", 2),
        ("electric vehicle", 2), ("tesla earnings", 3), ("cybertruck", 2),
    ],
    "S&P 500": [
        ("s&p", 3), ("s&p 500", 3), ("stock market", 2),
        ("wall street", 2), ("market rally", 2), ("market selloff", 2),
    ],
    "NASDAQ": [
        ("nasdaq", 3), ("tech stocks", 2), ("technology sector", 2),
    ],
    "Dow Jones": [
        ("dow", 3), ("dow jones", 3), ("djia", 3), ("blue chip", 2),
    ],
    "VIX (Fear Index)": [
        ("vix", 3), ("volatility", 2), ("fear index", 3),
        ("market fear", 2), ("uncertainty", 1),
    ],
}

#  5. EVENT TRIGGERS  — pattern-match root causes

EVENT_TRIGGERS = {
    "central_bank": {
        "keywords": [
            "fed", "federal reserve", "interest rate", "rate hike",
            "rate cut", "fomc", "monetary policy", "powell",
            "ecb", "bank of england", "bank of japan",
            "tightening", "easing", "quantitative",
        ],
        "label": "Central Bank Policy",
        "icon": "🏦",
    },
    "geopolitical": {
        "keywords": [
            "war", "conflict", "sanctions", "tariff", "trade war",
            "embargo", "tension", "military", "invasion",
            "escalation", "ceasefire", "diplomatic",
        ],
        "label": "Geopolitical Event",
        "icon": "🌍",
    },
    "earnings": {
        "keywords": [
            "earnings", "revenue", "profit", "quarterly results",
            "guidance", "beat estimates", "missed estimates",
            "earnings call", "fiscal quarter",
        ],
        "label": "Corporate Earnings",
        "icon": "💰",
    },
    "regulation": {
        "keywords": [
            "regulation", "sec", "lawsuit", "ban", "compliance",
            "legislation", "antitrust", "ruling", "court",
            "executive order", "crackdown",
        ],
        "label": "Regulatory Action",
        "icon": "⚖️",
    },
    "supply_shock": {
        "keywords": [
            "supply", "shortage", "surplus", "production cut",
            "output", "inventory", "disruption", "supply chain",
            "bottleneck", "opec cut",
        ],
        "label": "Supply / Demand Shock",
        "icon": "📦",
    },
    "macro_data": {
        "keywords": [
            "inflation", "cpi", "gdp", "unemployment", "jobs report",
            "nonfarm", "pmi", "consumer confidence", "retail sales",
            "recession", "economic data",
        ],
        "label": "Macro-Economic Data",
        "icon": "📊",
    },
    "weather": {
        "keywords": [
            "drought", "flood", "hurricane", "frost", "el nino",
            "la nina", "crop damage", "wildfire", "climate",
        ],
        "label": "Weather / Agriculture",
        "icon": "🌦️",
    },
    "crypto_event": {
        "keywords": [
            "halving", "fork", "defi", "hack", "exchange collapse",
            "stablecoin", "whale", "etf approval", "sec crypto",
            "mining difficulty", "hash rate",
        ],
        "label": "Crypto-Specific Event",
        "icon": "🔗",
    },
}

#  6. DATA SETTINGS

LOOKBACK_DAYS = 30  # 30 days. the attention span of a goldfish with a Bloomberg terminal
PRICE_CHANGE_THRESHOLD = 2.0
NEWS_MAX_AGE_HOURS = 96
NEWS_MAX_ARTICLES = 300

RELEVANCE_HIGH = 6
RELEVANCE_MEDIUM = 3

#  7. DASHBOARD SETTINGS

DASHBOARD_TITLE = "PulseEngine"

DASHBOARD_LAYOUT = "wide"
AUTO_REFRESH_SECONDS = 90   # refreshes every 90 seconds. like anxiety but automated and on a schedule
CHART_HEIGHT = 420
DEFAULT_CATEGORY = "Commodities"


#  8. CACHE / PERFORMANCE

CACHE_TTL_SECONDS = 300        # legacy fallback (unused directly)
PRICE_CACHE_TTL   = 90         # prices / metrics  → refresh ~every 1–2 min
NEWS_CACHE_TTL    = 300        # news articles      → refresh ~every 5 min
REQUEST_TIMEOUT = 20
MAX_RETRIES = 3                  # three strikes before we give up. very democratic
MAX_WORKERS = 4                  # news feed threads — reduced from 8, turns out being antisocial gets you banned
PRICE_FETCH_WORKERS = 3          # yfinance parallel workers — Yahoo has feelings too, apparently
YFINANCE_REQUEST_DELAY = 0.75    # seconds to sleep after each yfinance call. be polite. be very polite
YFINANCE_BACKOFF_BASE  = 1.0     # base seconds for exponential backoff. 1s → 2s → 4s. regret compounds

#  9. SOURCE CREDIBILITY WEIGHTS
#     Applied as a multiplier to relevance scores.

SOURCE_WEIGHTS: dict[str, float] = {
    "Reuters Business":     1.35,
    "Reuters Tech":         1.35,
    "CNBC Top News":        1.20,
    "BBC Business":         1.20,
    "MarketWatch":          1.20,
    "Economist Finance":    1.25,
    "CoinDesk":             1.10,
    "Yahoo Finance":        1.00,
    "NPR Business":         1.00,
    "Al Jazeera":           0.90,
    "Google News Business": 0.90,
    "Google News Tech":     0.90,
}

#  10. MOMENTUM SETTINGS

MOMENTUM_PERIOD = 10     # days for rate-of-change calculation
RSI_PERIOD = 14          # standard RSI window


#  11. SIGNAL SCORING THRESHOLDS  (score range: -10 to +10)

SIGNAL_THRESHOLDS: dict[str, float] = {
    "strong_bullish":   6.0,
    "bullish":          3.0,
    "slightly_bullish": 1.0,
    "neutral":         -1.0,
    "slightly_bearish":-3.0,
    "bearish":         -6.0,
    # below -6: strong_bearish
}

#  12. NEWS DEDUPLICATION

DEDUP_SIMILARITY_THRESHOLD = 0.65   # Jaccard similarity cutoff


#  13. STORAGE

STORAGE_DIR = "market_data"         # relative path for snapshot files


#  14. BACKTESTING

BACKTEST_WINDOW = 20                # max signals to evaluate


#  15. PER-ASSET-CLASS SIGNAL WEIGHTS
#      Multipliers applied to each raw component contribution.
#      1.0 = default weight.  Adjust to emphasise components
#      relevant to each asset class (e.g. momentum heavier for
#      crypto, sentiment/news heavier for equities).

ASSET_CLASS_WEIGHTS: dict[str, dict[str, float]] = {
    "Cryptocurrency": {
        "trend":          1.2,
        "momentum":       1.8,   # crypto momentum: 1.8x because crypto doesn't walk, it sprints off a cliff, some shmuck does a liquidity test every friday
        "rsi":            0.8,
        "sentiment":      1.2,
        "trend_strength": 1.2,
        "context":        0.5,   # crypto less correlated with broad market
    },
    "Tech Stocks": {
        "trend":          1.2,
        "momentum":       1.0,
        "rsi":            1.0,
        "sentiment":      1.6,   # earnings/news drives tech equities
        "trend_strength": 1.0,
        "context":        1.2,
    },
    "Commodities": {
        "trend":          1.3,
        "momentum":       1.0,
        "rsi":            0.8,
        "sentiment":      1.2,
        "trend_strength": 1.0,
        "context":        1.2,   # macro context matters for commodities
    },
    "Market Indices": {
        "trend":          1.5,
        "momentum":       1.2,
        "rsi":            0.5,   # indices rarely give clean RSI signals
        "sentiment":      1.0,
        "trend_strength": 1.2,
        "context":        1.5,   # indices ARE the broad context
    },
}

#  16. STORAGE RETENTION RULES

STORAGE_FULL_DETAIL_DAYS    = 7    # keep full snapshot for last N days
STORAGE_REDUCED_DETAIL_DAYS = 30   # keep reduced snapshot for up to N days
STORAGE_MAX_DAYS            = 60   # delete snapshots older than this
SNAPSHOT_LOAD_LIMIT         = 20   # max snapshots loaded by default


#  17. BACKGROUND SCAN SCHEDULE

SCAN_INTERVAL_MINUTES = 30   # stock up on data every 30 minutes... pun intended
