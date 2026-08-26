"""
========================================================================================
Institutional ICT Filter Ablation & Performance Comparison (334,414 Bars / 2022-2026)
========================================================================================
Compares:
1. Baseline: 09:45 Turnaround + FVG Limit Entry + 5.0 bps Stop
2. Config A: Baseline + 4H HTF Orderflow Filter (Pro-Trend Only)
3. Config B: Baseline + NY Lunch Blackout (Skip 12:00-13:30 ET)
4. Config C: Baseline + External Liquidity Sweep Gate (PDH/PDL, London H/L, Asia H/L)
5. Config D: Full Institutional Stack (4H Bias + Lunch Blackout + External Sweep)
========================================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def run_ict_ablation(
    df: pd.DataFrame,
    use_htf_filter: bool = False,
    filter_lunch: bool = False,
    require_external_sweep: bool = False,
    queen_bps: float = 10.0,
    runner_bps: float = 30.0,
    stop_bps: float = 5.0,
) -> pd.DataFrame:
    times = df.index
    opens = df["open"].to_numpy(dtype=np.float64)
    highs = df["high"].to_numpy(dtype=np.float64)
    lows = df["low"].to_numpy(dtype=np.float64)
    closes = df["close"].to_numpy(dtype=np.float64)
    n = len(df)

    # 1. Daily Levels (PDH / PDL)
    df_daily = df.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_daily["pdh"] = df_daily["high"].shift(1)
    df_daily["pdl"] = df_daily["low"].shift(1)
    daily_reindexed = df_daily.reindex(df.index, method="ffill")
    pdh_arr = daily_reindexed["pdh"].to_numpy()
    pdl_arr = daily_reindexed["pdl"].to_numpy()

    # 2. 4H Trend / Delivery (HTF Bias)
    df_4h = df.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_4h["ema20"] = df_4h["close"].ewm(span=20).mean()
    df_4h_reindexed = df_4h.reindex(df.index, method="ffill")
    htf_bias_arr = np.where(df_4h_reindexed["close"] > df_4h_reindexed["ema20"], 1, -1)

    time_strs = times.strftime("%H%M")
    hours = times.hour
    mins = times.minute

    # Tracking Sessions
    cur_asia_h, cur_asia_l = np.nan, np.nan
    cur_lon_h, cur_lon_l = np.nan, np.nan
    last_asia_h, last_asia_l = np.nan, np.nan
    last_lon_h, last_lon_l = np.nan, np.nan

    vibes = 0
    bagholder_entry = np.nan
    pain_threshold = np.nan

    def consult_crystal_ball(bias: int, idx: int):
        max_lb = min(15, idx)
        ext_o = opens[idx - 1]
        for k in range(1, max_lb + 1):
            is_opp = (closes[idx - k] < opens[idx - k]) if bias == 1 else (closes[idx - k] > opens[idx - k])
            if is_opp:
                ext_o = opens[idx - k]
                break
        return ext_o

    trades = []
    in_pos = False
    pos_dir = 0
    pos_entry_price = 0.0
    pos_entry_time = None
    active_sl = 0.0
    active_tp1 = 0.0
    active_tp2 = 0.0
    queen_filled = False
    pos_mfe = 0.0
    pos_mae = 0.0

    current_day = None
    daily_trades = 0
    pending_order = None

    for i in range(25, n):
        t = times[i]
        hhmm = time_strs[i]
        bar_date = t.date()
        h0, l0, c0, o0 = highs[i], lows[i], closes[i], opens[i]
        h2, l2 = highs[i - 2], lows[i - 2]
        hh = hours[i]
        mm = mins[i]

        if bar_date != current_day:
            current_day = bar_date
            daily_trades = 0
            pending_order = None

        # Track Asian Session (18:00 - 02:00)
        if hh == 18 and mm == 0:
            cur_asia_h, cur_asia_l = h0, l0
        elif (hh >= 18 or hh < 2):
            cur_asia_h = max(cur_asia_h, h0) if not np.isnan(cur_asia_h) else h0
            cur_asia_l = min(cur_asia_l, l0) if not np.isnan(cur_asia_l) else l0
        elif hh == 2 and mm == 0:
            last_asia_h, last_asia_l = cur_asia_h, cur_asia_l
            cur_lon_h, cur_lon_l = h0, l0
        elif (2 <= hh < 8):
            cur_lon_h = max(cur_lon_h, h0) if not np.isnan(cur_lon_h) else h0
            cur_lon_l = min(cur_lon_l, l0) if not np.isnan(cur_lon_l) else l0
        elif hh == 8 and mm == 0:
            last_lon_h, last_lon_l = cur_lon_h, cur_lon_l

        # -------------------------------------------------------------
        # 1. POSITION MANAGEMENT
        # -------------------------------------------------------------
        if in_pos:
            if pos_dir == 1:
                pos_mfe = max(pos_mfe, (h0 - pos_entry_price) / pos_entry_price * 10000.0)
                pos_mae = max(pos_mae, (pos_entry_price - l0) / pos_entry_price * 10000.0)

                if hhmm >= "1555":
                    q_pnl = (active_tp1 - pos_entry_price) if queen_filled else (c0 - pos_entry_price)
                    r_pnl = (c0 - pos_entry_price)
                    pnl_bps = ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Long",
                        "entry_price": pos_entry_price, "exit_price": c0, "pnl_bps": pnl_bps,
                        "is_win": pnl_bps > 0, "queen_hit": queen_filled, "runner_hit": False,
                        "mfe_bps": pos_mfe, "mae_bps": pos_mae,
                    })
                    in_pos = False

                elif l0 <= active_sl:
                    q_pnl = (active_tp1 - pos_entry_price) if queen_filled else (active_sl - pos_entry_price)
                    r_pnl = (active_sl - pos_entry_price)
                    pnl_bps = ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Long",
                        "entry_price": pos_entry_price, "exit_price": active_sl, "pnl_bps": pnl_bps,
                        "is_win": pnl_bps > 0, "queen_hit": queen_filled, "runner_hit": False,
                        "mfe_bps": pos_mfe, "mae_bps": pos_mae,
                    })
                    in_pos = False

                elif not queen_filled and h0 >= active_tp1:
                    queen_filled = True
                    active_sl = pos_entry_price  # BE Lock

                elif h0 >= active_tp2:
                    q_pnl = (active_tp1 - pos_entry_price)
                    r_pnl = (active_tp2 - pos_entry_price)
                    pnl_bps = ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Long",
                        "entry_price": pos_entry_price, "exit_price": active_tp2, "pnl_bps": pnl_bps,
                        "is_win": True, "queen_hit": True, "runner_hit": True,
                        "mfe_bps": pos_mfe, "mae_bps": pos_mae,
                    })
                    in_pos = False

            elif pos_dir == -1:
                pos_mfe = max(pos_mfe, (pos_entry_price - l0) / pos_entry_price * 10000.0)
                pos_mae = max(pos_mae, (h0 - pos_entry_price) / pos_entry_price * 10000.0)

                if hhmm >= "1555":
                    q_pnl = (pos_entry_price - active_tp1) if queen_filled else (pos_entry_price - c0)
                    r_pnl = (pos_entry_price - c0)
                    pnl_bps = ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Short",
                        "entry_price": pos_entry_price, "exit_price": c0, "pnl_bps": pnl_bps,
                        "is_win": pnl_bps > 0, "queen_hit": queen_filled, "runner_hit": False,
                        "mfe_bps": pos_mfe, "mae_bps": pos_mae,
                    })
                    in_pos = False

                elif h0 >= active_sl:
                    q_pnl = (pos_entry_price - active_tp1) if queen_filled else (pos_entry_price - active_sl)
                    r_pnl = (pos_entry_price - active_sl)
                    pnl_bps = ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Short",
                        "entry_price": pos_entry_price, "exit_price": active_sl, "pnl_bps": pnl_bps,
                        "is_win": pnl_bps > 0, "queen_hit": queen_filled, "runner_hit": False,
                        "mfe_bps": pos_mfe, "mae_bps": pos_mae,
                    })
                    in_pos = False

                elif not queen_filled and l0 <= active_tp1:
                    queen_filled = True
                    active_sl = pos_entry_price

                elif l0 <= active_tp2:
                    q_pnl = (pos_entry_price - active_tp1)
                    r_pnl = (pos_entry_price - active_tp2)
                    pnl_bps = ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Short",
                        "entry_price": pos_entry_price, "exit_price": active_tp2, "pnl_bps": pnl_bps,
                        "is_win": True, "queen_hit": True, "runner_hit": True,
                        "mfe_bps": pos_mfe, "mae_bps": pos_mae,
                    })
                    in_pos = False

        # -------------------------------------------------------------
        # 2. PENDING FVG LIMIT ORDER EVALUATION
        # -------------------------------------------------------------
        if pending_order is not None and not in_pos:
            p_dir = pending_order["dir"]
            p_limit = pending_order["limit"]
            p_sl = pending_order["sl"]
            p_bar = pending_order["bar"]

            if (i - p_bar) <= 6:
                # Time window checks
                in_time = ("0945" <= hhmm <= "1530")
                if filter_lunch and ("1200" <= hhmm <= "1330"):
                    in_time = False

                if in_time and daily_trades < 5:
                    if p_dir == 1 and l0 <= p_limit:
                        in_pos = True
                        pos_dir = 1
                        pos_entry_time = t
                        pos_entry_price = p_limit
                        active_sl = p_sl
                        active_tp1 = p_limit + (p_limit * (queen_bps / 10000.0))
                        active_tp2 = p_limit + (p_limit * (runner_bps / 10000.0))
                        queen_filled = False
                        pos_mfe = max(0.0, (h0 - pos_entry_price) / pos_entry_price * 10000.0)
                        pos_mae = max(0.0, (pos_entry_price - l0) / pos_entry_price * 10000.0)
                        daily_trades += 1
                        pending_order = None

                    elif p_dir == -1 and h0 >= p_limit:
                        in_pos = True
                        pos_dir = -1
                        pos_entry_time = t
                        pos_entry_price = p_limit
                        active_sl = p_sl
                        active_tp1 = p_limit - (p_limit * (queen_bps / 10000.0))
                        active_tp2 = p_limit - (p_limit * (runner_bps / 10000.0))
                        queen_filled = False
                        pos_mfe = max(0.0, (pos_entry_price - l0) / pos_entry_price * 10000.0)
                        pos_mae = max(0.0, (h0 - pos_entry_price) / pos_entry_price * 10000.0)
                        daily_trades += 1
                        pending_order = None
            else:
                pending_order = None

        # -------------------------------------------------------------
        # 3. CISD SIGNAL EVALUATION
        # -------------------------------------------------------------
        candle_pers = 1 if c0 > o0 else (-1 if c0 < o0 else 0)
        if vibes == 0:
            vibes = candle_pers if candle_pers != 0 else 1
            bagholder_entry = consult_crystal_ball(vibes, i)
            pain_threshold = h0 if vibes == 1 else l0

        if vibes == 1 and h0 > pain_threshold:
            pain_threshold = h0
            bagholder_entry = consult_crystal_ball(1, i)
        elif vibes == -1 and l0 < pain_threshold:
            pain_threshold = l0
            bagholder_entry = consult_crystal_ball(-1, i)

        active_lvl = bagholder_entry

        # Detect External Liquidity Sweeps in preceding 5 bars
        recent_low = min(lows[i-5:i+1])
        recent_high = max(highs[i-5:i+1])
        has_ext_sweep_bull = (
            (not np.isnan(pdl_arr[i]) and recent_low < pdl_arr[i]) or
            (not np.isnan(last_lon_l) and recent_low < last_lon_l) or
            (not np.isnan(last_asia_l) and recent_low < last_asia_l)
        )
        has_ext_sweep_bear = (
            (not np.isnan(pdh_arr[i]) and recent_high > pdh_arr[i]) or
            (not np.isnan(last_lon_h) and recent_high > last_lon_h) or
            (not np.isnan(last_asia_h) and recent_high > last_asia_h)
        )

        # Bullish CISD
        if vibes == -1 and c0 > active_lvl:
            vibes = 1
            pain_threshold = h0
            bagholder_entry = consult_crystal_ball(1, i)

            allow_signal = True
            if use_htf_filter and htf_bias_arr[i] != 1:
                allow_signal = False
            if require_external_sweep and not has_ext_sweep_bull:
                allow_signal = False

            if allow_signal:
                fvg_top = h2 if l0 > h2 else active_lvl
                sl_price = fvg_top - (fvg_top * (stop_bps / 10000.0))
                pending_order = {"dir": 1, "limit": fvg_top, "sl": sl_price, "bar": i}

        # Bearish CISD
        elif vibes == 1 and c0 < active_lvl:
            vibes = -1
            pain_threshold = l0
            bagholder_entry = consult_crystal_ball(-1, i)

            allow_signal = True
            if use_htf_filter and htf_bias_arr[i] != -1:
                allow_signal = False
            if require_external_sweep and not has_ext_sweep_bear:
                allow_signal = False

            if allow_signal:
                fvg_bot = l2 if h0 < l2 else active_lvl
                sl_price = fvg_bot + (fvg_bot * (stop_bps / 10000.0))
                pending_order = {"dir": -1, "limit": fvg_bot, "sl": sl_price, "bar": i}

    return pd.DataFrame(trades)


def main():
    print(f"\n{'='*110}", flush=True)
    print("INSTITUTIONAL ICT FILTER ABLATION & PERFORMANCE COMPARISON (334,414 BARS / 2022-2026)", flush=True)
    print("=" * 110, flush=True)

    data_path = _root / "data/NQ1_5m.parquet"
    df = pd.read_parquet(data_path)

    configs = [
        {
            "name": "1. Baseline (09:45 Turnaround + FVG Limit + 5bps SL)",
            "htf": False, "lunch": False, "sweep": False,
        },
        {
            "name": "2. Baseline + 4H HTF Orderflow Filter",
            "htf": True, "lunch": False, "sweep": False,
        },
        {
            "name": "3. Baseline + NY Lunch Blackout (12:00-13:30)",
            "htf": False, "lunch": True, "sweep": False,
        },
        {
            "name": "4. Baseline + External Sweep Gate (PDH/PDL/Lon/Asia)",
            "htf": False, "lunch": False, "sweep": True,
        },
        {
            "name": "5. Config A+B: 4H HTF Filter + Lunch Blackout",
            "htf": True, "lunch": True, "sweep": False,
        },
        {
            "name": "6. Full Institutional Stack: 4H + Lunch + Ext Sweep",
            "htf": True, "lunch": True, "sweep": True,
        },
    ]

    results = []
    for cfg in configs:
        trades = run_ict_ablation(
            df,
            use_htf_filter=cfg["htf"],
            filter_lunch=cfg["lunch"],
            require_external_sweep=cfg["sweep"],
        )
        if len(trades) == 0:
            continue

        wins = trades[trades["pnl_bps"] > 0]
        losses = trades[trades["pnl_bps"] < 0]
        gp = wins["pnl_bps"].sum()
        gl = abs(losses["pnl_bps"].sum())
        pf = gp / gl if gl > 0 else np.nan
        wr = len(wins) / len(trades) * 100.0
        queen_reach = trades["queen_hit"].mean() * 100.0
        runner_reach = trades["runner_hit"].mean() * 100.0
        net_bps = trades["pnl_bps"].sum()
        exp_bps = trades["pnl_bps"].mean()

        # Approximate equity on 1 NQ contract ($20/pt)
        # NQ average price ~18,000 => 1 bps = 1.8 pts = $36.00
        approx_net_usd = net_bps * 36.0

        results.append({
            "Configuration": cfg["name"],
            "Trades": len(trades),
            "Win Rate": f"{wr:.1f}%",
            "Profit Factor": f"{pf:.2f}",
            "Queen (+10bps) %": f"{queen_reach:.1f}%",
            "Runner (+30bps) %": f"{runner_reach:.1f}%",
            "Net Bps (Alpha)": f"{net_bps:+,.1f} bps",
            "Expectancy": f"{exp_bps:+,.2f} bps/tr",
            "Approx Net P&L ($)": f"${approx_net_usd:+,.0f}",
        })

    print(pd.DataFrame(results).to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
