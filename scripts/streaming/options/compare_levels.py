"""
compare_levels.py
=================
Side-by-side comparison of dealer levels across three perspectives:

  1. **SPY translated** — SPY cash chain → calculate_dealer_levels →
     translate_to_futures (multiplicative scaling to /ES)
  2. **SPX**            — SPX index chain → calculate_dealer_levels
     (additive basis to /ES)
  3. **/ES (RTD)**      — TOS RTD futures options → calculate_futures_gex
     (Black-76 model, native futures chain)

This validates that the three independent paths produce consistent
call walls, put walls, zero gamma, and total GEX.

Usage::

    python -m scripts.streaming.options.compare_levels
    python -m scripts.streaming.options.compare_levels --symbol /ES
    python -m scripts.streaming.options.compare_levels --symbol /NQ
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from dataclasses import replace

log = logging.getLogger(__name__)


def _nearest_friday(d: date) -> date:
    days_ahead = 4 - d.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return d + timedelta(days=days_ahead)


def _print_header(title: str):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def _print_levels(label: str, spot: float, call_wall, put_wall, zero_gamma,
                   zero_gamma_da, total_gex, gamma_magnet=None, source="",
                   call_wall_0dte=None, put_wall_0dte=None):
    print(f"\n  [{label}]  ({source})")
    print(f"    Spot:          {spot:,.2f}")
    if call_wall:
        print(f"    Call Wall:     {call_wall:,.2f}  (\u0394 {call_wall - spot:+.2f})")
    else:
        print(f"    Call Wall:     N/A")
    if put_wall:
        print(f"    Put Wall:      {put_wall:,.2f}  (\u0394 {put_wall - spot:+.2f})")
    else:
        print(f"    Put Wall:      N/A")
    if call_wall_0dte:
        print(f"    Call Wall 0DTE:{call_wall_0dte:,.2f}  (\u0394 {call_wall_0dte - spot:+.2f})")
    if put_wall_0dte:
        print(f"    Put Wall 0DTE: {put_wall_0dte:,.2f}  (\u0394 {put_wall_0dte - spot:+.2f})")
    print(f"    Zero Gamma:    {zero_gamma:,.2f}  (\u0394 {zero_gamma - spot:+.2f})" if zero_gamma else "    Zero Gamma:    N/A")
    print(f"    Zero Gamma DA: {zero_gamma_da:,.2f}" if zero_gamma_da else "    Zero Gamma DA: N/A")
    print(f"    Total GEX:     {total_gex:,.2f}")
    if gamma_magnet is not None:
        print(f"    Gamma Magnet:  {gamma_magnet:,.2f}  (\u0394 {gamma_magnet - spot:+.2f})" if gamma_magnet else "    Gamma Magnet:  N/A")


def _compare_row(label: str, spy_val, spx_val, es_val):
    """Print a single comparison row across the three sources."""
    def fmt(v):
        if v is None:
            return "N/A"
        return f"{v:,.2f}"

    diff_spy_spx = ""
    if spy_val is not None and spx_val is not None:
        diff_spy_spx = f"  Δ={spx_val - spy_val:+.2f}"

    diff_spx_es = ""
    if spx_val is not None and es_val is not None:
        diff_spx_es = f"  Δ={es_val - spx_val:+.2f}"

    print(f"  {label:<20s}  SPY={fmt(spy_val):>12s}  SPX={fmt(spx_val):>12s}  /ES={fmt(es_val):>12s}{diff_spy_spx}{diff_spx_es}")


def run_comparison(symbol: str = "/ES"):
    """Run the full side-by-side comparison."""
    from scripts.streaming.options.config import (
        SECRETS_PATH, TOKEN_PATH, INDEX_TO_FUTURES, FUTURES_TO_INDEX,
    )
    from scripts.streaming.options.options_fetcher import (
        create_client, fetch_option_chain_data, fetch_futures_quote,
    )
    from scripts.streaming.options.gex_calculator import calculate_dealer_levels
    from scripts.streaming.options.futures_translator import translate_to_futures

    # Map futures symbol to ETF and index tickers
    if symbol == "/ES":
        etf_ticker = "SPY"
        idx_ticker = "SPX"
    elif symbol == "/NQ":
        etf_ticker = "QQQ"
        idx_ticker = "NDX"
    elif symbol == "/RTY":
        etf_ticker = "IWM"
        idx_ticker = "RUT"
    elif symbol == "/YM":
        etf_ticker = "DIA"
        idx_ticker = "DJX"
    else:
        # Fallback: look up in FUTURES_TO_INDEX
        idx_ticker = FUTURES_TO_INDEX.get(symbol, "")
        etf_ticker = ""
        if not etf_ticker:
            print(f"No ETF/index mapping for {symbol}")
            return

    expiry = _nearest_friday(date.today())

    _print_header(f"Side-by-Side Level Comparison: {symbol}")
    print(f"  ETF Proxy:   {etf_ticker}")
    print(f"  Index:       {idx_ticker}")
    print(f"  Front Expiry: {expiry}")
    print(f"  DTE Range:    0-7 (front-week, day-trading focus)")

    # ─── 1. SPY (ETF) → calculate_dealer_levels → translate_to_futures ───
    spy_levels = None
    spy_translated = None
    spy_spot = None
    try:
        print(f"\n  Fetching {etf_ticker} chain from Schwab...")
        client = create_client(SECRETS_PATH, TOKEN_PATH)
        etf_chain = fetch_option_chain_data(client, etf_ticker, [7])

        spy_spot = float(etf_chain.spot_price)
        print(f"  {etf_ticker} spot: {spy_spot:.2f}, {len(etf_chain.calls)} calls, {len(etf_chain.puts)} puts")

        spy_levels = calculate_dealer_levels(
            etf_chain, etf_ticker,
            min_oi_floor=500,
            wall_scope="FRONT_WEEK_WEIGHTED",
            wall_dte_range=(0, 7),
        )

        # Translate to futures
        fut = fetch_futures_quote(symbol)
        if fut and fut.price:
            spy_translated = translate_to_futures(spy_levels, fut)
            print(f"  {symbol} futures price: {fut.price:.2f}")
        else:
            print(f"  WARNING: No futures quote for {symbol}")
    except Exception as e:
        print(f"  ERROR fetching {etf_ticker}: {e}")
        log.debug("ETF fetch error", exc_info=True)

    # ─── 2. SPX (Index) → calculate_dealer_levels ───
    spx_levels = None
    spx_spot = None
    try:
        print(f"\n  Fetching {idx_ticker} chain from Schwab...")
        client = create_client(SECRETS_PATH, TOKEN_PATH)
        idx_chain = fetch_option_chain_data(client, idx_ticker, [7])

        spx_spot = float(idx_chain.spot_price)
        print(f"  {idx_ticker} spot: {spx_spot:.2f}, {len(idx_chain.calls)} calls, {len(idx_chain.puts)} puts")

        spx_levels = calculate_dealer_levels(
            idx_chain, idx_ticker,
            min_oi_floor=500,
            wall_scope="FRONT_WEEK_WEIGHTED",
            wall_dte_range=(0, 7),
        )
    except Exception as e:
        print(f"  ERROR fetching {idx_ticker}: {e}")
        log.debug("Index fetch error", exc_info=True)

    # ─── 3. /ES (RTD) → calculate_futures_gex ───
    es_levels = None
    es_spot = None
    es_result = None
    try:
        print(f"\n  Fetching {symbol} from TOS RTD...")
        from scripts.streaming.options.tos_rtd.adapter import TOSRTDAdapter, RTDConfig
        from scripts.streaming.options.tos_rtd.rtd_gex_calculator import calculate_futures_gex
        from scripts.streaming.options.config import TOS_RTD_SYMBOL_CONFIG
        import time

        # Use per-symbol strike tiers and expiry count from config
        sym_config = TOS_RTD_SYMBOL_CONFIG.get(symbol, {})
        strike_tiers = sym_config.get("strike_tiers", [(100, 5.0), (300, 10.0), (600, 25.0)])
        # For day-trading comparison: 3 expiries (0DTE + front + next) for faster streaming
        num_expiries = 3
        min_oi_floor = sym_config.get("min_oi_floor", 50)
        # Use the widest tier for the initial scan
        max_range = int(strike_tiers[-1][0]) if strike_tiers else 600
        max_spacing = float(strike_tiers[-1][1]) if strike_tiers else 25.0

        print(f"  RTD config: {num_expiries} expiries, strike tiers={strike_tiers}, min_oi={min_oi_floor}")

        config = RTDConfig(
            strike_range=max_range,
            strike_spacing=max_spacing,
            symbol_configs={symbol: {"strike_range": max_range, "strike_spacing": max_spacing}},
        )
        adapter = TOSRTDAdapter(config)

        # Build list of upcoming Friday expiries
        from datetime import datetime as dt_cls
        today_date = date.today()
        expiry_dates = []
        for i in range(num_expiries):
            d = today_date + timedelta(days=i * 7)
            # Find the Friday of that week
            days_to_fri = (4 - d.weekday()) % 7
            expiry_dates.append(d + timedelta(days=days_to_fri))

        print(f"  Expiry dates: {expiry_dates}")
        adapter.start(symbols=[symbol], expiry=expiry_dates[0])
        time.sleep(3)
        es_spot = adapter.get_futures_price(symbol)

        if es_spot:
            print(f"  {symbol} RTD price: {es_spot:.2f}")
            adapter.stop()
            time.sleep(1)
            # Start with all expiry dates and current price for strike selection
            adapter.start(
                symbols=[symbol], expiry=expiry_dates[0],
                current_price={symbol: es_spot},
                expiries=expiry_dates,
            )
            print(f"  Waiting 5s for option Greeks to stream across {num_expiries} expiries...")
            time.sleep(5)

            es_result = calculate_futures_gex(adapter, symbol)
            if es_result:
                es_levels = es_result.dealer_levels
            adapter.stop()
        else:
            print(f"  No RTD price for {symbol} — is TOS desktop running?")
            adapter.stop()
    except Exception as e:
        print(f"  ERROR fetching {symbol} from RTD: {e}")
        log.debug("RTD fetch error", exc_info=True)

    # ─── Comparison Table ───
    _print_header("COMPARISON TABLE (Delta-Adjusted)")

    # call_wall / put_wall are now delta-adjusted natively in calculate_dealer_levels.
    # zero_gamma_delta_adj and total_gex_delta_adj were already delta-adjusted.
    spy_cw = spy_translated.call_wall if spy_translated else None
    spy_pw = spy_translated.put_wall if spy_translated else None
    spy_cw_0dte = getattr(spy_translated, 'call_wall_0dte', None) if spy_translated else None
    spy_pw_0dte = getattr(spy_translated, 'put_wall_0dte', None) if spy_translated else None
    spy_zg = spy_translated.zero_gamma_delta_adj if spy_translated else None
    spy_gex = spy_translated.total_gex_delta_adj if spy_translated else None
    spy_gm = spy_translated.gamma_magnet if spy_translated else None
    spy_spot_f = spy_translated.futures_price if spy_translated else (spy_spot or 0)

    spx_cw = spx_levels.call_wall if spx_levels else None
    spx_pw = spx_levels.put_wall if spx_levels else None
    spx_cw_0dte = getattr(spx_levels, 'call_wall_0dte', None) if spx_levels else None
    spx_pw_0dte = getattr(spx_levels, 'put_wall_0dte', None) if spx_levels else None
    spx_zg = spx_levels.zero_gamma_delta_adj if spx_levels else None
    spx_gex = spx_levels.total_gex_delta_adj if spx_levels else None
    spx_gm = spx_levels.gamma_magnet if spx_levels else None
    spx_spot_f = spx_spot or 0

    es_cw = es_levels.call_wall if es_levels else None
    es_pw = es_levels.put_wall if es_levels else None
    es_cw_0dte = getattr(es_levels, 'call_wall_0dte', None) if es_levels else None
    es_pw_0dte = getattr(es_levels, 'put_wall_0dte', None) if es_levels else None
    es_zg = es_levels.zero_gamma_delta_adj if es_levels else None
    es_gex = es_levels.total_gex_delta_adj if es_levels else None
    es_gm = es_levels.gamma_magnet if es_levels else None
    es_spot_f = es_spot or 0

    # Print individual summaries
    if spy_translated:
        _print_levels(f"{etf_ticker} \u2192 {symbol}", spy_spot_f,
                      spy_cw, spy_pw, spy_zg, None, spy_gex, spy_gm,
                      source="Schwab ETF chain + translate (delta-adjusted)",
                      call_wall_0dte=spy_cw_0dte, put_wall_0dte=spy_pw_0dte)
    if spx_levels:
        _print_levels(f"{idx_ticker}", spx_spot_f,
                      spx_cw, spx_pw, spx_zg, None, spx_gex, spx_gm,
                      source="Schwab index chain (delta-adjusted)",
                      call_wall_0dte=spx_cw_0dte, put_wall_0dte=spx_pw_0dte)
    if es_levels:
        _print_levels(f"{symbol} (RTD)", es_spot_f,
                      es_cw, es_pw, es_zg, None, es_gex, es_gm,
                      source="TOS RTD futures options (Black-76, delta-adjusted)",
                      call_wall_0dte=es_cw_0dte, put_wall_0dte=es_pw_0dte)

    # Side-by-side table
    print(f"\n  {'Metric':<20s}  {'SPY trans':>12s}  {'SPX':>12s}  {'/ES RTD':>12s}")
    print(f"  {'-' * 20}  {'-' * 12}  {'-' * 12}  {'-' * 12}")
    _compare_row("Spot", spy_spot_f, spx_spot_f, es_spot_f)
    _compare_row("Call Wall", spy_cw, spx_cw, es_cw)
    _compare_row("Put Wall", spy_pw, spx_pw, es_pw)
    _compare_row("Call Wall 0DTE", spy_cw_0dte, spx_cw_0dte, es_cw_0dte)
    _compare_row("Put Wall 0DTE", spy_pw_0dte, spx_pw_0dte, es_pw_0dte)
    _compare_row("Zero Gamma (DA)", spy_zg, spx_zg, es_zg)
    _compare_row("Total GEX (DA)", spy_gex, spx_gex, es_gex)
    _compare_row("Gamma Magnet", spy_gm, spx_gm, es_gm)

    # Wall distances from spot (day-trading context)
    print(f"\n  --- Wall Distance from Spot (Day-Trading Context) ---")
    def _dist_row(label: str, cw, pw, spot_f):
        cw_d = f"{cw - spot_f:+.2f}" if cw and spot_f else "N/A"
        pw_d = f"{pw - spot_f:+.2f}" if pw and spot_f else "N/A"
        print(f"  {label:<20s}  CW={cw_d:>10s}  PW={pw_d:>10s}  Range={cw - pw:.2f}" if (cw and pw) else f"  {label:<20s}  CW={cw_d:>10s}  PW={pw_d:>10s}")
    if spy_translated:
        _dist_row("SPY trans (weekly)", spy_cw, spy_pw, spy_spot_f)
        _dist_row("SPY trans (0DTE)", spy_cw_0dte, spy_pw_0dte, spy_spot_f)
    if spx_levels:
        _dist_row(f"{idx_ticker} (weekly)", spx_cw, spx_pw, spx_spot_f)
        _dist_row(f"{idx_ticker} (0DTE)", spx_cw_0dte, spx_pw_0dte, spx_spot_f)
    if es_levels:
        _dist_row(f"{symbol} RTD (weekly)", es_cw, es_pw, es_spot_f)
        _dist_row(f"{symbol} RTD (0DTE)", es_cw_0dte, es_pw_0dte, es_spot_f)

    # EM comparison (from unified_levels.json + weekly_em_scope.json)
    print(f"\n  --- Expected Move (from weekly_em_scope.json) ---")
    try:
        import json
        from scripts.streaming.options.config import REPO_ROOT
        scope_path = REPO_ROOT / "data" / "options" / "weekly_em_scope.json"
        scope_data = json.loads(scope_path.read_text(encoding="utf-8"))
        for check_ticker in [etf_ticker, idx_ticker, symbol.replace("/", "")]:
            if check_ticker in scope_data:
                sc = scope_data[check_ticker]
                em_val = (sc.get("em_upper", 0) - sc.get("em_lower", 0)) / 2.0
                print(f"    {check_ticker}: weekly EM \u00b1{em_val:.2f} "
                      f"(expiry {sc.get('expiry','?')}, captured {sc.get('captured_on','?')})")
    except Exception as e:
        print(f"    Error reading weekly_em_scope.json: {e}")

    print(f"\n{'=' * 70}")
    print("Done.")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    parser = argparse.ArgumentParser(description="Side-by-side level comparison: SPY translated vs SPX vs /ES RTD")
    parser.add_argument("--symbol", default="/ES", help="Futures symbol (default: /ES)")
    args = parser.parse_args()
    run_comparison(symbol=args.symbol)


if __name__ == "__main__":
    main()