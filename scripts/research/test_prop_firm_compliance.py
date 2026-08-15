"""
Prop Firm Compliance & Monte Carlo Stress Test for 15m MTF IFVG + CISD Strategy.
================================================================================
Tests strategy trades against canonical prop firm evaluation profiles:
- Apex 50K ($3,000 Target, $2,500 Live Trailing Drawdown, 30-Day Window)
- Topstep 50K ($3,000 Target, $2,000 EOD Trailing DD, $1,000 Daily Loss Limit, 60-Day Window)
- FTMO 50K ($5,000 Target, $5,000 Static DD, $2,500 DLL, 30% Consistency Rule)
- Evaluates both Micro Sizing (2 contracts) and Prop Standard Sizing (1 Mini / 10 Micros).
"""
from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd
import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
_root_dir = str(_current_dir.parent) if _current_dir.name == "scripts" else str(Path(__file__).resolve().parents[2])
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from scripts.libs_py.data.loader import DataLoader
from scripts.trading_framework.config.config_loader import load_config
from scripts.strategies.ifvg_cisd.core.ifvg_cisd_strategy import IFVGCISDStrategy
from scripts.trading_framework.ml.prop_firm_simulator import PropFirmSimulator, FIRM_PROFILES


def run_prop_firm_stress_test(symbol: str = "NQ1"):
    print("=" * 80)
    print(f"🏛️ PROP FIRM EVALUATION & STRESS TEST: 15m MTF IFVG + CISD ({symbol})")
    print("=" * 80)

    config = load_config("scripts/trading_framework/config/sessions.yaml")
    loader = DataLoader(config)
    print(f"📥 Loading full 10-year dataset for {symbol}...")
    df = loader.load_enriched(symbol)

    strategy = IFVGCISDStrategy(ticker=symbol)
    params = {
        "resample_tf": "15min",
        "r_mult_tp1": 1.5,
        "r_mult_tp2": 1.75,
        "atr_risk_mult": 2.2,
        "max_trades_per_day": 1,
        "filter_lunch": False,
        "use_authoritative_cisd": False,
    }

    signals = strategy.hunt(df, params)
    print(f"✅ Generated {len(signals):,d} signals across 10 years.")

    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    times = df.index

    # Test two sizing modes: 
    # Mode A: Conservative 2 Micros (MNQ, $4/pt)
    # Mode B: Prop Evaluation Standard (1 Mini NQ or 10 Micros MNQ, $20/pt)
    for sizing_name, contracts, pt_val in [
        ("Conservative 2 Micros (MNQ)", 2, 2.0),
        ("Standard Prop Sizing (1 Mini / 10 Micros NQ)", 10, 2.0),
    ]:
        print("\n" + "=" * 80)
        print(f"💼 SIZING PROFILE: {sizing_name}")
        print("=" * 80)

        comm_total = 1.05 * 2 * contracts
        slippage_cost = 0.25

        sig_times = signals["signal_time"].values
        sig_directions = signals["direction"].values
        sig_entries = signals["entry_price"].values
        sig_stops = signals["stop_price"].values
        sig_risks = signals["risk_pts"].values

        data_times_int = times.view("int64")
        sig_times_int = pd.to_datetime(sig_times).view("int64")
        start_indices = np.searchsorted(data_times_int, sig_times_int)

        n_data = len(df)
        trade_log = []

        for i in range(len(signals)):
            start_idx = start_indices[i]
            if start_idx >= n_data:
                continue

            is_long = sig_directions[i] == "long"
            entry_raw = float(sig_entries[i])
            risk = max(float(sig_risks[i]), 1.0)
            orig_stop = float(sig_stops[i])

            executed_entry = entry_raw + slippage_cost if is_long else entry_raw - slippage_cost
            
            # EOD 15:55 ET Hard Flattening or Max 15 bars
            end_idx = min(start_idx + 15, n_data)
            sig_date = times[start_idx].date()
            for check_b in range(start_idx, end_idx):
                if times[check_b].date() != sig_date or (times[check_b].hour == 15 and times[check_b].minute >= 55):
                    end_idx = check_b + 1
                    break

            tp_target = executed_entry + (risk * 1.5) if is_long else executed_entry - (risk * 1.5)

            tp_hit = False
            stop_hit = False
            exit_bar_idx = end_idx - 1

            for b_idx in range(start_idx, end_idx):
                h = highs[b_idx]
                l = lows[b_idx]

                if is_long:
                    if l <= orig_stop:
                        stop_hit = True
                        exit_bar_idx = b_idx
                        break
                    if h >= tp_target:
                        tp_hit = True
                        exit_bar_idx = b_idx
                        break
                else:
                    if h >= orig_stop:
                        stop_hit = True
                        exit_bar_idx = b_idx
                        break
                    if l <= tp_target:
                        tp_hit = True
                        exit_bar_idx = b_idx
                        break
            
            if stop_hit:
                exit_p = orig_stop - slippage_cost if is_long else orig_stop + slippage_cost
            elif tp_hit:
                exit_p = tp_target - slippage_cost if is_long else tp_target + slippage_cost
            else:
                exit_p = closes[exit_bar_idx] - slippage_cost if is_long else closes[exit_bar_idx] + slippage_cost

            pnl_pts = (exit_p - executed_entry) if is_long else (executed_entry - exit_p)
            pnl_usd = (pnl_pts * pt_val * contracts) - comm_total
            pnl_pct = (pnl_usd / 50000.0) * 100.0

            trade_log.append({
                "entry_time": times[start_idx],
                "exit_time": times[exit_bar_idx],
                "direction": sig_directions[i],
                "pnl_usd": pnl_usd,
                "pnl_pct": pnl_pct,
                "is_win": pnl_usd > 0,
            })

        df_trades = pd.DataFrame(trade_log)
        print(f"📊 10-Year Trade Sample: {len(df_trades):,d} Trades | Win Rate: {df_trades['is_win'].mean() * 100.0:.2f}% | Total PnL: ${df_trades['pnl_usd'].sum():,.2f}")

        sim = PropFirmSimulator(account_size=50000.0)

        for profile_key in ["topstep_50k", "apex_50k", "ftmo_50k"]:
            profile = FIRM_PROFILES[profile_key]
            mc = sim.run_monte_carlo(df_trades, profile, n_simulations=2000)

            days_str = f"{mc.median_days_to_pass:.0f} trading days" if mc.median_days_to_pass is not None else "N/A (Timeout)"
            avg_days_str = f"{mc.avg_days_to_pass:.1f} days" if mc.avg_days_to_pass is not None else "N/A"

            print(f"\n🏢 Firm: {profile.name:<14} | Target: ${profile.profit_target:,.0f} | Trailing DD: ${profile.max_trailing_drawdown:,.0f} | DLL: ${profile.daily_loss_limit:,.0f}")
            print(f"   🎯 Pass Rate (MC)     : {mc.pass_rate_pct:.1f}% (Grade: {mc.grade})")
            print(f"   💥 Blow Rate (MC)     : {mc.blow_rate_pct:.1f}%")
            print(f"   ⏱️ Median Days to Pass: {days_str} (Avg: {avg_days_str})")
            print(f"   📉 Avg Max Drawdown   : ${mc.avg_max_drawdown:,.2f}")


if __name__ == "__main__":
    run_prop_firm_stress_test("NQ1")
