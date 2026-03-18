"""
options_fetcher.py
==================
All Charles Schwab API I/O lives here.

Public surface
--------------
create_client()          — Authenticated schwab.Client from secrets/token files.
fetch_option_chain_data()— Full option chain for a ticker, filtered to DTE targets.
fetch_futures_quote()    — Current price for a front-month futures symbol.

Domain objects
--------------
OptionContract  — Single option contract with greeks and market data.
OptionChainData — All calls/puts for one underlying, one DTE window.
FuturesQuote    — A single futures price snapshot.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import schwab

try:
    import yfinance as yf
except ImportError:
    yf = None

from .config import SCHWAB_INDEX_PREFIX, SECRETS_PATH, TOKEN_PATH

log = logging.getLogger(__name__)


FUTURES_YF_MAP = {
    "/ES": "ES=F",
    "/NQ": "NQ=F",
}


# ---------------------------------------------------------------------------
# Domain objects
# ---------------------------------------------------------------------------

@dataclass
class OptionContract:
    symbol: str
    strike: float
    expiry: date
    contract_type: str       # "CALL" or "PUT"
    open_interest: int
    volume: int
    mark: float
    bid: float
    ask: float
    iv: float                # decimal, e.g. 0.20 for 20%
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    dte: int


@dataclass
class OptionChainData:
    underlying_symbol: str   # normalised Schwab API symbol
    spot_price: float
    calls: list[OptionContract] = field(default_factory=list)
    puts:  list[OptionContract] = field(default_factory=list)


@dataclass
class FuturesQuote:
    symbol: str
    price: float


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _schwab_symbol(symbol: str) -> str:
    """Return the Schwab API symbol for *symbol*, applying the $ prefix where needed."""
    return SCHWAB_INDEX_PREFIX.get(symbol.upper(), symbol)


def _best_mark(opt: dict[str, Any]) -> float:
    if opt.get("mark") is not None:
        return float(opt["mark"])
    return (float(opt.get("bid", 0)) + float(opt.get("ask", 0))) / 2.0


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _parse_contract(raw: dict[str, Any], contract_type: str) -> OptionContract | None:
    """Parse a single raw Schwab option dict into an OptionContract."""
    try:
        exp_str = raw.get("expirationDate", "")
        exp_date = date.fromisoformat(exp_str[:10]) if exp_str else date.today()
        iv_raw = raw.get("volatility")
        iv = float(iv_raw) / 100.0 if iv_raw is not None else 0.0
        return OptionContract(
            symbol=raw.get("symbol", ""),
            strike=_safe_float(raw.get("strikePrice")),
            expiry=exp_date,
            contract_type=contract_type,
            open_interest=int(raw.get("openInterest") or 0),
            volume=int(raw.get("totalVolume") or 0),
            mark=_best_mark(raw),
            bid=_safe_float(raw.get("bid")),
            ask=_safe_float(raw.get("ask")),
            iv=iv,
            delta=_safe_float(raw.get("delta")),
            gamma=_safe_float(raw.get("gamma")),
            theta=_safe_float(raw.get("theta")),
            vega=_safe_float(raw.get("vega")),
            rho=_safe_float(raw.get("rho")),
            dte=int(raw.get("daysToExpiration") or 0),
        )
    except Exception as exc:
        log.debug("Contract parse error (%s): %s", raw.get("symbol", "?"), exc)
        return None


def _parse_exp_key(exp_key: str) -> tuple[date, int]:
    """
    Parse Schwab expiration key format: "YYYY-MM-DD:DTE".

    Returns
    -------
    tuple[date, int]
        (expiry_date, dte)
    """
    date_part, _, dte_part = exp_key.partition(":")
    exp_date = date.fromisoformat(date_part)
    if dte_part:
        try:
            return exp_date, int(dte_part)
        except ValueError:
            pass
    return exp_date, (exp_date - date.today()).days


def _select_expiration_keys(
    option_map: dict[str, dict[str, list[dict]]],
    dte_targets: list[int],
) -> set[str]:
    """
    Select nearest available expiration keys for each target DTE.

    This is robust for weekends/overnights where exact 0DTE/1DTE calendar
    dates may not exist; it chooses the closest listed expiries instead.
    """
    if not option_map:
        return set()

    parsed: list[tuple[str, date, int]] = []
    for exp_key in option_map.keys():
        try:
            exp_date, dte = _parse_exp_key(exp_key)
            parsed.append((exp_key, exp_date, dte))
        except ValueError:
            log.debug("Could not parse expiry key: %s", exp_key)

    if not parsed:
        return set()

    selected: set[str] = set()
    for target in dte_targets:
        # Prefer nearest non-negative DTE first; fallback to absolute nearest.
        non_negative = [p for p in parsed if p[2] >= 0]
        pool = non_negative if non_negative else parsed
        best = min(pool, key=lambda p: (abs(p[2] - target), p[2], p[1]))
        selected.add(best[0])

    # Ensure at least one expiry exists even if targets are empty.
    if not selected:
        best = min(parsed, key=lambda p: (abs(p[2]), p[1]))
        selected.add(best[0])

    return selected


def _extract_contracts(
    option_map: dict[str, dict[str, list[dict]]],
    contract_type: str,
    selected_exp_keys: set[str],
) -> list[OptionContract]:
    """Flatten callExpDateMap/putExpDateMap for the selected expirations."""
    contracts: list[OptionContract] = []
    for exp_key, strikes in option_map.items():
        if exp_key not in selected_exp_keys:
            continue
        for _strike_key, contr_list in strikes.items():
            for raw in contr_list:
                parsed = _parse_contract(raw, contract_type)
                if parsed is not None:
                    contracts.append(parsed)
    return contracts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_client(
    secrets_path: Path = SECRETS_PATH,
    token_path: Path = TOKEN_PATH,
) -> Any:
    """
    Build an authenticated Schwab API client.

    Parameters
    ----------
    secrets_path : Path to secrets.json (app_key / app_secret).
    token_path   : Path to token.json (OAuth tokens).

    Returns
    -------
    schwab.client.Client
    """
    if not secrets_path.exists():
        raise FileNotFoundError(f"secrets.json not found at {secrets_path}")
    if not token_path.exists():
        raise FileNotFoundError(f"token.json not found at {token_path}")

    secrets = json.loads(secrets_path.read_text())
    client = schwab.auth.client_from_token_file(
        token_path=str(token_path),
        api_key=secrets["app_key"],
        app_secret=secrets["app_secret"],
        enforce_enums=False,
    )
    log.info("Schwab client created (token: %s)", token_path.name)
    return client


def fetch_option_chain_data(
    client: Any,
    symbol: str,
    dte_targets: list[int],
) -> OptionChainData:
    """
    Pull the full option chain for *symbol*, retaining only expirations in
    *dte_targets* (e.g. [0, 1] for 0DTE and 1DTE).

    Parameters
    ----------
    client      : Authenticated Schwab client (from create_client()).
    symbol      : Human-readable ticker, e.g. "SPX", "NDX", "SPY", "QQQ".
    dte_targets : List of target DTE values (calendar days from today).

    Raises
    ------
    RuntimeError  : On HTTP error, rate-limit, or non-SUCCESS API response.
    """
    api_sym = _schwab_symbol(symbol)
    today = date.today()
    # Query a wide enough window so weekend/overnight runs still return expiries.
    max_dte = max(dte_targets) + 10

    response = client.get_option_chain(
        api_sym,
        from_date=today,
        to_date=today + timedelta(days=max_dte),
        include_underlying_quote=True,
    )

    if response.status_code == 429:
        raise RuntimeError(
            f"Schwab API rate-limited while fetching option chain for {symbol}"
        )
    if response.status_code != 200:
        raise RuntimeError(
            f"Option chain HTTP {response.status_code} for {symbol} ({api_sym})"
        )

    payload = response.json()
    status = payload.get("status")
    if status and status != "SUCCESS":
        raise RuntimeError(
            f"Option chain status='{status}' for {symbol} ({api_sym})"
        )

    # Extract spot price from nested underlying quote
    underlying = payload.get("underlying") or {}
    spot: float = _safe_float(
        underlying.get("mark") or underlying.get("last") or payload.get("underlyingPrice")
    )
    if spot == 0:
        log.warning("Spot price is zero for %s — levels may be inaccurate.", symbol)

    call_map = payload.get("callExpDateMap", {})
    put_map = payload.get("putExpDateMap", {})

    # Pick nearest available expirations based on whichever map is populated.
    exp_source_map = call_map if call_map else put_map
    selected_exp_keys = _select_expiration_keys(exp_source_map, dte_targets)

    calls = _extract_contracts(
        call_map, "CALL", selected_exp_keys
    )
    puts = _extract_contracts(
        put_map, "PUT", selected_exp_keys
    )

    log.info(
        "Option chain %s (%s): spot=%.2f  calls=%d  puts=%d  dte_targets=%s  selected_exp=%s",
        symbol, api_sym, spot, len(calls), len(puts), dte_targets, sorted(selected_exp_keys),
    )
    return OptionChainData(
        underlying_symbol=api_sym,
        spot_price=spot,
        calls=calls,
        puts=puts,
    )


def fetch_futures_quote(client: Any, symbol: str) -> FuturesQuote:
    """
    Fetch the current price for a front-month futures symbol (e.g. "/ES", "/NQ").

    Parameters
    ----------
    client : Authenticated Schwab client.
    symbol : Futures symbol string, e.g. "/ES".

    Raises
    ------
    RuntimeError : On HTTP error or missing price field.
    """
    import requests
    import json
    # Always read the access token directly from token.json
    try:
        with open('token.json', 'r') as f:
            token_data = json.load(f)
            access_token = token_data['token']['access_token']
    except Exception as e:
        raise RuntimeError(f'Could not read access token from token.json: {e}')

    url = f'https://api.schwabapi.com/marketdata/v1/quotes?symbols={symbol}&fields=quote'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json',
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        log.warning(f"Schwab API HTTP {response.status_code} for {url}")
        return None
    data = response.json()
    key = next(iter(data.keys()), None)
    if key is None:
        return None
    quote = data[key].get("quote", {})
    price = _safe_float(
        quote.get("lastPrice")
        or quote.get("last")
        or quote.get("mark")
        or quote.get("closePrice")
    )
    if price > 0:
        return FuturesQuote(symbol=symbol, price=price)
    return None

    def _fetch_from_yfinance() -> float | None:
        if yf is None:
            return None
        yf_symbol = FUTURES_YF_MAP.get(symbol)
        if not yf_symbol:
            return None
        try:
            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(period="5d", interval="1d")
            if not hist.empty:
                close = hist["Close"].dropna()
                if not close.empty:
                    return float(close.iloc[-1])
            info = ticker.fast_info if hasattr(ticker, "fast_info") else {}
            last = info.get("lastPrice") if info else None
            return float(last) if last is not None else None
        except Exception as exc:
            log.warning("yfinance fallback failed for %s (%s): %s", symbol, yf_symbol, exc)
            return None

    price = _fetch_from_schwab()
    source = "schwab"
    if price is None:
        price = _fetch_from_yfinance()
        source = "yfinance"

    if price is None or price <= 0:
        raise RuntimeError(
            f"Futures quote unavailable for {symbol} from Schwab and yfinance fallback"
        )

    log.info("Futures quote %s: %.2f (source=%s)", symbol, price, source)
    return FuturesQuote(symbol=symbol, price=price)
