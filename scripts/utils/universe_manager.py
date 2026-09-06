"""
Universe Manager — Central Single Source of Truth for Dynamic Hot-Reloadable Tickers
Supports hot-reloading for:
1. Active Options Pipeline (ACTIVE_TICKERS, PRIORITY_TICKERS)
2. Options Strategy Engine (per-strategy tickers: WHEEL, INCOME_CC, BEN_CSP, BEN_SPREAD, etc.)
3. Screener Engines (Qullamaggie, Minervini, Stockbee)
4. CSP & Spread Ranking Scanners

Allows adding, removing, and reading tickers while processes are running 24/7.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Set, Optional, Any

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Fallback root resolution
_current_dir = Path(__file__).resolve().parent
REPO_ROOT = _current_dir.parent.parent if _current_dir.name == "utils" else Path(".")
UNIVERSE_JSON_PATH = REPO_ROOT / "data" / "universe" / "scan_universe.json"
WATCHLIST_TXT_PATH = REPO_ROOT / "data" / "universe" / "watchlist.txt"

_CACHE: Dict[str, Any] = {}
_LAST_MTIME_JSON: float = 0.0
_LAST_MTIME_TXT: float = 0.0


def _load_data_if_modified():
    """Checks file timestamps and reloads memory cache in < 1ms if modified."""
    global _CACHE, _LAST_MTIME_JSON, _LAST_MTIME_TXT

    if UNIVERSE_JSON_PATH.exists():
        try:
            mtime = UNIVERSE_JSON_PATH.stat().st_mtime
            if mtime > _LAST_MTIME_JSON:
                with open(UNIVERSE_JSON_PATH, "r", encoding="utf-8") as f:
                    _CACHE = json.load(f)
                _LAST_MTIME_JSON = mtime
        except Exception as e:
            pass

    if WATCHLIST_TXT_PATH.exists():
        try:
            mtime_txt = WATCHLIST_TXT_PATH.stat().st_mtime
            if mtime_txt > _LAST_MTIME_TXT:
                wl = []
                with open(WATCHLIST_TXT_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        c = line.strip().upper()
                        if c and not c.startswith("#"):
                            wl.append(c)
                _CACHE["watchlist"] = wl
                _LAST_MTIME_TXT = mtime_txt
        except Exception:
            pass


def get_active_options_tickers() -> List[str]:
    """Returns active tickers for GEX / dealer levels options pipeline."""
    _load_data_if_modified()
    return _CACHE.get("active_options_tickers", [
        "SPX", "SPY", "NDX", "QQQ", "NQ", "ES", "IWM", "DIA", 
        "AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL", "AMZN", "AVGO"
    ])


def get_priority_options_tickers() -> List[str]:
    """Returns Tier-1 priority tickers (scanned every 60s)."""
    _load_data_if_modified()
    return _CACHE.get("priority_options_tickers", ["SPX", "SPY", "QQQ", "NQ", "ES"])


def get_strategy_tickers(strategy_name: str, fallback: Optional[List[str]] = None) -> List[str]:
    """Returns tickers configured for a specific Strategy Engine strategy."""
    _load_data_if_modified()
    st_map = _CACHE.get("strategy_engine_tickers", {})
    key = strategy_name.lower().replace("-", "_")
    if key in st_map:
        return st_map[key]
    return fallback or ["NVDA", "TSLA", "AAPL", "GOOGL", "MSFT", "AMZN"]


def get_index_tickers() -> Set[str]:
    """Returns index and ETF tickers."""
    return {"SPY", "SPX", "QQQ", "IWM", "NDX", "DIA", "RUT", "NQ", "ES"}


def get_stock_tickers() -> Set[str]:
    """Returns all equity tickers across options and strategies."""
    active = set(get_active_options_tickers())
    indices = get_index_tickers()
    return active - indices


def get_universe(category: str = "csp", dynamic: bool = False) -> List[str]:
    """General category lookup."""
    _load_data_if_modified()
    cat_key = category.lower()

    if cat_key in ("csp", "csp_universe"):
        if dynamic:
            return get_dynamic_csp_universe()
        res = _CACHE.get("csp_universe", [])
    elif cat_key in ("momentum", "momentum_universe", "screener"):
        res = _CACHE.get("momentum_universe", [])
    elif cat_key in ("active_options", "options"):
        res = _CACHE.get("active_options_tickers", [])
    elif cat_key == "priority":
        res = _CACHE.get("priority_options_tickers", [])
    elif cat_key == "watchlist":
        res = _CACHE.get("watchlist", [])
    elif cat_key == "all":
        combined: Set[str] = set()
        for k, v in _CACHE.items():
            if isinstance(v, list):
                combined.update(v)
            elif isinstance(v, dict):
                for sub_v in v.values():
                    if isinstance(sub_v, list):
                        combined.update(sub_v)
        return sorted(list(combined))
    else:
        res = _CACHE.get(category, [])

    # Merge custom watchlist if exists
    custom_wl = _CACHE.get("watchlist", [])
    if custom_wl and cat_key in ("csp", "momentum"):
        res = list(dict.fromkeys(res + custom_wl))

    return res


DYNAMIC_CSP_CACHE_PATH = REPO_ROOT / "data" / "universe" / "dynamic_csp_universe.json"


def get_dynamic_csp_universe(force_refresh: bool = False, max_candidates: int = 150) -> List[str]:
    """
    Retrieves dynamically screened CSP candidate tickers from Finviz (Optionable, Price > $7,
    > 200 SMA, Profitable, Volatility > 3%, Volume > 500k) and merges them with the base
    curated csp_universe and custom watchlist.
    Uses disk caching to keep performance instant (< 1ms) after initial daily fetch.
    """
    base_tickers = get_universe("csp", dynamic=False)

    # 1. Check local cache freshness (6 hours)
    if not force_refresh and DYNAMIC_CSP_CACHE_PATH.exists():
        try:
            mtime = DYNAMIC_CSP_CACHE_PATH.stat().st_mtime
            if (datetime.now().timestamp() - mtime) < 21600:
                with open(DYNAMIC_CSP_CACHE_PATH, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if isinstance(cached, list) and len(cached) > 0:
                    combined = list(dict.fromkeys(base_tickers + cached))
                    return combined
        except Exception:
            pass

    # 2. Query Finviz Screener
    discovered: List[str] = []
    try:
        from finvizfinance.screener.overview import Overview
        f = Overview()
        filters = {
            'Industry': 'Stocks only (ex-Funds)',
            'Price': 'Over $7',
            '200-Day Simple Moving Average': 'Price above SMA200',
            'Option/Short': 'Optionable',
            'Average Volume': 'Over 500K',
            'P/E': 'Profitable (>0)',
            'Volatility': 'Month - Over 3%',
        }
        f.set_filter(filters_dict=filters)
        df = f.screener_view()
        if df is not None and not df.empty and "Ticker" in df.columns:
            bug_active = False
            doubled_count = sum(1 for t in df["Ticker"].astype(str) if len(t) > 1 and t[0] == t[1])
            if len(df) > 0 and doubled_count / len(df) > 0.5:
                bug_active = True

            for raw_t in df["Ticker"].astype(str):
                sym = raw_t.strip().upper()
                if not sym or "." in sym:
                    continue
                if bug_active and len(sym) > 1:
                    sym = sym[1:]
                discovered.append(sym)
                if len(discovered) >= max_candidates:
                    break

        if discovered:
            DYNAMIC_CSP_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(DYNAMIC_CSP_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(discovered, f, indent=2)
            print(f"📡 Dynamic CSP Universe refreshed: Found {len(discovered)} market-wide candidates.")
    except Exception as e:
        print(f"⚠️ Dynamic Finviz fetch unavailable ({e}). Falling back to static universe.")

    combined = list(dict.fromkeys(base_tickers + discovered))
    return combined


DYNAMIC_VELOCITY_CACHE_PATH = REPO_ROOT / "data" / "universe" / "dynamic_velocity_universe.json"


def get_dynamic_velocity_universe(force_refresh: bool = False, max_candidates: int = 150) -> List[str]:
    """
    Retrieves dynamically screened velocity momentum candidates from Finviz
    (Price >= $10, Change >= +3%, Rel Vol >= 1.0, Avg Vol > 100k, Exclude Biotechnology)
    matching Ben Bennett's ThinkorSwim Velocity Scan, with disk caching.
    """
    base_tickers = get_universe("momentum", dynamic=False)

    if not force_refresh and DYNAMIC_VELOCITY_CACHE_PATH.exists():
        try:
            mtime = DYNAMIC_VELOCITY_CACHE_PATH.stat().st_mtime
            if (datetime.now().timestamp() - mtime) < 21600:
                with open(DYNAMIC_VELOCITY_CACHE_PATH, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if isinstance(cached, list) and len(cached) > 0:
                    return cached
        except Exception:
            pass

    discovered: List[str] = []
    try:
        from finvizfinance.screener.overview import Overview
        f = Overview()
        filters = {
            'Industry': 'Stocks only (ex-Funds)',
            'Price': 'Over $10',
            'Change': 'Up 3%',
            'Average Volume': 'Over 100K',
            'Relative Volume': 'Over 1',
        }
        f.set_filter(filters_dict=filters)
        df = f.screener_view()
        if df is not None and not df.empty and "Ticker" in df.columns:
            # Exclude Biotechnology (ThinkorSwim exact exclusion)
            if "Industry" in df.columns:
                df = df[~df["Industry"].astype(str).str.contains("Biotechnology", case=False, na=False)]

            bug_active = False
            doubled_count = sum(1 for t in df["Ticker"].astype(str) if len(t) > 1 and t[0] == t[1])
            if len(df) > 0 and doubled_count / len(df) > 0.5:
                bug_active = True

            for raw_t in df["Ticker"].astype(str):
                sym = raw_t.strip().upper()
                if not sym or "." in sym:
                    continue
                if bug_active and len(sym) > 1:
                    sym = sym[1:]
                discovered.append(sym)
                if len(discovered) >= max_candidates:
                    break

        if discovered:
            DYNAMIC_VELOCITY_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(DYNAMIC_VELOCITY_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(discovered, f, indent=2)
            print(f"⚡ Dynamic Velocity Universe refreshed: Found {len(discovered)} momentum candidates (Ex-Biotech).")
    except Exception as e:
        print(f"⚠️ Dynamic Velocity fetch unavailable ({e}). Falling back to static universe.")

    return discovered if discovered else base_tickers


DYNAMIC_INSTITUTIONAL_CACHE_PATH = REPO_ROOT / "data" / "universe" / "dynamic_institutional_universe.json"


def get_dynamic_institutional_universe(force_refresh: bool = False, max_candidates: int = 100) -> List[str]:
    """
    Retrieves dynamically screened institutional growth leaders from Finviz
    (EPS YoY/QoQ > 20%, Sales YoY/QoQ > 20%, Price > 200 SMA, Price >= $10, Avg Vol > 300k).
    """
    base_tickers = get_universe("all")

    if not force_refresh and DYNAMIC_INSTITUTIONAL_CACHE_PATH.exists():
        try:
            mtime = DYNAMIC_INSTITUTIONAL_CACHE_PATH.stat().st_mtime
            if (datetime.now().timestamp() - mtime) < 21600:
                with open(DYNAMIC_INSTITUTIONAL_CACHE_PATH, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if isinstance(cached, list) and len(cached) > 0:
                    return list(dict.fromkeys(base_tickers + cached))
        except Exception:
            pass

    discovered: List[str] = []
    try:
        from finvizfinance.screener.overview import Overview
        f = Overview()
        filters = {
            'Industry': 'Stocks only (ex-Funds)',
            'Price': 'Over $10',
            '200-Day Simple Moving Average': 'Price above SMA200',
            'EPS growthqtr over qtr': 'Over 25%',
            'Sales growthqtr over qtr': 'Over 25%',
            'Average Volume': 'Over 300K',
        }
        f.set_filter(filters_dict=filters)
        df = f.screener_view()
        if df is not None and not df.empty and "Ticker" in df.columns:
            bug_active = False
            doubled_count = sum(1 for t in df["Ticker"].astype(str) if len(t) > 1 and t[0] == t[1])
            if len(df) > 0 and doubled_count / len(df) > 0.5:
                bug_active = True

            for raw_t in df["Ticker"].astype(str):
                sym = raw_t.strip().upper()
                if not sym or "." in sym:
                    continue
                if bug_active and len(sym) > 1:
                    sym = sym[1:]
                discovered.append(sym)
                if len(discovered) >= max_candidates:
                    break

        if discovered:
            DYNAMIC_INSTITUTIONAL_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(DYNAMIC_INSTITUTIONAL_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(discovered, f, indent=2)
            print(f"🏛️ Dynamic Institutional Universe refreshed: Found {len(discovered)} fundamental growth leaders.")
    except Exception as e:
        print(f"⚠️ Dynamic Institutional fetch unavailable ({e}). Falling back to static universe.")

    return list(dict.fromkeys(base_tickers + discovered))



def add_ticker(ticker: str, category: str = "csp_universe", strategy: Optional[str] = None) -> bool:
    """Adds a ticker symbol into the central JSON file."""
    _load_data_if_modified()
    ticker = ticker.strip().upper()

    if strategy:
        st_map = _CACHE.setdefault("strategy_engine_tickers", {})
        strat_key = strategy.lower().replace("-", "_")
        s_list = st_map.setdefault(strat_key, [])
        if ticker not in s_list:
            s_list.append(ticker)
            _save_cache()
            print(f"✅ Added '{ticker}' to strategy '{strategy}'.")
            return True
        return False

    cat_key = category if category in _CACHE else f"{category}_universe"
    if cat_key not in _CACHE:
        _CACHE[cat_key] = []

    if ticker not in _CACHE[cat_key]:
        _CACHE[cat_key].append(ticker)
        _save_cache()
        print(f"✅ Added '{ticker}' to '{cat_key}'. Total tickers: {len(_CACHE[cat_key])}")
        return True
    else:
        print(f"ℹ️ '{ticker}' is already present in '{cat_key}'.")
        return False


def remove_ticker(ticker: str, category: str = "csp_universe", strategy: Optional[str] = None) -> bool:
    """Removes a ticker symbol from the central JSON file."""
    _load_data_if_modified()
    ticker = ticker.strip().upper()

    if strategy:
        st_map = _CACHE.get("strategy_engine_tickers", {})
        strat_key = strategy.lower().replace("-", "_")
        if strat_key in st_map and ticker in st_map[strat_key]:
            st_map[strat_key].remove(ticker)
            _save_cache()
            print(f"🗑️ Removed '{ticker}' from strategy '{strategy}'.")
            return True
        return False

    cat_key = category if category in _CACHE else f"{category}_universe"
    if cat_key in _CACHE and ticker in _CACHE[cat_key]:
        _CACHE[cat_key].remove(ticker)
        _save_cache()
        print(f"🗑️ Removed '{ticker}' from '{cat_key}'. Remaining: {len(_CACHE[cat_key])}")
        return True
    else:
        print(f"⚠️ '{ticker}' not found in '{cat_key}'.")
        return False


def _save_cache():
    UNIVERSE_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(UNIVERSE_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(_CACHE, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Central Dynamic Universe Manager CLI")
    parser.add_argument("--list", type=str, default=None, help="List tickers in a category ('csp', 'momentum', 'active_options', 'strategy:<name>', 'all')")
    parser.add_argument("--add", type=str, default=None, help="Add a ticker symbol")
    parser.add_argument("--remove", type=str, default=None, help="Remove a ticker symbol")
    parser.add_argument("--category", type=str, default="csp_universe", help="Target category (default: csp_universe)")
    parser.add_argument("--strategy", type=str, default=None, help="Target strategy name (e.g. 'wheel', 'ben_csp', 'income_cc')")

    args = parser.parse_args()

    if args.add:
        add_ticker(args.add, args.category, args.strategy)
    elif args.remove:
        remove_ticker(args.remove, args.category, args.strategy)
    elif args.list:
        if args.list.startswith("strategy:"):
            sname = args.list.split(":", 1)[1]
            tickers = get_strategy_tickers(sname)
            print(f"\n📋 [STRATEGY: {sname.upper()}] Tickers ({len(tickers)}):")
            print(", ".join(tickers) + "\n")
        else:
            tickers = get_universe(args.list)
            print(f"\n📋 [{args.list.upper()}] Universe ({len(tickers)} tickers):")
            print(", ".join(tickers) + "\n")
    else:
        _load_data_if_modified()
        print("\n🌐 Central Universe Summary:")
        for k, v in _CACHE.items():
            if isinstance(v, list):
                print(f"  • {k:<25} ({len(v)} tickers)")
            elif isinstance(v, dict):
                print(f"  • {k:<25} ({len(v)} strategies)")
                for sk, sv in v.items():
                    print(f"      - {sk:<20} ({len(sv)} tickers)")
        print("\nUsage:")
        print("  python -m scripts.utils.universe_manager --list csp")
        print("  python -m scripts.utils.universe_manager --list strategy:wheel")
        print("  python -m scripts.utils.universe_manager --add CRWD --category csp")
        print("  python -m scripts.utils.universe_manager --add BE --strategy wheel\n")


if __name__ == "__main__":
    main()
