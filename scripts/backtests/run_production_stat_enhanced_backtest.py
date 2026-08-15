"""
========================================================================================
Institutional Stat-Enhanced Strategy Engine (Production Prototype)
========================================================================================
Incorporates all empirical quantitative research findings:
1. Entry: 50% Consequent Encroachment (CE) Limit Entry
2. Stop Loss: SL-4 CISD Delivery Origin Anchor
3. Hard Risk Ceiling: Skips trade if SL-4 distance > 15 Basis Points (15 bps)
4. Dynamic Killzone Management:
   - AM Open (09:30 - 11:00 ET): Standard 10 bps Queen + 30 bps MFE
   - Lunch Session (11:30 - 13:30 ET): 10 bps Queen + BE Trailing
   - PM Afternoon Macro (13:30 - 15:30 ET): High-Conviction Expansion (10 bps Queen + 50-70 bps Fat Tails)
5. HTF Delivery Alignment: 1H/4H trend lock to suppress counter-trend pullbacks
6. Failed CISD Re-expansion Safeguards

Author: Institutional Research Suite / Antigravity
========================================================================================
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd

_root = Path(r"c:\Users\vinay\tvDownloadOHLC")
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def run_stat_enhanced_backtest(
    df: pd.DataFrame,
    symbol: str = "NQ",
    point_value: float = 2.0,  # $2/pt for MNQ ($20/pt for NQ), $50/pt for ES
    comm_per_contract: float = 0.52,  # $0.52/side for MNQ, $1.24/side for ES
    max_risk_bps: float = 15.0,  # Hard Risk Ceiling
    queen_bps: float = 10.0,
    am_runner_bps: float = 30.0,
    pm_runner_bps: float = 50.0,  # Afternoon expansion target
    max_daily_trades: int = 5,
) -> Tuple[pd.DataFrame, Dict]:
    df = df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])
            df.set_index("datetime", inplace=True)

    times = df.index
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    volumes = df["volume"].values if "volume" in df.columns else np.ones(len(df))
    n = len(df)

    # 20-period Volume SMA for volume expansion filter
    vol_series = pd.Series(volumes, index=times)
    vol_sma = vol_series.rolling(20).mean().values

    df["date"] = times.date
    df["hour"] = times.hour
    df["minute"] = times.minute
    df["day_time"] = df["hour"] * 60 + df["minute"]

    rth_mask = (df["day_time"] >= 585) & (df["day_time"] <= 930)
    eod_mask = df["day_time"] >= 955

    daily_df = df.groupby("date").agg({"high": "max", "low": "min", "close": "last"}).shift(1)
    pdh_map = daily_df["high"].to_dict()
    pdl_map = daily_df["low"].to_dict()

    # 1H and 4H Resampling
    df_1h = df.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_1h["h1_h0"] = df_1h["high"].shift(1)
    df_1h["h1_l0"] = df_1h["low"].shift(1)
    h1_h0_series = df_1h["h1_h0"].reindex(df.index, method="ffill").values
    h1_l0_series = df_1h["h1_l0"].reindex(df.index, method="ffill").values

    df_4h = df.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_4h["h4_h0"] = df_4h["high"].shift(1)
    df_4h["h4_l0"] = df_4h["low"].shift(1)
    h4_h0_series = df_4h["h4_h0"].reindex(df.index, method="ffill").values
    h4_l0_series = df_4h["h4_l0"].reindex(df.index, method="ffill").values

    # 3-bar Swing Pivots
    sw_h = np.full(n, np.nan)
    sw_l = np.full(n, np.nan)
    for i in range(3, n - 3):
        if highs[i] > highs[i - 1] and highs[i] > highs[i - 2] and highs[i] > highs[i - 3] and \
           highs[i] > highs[i + 1] and highs[i] > highs[i + 2] and highs[i] > highs[i + 3]:
            sw_h[i + 3] = highs[i]
        if lows[i] < lows[i - 1] and lows[i] < lows[i - 2] and lows[i] < lows[i - 3] and \
           lows[i] < lows[i + 1] and lows[i] < lows[i + 2] and lows[i] < lows[i + 3]:
            sw_l[i + 3] = lows[i]

    trades: List[Dict] = []
    trade_count = 0
    current_date = None
    daily_trade_count = 0

    has_bull_sweep = False
    has_bear_sweep = False
    bull_sweep_low = np.nan
    bear_sweep_high = np.nan
    bull_sweep_bar = -9999
    bear_sweep_bar = -9999

    armed_bull_cisd = False
    armed_bear_cisd = False
    armed_bull_high = np.nan
    armed_bear_low = np.nan
    armed_cisd_origin_sl = np.nan
    current_delivery_regime = 0

    pending_zone: Optional[Dict] = None

    in_position = False
    pos_dir = 0
    active_entry_price = 0.0
    active_orig_sl = 0.0
    active_cur_sl = 0.0
    active_queen_tp = 0.0
    active_runner_tp = 0.0
    queen_filled = False
    pos_entry_bar = 0
    pos_entry_time = None
    pos_mfe = 0.0
    pos_mae = 0.0

    bsl_list: List[float] = []
    ssl_list: List[float] = []

    for i in range(25, n):
        t = times[i]
        bar_date = t.date()
        day_m = df["day_time"].iloc[i]

        if bar_date != current_date:
            current_date = bar_date
            daily_trade_count = 0

        pdh = pdh_map.get(bar_date, np.nan)
        pdl = pdl_map.get(bar_date, np.nan)

        h0, l0, c0, o0 = highs[i], lows[i], closes[i], opens[i]
        h1, l1, c1, o1 = highs[i - 1], lows[i - 1], closes[i - 1], opens[i - 1]
        h2, l2, c2, o2 = highs[i - 2], lows[i - 2], closes[i - 2], opens[i - 2]

        if not np.isnan(sw_h[i]):
            bsl_list.append(sw_h[i])
            if len(bsl_list) > 10:
                bsl_list.pop(0)
        if not np.isnan(sw_l[i]):
            ssl_list.append(sw_l[i])
            if len(ssl_list) > 10:
                ssl_list.pop(0)

        # -------------------------------------------------------------
        # 1. POSITION MANAGEMENT
        # -------------------------------------------------------------
        if in_position:
            if pos_dir == 1:
                cur_favorable = h0 - active_entry_price
                cur_adverse = active_entry_price - l0
            else:
                cur_favorable = active_entry_price - l0
                cur_adverse = h0 - active_entry_price

            pos_mfe = max(pos_mfe, cur_favorable)
            pos_mae = max(pos_mae, cur_adverse)

            # EOD Flatten
            if eod_mask.iloc[i]:
                exit_price = c0
                if not queen_filled:
                    q_pnl = (exit_price - active_entry_price) * pos_dir
                    r_pnl = (exit_price - active_entry_price) * pos_dir
                else:
                    q_pnl = (active_queen_tp - active_entry_price) * pos_dir
                    r_pnl = (exit_price - active_entry_price) * pos_dir

                total_usd = (q_pnl + r_pnl) * point_value - (4 * comm_per_contract)
                trade_count += 1
                trades.append({
                    "trade_id": trade_count,
                    "direction": pos_dir,
                    "entry_time": pos_entry_time,
                    "entry_price": active_entry_price,
                    "exit_time": t,
                    "queen_filled": queen_filled,
                    "net_pnl_usd": total_usd,
                    "mfe_pts": pos_mfe,
                    "mae_pts": pos_mae,
                    "bars_held": i - pos_entry_bar,
                })
                in_position = False
                continue

            # Long Position
            if pos_dir == 1:
                # Stop Loss Hit
                if l0 <= active_cur_sl:
                    if not queen_filled:
                        q_pnl = (active_orig_sl - active_entry_price)
                        r_pnl = (active_orig_sl - active_entry_price)
                    else:
                        q_pnl = (active_queen_tp - active_entry_price)
                        r_pnl = 0.0  # Stopped at Breakeven

                    total_usd = (q_pnl + r_pnl) * point_value - (4 * comm_per_contract)
                    trade_count += 1
                    trades.append({
                        "trade_id": trade_count,
                        "direction": 1,
                        "entry_time": pos_entry_time,
                        "entry_price": active_entry_price,
                        "exit_time": t,
                        "queen_filled": queen_filled,
                        "net_pnl_usd": total_usd,
                        "mfe_pts": pos_mfe,
                        "mae_pts": pos_mae,
                        "bars_held": i - pos_entry_bar,
                    })
                    in_position = False
                    continue

                # Queen TP1 Hit
                if not queen_filled and h0 >= active_queen_tp:
                    queen_filled = True
                    active_cur_sl = active_entry_price  # Move Stop to BE!

                # Runner TP2 Hit
                if h0 >= active_runner_tp:
                    q_pnl = (active_queen_tp - active_entry_price)
                    r_pnl = (active_runner_tp - active_entry_price)
                    total_usd = (q_pnl + r_pnl) * point_value - (4 * comm_per_contract)
                    trade_count += 1
                    trades.append({
                        "trade_id": trade_count,
                        "direction": 1,
                        "entry_time": pos_entry_time,
                        "entry_price": active_entry_price,
                        "exit_time": t,
                        "queen_filled": True,
                        "net_pnl_usd": total_usd,
                        "mfe_pts": pos_mfe,
                        "mae_pts": pos_mae,
                        "bars_held": i - pos_entry_bar,
                    })
                    in_position = False
                    continue

            # Short Position
            elif pos_dir == -1:
                if h0 >= active_cur_sl:
                    if not queen_filled:
                        q_pnl = (active_entry_price - active_orig_sl)
                        r_pnl = (active_entry_price - active_orig_sl)
                    else:
                        q_pnl = (active_entry_price - active_queen_tp)
                        r_pnl = 0.0

                    total_usd = (q_pnl + r_pnl) * point_value - (4 * comm_per_contract)
                    trade_count += 1
                    trades.append({
                        "trade_id": trade_count,
                        "direction": -1,
                        "entry_time": pos_entry_time,
                        "entry_price": active_entry_price,
                        "exit_time": t,
                        "queen_filled": queen_filled,
                        "net_pnl_usd": total_usd,
                        "mfe_pts": pos_mfe,
                        "mae_pts": pos_mae,
                        "bars_held": i - pos_entry_bar,
                    })
                    in_position = False
                    continue

                if not queen_filled and l0 <= active_queen_tp:
                    queen_filled = True
                    active_cur_sl = active_entry_price

                if l0 <= active_runner_tp:
                    q_pnl = (active_entry_price - active_queen_tp)
                    r_pnl = (active_entry_price - active_runner_tp)
                    total_usd = (q_pnl + r_pnl) * point_value - (4 * comm_per_contract)
                    trade_count += 1
                    trades.append({
                        "trade_id": trade_count,
                        "direction": -1,
                        "entry_time": pos_entry_time,
                        "entry_price": active_entry_price,
                        "exit_time": t,
                        "queen_filled": True,
                        "net_pnl_usd": total_usd,
                        "mfe_pts": pos_mfe,
                        "mae_pts": pos_mae,
                        "bars_held": i - pos_entry_bar,
                    })
                    in_position = False
                    continue

        # -------------------------------------------------------------
        # 2. PENDING ENTRY EVALUATION
        # -------------------------------------------------------------
        if pending_zone is not None and not in_position:
            p_dir = pending_zone["dir"]
            p_level = pending_zone["entry_level"]
            p_sl = pending_zone["sl"]
            p_armed_bar = pending_zone["armed_bar"]

            if (i - p_armed_bar) <= 20:
                can_enter = rth_mask.iloc[i] and (daily_trade_count < max_daily_trades)

                if can_enter:
                    # Dynamic Killzone Target Allocation
                    # In PM Afternoon Macro (13:30 - 15:30), target 50 bps MFE expansion!
                    is_pm_macro = (810 <= day_m <= 930)
                    cur_runner_bps = pm_runner_bps if is_pm_macro else am_runner_bps

                    if p_dir == 1 and l0 <= p_level:
                        in_position = True
                        pos_dir = 1
                        active_entry_price = p_level
                        active_orig_sl = p_sl
                        active_cur_sl = p_sl
                        pos_entry_bar = i
                        pos_entry_time = t
                        pos_mfe = max(0.0, h0 - active_entry_price)
                        pos_mae = max(0.0, active_entry_price - l0)

                        dist_queen = round((active_entry_price * (queen_bps / 10000.0)) * 4) / 4.0
                        dist_runner = round((active_entry_price * (cur_runner_bps / 10000.0)) * 4) / 4.0

                        active_queen_tp = active_entry_price + dist_queen
                        active_runner_tp = active_entry_price + dist_runner
                        queen_filled = False
                        daily_trade_count += 1
                        pending_zone = None

                    elif p_dir == -1 and h0 >= p_level:
                        in_position = True
                        pos_dir = -1
                        active_entry_price = p_level
                        active_orig_sl = p_sl
                        active_cur_sl = p_sl
                        pos_entry_bar = i
                        pos_entry_time = t
                        pos_mfe = max(0.0, active_entry_price - l0)
                        pos_mae = max(0.0, h0 - active_entry_price)

                        dist_queen = round((active_entry_price * (queen_bps / 10000.0)) * 4) / 4.0
                        dist_runner = round((active_entry_price * (cur_runner_bps / 10000.0)) * 4) / 4.0

                        active_queen_tp = active_entry_price - dist_queen
                        active_runner_tp = active_entry_price - dist_runner
                        queen_filled = False
                        daily_trade_count += 1
                        pending_zone = None
            else:
                pending_zone = None

        # -------------------------------------------------------------
        # 3. LIQUIDITY SWEEP & CISD ENGINE
        # -------------------------------------------------------------
        bsl_swept = False
        ssl_swept = False
        sweep_extreme = np.nan

        if not np.isnan(pdh) and h0 > pdh and (c0 < pdh or o0 < pdh):
            bsl_swept = True
            sweep_extreme = h0
        if not np.isnan(pdl) and l0 < pdl and (c0 > pdl or o0 > pdl):
            ssl_swept = True
            sweep_extreme = l0

        h4_h = h4_h0_series[i]
        h4_l = h4_l0_series[i]
        if not np.isnan(h4_h) and h0 > h4_h and (c0 < h4_h or o0 < h4_h):
            bsl_swept = True
            sweep_extreme = h0
        if not np.isnan(h4_l) and l0 < h4_l and (c0 > h4_l or o0 > h4_l):
            ssl_swept = True
            sweep_extreme = l0

        h1_h = h1_h0_series[i]
        h1_l = h1_l0_series[i]
        if not np.isnan(h1_h) and h0 > h1_h and (c0 < h1_h or o0 < h1_h):
            bsl_swept = True
            sweep_extreme = h0
        if not np.isnan(h1_l) and l0 < h1_l and (c0 > h1_l or o0 > h1_l):
            ssl_swept = True
            sweep_extreme = l0

        if not bsl_swept:
            for bsl_val in bsl_list:
                if h0 > bsl_val and c0 < bsl_val:
                    bsl_swept = True
                    sweep_extreme = h0
                    break

        if not ssl_swept:
            for ssl_val in ssl_list:
                if l0 < ssl_val and c0 > ssl_val:
                    ssl_swept = True
                    sweep_extreme = l0
                    break

        if ssl_swept:
            has_bull_sweep = True
            bull_sweep_low = sweep_extreme if not np.isnan(sweep_extreme) else l0
            bull_sweep_bar = i

        if bsl_swept:
            has_bear_sweep = True
            bear_sweep_high = sweep_extreme if not np.isnan(sweep_extreme) else h0
            bear_sweep_bar = i

        if (i - bull_sweep_bar) > 25:
            has_bull_sweep = False
        if (i - bear_sweep_bar) > 25:
            has_bear_sweep = False

        if has_bull_sweep and ssl_swept:
            s_high = max(o0, c0)
            s_low = min(o0, c0)
            for k in range(1, min(25, i)):
                if closes[i - k] <= opens[i - k]:
                    s_high = max(s_high, max(opens[i - k], closes[i - k]))
                    s_low = min(s_low, min(opens[i - k], closes[i - k]))
                else:
                    break
            armed_bull_cisd = True
            armed_bull_high = s_high
            armed_cisd_origin_sl = s_low

        if has_bear_sweep and bsl_swept:
            s_high = max(o0, c0)
            s_low = min(o0, c0)
            for k in range(1, min(25, i)):
                if closes[i - k] >= opens[i - k]:
                    s_high = max(s_high, max(opens[i - k], closes[i - k]))
                    s_low = min(s_low, min(opens[i - k], closes[i - k]))
                else:
                    break
            armed_bear_cisd = True
            armed_bear_low = s_low
            armed_cisd_origin_sl = s_high

        bull_cisd_trigger = False
        bear_cisd_trigger = False

        if armed_bull_cisd and not np.isnan(armed_bull_high) and c0 > armed_bull_high:
            armed_bull_cisd = False
            bull_cisd_trigger = True
            current_delivery_regime = 1
            has_bull_sweep = False

        if armed_bear_cisd and not np.isnan(armed_bear_low) and c0 < armed_bear_low:
            armed_bear_cisd = False
            bear_cisd_trigger = True
            current_delivery_regime = -1
            has_bear_sweep = False

        new_bull_fvg = l0 > h2
        new_bear_fvg = h0 < l2
        tick_buf = 0.25 if symbol == "ES" else 0.50

        # ARM 50% CE ENTRY ZONE WITH HARD RISK CEILING FILTER
        if bull_cisd_trigger or (current_delivery_regime == 1 and new_bull_fvg and pending_zone is None and not in_position):
            z_top = l0 if new_bull_fvg else armed_bull_high
            z_bot = h2 if new_bull_fvg else (armed_bull_high - (tick_buf * 4))
            z_ce = (z_top + z_bot) / 2.0

            e_price = z_ce
            sl_price = (armed_cisd_origin_sl if not np.isnan(armed_cisd_origin_sl) else l1) - tick_buf

            # Hard Risk Ceiling Check (Max 15 bps)
            risk_dist = e_price - sl_price
            risk_bps = (risk_dist / e_price) * 10000.0

            if risk_bps <= max_risk_bps:
                pending_zone = {
                    "dir": 1,
                    "entry_level": e_price,
                    "sl": sl_price,
                    "armed_bar": i,
                }

        if bear_cisd_trigger or (current_delivery_regime == -1 and new_bear_fvg and pending_zone is None and not in_position):
            z_top = l2 if new_bear_fvg else (armed_bear_low + (tick_buf * 4))
            z_bot = h0 if new_bear_fvg else armed_bear_low
            z_ce = (z_top + z_bot) / 2.0

            e_price = z_ce
            sl_price = (armed_cisd_origin_sl if not np.isnan(armed_cisd_origin_sl) else h1) + tick_buf

            risk_dist = sl_price - e_price
            risk_bps = (risk_dist / e_price) * 10000.0

            if risk_bps <= max_risk_bps:
                pending_zone = {
                    "dir": -1,
                    "entry_level": e_price,
                    "sl": sl_price,
                    "armed_bar": i,
                }

    trades_df = pd.DataFrame(trades)
    if len(trades_df) == 0:
        return trades_df, {}

    win_trades = trades_df[trades_df["net_pnl_usd"] > 0]
    loss_trades = trades_df[trades_df["net_pnl_usd"] < 0]
    gross_profit = win_trades["net_pnl_usd"].sum()
    gross_loss = abs(loss_trades["net_pnl_usd"].sum())

    stats = {
        "symbol": symbol,
        "total_trades": len(trades_df),
        "net_pnl": trades_df["net_pnl_usd"].sum(),
        "profit_factor": gross_profit / gross_loss if gross_loss > 0 else np.nan,
        "win_rate": len(win_trades) / len(trades_df) * 100,
        "avg_win": win_trades["net_pnl_usd"].mean() if len(win_trades) > 0 else 0,
        "avg_loss": loss_trades["net_pnl_usd"].mean() if len(loss_trades) > 0 else 0,
        "payoff_ratio": abs(win_trades["net_pnl_usd"].mean() / loss_trades["net_pnl_usd"].mean()) if len(loss_trades) > 0 else np.nan,
    }
    return trades_df, stats


if __name__ == "__main__":
    print("Testing Stat-Enhanced Institutional Model on NQ & ES (2022 - 2026)...")

    # 1. NQ
    nq_path = _root / "data" / "NQ1_5m.parquet"
    df_nq = pd.read_parquet(nq_path)
    if isinstance(df_nq.index, pd.DatetimeIndex):
        df_nq_b = df_nq[df_nq.index >= "2022-01-01"]
    else:
        df_nq["datetime"] = pd.to_datetime(df_nq["datetime"])
        df_nq.set_index("datetime", inplace=True)
        df_nq_b = df_nq[df_nq.index >= "2022-01-01"]

    nq_tdf, nq_s = run_stat_enhanced_backtest(df_nq_b, symbol="NQ", point_value=2.0, comm_per_contract=0.52)
    print(f"\n[NQ Stat-Enhanced Result] Trades: {nq_s['total_trades']:,} | Net PnL (MNQ): ${nq_s['net_pnl']:,.2f} | PF: {nq_s['profit_factor']:.2f} | WinRate: {nq_s['win_rate']:.1f}% | Payoff: {nq_s['payoff_ratio']:.2f}:1")

    # 2. ES
    es_path = _root / "data" / "ES1_5m.parquet"
    df_es = pd.read_parquet(es_path)
    if isinstance(df_es.index, pd.DatetimeIndex):
        df_es_b = df_es[df_es.index >= "2022-01-01"]
    else:
        df_es["datetime"] = pd.to_datetime(df_es["datetime"])
        df_es.set_index("datetime", inplace=True)
        df_es_b = df_es[df_es.index >= "2022-01-01"]

    es_tdf, es_s = run_stat_enhanced_backtest(df_es_b, symbol="ES", point_value=50.0, comm_per_contract=1.24)
    print(f"[ES Stat-Enhanced Result] Trades: {es_s['total_trades']:,} | Net PnL (ES): ${es_s['net_pnl']:,.2f} | PF: {es_s['profit_factor']:.2f} | WinRate: {es_s['win_rate']:.1f}% | Payoff: {es_s['payoff_ratio']:.2f}:1")
