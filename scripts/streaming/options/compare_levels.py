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
                   zero_gamma_da, total_gex, gamma_magnet=None, source=""):
    print(f"\n  [{label}]  ({source})")
    print(f"    Spot:          {spot:,.2f}")
    print(f"    Call Wall:     {call_wall:,.2f}" if call_wall else "    Call Wall:     N/A")
    print(f"    Put Wall:      {put_wall:,.2f}" if put_wall else "    Put Wall:      N/A")
    print(f"    Zero Gamma:    {zero_gamma:,.2f}" if zero_gamma else "    Zero Gamma:    N/A")
    print(f"    Zero Gamma DA: {zero_gamma_da:,.2f}" if zero_gamma_da else "    Zero Gamma DA: N/A")
    print(f"    Total GEX:     {total_gex:,.2f}")
    if gamma_magnet is not None:
        print(f"    Gamma Magnet:  {gamma_magnet:,.2f}" if gamma_magnet else "    Gamma Magnet:  N/A")


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
    print(f"  DTE Target:   7")

    # ─── 1. SPY (ETF) → calculate_dealer_levels → translate_to_futures ───
    spy_levels = None
    spy_translated = None
    spy_spot = None
    try:
        print(f"\n  Fetching {etf_ticker} chain from Schwab...")
        client = create_client(SECRETS_PATH, TOKEN_PATH)
        etf_chain = fetch_option_chain_data(client, etf_ticker, [7])

        from datetime import datetime
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("America/New_York")).date()
        near_calls = [c for c in etf_chain.calls if (c.expiry - today).days <= 14]
        near_puts = [c for c in etf_chain.puts if (c.expiry - today).days <= 14]
        etf_chain = replace(etf_chain, contracts=near_calls + near_puts)

        spy_spot = float(etf_chain.spot_price)
        print(f"  {etf_ticker} spot: {spy_spot:.2f}, {len(near_calls)} calls, {len(near_puts)} puts")

        spy_levels = calculate_dealer_levels(
            etf_chain, etf_ticker,
            min_oi_floor=500,
            wall_scope="FRONT_WEEK_WEIGHTED",
            wall_dte_range=(0, 14),
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

        from datetime import datetime
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("America/New_York")).date()
        near_calls = [c for c in idx_chain.calls if (c.expiry - today).days <= 14]
        near_puts = [c for c in idx_chain.puts if (c.expiry - today).days <= 14]
        idx_chain = replace(idx_chain, contracts=near_calls + near_puts)

        spx_spot = float(idx_chain.spot_price)
        print(f"  {idx_ticker} spot: {spx_spot:.2f}, {len(near_calls)} calls, {len(near_puts)} puts")

        spx_levels = calculate_dealer_levels(
            idx_chain, idx_ticker,
            min_oi_floor=500,
            wall_scope="FRONT_WEEK_WEIGHTED",
            wall_dte_range=(0, 14),
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
        num_expiries = sym_config.get("num_expiries", 6)
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
            print(f"  Waiting 8s for option Greeks to stream across {num_expiries} expiries...")
            time.sleep(8)

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

    # ─── Comparison Table (Delta-Adjusted) ───
    _print_header("COMPARISON TABLE (Delta-Adjusted Levels)")

    # Extract delta-adjusted values — call_wall_da, put_wall_da,
    # zero_gamma_delta_adj, total_gex_delta_adj
    spy_cw = getattr(spy_translated, 'call_wall_da', None) if spy_translated else None
    spy_pw = getattr(spy_translated, 'put_wall_da', None) if spy_translated else None
    spy_zg = getattr(spy_translated, 'zero_gamma_delta_adj', None) if spy_translated else None
    spy_zgda = spy_zg  # Already delta-adjusted
    spy_gex = getattr(spy_translated, 'total_gex_delta_adj', None) if spy_translated else None
    spy_gm = getattr(spy_translated, 'gamma_magnet', None) if spy_translated else None
    spy_spot_f = spy_translated.futures_price if spy_translated else (spy_spot or 0)

    spx_cw = getattr(spx_levels, 'call_wall_da', None) if spx_levels else None
    spx_pw = getattr(spx_levels, 'put_wall_da', None) if spx_levels else None
    spx_zg = getattr(spx_levels, 'zero_gamma_delta_adj', None) if spx_levels else None
    spx_zgda = spx_zg  # Already delta-adjusted
    spx_gex = getattr(spx_levels, 'total_gex_delta_adj', None) if spx_levels else None
    spx_gm = getattr(spx_levels, 'gamma_magnet', None) if spx_levels else None
    spx_spot_f = spx_spot or 0

    es_cw = getattr(es_levels, 'call_wall_da', None) if es_levels else None
    es_pw = getattr(es_levels, 'put_wall_da', None) if es_levels else None
    es_zg = getattr(es_levels, 'zero_gamma_delta_adj', None) if es_levels else None
    es_zgda = es_zg  # Already delta-adjusted
    es_gex = getattr(es_levels, 'total_gex_delta_adj', None) if es_levels else None
    es_gm = getattr(es_levels, 'gamma_magnet', None) if es_levels else None
    es_spot_f = es_spot or 0

    # Print individual summaries (delta-adjusted)
    if spy_translated:
        _print_levels(f"{etf_ticker} \u2192 {symbol} (DA)", spy_spot_f,
                      getattr(spy_translated, 'call_wall_da', None),
                      getattr(spy_translated, 'put_wall_da', None),
                      getattr(spy_translated, 'zero_gamma_delta_adj', None),
                      None,
                      getattr(spy_translated, 'total_gex_delta_adj', 0.0),
                      getattr(spy_translated, 'gamma_magnet', None),
                      source="Schwab ETF chain + translate (delta-adjusted)")
    if spx_levels:
        _print_levels(f"{idx_ticker} (DA)", spx_spot_f,
                      getattr(spx_levels, 'call_wall_da', None),
                      getattr(spx_levels, 'put_wall_da', None),
                      getattr(spx_levels, 'zero_gamma_delta_adj', None),
                      None,
                      getattr(spx_levels, 'total_gex_delta_adj', 0.0),
                      getattr(spx_levels, 'gamma_magnet', None),
                      source="Schwab index chain (delta-adjusted)")
    if es_levels:
        _print_levels(f"{symbol} (RTD, DA)", es_spot_f,
                      getattr(es_levels, 'call_wall_da', None),
                      getattr(es_levels, 'put_wall_da', None),
                      getattr(es_levels, 'zero_gamma_delta_adj', None),
                      None,
                      getattr(es_levels, 'total_gex_delta_adj', 0.0),
                      getattr(es_levels, 'gamma_magnet', None),
                      source="TOS RTD futures options (Black-76, delta-adjusted)")

    # Side-by-side table
    print(f"\n  {'Metric':<20s}  {'SPY trans':>12s}  {'SPX':>12s}  {'/ES RTD':>12s}")
    print(f"  {'-' * 20}  {'-' * 12}  {'-' * 12}  {'-' * 12}")
    _compare_row("Spot", spy_spot_f, spx_spot_f, es_spot_f)
    _compare_row("Call Wall (DA)", spy_cw, spx_cw, es_cw)
    _compare_row("Put Wall (DA)", spy_pw, spx_pw, es_pw)
    _compare_row("Zero Gamma (DA)", spy_zg, spx_zg, es_zg)
    _compare_row("Total GEX (DA)", spy_gex, spx_gex, es_gex)
    _compare_row("Gamma Magnet", spy_gm, spx_gm, es_gm)

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