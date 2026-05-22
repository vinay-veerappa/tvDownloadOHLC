import argparse
import json
import sys
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import yfinance as yf
except ImportError:
    yf = None

from scripts.streaming.options.config import (
    ETF_FALLBACK,
    FUTURES_YF_MAP,
    MACRO_DTE_TARGETS,
    MIN_NONZERO_OI_CONTRACTS,
)
from scripts.streaming.options.options_fetcher import (
    OptionChainData,
    OptionContract,
    create_client,
    fetch_futures_option_chain_data,
    fetch_option_chain_data,
    _today_ny,
    _safe_float,
)


def _chain_has_actionable_oi(chain: Any) -> bool:
    contracts = list(getattr(chain, "calls", [])) + list(getattr(chain, "puts", []))
    nonzero_oi = sum(1 for c in contracts if int(getattr(c, "open_interest", 0) or 0) > 0)
    return nonzero_oi >= MIN_NONZERO_OI_CONTRACTS


def _normalize_contract(contract: Any, side: str) -> dict[str, Any]:
    expiry = getattr(contract, "expiry", None)
    expiry_value = expiry.isoformat() if hasattr(expiry, "isoformat") else (str(expiry) if expiry else None)
    return {
        "symbol": getattr(contract, "symbol", None),
        "strike": float(getattr(contract, "strike", 0.0) or 0.0),
        "type": side,
        "contract_type": side,
        "expiry": expiry_value,
        "last": getattr(contract, "last", None),
        "bid": getattr(contract, "bid", None),
        "ask": getattr(contract, "ask", None),
        "mark": getattr(contract, "mark", None),
        "volume": int(getattr(contract, "volume", 0) or 0),
        "open_interest": int(getattr(contract, "open_interest", 0) or 0),
        "iv": getattr(contract, "iv", None),
        "delta": getattr(contract, "delta", None),
        "gamma": getattr(contract, "gamma", None),
        "theta": getattr(contract, "theta", None),
        "vega": getattr(contract, "vega", None),
        "rho": getattr(contract, "rho", None),
        "dte": int(getattr(contract, "dte", 0) or 0),
    }


def _parse_yf_contract(row: Any, expiry: date, dte: int, contract_type: str) -> OptionContract:
    def _get_field(obj: Any, field: str, default: Any = None) -> Any:
        if hasattr(obj, "get"):
            return obj.get(field, default)
        return getattr(obj, field, default)

    def _safe_int(val: Any) -> int:
        try:
            if val is None or (isinstance(val, float) and (val != val or val == float("inf"))):
                return 0
            return int(val)
        except Exception:
            return 0

    return OptionContract(
        symbol=str(_get_field(row, "contractSymbol", "")),
        strike=float(_get_field(row, "strike", 0.0)),
        type=contract_type,
        contract_type=contract_type,
        expiry=expiry,
        open_interest=_safe_int(_get_field(row, "openInterest")),
        volume=_safe_int(_get_field(row, "volume")),
        last=float(_get_field(row, "lastPrice", 0.0)),
        bid=float(_get_field(row, "bid", 0.0)),
        ask=float(_get_field(row, "ask", 0.0)),
        mark=(float(_get_field(row, "bid", 0.0)) + float(_get_field(row, "ask", 0.0))) / 2.0,
        iv=float(_get_field(row, "impliedVolatility", 0.0)),
        dte=dte,
    )


def _fetch_from_yfinance(ticker: str) -> OptionChainData | None:
    if yf is None:
        return None

    try:
        if ticker.startswith("/"):
            yf_ticker = FUTURES_YF_MAP.get(ticker, ticker)
        else:
            yf_ticker = f"^{ticker}" if ticker in ("SPX", "NDX", "DJX", "RUT", "VIX") else ticker

        yft = yf.Ticker(yf_ticker)
        expiries = yft.options
        if not expiries:
            return None

        spot = _safe_float(yft.fast_info.get("lastPrice", 0.0))
        spot_open = _safe_float(yft.fast_info.get("openPrice", 0.0))
        calls: list[OptionContract] = []
        puts: list[OptionContract] = []
        today = _today_ny()

        for exp in expiries:
            try:
                chain = yft.option_chain(exp)
                exp_date = date.fromisoformat(exp)
                dte = (exp_date - today).days
                for row in chain.calls.itertuples(index=False):
                    calls.append(_parse_yf_contract(row, exp_date, dte, "CALL"))
                for row in chain.puts.itertuples(index=False):
                    puts.append(_parse_yf_contract(row, exp_date, dte, "PUT"))
            except Exception:
                continue

        return OptionChainData(
            ticker=ticker,
            spot=spot,
            spot_open=spot_open,
            timestamp=datetime.utcnow(),
            contracts=calls + puts,
            underlying_symbol=ticker,
            spot_price=spot,
        )
    except Exception:
        return None


def _fetch_primary_chain(symbol: str) -> OptionChainData | None:
    try:
        if symbol.startswith("/"):
            return fetch_futures_option_chain_data(symbol, MACRO_DTE_TARGETS)
        client = create_client()
        return fetch_option_chain_data(client, symbol, MACRO_DTE_TARGETS)
    except Exception:
        # 1. Secondary Fallback: Dolt EOD Database
        try:
            from scripts.streaming.options.dolt_fallback import fetch_from_dolt
            chain = fetch_from_dolt(symbol)
            if chain:
                return chain
        except Exception:
            pass
            
        # 2. Tertiary Fallback: yfinance (fallback-of-fallback)
        return _fetch_from_yfinance(symbol)


def _fetch_snapshot(symbol: str) -> dict[str, Any]:
    ticker = symbol.upper()
    chain = _fetch_primary_chain(ticker)

    source_ticker = ticker
    if chain and (not chain.calls and not chain.puts or not _chain_has_actionable_oi(chain)):
        fallback = ETF_FALLBACK.get(ticker)
        if fallback:
            fallback_chain = _fetch_primary_chain(fallback)
            if fallback_chain and (fallback_chain.calls or fallback_chain.puts):
                chain = fallback_chain
                source_ticker = fallback

    if not chain:
        return {
            "ticker": ticker,
            "api_symbol": ticker,
            "source_ticker": source_ticker,
            "snapshot_time": datetime.utcnow().isoformat(),
            "spot": None,
            "calls": [],
            "puts": [],
            "error": "No option chain data available from existing pipeline",
        }

    return {
        "ticker": ticker,
        "api_symbol": chain.underlying_symbol or source_ticker,
        "source_ticker": source_ticker,
        "snapshot_time": chain.timestamp.isoformat() if getattr(chain, "timestamp", None) else datetime.utcnow().isoformat(),
        "spot": float(getattr(chain, "spot_price", 0.0) or getattr(chain, "spot", 0.0) or 0.0) or None,
        "calls": [_normalize_contract(c, "call") for c in chain.calls],
        "puts": [_normalize_contract(p, "put") for p in chain.puts],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch a normalized live option-chain snapshot for V3 fallback lookups")
    parser.add_argument("--tickers", nargs="+", required=True)
    args = parser.parse_args()

    snapshots: list[dict[str, Any]] = []
    for ticker in args.tickers:
        try:
            snapshots.append(_fetch_snapshot(ticker))
        except Exception as exc:
            snapshots.append(
                {
                    "ticker": ticker.upper(),
                    "api_symbol": ticker.upper(),
                    "snapshot_time": datetime.utcnow().isoformat(),
                    "spot": None,
                    "calls": [],
                    "puts": [],
                    "error": str(exc),
                }
            )

    print(json.dumps(snapshots))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())