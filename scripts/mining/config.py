"""Mining configuration, archetypes, and query taxonomy."""
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data" / "strategies" / "raw_mined"

# Curated queries per strategy archetype
ARCHETYPE_QUERIES: Dict[str, Dict[str, List[str]]] = {
    "mean_reversion": {
        "youtube": [
            "VWAP mean reversion trading strategy rules",
            "Bollinger Bands RSI strategy backtest",
            "Keltner Channel mean reversion futures",
        ],
        "tradingview": [
            "mean reversion",
            "vwap bands reversion",
            "bollinger rsi strategy",
        ],
        "quantpedia": [
            "mean-reversion",
            "reversal",
            "volatility",
        ],
        "github": [
            "mean reversion strategy pine script",
            "vwap mean reversion python",
        ],
    },
    "opening_range": {
        "youtube": [
            "opening range breakout rule based strategy",
            "initial balance breakout trading strategy",
            "09:30 ORB futures backtest",
        ],
        "tradingview": [
            "opening range breakout",
            "initial balance strategy",
            "orb strategy",
        ],
        "quantpedia": [
            "intraday",
            "opening-range",
            "momentum",
        ],
        "github": [
            "opening range breakout strategy",
            "orb futures strategy python",
        ],
    },
    "ema_pullback": {
        "youtube": [
            "mechanical EMA pullback strategy rules",
            "EMA 20 50 trend pullback backtest",
            "moving average pullback strategy",
        ],
        "tradingview": [
            "ema pullback strategy",
            "moving average trend pullback",
            "ema ribbon strategy",
        ],
        "quantpedia": [
            "trend-following",
            "momentum",
        ],
        "github": [
            "ema pullback strategy pine",
            "trend pullback trading strategy",
        ],
    },
    "squeeze_breakout": {
        "youtube": [
            "TTM Squeeze trading strategy backtest",
            "bollinger band squeeze breakout rules",
            "ATR expansion breakout strategy",
        ],
        "tradingview": [
            "ttm squeeze strategy",
            "bollinger squeeze breakout",
            "keltner squeeze",
        ],
        "quantpedia": [
            "volatility-breakout",
            "volatility",
        ],
        "github": [
            "ttm squeeze python strategy",
            "volatility breakout strategy",
        ],
    },
    "ict_smc": {
        "youtube": [
            "FVG CISD strategy mechanical rules",
            "liquidity sweep market structure shift backtest",
            "silver bullet mechanical trading strategy",
        ],
        "tradingview": [
            "fvg strategy",
            "liquidity sweep strategy",
            "market structure shift strategy",
        ],
        "quantpedia": [
            "order-flow",
            "microstructure",
        ],
        "github": [
            "ict smc strategy pine",
            "fair value gap strategy python",
        ],
    },
    "the_strat": {
        "youtube": [
            "TheStrat trading strategy backtest rules",
            "The Strat 2-1-2 strategy backtest",
            "TheStrat 3-1-2 reversal strategy rules",
            "Rob Smith The Strat mechanical rules",
        ],
        "tradingview": [
            "the strat",
            "thestrat strategy",
            "2-1-2 continuation",
            "strat reversal",
        ],
        "quantpedia": [
            "candlestick",
            "inside-bar",
            "reversal",
        ],
        "github": [
            "the strat pine script",
            "thestrat trading strategy",
            "the strat python",
        ],
        "reddit": [
            "thestrat",
            "the strat 2-1-2",
        ],
        "futures_io": [
            "the strat",
            "rob smith",
            "inside bar outside bar",
        ],
    },
    "gamma_exposure_gex": {
        "youtube": [
            "gamma exposure GEX trading strategy rules",
            "zero gamma flip volatility trigger strategy",
            "call wall put wall market maker hedging backtest",
            "dealer gamma positioning spotgamma menthorq",
        ],
        "tradingview": [
            "gamma exposure",
            "net gex",
            "zero gamma flip",
            "call wall put wall",
            "dealer gamma",
        ],
        "quantpedia": [
            "options-gamma",
            "market-maker",
            "volatility-risk-premium",
            "dealer-inventory",
        ],
        "github": [
            "gamma exposure python",
            "gex trading strategy",
            "dealer gamma positioning",
        ],
        "reddit": [
            "gamma exposure GEX",
            "zero gamma level SPX",
            "dealer positioning options",
        ],
        "futures_io": [
            "gamma exposure",
            "gex levels",
            "market maker hedging",
        ],
    },
    "options_0dte_intraday": {
        "youtube": [
            "0DTE SPX iron condor mechanical rules backtest",
            "0DTE credit spread risk management strategy",
            "0DTE gamma scalping intraday options strategy",
            "expected move 0DTE trading rules",
        ],
        "tradingview": [
            "0dte strategy",
            "expected move iron condor",
            "intraday options credit",
        ],
        "quantpedia": [
            "short-volatility",
            "options-intraday",
            "delta-neutral",
        ],
        "github": [
            "0dte spx strategy python",
            "0dte iron condor backtest",
            "intraday options trading",
        ],
        "reddit": [
            "0DTE SPX strategy",
            "0DTE iron condor rules",
            "0DTE stop loss multiple",
        ],
        "futures_io": [
            "0dte options",
            "intraday spx options",
        ],
    },
    "options_orderflow_sweeps": {
        "youtube": [
            "unusual options activity strategy rules",
            "options flow sweeps institutional dark pool strategy",
            "golden sweep options trading system backtest",
            "unusual whales options flow strategy",
        ],
        "tradingview": [
            "unusual options activity",
            "options flow scanner",
            "institutional sweeps",
        ],
        "quantpedia": [
            "informed-trading",
            "options-flow",
            "order-flow",
        ],
        "github": [
            "unusual options activity scanner",
            "options flow tracker python",
            "cboe sweep detector",
        ],
        "reddit": [
            "unusual options activity",
            "options sweeps golden sweep",
            "unusual whales flow",
        ],
        "futures_io": [
            "options order flow",
            "institutional option block prints",
        ],
    },
    "options_volatility_events": {
        "youtube": [
            "earnings IV crush options trading strategy rules",
            "post earnings announcement drift PEAD options strategy",
            "VIX contango backwardation roll yield trading backtest",
            "pre earnings implied volatility run up strategy",
        ],
        "tradingview": [
            "iv crush strategy",
            "earnings straddle",
            "pead options",
            "vix term structure",
        ],
        "quantpedia": [
            "earnings-announcement",
            "volatility-arbitrage",
            "vix-roll-yield",
            "skew-arbitrage",
        ],
        "github": [
            "earnings iv crush python",
            "options volatility arbitrage",
            "vix term structure trading",
        ],
        "reddit": [
            "earnings IV crush strategy",
            "trading PEAD options",
            "VIX contango options",
        ],
        "futures_io": [
            "earnings options volatility",
            "vix backwardation trading",
        ],
    },
    "options_spreads_income": {
        "youtube": [
            "the wheel strategy mechanical rules options backtest",
            "broken wing butterfly options strategy rules",
            "tastytrade 45 DTE mechanical options selling backtest",
            "calendar diagonal spread trading strategy rules",
            "poor mans covered call PMCC strategy",
        ],
        "tradingview": [
            "wheel strategy",
            "broken wing butterfly",
            "poor mans covered call",
            "credit spread",
        ],
        "quantpedia": [
            "covered-call",
            "options-spread",
            "equity-premium-harvesting",
        ],
        "github": [
            "wheel strategy python backtest",
            "broken wing butterfly options",
            "options income strategy",
        ],
        "reddit": [
            "the wheel strategy results",
            "broken wing butterfly setup",
            "tastytrade 45 DTE 21 DTE",
        ],
        "futures_io": [
            "credit spreads income",
            "butterfly options strategy",
        ],
    },
    "range_chop_congestion": {
        "youtube": [
            "mechanical range bound trading strategy rules",
            "how to identify chop zones and congestion boxes",
            "donchian channel range trading strategy backtest",
            "support resistance boundary bounce trading system",
        ],
        "tradingview": [
            "range breakout strategy",
            "consolidation box strategy",
            "darvas box",
            "chop filter",
        ],
        "quantpedia": [
            "support-resistance",
            "range-bound",
            "consolidation",
        ],
        "github": [
            "range trading strategy pine",
            "consolidation detector python",
            "darvas box strategy",
        ],
        "reddit": [
            "trading chop zones",
            "range bound trading strategy futures",
        ],
        "futures_io": [
            "range trading",
            "congestion box breakout",
            "chop indicator",
        ],
    },
    "indicator_oscillators": {
        "youtube": [
            "mechanical RSI divergence trading strategy backtest",
            "MACD histogram momentum pullback rules",
            "Supertrend ATR trailing stop mechanical strategy",
            "stochastic oscillator overbought oversold backtest",
        ],
        "tradingview": [
            "rsi divergence strategy",
            "macd momentum strategy",
            "supertrend strategy",
        ],
        "quantpedia": [
            "oscillator",
            "rsi",
            "momentum",
            "trend-following",
        ],
        "github": [
            "rsi divergence pine script",
            "supertrend trading strategy python",
            "macd strategy",
        ],
        "reddit": [
            "RSI divergence backtest results",
            "supertrend indicator strategy",
        ],
        "futures_io": [
            "rsi divergence",
            "supertrend ninja",
            "oscillator strategy",
        ],
    },
    "stock_scanners_screeners": {
        "youtube": [
            "Trade Ideas stock scanner settings mechanical rules",
            "relative volume RVOL stock scanner strategy",
            "pre market gap and go scanner strategy backtest",
            "episodic pivot stock screener mechanical rules",
            "high tight flag stock scanner rules",
        ],
        "tradingview": [
            "stock scanner",
            "rvol scanner",
            "gap and go",
            "episodic pivot",
            "high tight flag",
        ],
        "quantpedia": [
            "momentum",
            "earnings-announcement",
            "size-factor",
            "turnover",
        ],
        "github": [
            "stock screener python",
            "finviz screener python",
            "rvol scanner python",
            "trade ideas scanner",
        ],
        "reddit": [
            "stock scanner settings",
            "Trade Ideas scanner",
            "RVOL scanner",
            "gap scanner",
        ],
        "futures_io": [
            "stock scanner",
            "market scanner",
        ],
    },
    "volatility_systems_vcp": {
        "youtube": [
            "volatility contraction pattern VCP Mark Minervini rules",
            "Toby Crabel NR7 narrow range breakout strategy backtest",
            "ATR expansion breakout stock screening rules",
            "volatility squeeze scanner mechanical backtest",
            "historical volatility vs implied volatility scanner",
        ],
        "tradingview": [
            "vcp pattern",
            "volatility contraction",
            "nr7 breakout",
            "atr expansion",
            "volatility breakout",
        ],
        "quantpedia": [
            "volatility",
            "volatility-breakout",
            "implied-volatility",
            "atr",
        ],
        "github": [
            "volatility contraction pattern python",
            "minervini vcp scanner",
            "nr7 breakout python",
            "atr expansion strategy",
        ],
        "reddit": [
            "volatility contraction pattern VCP",
            "Minervini VCP rules",
            "NR7 breakout strategy",
        ],
        "futures_io": [
            "toby crabel",
            "narrow range 7",
            "volatility breakout",
        ],
    },
}

# Dedicated Google NotebookLM Knowledge Base Registries
NOTEBOOK_MAPPINGS: Dict[str, Dict[str, str]] = {
    "stock_scanners_screeners": {
        "id": "80b7afae-c643-4af5-89ce-fdf309ab3034",
        "title": "Stock Scanners & Algorithmic Screener Systems",
        "url": "https://notebooklm.google.com/notebook/80b7afae-c643-4af5-89ce-fdf309ab3034",
    },
    "volatility_systems_vcp": {
        "id": "6c55f605-5ce5-4530-bba4-14c4be9a4cfd",
        "title": "Volatility-Based Strategies & Contraction Patterns (VCP, ATR, NR7)",
        "url": "https://notebooklm.google.com/notebook/6c55f605-5ce5-4530-bba4-14c4be9a4cfd",
    },
    "gamma_exposure_gex": {
        "id": "dbbc0d63-d9df-4378-a958-d8f15ac60f3b",
        "title": "Gamma Exposure (GEX) & Market Maker Hedging Strategies",
        "url": "https://notebooklm.google.com/notebook/dbbc0d63-d9df-4378-a958-d8f15ac60f3b",
    },
    "options_0dte_intraday": {
        "id": "738e4a0a-5bd4-4c30-8f3a-378d33e57c7a",
        "title": "0DTE & Intraday Options Strategies",
        "url": "https://notebooklm.google.com/notebook/738e4a0a-5bd4-4c30-8f3a-378d33e57c7a",
    },
    "options_orderflow_sweeps": {
        "id": "38589732-c5f0-43e5-9c29-b6fd0be0e051",
        "title": "Options Order Flow & Unusual Institutional Activity",
        "url": "https://notebooklm.google.com/notebook/38589732-c5f0-43e5-9c29-b6fd0be0e051",
    },
    "options_volatility_events": {
        "id": "0861f9b9-ce76-4cbb-84a7-532fd157880e",
        "title": "Options Volatility, IV Crush & Event Trading",
        "url": "https://notebooklm.google.com/notebook/0861f9b9-ce76-4cbb-84a7-532fd157880e",
    },
    "options_spreads_income": {
        "id": "ef3a98ae-ac9a-40f6-b423-13b63f6d87a1",
        "title": "Options Multi-Leg Spreads & Systematic Income",
        "url": "https://notebooklm.google.com/notebook/ef3a98ae-ac9a-40f6-b423-13b63f6d87a1",
    },
    "indicator_oscillators": {
        "id": "c9e73ff9-b36b-4d74-af98-7a35c70c3d3d",
        "title": "Indicator & Oscillator Systematic Strategies",
        "url": "https://notebooklm.google.com/notebook/c9e73ff9-b36b-4d74-af98-7a35c70c3d3d",
    },
    "the_strat": {
        "id": "4f569cc3-220e-408d-afaf-47add3fb67f1",
        "title": "The Strat Methodology & Automated Trading Systems",
        "url": "https://notebooklm.google.com/notebook/4f569cc3-220e-408d-afaf-47add3fb67f1",
    },
    "range_chop_congestion": {
        "id": "b52fb636-8a91-40f3-9035-def8b94cb090",
        "title": "Consolidation & Range Day Trading Strategies",
        "url": "https://notebooklm.google.com/notebook/b52fb636-8a91-40f3-9035-def8b94cb090",
    },
    "mean_reversion": {
        "id": "c9856fd5-3394-49db-ac05-9594db94dd00",
        "title": "VWAP Trading Strategies Master Knowledge Base",
        "url": "https://notebooklm.google.com/notebook/c9856fd5-3394-49db-ac05-9594db94dd00",
    },
    "opening_range": {
        "id": "d86e9c4d-5645-47b2-9ccb-29bd58fdfc22",
        "title": "0930 All Day ORB Data Analysis",
        "url": "https://notebooklm.google.com/notebook/d86e9c4d-5645-47b2-9ccb-29bd58fdfc22",
    },
    "squeeze_breakout": {
        "id": "902133c5-3efc-4853-ac18-2631efb61397",
        "title": "Keltner Channel APEX Strategy Architecture & Research",
        "url": "https://notebooklm.google.com/notebook/902133c5-3efc-4853-ac18-2631efb61397",
    },
    "ict_smc": {
        "id": "00068bc6-fb1e-40ce-aa93-d032d6478db5",
        "title": "ICT Orderblock Model & Market Analysis",
        "url": "https://notebooklm.google.com/notebook/00068bc6-fb1e-40ce-aa93-d032d6478db5",
    },
}

# High-signal YouTube channel IDs / handles for direct playlist mining
YOUTUBE_CREATOR_HANDLES = [
    # Quant, Algos & Backtesting
    "TheArtofTrading",
    "TradeZoneOfficial",
    "CriticalTrading",
    "DaveTeaches",
    "QuantNomad",
    "AlgoTradingWithKevinDavey",
    "BetterSystemTraderPodcast",
    "parttimelarry",
    "CodeTradingCafe",
    "imjesstwoone",
    # GEX & Options Microstructure
    "SpotGamma",
    "DocMcGraw",
    "OptionAlpha",
    "tastytrade1",
    "therealshadowtrader",
    "KamikazeCash",
    "MenthorQ",
    # Stock Scanners, VCP & Volatility Systems
    "TheRealMarkMinervini",
    "lindaraschke6565",
    "TraderLion",
    "RichardMoglen",
    "KristjanQullamaggie",
    "StockChartsTV",
    # TheStrat Methodology
    "SaraStratSniper",
    "AlexsOptions",
    # Market Profiling & Price Action
    "ACTrades",
    "thecurrencymerchant",
    "theMMXMtrader",
    "theOTEtrader",
    "ThomasWade",
    "NQStats",
    "edgeful",
    "nexus-fi",
]

# Request headers
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
}

