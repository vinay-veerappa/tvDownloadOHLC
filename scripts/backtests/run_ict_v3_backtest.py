"""
ICT v3 Backtest — Built on the proven original (SL-4 + FVG Touch)
==================================================================
Starts from the validated baseline (WR 61.6%, PF 2.49) and layers in:
  1. Session range sweeps (Asia 18:00-02:00, London 02:00-08:00, NYAM 09:30-10:00)
  2. Risk-based position sizing (contracts = risk_usd / (sl_dist_pts * point_value))
  3. Spec-aligned params (15bps ceiling, 1.5x volume gate, 30bps runner)
  4. Optional 1m intrabar execution for fill fidelity
  5. Prop firm account sizing (50K, 25K presets)

The CISD logic, SL-4 stop, and FVG Touch entry are UNCHANGED from the original.
"""

from __future__ import annotations
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


@dataclass
class TradeRecord:
    trade_id: int
    direction: int
    entry_time: pd.Timestamp
    entry_bar: int
    entry_price: float
    entry_model: str
    stop_loss: float
    sl_model: str
    num_contracts: int
    risk_usd: float
    queen_tp: float
    runner_tp: float
    queen_exit_time: Optional[pd.Timestamp] = None
    queen_exit_price: Optional[float] = None
    queen_exit_reason: str = ""
    queen_pnl_pts: float = 0.0
    runner_exit_time: Optional[pd.Timestamp] = None
    runner_exit_price: Optional[float] = None
    runner_exit_reason: str = ""
    runner_pnl_pts: float = 0.0
    total_pnl_usd: float = 0.0
    bars_held: int = 0
    mfe_pts: float = 0.0
    mae_pts: float = 0.0
    sweep_source: str = ""


# Prop firm presets: (account_size, risk_pct, max_contracts)
PROP_FIRM_PRESETS = {
    "50K": {"account_size": 50000, "risk_pct": 1.0, "max_contracts": 10},   # $500 risk
    "25K": {"account_size": 25000, "risk_pct": 1.0, "max_contracts": 5},    # $250 risk
    "150K": {"account_size": 150000, "risk_pct": 0.5, "max_contracts": 20}, # $750 risk
    "MNQ_50K": {"account_size": 50000, "risk_pct": 0.5, "max_contracts": 20}, # $250 risk, micro
}


def compute_session_levels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes Asia (18:00-02:00 ET) and London (02:00-08:00 ET) session highs/lows.
    Uses RUNNING H/L — the session level is only available AFTER the session closes.
    This avoids lookahead bias: you cannot sweep a session level that is still forming.

    Asia H/L: computed bar-by-bar during 18:00-02:00, available from 02:00 onward.
    London H/L: computed bar-by-bar during 02:00-08:00, available from 08:00 onward.
    """
    times = df.index
    hhmm = times.strftime("%H%M")
    n = len(df)

    is_asia = (hhmm >= "1800") | (hhmm < "0200")
    is_london = (hhmm >= "0200") & (hhmm < "0800")

    asia_h = np.full(n, np.nan)
    asia_l = np.full(n, np.nan)
    lon_h = np.full(n, np.nan)
    lon_l = np.full(n, np.nan)

    cur_asia_h = np.nan
    cur_asia_l = np.nan
    cur_lon_h = np.nan
    cur_lon_l = np.nan
    in_asia = False
    in_lon = False
    asia_complete = False
    lon_complete = False

    for i in range(n):
        h = df["high"].iloc[i]
        l = df["low"].iloc[i]
        bar_is_asia = bool(is_asia[i])
        bar_is_lon = bool(is_london[i])

        # Asia session tracking
        if bar_is_asia and not in_asia:
            # Asia session just started
            cur_asia_h = h
            cur_asia_l = l
            in_asia = True
            asia_complete = False
        elif bar_is_asia and in_asia:
            cur_asia_h = max(cur_asia_h, h)
            cur_asia_l = min(cur_asia_l, l)
        elif not bar_is_asia and in_asia:
            # Asia session just ended — freeze the levels
            in_asia = False
            asia_complete = True

        # London session tracking
        if bar_is_lon and not in_lon:
            cur_lon_h = h
            cur_lon_l = l
            in_lon = True
            lon_complete = False
        elif bar_is_lon and in_lon:
            cur_lon_h = max(cur_lon_h, h)
            cur_lon_l = min(cur_lon_l, l)
        elif not bar_is_lon and in_lon:
            in_lon = False
            lon_complete = True

        # Only set the levels AFTER the session completes
        if asia_complete and not in_asia:
            asia_h[i] = cur_asia_h
            asia_l[i] = cur_asia_l
        if lon_complete and not in_lon:
            lon_h[i] = cur_lon_h
            lon_l[i] = cur_lon_l

    df_out = df.copy()
    df_out["asia_h"] = asia_h
    df_out["asia_l"] = asia_l
    df_out["lon_h"] = lon_h
    df_out["lon_l"] = lon_l

    # Forward-fill the completed session levels so they persist through the trading day
    df_out["asia_h"] = df_out["asia_h"].ffill()
    df_out["asia_l"] = df_out["asia_l"].ffill()
    df_out["lon_h"] = df_out["lon_h"].ffill()
    df_out["lon_l"] = df_out["lon_l"].ffill()

    return df_out


def run_ict_v3_backtest(
    df: pd.DataFrame,
    df_1m: Optional[pd.DataFrame] = None,
    entry_model: str = "FVG_Touch",
    sl_model: str = "SL4_CISD_Origin",
    use_htf_filter: bool = True,
    queen_bps: float = 10.0,
    runner_mfe_bps: float = 30.0,
    point_value: float = 2.0,
    comm_per_contract: float = 0.52,
    max_wait_bars: int = 20,
    max_daily_trades: int = 5,
    max_risk_bps: float = 15.0,
    min_volume_mult: float = 1.5,
    use_session_sweeps: bool = True,
    risk_usd: float = 250.0,
    max_contracts: int = 10,
    use_1m_execution: bool = False,
) -> Tuple[pd.DataFrame, Dict]:
    """
    v3 backtest built on the proven original logic.
    """

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

    # Session windows
    df["date"] = times.date
    df["hour"] = times.hour
    df["minute"] = times.minute
    df["day_time"] = df["hour"] * 60 + df["minute"]
    rth_mask = (df["day_time"] >= 585) & (df["day_time"] <= 930)  # 09:45-15:30
    eod_mask = df["day_time"] >= 955  # 15:55
    time_strs = times.strftime("%H%M")

    # Volume SMA
    vol_sma = pd.Series(volumes).rolling(20).mean().values

    # Daily PDH/PDL
    daily_df = df.groupby("date").agg({"high": "max", "low": "min", "close": "last"}).shift(1)
    pdh_map = daily_df["high"].to_dict()
    pdl_map = daily_df["low"].to_dict()

    # 1H and 4H sweeps (from original)
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

    # === HTF FVG Detection (1H, 4H, Daily, Weekly) ===
    # A bullish FVG: bar[i].low > bar[i-2].high (gap between bar i-2 high and bar i low)
    # A bearish FVG: bar[i].high < bar[i-2].low (gap between bar i-2 low and bar i high)
    # The FVG boundary acts as a liquidity level — price sweeps back to fill it.
    # We store active FVGs as (level, type) and remove them when filled (mitigated).

    def detect_htf_fvgs(df_htf, label):
        """Detect 3-bar FVGs on a resampled HTF DataFrame. Returns list of (bar_index, fvg_top, fvg_bot, is_bull)."""
        fvgs = []
        h = df_htf["high"].values
        l = df_htf["low"].values
        for i in range(2, len(df_htf)):
            if l[i] > h[i - 2]:  # bullish FVG
                fvgs.append((i, l[i], h[i - 2], True))  # (bar_idx, top, bot, is_bull)
            if h[i] < l[i - 2]:  # bearish FVG
                fvgs.append((i, l[i - 2], h[i], False))  # (bar_idx, top, bot, is_bull)
        return df_htf.index, fvgs

    # Build HTF FVG lists with their timestamps for later mapping to 5m bars
    htf_fvg_data = {}
    for tf, df_tf, name in [("1H", df_1h, "1H_FVG"), ("4H", df_4h, "4H_FVG")]:
        ts, fvgs = detect_htf_fvgs(df_tf, name)
        htf_fvg_data[name] = (ts, fvgs)

    # Daily FVGs
    df_daily = df.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    ts_d, fvgs_d = detect_htf_fvgs(df_daily, "Daily_FVG")
    htf_fvg_data["Daily_FVG"] = (ts_d, fvgs_d)

    # Weekly FVGs
    df_weekly = df.resample("1W").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    ts_w, fvgs_w = detect_htf_fvgs(df_weekly, "Weekly_FVG")
    htf_fvg_data["Weekly_FVG"] = (ts_w, fvgs_w)

    # Build active HTF FVG lookup: for each 5m bar, which HTF FVGs are active (formed but not yet filled)
    # An FVG is "active" from the bar AFTER it forms until price fills it.
    # For sweeps: a bullish FVG is swept when price's low touches the FVG top (L0 <= fvg_top).
    # A bearish FVG is swept when price's high touches the FVG bottom (H0 >= fvg_bot).
    # We store the FVG boundary as the "sweep level" — the edge price returns to.

    def build_htf_fvg_levels(times_5m, htf_fvg_data):
        """For each 5m bar, build lists of active HTF FVG boundaries (sweep levels)."""
        # Returns: dict of arrays — htf_fvg_bsl_levels[i] = list of (level, source) for buy-side liquidity
        #         htf_fvg_ssl_levels[i] = list of (level, source) for sell-side liquidity
        # BSL = price swept a bullish FVG top (buy-side liquidity above)
        # SSL = price swept a bearish FVG bottom (sell-side liquidity below)
        # Actually: a bullish FVG has its TOP as a level price returns to — sweeping that top is a BSL sweep.
        # A bearish FVG has its BOTTOM as a level price returns to — sweeping that bottom is an SSL sweep.

        n_5m = len(times_5m)
        # For each HTF FVG, we need to know when it becomes active and track if it's been filled.
        # Active FVGs: store as list of (start_time, fvg_top, fvg_bot, is_bull, source_name)

        all_fvgs = []
        for name, (ts, fvgs) in htf_fvg_data.items():
            for bar_idx, fvg_top, fvg_bot, is_bull in fvgs:
                if bar_idx < len(ts):
                    form_time = ts[bar_idx]
                    all_fvgs.append((form_time, fvg_top, fvg_bot, is_bull, name))

        all_fvgs.sort(key=lambda x: x[0])

        # For each 5m bar, find which FVGs are active (formed before this bar, not yet filled)
        # An FVG is filled when price trades through it.
        # Bullish FVG filled when 5m low <= fvg_bot (price filled the gap completely)
        # Bearish FVG filled when 5m high >= fvg_top
        active_fvgs = []  # list of [form_time, fvg_top, fvg_bot, is_bull, source, filled]
        htf_bsl_levels = [[] for _ in range(n_5m)]  # buy-side liquidity (bullish FVG tops)
        htf_ssl_levels = [[] for _ in range(n_5m)]  # sell-side liquidity (bearish FVG bots)

        fvg_idx = 0
        for i in range(n_5m):
            t = times_5m[i]
            h0 = highs[i]
            l0 = lows[i]

            # Add newly formed FVGs
            while fvg_idx < len(all_fvgs) and all_fvgs[fvg_idx][0] <= t:
                ft, ftop, fbot, is_bull, src = all_fvgs[fvg_idx]
                active_fvgs.append([ft, ftop, fbot, is_bull, src, False])
                fvg_idx += 1

            # Check and update active FVGs
            remaining = []
            for fvg in active_fvgs:
                ft, ftop, fbot, is_bull, src, filled = fvg
                if filled:
                    continue

                # Check if this FVG is swept by the current bar
                # Bullish FVG: price returns to fill it — the TOP is the sweep level (BSL)
                # A sweep of a bullish FVG top = price's low touches the top (l0 <= ftop) and close > ftop
                # Bearish FVG: price returns to fill it — the BOT is the sweep level (SSL)
                # A sweep of a bearish FVG bot = price's high touches the bot (h0 >= fbot) and close < fbot

                # Check if FVG is fully filled (mitigated)
                if is_bull and l0 <= fbot:
                    fvg[5] = True  # filled
                    continue
                if not is_bull and h0 >= ftop:
                    fvg[5] = True  # filled
                    continue

                # FVG still active — add its boundary as a sweep level
                if is_bull:
                    htf_bsl_levels[i].append((ftop, src))
                else:
                    htf_ssl_levels[i].append((fbot, src))

                remaining.append(fvg)

            active_fvgs = [f for f in active_fvgs if not f[5]]

        return htf_bsl_levels, htf_ssl_levels

    htf_fvg_bsl, htf_fvg_ssl = build_htf_fvg_levels(times, htf_fvg_data)

    # Session sweeps (NEW)
    asia_h_arr = np.full(n, np.nan)
    asia_l_arr = np.full(n, np.nan)
    lon_h_arr = np.full(n, np.nan)
    lon_l_arr = np.full(n, np.nan)

    if use_session_sweeps:
        df_sess = compute_session_levels(df)
        if "asia_h" in df_sess.columns:
            asia_h_arr = df_sess["asia_h"].values
            asia_l_arr = df_sess["asia_l"].values
            lon_h_arr = df_sess["lon_h"].values
            lon_l_arr = df_sess["lon_l"].values

    # 3-bar swing pivots (from original) — build rolling lists
    sw_h = np.full(n, np.nan)
    sw_l = np.full(n, np.nan)
    for i in range(3, n - 3):
        if highs[i] > highs[i - 1] and highs[i] > highs[i - 2] and highs[i] > highs[i - 3] and \
           highs[i] > highs[i + 1] and highs[i] > highs[i + 2] and highs[i] > highs[i + 3]:
            sw_h[i + 3] = highs[i]
        if lows[i] < lows[i - 1] and lows[i] < lows[i - 2] and lows[i] < lows[i - 3] and \
           lows[i] < lows[i + 1] and lows[i] < lows[i + 2] and lows[i] < lows[i + 3]:
            sw_l[i + 3] = lows[i]

    # Rolling swing lists (like the original)
    bsl_list: List[float] = []
    ssl_list: List[float] = []

    # 1m data for intrabar execution
    use_1m = use_1m_execution and df_1m is not None and len(df_1m) > 0
    if use_1m:
        if not isinstance(df_1m.index, pd.DatetimeIndex):
            df_1m["datetime"] = pd.to_datetime(df_1m["datetime"])
            df_1m.set_index("datetime", inplace=True)
        df_1m = df_1m.sort_index()
        df_1m_lookup = df_1m.groupby(pd.Grouper(freq="5min", closed="right", label="right"))

    # State
    trades: List[TradeRecord] = []
    trade_count = 0
    current_date = None
    daily_trade_count = 0

    has_bull_sweep = False
    has_bear_sweep = False
    bull_sweep_low = np.nan
    bear_sweep_high = np.nan
    bull_sweep_bar = -9999
    bear_sweep_bar = -9999
    last_sweep_source = ""

    armed_bull_cisd = False
    armed_bear_cisd = False
    armed_bull_high = np.nan
    armed_bear_low = np.nan
    armed_cisd_origin_sl = np.nan
    current_delivery_regime = 0

    pending_zone: Optional[Dict] = None
    in_position = False
    pos_dir = 0
    pos_entry_bar = 0
    pos_entry_time = None
    pos_entry_price = 0.0
    pos_num_contracts = 2
    pos_risk_usd = 0.0
    active_stop_loss = 0.0
    active_queen_tp = 0.0
    active_runner_tp = 0.0
    active_sl_model = ""
    active_entry_model = ""
    queen_filled = False
    pos_mfe = 0.0
    pos_mae = 0.0

    for i in range(25, n):
        t = times[i]
        bar_date = times[i].date()
        hhmm = time_strs[i]
        is_eod = bool(eod_mask.iloc[i])

        if bar_date != current_date:
            current_date = bar_date
            daily_trade_count = 0

        h0, l0, c0, o0 = highs[i], lows[i], closes[i], opens[i]
        h1, l1 = highs[i - 1], lows[i - 1]
        h2, l2 = highs[i - 2], lows[i - 2]

        # === POSITION MANAGEMENT ===
        if in_position:
            if use_1m:
                # Evaluate on 1m bars within this 5m bar
                try:
                    bars_1m = df_1m_lookup.get_group(t)
                except KeyError:
                    bars_1m = None
                closed_this_5m = False
                if bars_1m is not None and len(bars_1m) > 0:
                    for _, mbar in bars_1m.iterrows():
                        mh, ml, mc = mbar["high"], mbar["low"], mbar["close"]
                        m_time = mbar.name
                        m_is_eod = m_time.strftime("%H%M") >= "1555"

                        if pos_dir == 1:
                            pos_mfe = max(pos_mfe, mh - pos_entry_price)
                            pos_mae = max(pos_mae, pos_entry_price - ml)
                            if ml <= active_stop_loss:
                                q_pnl = (active_queen_tp - pos_entry_price) if queen_filled else (active_stop_loss - pos_entry_price)
                                r_pnl = (active_stop_loss - pos_entry_price) if not queen_filled else (0.0 if active_stop_loss == pos_entry_price else (active_stop_loss - pos_entry_price))
                                total_usd = (q_pnl + r_pnl) * pos_num_contracts * point_value - (2 * pos_num_contracts * comm_per_contract)
                                trade_count += 1
                                trades.append(TradeRecord(trade_count, 1, pos_entry_time, pos_entry_bar, pos_entry_price, active_entry_model, active_stop_loss, active_sl_model, pos_num_contracts, pos_risk_usd, active_queen_tp, active_runner_tp, t, active_queen_tp if queen_filled else active_stop_loss, "Queen Covered" if queen_filled else "Stop Loss", q_pnl, t, active_stop_loss, "Runner BE" if queen_filled else "Runner Stop", r_pnl, total_usd, i - pos_entry_bar, pos_mfe, pos_mae, last_sweep_source))
                                in_position = False; closed_this_5m = True; break
                            if not queen_filled and mh >= active_queen_tp:
                                queen_filled = True; active_stop_loss = pos_entry_price
                            if mh >= active_runner_tp:
                                q_pnl = (active_queen_tp - pos_entry_price); r_pnl = (active_runner_tp - pos_entry_price)
                                total_usd = (q_pnl + r_pnl) * pos_num_contracts * point_value - (2 * pos_num_contracts * comm_per_contract)
                                trade_count += 1
                                trades.append(TradeRecord(trade_count, 1, pos_entry_time, pos_entry_bar, pos_entry_price, active_entry_model, active_stop_loss, active_sl_model, pos_num_contracts, pos_risk_usd, active_queen_tp, active_runner_tp, t, active_queen_tp, "Queen Covered", q_pnl, t, active_runner_tp, "Runner TP2", r_pnl, total_usd, i - pos_entry_bar, pos_mfe, pos_mae, last_sweep_source))
                                in_position = False; closed_this_5m = True; break
                        elif pos_dir == -1:
                            pos_mfe = max(pos_mfe, pos_entry_price - ml)
                            pos_mae = max(pos_mae, mh - pos_entry_price)
                            if mh >= active_stop_loss:
                                q_pnl = (pos_entry_price - active_queen_tp) if queen_filled else (pos_entry_price - active_stop_loss)
                                r_pnl = (pos_entry_price - active_stop_loss) if not queen_filled else (0.0 if active_stop_loss == pos_entry_price else (pos_entry_price - active_stop_loss))
                                total_usd = (q_pnl + r_pnl) * pos_num_contracts * point_value - (2 * pos_num_contracts * comm_per_contract)
                                trade_count += 1
                                trades.append(TradeRecord(trade_count, -1, pos_entry_time, pos_entry_bar, pos_entry_price, active_entry_model, active_stop_loss, active_sl_model, pos_num_contracts, pos_risk_usd, active_queen_tp, active_runner_tp, t, active_queen_tp if queen_filled else active_stop_loss, "Queen Covered" if queen_filled else "Stop Loss", q_pnl, t, active_stop_loss, "Runner BE" if queen_filled else "Runner Stop", r_pnl, total_usd, i - pos_entry_bar, pos_mfe, pos_mae, last_sweep_source))
                                in_position = False; closed_this_5m = True; break
                            if not queen_filled and ml <= active_queen_tp:
                                queen_filled = True; active_stop_loss = pos_entry_price
                            if ml <= active_runner_tp:
                                q_pnl = (pos_entry_price - active_queen_tp); r_pnl = (pos_entry_price - active_runner_tp)
                                total_usd = (q_pnl + r_pnl) * pos_num_contracts * point_value - (2 * pos_num_contracts * comm_per_contract)
                                trade_count += 1
                                trades.append(TradeRecord(trade_count, -1, pos_entry_time, pos_entry_bar, pos_entry_price, active_entry_model, active_stop_loss, active_sl_model, pos_num_contracts, pos_risk_usd, active_queen_tp, active_runner_tp, t, active_queen_tp, "Queen Covered", q_pnl, t, active_runner_tp, "Runner TP2", r_pnl, total_usd, i - pos_entry_bar, pos_mfe, pos_mae, last_sweep_source))
                                in_position = False; closed_this_5m = True; break

                # EOD flatten on 5m close if still open
                if is_eod and in_position and not closed_this_5m:
                    if pos_dir == 1:
                        q_pnl = (active_queen_tp - pos_entry_price) if queen_filled else (c0 - pos_entry_price)
                        r_pnl = (c0 - pos_entry_price)
                    else:
                        q_pnl = (pos_entry_price - active_queen_tp) if queen_filled else (pos_entry_price - c0)
                        r_pnl = (pos_entry_price - c0)
                    total_usd = (q_pnl + r_pnl) * pos_num_contracts * point_value - (2 * pos_num_contracts * comm_per_contract)
                    trade_count += 1
                    trades.append(TradeRecord(trade_count, pos_dir, pos_entry_time, pos_entry_bar, pos_entry_price, active_entry_model, active_stop_loss, active_sl_model, pos_num_contracts, pos_risk_usd, active_queen_tp, active_runner_tp, t, active_queen_tp if queen_filled else c0, "Queen Covered" if queen_filled else "EOD", q_pnl, t, c0, "Runner EOD", r_pnl, total_usd, i - pos_entry_bar, pos_mfe, pos_mae, last_sweep_source))
                    in_position = False
            else:
                # 5m execution (from original)
                if pos_dir == 1:
                    pos_mfe = max(pos_mfe, h0 - pos_entry_price)
                    pos_mae = max(pos_mae, pos_entry_price - l0)
                    if l0 <= active_stop_loss:
                        q_pnl = (active_queen_tp - pos_entry_price) if queen_filled else (active_stop_loss - pos_entry_price)
                        r_pnl = (active_stop_loss - pos_entry_price) if not queen_filled else (0.0 if active_stop_loss == pos_entry_price else (active_stop_loss - pos_entry_price))
                        total_usd = (q_pnl + r_pnl) * pos_num_contracts * point_value - (2 * pos_num_contracts * comm_per_contract)
                        trade_count += 1
                        trades.append(TradeRecord(trade_count, 1, pos_entry_time, pos_entry_bar, pos_entry_price, active_entry_model, active_stop_loss, active_sl_model, pos_num_contracts, pos_risk_usd, active_queen_tp, active_runner_tp, t, active_queen_tp if queen_filled else active_stop_loss, "Queen Covered" if queen_filled else "Stop Loss", q_pnl, t, active_stop_loss, "Runner BE" if queen_filled else "Runner Stop", r_pnl, total_usd, i - pos_entry_bar, pos_mfe, pos_mae, last_sweep_source))
                        in_position = False; continue
                    if not queen_filled and h0 >= active_queen_tp:
                        queen_filled = True; active_stop_loss = pos_entry_price
                    if h0 >= active_runner_tp:
                        q_pnl = (active_queen_tp - pos_entry_price); r_pnl = (active_runner_tp - pos_entry_price)
                        total_usd = (q_pnl + r_pnl) * pos_num_contracts * point_value - (2 * pos_num_contracts * comm_per_contract)
                        trade_count += 1
                        trades.append(TradeRecord(trade_count, 1, pos_entry_time, pos_entry_bar, pos_entry_price, active_entry_model, active_stop_loss, active_sl_model, pos_num_contracts, pos_risk_usd, active_queen_tp, active_runner_tp, t, active_queen_tp, "Queen Covered", q_pnl, t, active_runner_tp, "Runner TP2", r_pnl, total_usd, i - pos_entry_bar, pos_mfe, pos_mae, last_sweep_source))
                        in_position = False; continue
                elif pos_dir == -1:
                    pos_mfe = max(pos_mfe, pos_entry_price - l0)
                    pos_mae = max(pos_mae, h0 - pos_entry_price)
                    if h0 >= active_stop_loss:
                        q_pnl = (pos_entry_price - active_queen_tp) if queen_filled else (pos_entry_price - active_stop_loss)
                        r_pnl = (pos_entry_price - active_stop_loss) if not queen_filled else (0.0 if active_stop_loss == pos_entry_price else (pos_entry_price - active_stop_loss))
                        total_usd = (q_pnl + r_pnl) * pos_num_contracts * point_value - (2 * pos_num_contracts * comm_per_contract)
                        trade_count += 1
                        trades.append(TradeRecord(trade_count, -1, pos_entry_time, pos_entry_bar, pos_entry_price, active_entry_model, active_stop_loss, active_sl_model, pos_num_contracts, pos_risk_usd, active_queen_tp, active_runner_tp, t, active_queen_tp if queen_filled else active_stop_loss, "Queen Covered" if queen_filled else "Stop Loss", q_pnl, t, active_stop_loss, "Runner BE" if queen_filled else "Runner Stop", r_pnl, total_usd, i - pos_entry_bar, pos_mfe, pos_mae, last_sweep_source))
                        in_position = False; continue
                    if not queen_filled and l0 <= active_queen_tp:
                        queen_filled = True; active_stop_loss = pos_entry_price
                    if l0 <= active_runner_tp:
                        q_pnl = (pos_entry_price - active_queen_tp); r_pnl = (pos_entry_price - active_runner_tp)
                        total_usd = (q_pnl + r_pnl) * pos_num_contracts * point_value - (2 * pos_num_contracts * comm_per_contract)
                        trade_count += 1
                        trades.append(TradeRecord(trade_count, -1, pos_entry_time, pos_entry_bar, pos_entry_price, active_entry_model, active_stop_loss, active_sl_model, pos_num_contracts, pos_risk_usd, active_queen_tp, active_runner_tp, t, active_queen_tp, "Queen Covered", q_pnl, t, active_runner_tp, "Runner TP2", r_pnl, total_usd, i - pos_entry_bar, pos_mfe, pos_mae, last_sweep_source))
                        in_position = False; continue

                if is_eod and in_position:
                    if pos_dir == 1:
                        q_pnl = (active_queen_tp - pos_entry_price) if queen_filled else (c0 - pos_entry_price)
                        r_pnl = (c0 - pos_entry_price)
                    else:
                        q_pnl = (pos_entry_price - active_queen_tp) if queen_filled else (pos_entry_price - c0)
                        r_pnl = (pos_entry_price - c0)
                    total_usd = (q_pnl + r_pnl) * pos_num_contracts * point_value - (2 * pos_num_contracts * comm_per_contract)
                    trade_count += 1
                    trades.append(TradeRecord(trade_count, pos_dir, pos_entry_time, pos_entry_bar, pos_entry_price, active_entry_model, active_stop_loss, active_sl_model, pos_num_contracts, pos_risk_usd, active_queen_tp, active_runner_tp, t, active_queen_tp if queen_filled else c0, "Queen Covered" if queen_filled else "EOD", q_pnl, t, c0, "Runner EOD", r_pnl, total_usd, i - pos_entry_bar, pos_mfe, pos_mae, last_sweep_source))
                    in_position = False

        # === PENDING ZONE FILL ===
        if pending_zone is not None and not in_position:
            p_dir = pending_zone["dir"]
            p_level = pending_zone["entry_level"]
            p_sl = pending_zone["sl"]
            p_armed_bar = pending_zone["armed_bar"]
            p_entry_model = pending_zone["entry_model"]
            p_sl_model = pending_zone["sl_model"]
            p_sweep_source = pending_zone.get("sweep_source", "")

            if (i - p_armed_bar) <= max_wait_bars:
                # Volume gate (NEW — spec says 1.5x)
                cur_vol = vol_sma[i] if not np.isnan(vol_sma[i]) else 1.0
                passes_vol = volumes[i] >= (min_volume_mult * cur_vol)

                # Risk ceiling (NEW — spec says 15 bps)
                risk_dist = abs(p_level - p_sl)
                risk_bps = (risk_dist / p_level) * 10000.0
                passes_risk = risk_bps <= max_risk_bps

                can_enter = bool(rth_mask.iloc[i]) and (daily_trade_count < max_daily_trades) and passes_vol and passes_risk

                if use_htf_filter and current_delivery_regime != 0:
                    if p_dir != current_delivery_regime:
                        can_enter = False

                if can_enter:
                    if p_dir == 1 and l0 <= p_level:
                        # Position sizing (NEW)
                        sl_dist_pts = abs(p_level - p_sl)
                        if sl_dist_pts <= 0:
                            pending_zone = None; continue
                        contracts = max(2, int(risk_usd / (sl_dist_pts * point_value)))
                        contracts = min(contracts, max_contracts)

                        in_position = True; pos_dir = 1
                        pos_entry_price = p_level; active_stop_loss = p_sl
                        active_sl_model = p_sl_model; active_entry_model = p_entry_model
                        pos_entry_bar = i; pos_entry_time = t
                        pos_num_contracts = contracts; pos_risk_usd = risk_usd
                        pos_mfe = max(0.0, h0 - pos_entry_price)
                        pos_mae = max(0.0, pos_entry_price - l0)
                        last_sweep_source = p_sweep_source

                        dist_q = round(p_level * (queen_bps / 10000.0) * 4) / 4.0
                        dist_r = round(p_level * (runner_mfe_bps / 10000.0) * 4) / 4.0
                        active_queen_tp = p_level + dist_q
                        active_runner_tp = p_level + dist_r
                        queen_filled = False
                        daily_trade_count += 1
                        pending_zone = None

                    elif p_dir == -1 and h0 >= p_level:
                        sl_dist_pts = abs(p_sl - p_level)
                        if sl_dist_pts <= 0:
                            pending_zone = None; continue
                        contracts = max(2, int(risk_usd / (sl_dist_pts * point_value)))
                        contracts = min(contracts, max_contracts)

                        in_position = True; pos_dir = -1
                        pos_entry_price = p_level; active_stop_loss = p_sl
                        active_sl_model = p_sl_model; active_entry_model = p_entry_model
                        pos_entry_bar = i; pos_entry_time = t
                        pos_num_contracts = contracts; pos_risk_usd = risk_usd
                        pos_mfe = max(0.0, pos_entry_price - l0)
                        pos_mae = max(0.0, h0 - pos_entry_price)
                        last_sweep_source = p_sweep_source

                        dist_q = round(p_level * (queen_bps / 10000.0) * 4) / 4.0
                        dist_r = round(p_level * (runner_mfe_bps / 10000.0) * 4) / 4.0
                        active_queen_tp = p_level - dist_q
                        active_runner_tp = p_level - dist_r
                        queen_filled = False
                        daily_trade_count += 1
                        pending_zone = None
            else:
                pending_zone = None

        # === SWEEP DETECTION (Daily + 4H + 1H + Session + Intraday) ===
        bsl_swept = False
        ssl_swept = False
        sweep_extreme = np.nan
        sweep_src = ""

        pdh = pdh_map.get(bar_date, np.nan)
        pdl = pdl_map.get(bar_date, np.nan)
        if not np.isnan(pdh) and h0 > pdh and (c0 < pdh or o0 < pdh):
            bsl_swept = True; sweep_extreme = h0; sweep_src = "PDH"
        if not np.isnan(pdl) and l0 < pdl and (c0 > pdl or o0 > pdl):
            ssl_swept = True; sweep_extreme = l0; sweep_src = "PDL"

        # 4H sweeps
        h4_h = h4_h0_series[i] if i < len(h4_h0_series) else np.nan
        h4_l = h4_l0_series[i] if i < len(h4_l0_series) else np.nan
        if not np.isnan(h4_h) and h0 > h4_h and (c0 < h4_h or o0 < h4_h):
            bsl_swept = True; sweep_extreme = h0; sweep_src = "4H_BSL"
        if not np.isnan(h4_l) and l0 < h4_l and (c0 > h4_l or o0 > h4_l):
            ssl_swept = True; sweep_extreme = l0; sweep_src = "4H_SSL"

        # 1H sweeps
        h1_h = h1_h0_series[i] if i < len(h1_h0_series) else np.nan
        h1_l = h1_l0_series[i] if i < len(h1_l0_series) else np.nan
        if not np.isnan(h1_h) and h0 > h1_h and (c0 < h1_h or o0 < h1_h):
            bsl_swept = True; sweep_extreme = h0; sweep_src = "1H_BSL"
        if not np.isnan(h1_l) and l0 < h1_l and (c0 > h1_l or o0 > h1_l):
            ssl_swept = True; sweep_extreme = l0; sweep_src = "1H_SSL"

        # Session sweeps (NEW — only completed session levels)
        if use_session_sweeps:
            if not bsl_swept and i < len(asia_h_arr) and not np.isnan(asia_h_arr[i]):
                if h0 > asia_h_arr[i] and (c0 < asia_h_arr[i] or o0 < asia_h_arr[i]):
                    bsl_swept = True; sweep_extreme = h0; sweep_src = "Asia_H"
            if not ssl_swept and i < len(asia_l_arr) and not np.isnan(asia_l_arr[i]):
                if l0 < asia_l_arr[i] and (c0 > asia_l_arr[i] or o0 > asia_l_arr[i]):
                    ssl_swept = True; sweep_extreme = l0; sweep_src = "Asia_L"
            if not bsl_swept and i < len(lon_h_arr) and not np.isnan(lon_h_arr[i]):
                if h0 > lon_h_arr[i] and (c0 < lon_h_arr[i] or o0 < lon_h_arr[i]):
                    bsl_swept = True; sweep_extreme = h0; sweep_src = "Lon_H"
            if not ssl_swept and i < len(lon_l_arr) and not np.isnan(lon_l_arr[i]):
                if l0 < lon_l_arr[i] and (c0 > lon_l_arr[i] or o0 > lon_l_arr[i]):
                    ssl_swept = True; sweep_extreme = l0; sweep_src = "Lon_L"

        # HTF FVG sweeps (1H, 4H, Daily, Weekly FVGs as liquidity levels)
        # Bullish FVG top = BSL (price sweeps up into the gap from below)
        # Bearish FVG bot = SSL (price sweeps down into the gap from above)
        if not bsl_swept and i < len(htf_fvg_bsl):
            for fvg_level, fvg_src in htf_fvg_bsl[i]:
                if h0 > fvg_level and (c0 < fvg_level or o0 < fvg_level):
                    bsl_swept = True; sweep_extreme = h0; sweep_src = fvg_src + "_BSL"
                    break
        if not ssl_swept and i < len(htf_fvg_ssl):
            for fvg_level, fvg_src in htf_fvg_ssl[i]:
                if l0 < fvg_level and (c0 > fvg_level or o0 > fvg_level):
                    ssl_swept = True; sweep_extreme = l0; sweep_src = fvg_src + "_SSL"
                    break

        # Update rolling swing lists (from original)
        if i < n and not np.isnan(sw_h[i]):
            bsl_list.append(sw_h[i])
            if len(bsl_list) > 10: bsl_list.pop(0)
        if i < n and not np.isnan(sw_l[i]):
            ssl_list.append(sw_l[i])
            if len(ssl_list) > 10: ssl_list.pop(0)

        # Intraday swing sweeps (from original — uses rolling list)
        if not bsl_swept:
            for bsl_val in bsl_list:
                if h0 > bsl_val and c0 < bsl_val:
                    bsl_swept = True; sweep_extreme = h0; sweep_src = "Swing_H"; break
        if not ssl_swept:
            for ssl_val in ssl_list:
                if l0 < ssl_val and c0 > ssl_val:
                    ssl_swept = True; sweep_extreme = l0; sweep_src = "Swing_L"; break

        if ssl_swept:
            has_bull_sweep = True
            bull_sweep_low = sweep_extreme if not np.isnan(sweep_extreme) else l0
            bull_sweep_bar = i
            last_sweep_source = sweep_src
        if bsl_swept:
            has_bear_sweep = True
            bear_sweep_high = sweep_extreme if not np.isnan(sweep_extreme) else h0
            bear_sweep_bar = i
            last_sweep_source = sweep_src

        if (i - bull_sweep_bar) > 25: has_bull_sweep = False
        if (i - bear_sweep_bar) > 25: has_bear_sweep = False

        # === CISD (min 3-candle opposing run) ===
        if has_bull_sweep and ssl_swept:
            s_high = max(o0, c0)
            s_low = min(o0, c0)
            run_len = 0
            for k in range(1, min(25, i)):
                if closes[i - k] <= opens[i - k]:
                    s_high = max(s_high, max(opens[i - k], closes[i - k]))
                    s_low = min(s_low, min(opens[i - k], closes[i - k]))
                    run_len += 1
                else:
                    break
            if run_len >= 3:
                armed_bull_cisd = True
                armed_bull_high = s_high
                armed_cisd_origin_sl = s_low

        if has_bear_sweep and bsl_swept:
            s_high = max(o0, c0)
            s_low = min(o0, c0)
            run_len = 0
            for k in range(1, min(25, i)):
                if closes[i - k] >= opens[i - k]:
                    s_high = max(s_high, max(opens[i - k], closes[i - k]))
                    s_low = min(s_low, min(opens[i - k], closes[i - k]))
                    run_len += 1
                else:
                    break
            if run_len >= 3:
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

        # === ARM ENTRY ZONE (min 2-tick FVG, min 10 bps SL, skip if entry==SL) ===
        min_fvg_gap = 0.50  # 2 ticks on NQ (0.25 tick size)
        new_bull_fvg = l0 > h2 and (l0 - h2) >= min_fvg_gap
        new_bear_fvg = h0 < l2 and (l2 - h0) >= min_fvg_gap

        if bull_cisd_trigger or (current_delivery_regime == 1 and new_bull_fvg and pending_zone is None and not in_position):
            z_top = l0 if new_bull_fvg else armed_bull_high
            z_bot = h2 if new_bull_fvg else (armed_bull_high - 1.0)
            z_ce = (z_top + z_bot) / 2.0

            if entry_model == "FVG_CE_50": e_price = z_ce
            elif entry_model == "CISD_Level": e_price = armed_bull_high if not np.isnan(armed_bull_high) else z_top
            else: e_price = z_top

            # SL-4: CISD delivery origin. No fallback — skip if no CISD origin.
            sl_price = np.nan
            if sl_model == "SL1_SweepWick": sl_price = (bull_sweep_low if not np.isnan(bull_sweep_low) else l1) - 0.50
            elif sl_model == "SL4_CISD_Origin":
                if not np.isnan(armed_cisd_origin_sl):
                    sl_price = armed_cisd_origin_sl - 0.50
            else: sl_price = (h2 if new_bull_fvg else bull_sweep_low) - 0.50

            # Sanity checks: SL must be valid, below entry, min 2 bps risk
            if np.isnan(sl_price) or sl_price >= e_price:
                pass  # skip — invalid SL
            else:
                risk_bps = ((e_price - sl_price) / e_price) * 10000.0
                if risk_bps >= 2.0 and risk_bps <= max_risk_bps:
                    pending_zone = {"dir": 1, "entry_level": e_price, "sl": sl_price, "armed_bar": i,
                                    "entry_model": entry_model, "sl_model": sl_model, "sweep_source": last_sweep_source}

        if bear_cisd_trigger or (current_delivery_regime == -1 and new_bear_fvg and pending_zone is None and not in_position):
            z_top = l2 if new_bear_fvg else (armed_bear_low + 1.0)
            z_bot = h0 if new_bear_fvg else armed_bear_low
            z_ce = (z_top + z_bot) / 2.0

            if entry_model == "FVG_CE_50": e_price = z_ce
            elif entry_model == "CISD_Level": e_price = armed_bear_low if not np.isnan(armed_bear_low) else z_bot
            else: e_price = z_bot

            # SL-4: CISD delivery origin. No fallback — skip if no CISD origin.
            sl_price = np.nan
            if sl_model == "SL1_SweepWick": sl_price = (bear_sweep_high if not np.isnan(bear_sweep_high) else h1) + 0.50
            elif sl_model == "SL4_CISD_Origin":
                if not np.isnan(armed_cisd_origin_sl):
                    sl_price = armed_cisd_origin_sl + 0.50
            else: sl_price = (l2 if new_bear_fvg else bear_sweep_high) + 0.50

            # Sanity checks: SL must be valid, above entry, min 10 bps risk
            if np.isnan(sl_price) or sl_price <= e_price:
                pass  # skip — invalid SL
            else:
                risk_bps = ((sl_price - e_price) / e_price) * 10000.0
                if risk_bps >= 2.0 and risk_bps <= max_risk_bps:
                    pending_zone = {"dir": -1, "entry_level": e_price, "sl": sl_price, "armed_bar": i,
                                    "entry_model": entry_model, "sl_model": sl_model, "sweep_source": last_sweep_source}

    # Compile results
    trades_data = []
    for tr in trades:
        trades_data.append({
            "trade_id": tr.trade_id, "direction": tr.direction,
            "entry_time": tr.entry_time, "exit_time": tr.runner_exit_time,
            "entry_price": tr.entry_price, "stop_loss": tr.stop_loss,
            "num_contracts": tr.num_contracts, "risk_usd": tr.risk_usd,
            "queen_filled": tr.queen_exit_reason == "Queen Covered",
            "exit_reason": tr.runner_exit_reason,
            "net_pnl_usd": tr.total_pnl_usd,
            "mfe_pts": tr.mfe_pts, "mae_pts": tr.mae_pts,
            "bars_held": tr.bars_held, "sweep_source": tr.sweep_source,
        })
    trades_df = pd.DataFrame(trades_data)
    if len(trades_df) == 0:
        return trades_df, {"total_trades": 0}

    w = trades_df[trades_df["net_pnl_usd"] > 0]
    l = trades_df[trades_df["net_pnl_usd"] < 0]
    gp = w["net_pnl_usd"].sum()
    gl = abs(l["net_pnl_usd"].sum())
    cum = trades_df["net_pnl_usd"].cumsum()
    max_dd = (cum - cum.cummax()).min()

    stats = {
        "total_trades": len(trades_df),
        "win_rate": (len(w) / len(trades_df)) * 100,
        "profit_factor": (gp / gl) if gl > 0 else float("inf"),
        "net_pnl": trades_df["net_pnl_usd"].sum(),
        "avg_win": w["net_pnl_usd"].mean() if len(w) else 0,
        "avg_loss": l["net_pnl_usd"].mean() if len(l) else 0,
        "payoff_ratio": abs(w["net_pnl_usd"].mean() / l["net_pnl_usd"].mean()) if len(l) and len(w) else 0,
        "max_dd": max_dd,
        "avg_contracts": trades_df["num_contracts"].mean(),
    }
    return trades_df, stats


def main():
    import argparse
    p = argparse.ArgumentParser(description="ICT v3 Backtest")
    p.add_argument("--symbol", default="NQ", choices=["NQ", "ES"])
    p.add_argument("--start", default="2020-01-01")
    p.add_argument("--end", default="2026-08-11")
    p.add_argument("--entry", default="FVG_Touch", choices=["FVG_Touch", "FVG_CE_50", "CISD_Level"])
    p.add_argument("--sl", default="SL4_CISD_Origin", choices=["SL1_SweepWick", "SL4_CISD_Origin", "FVG_FormingWick"])
    p.add_argument("--queen-bps", type=float, default=10.0)
    p.add_argument("--runner-bps", type=float, default=30.0)
    p.add_argument("--max-risk-bps", type=float, default=15.0)
    p.add_argument("--min-vol-mult", type=float, default=1.5)
    p.add_argument("--max-daily-trades", type=int, default=5)
    p.add_argument("--max-wait-bars", type=int, default=20)
    p.add_argument("--risk-usd", type=float, default=250.0)
    p.add_argument("--max-contracts", type=int, default=10)
    p.add_argument("--prop-firm", default=None, choices=list(PROP_FIRM_PRESETS.keys()))
    p.add_argument("--no-session-sweeps", dest="session_sweeps", action="store_false")
    p.add_argument("--no-htf-filter", dest="htf_filter", action="store_false")
    p.add_argument("--use-1m", action="store_true")
    args = p.parse_args()

    sym_file = "NQ1_5m" if args.symbol == "NQ" else "ES1_5m"
    df = pd.read_parquet(_root / "data" / f"{sym_file}.parquet")
    if not isinstance(df.index, pd.DatetimeIndex):
        df["datetime"] = pd.to_datetime(df["datetime"]); df.set_index("datetime", inplace=True)
    df = df[(df.index >= args.start) & (df.index <= args.end)].sort_index()

    pv = 2.0 if args.symbol == "NQ" else 5.0
    comm = 0.52 if args.symbol == "NQ" else 0.40
    risk_usd = args.risk_usd
    max_contracts = args.max_contracts

    if args.prop_firm:
        preset = PROP_FIRM_PRESETS[args.prop_firm]
        risk_usd = preset["account_size"] * preset["risk_pct"] / 100
        max_contracts = preset["max_contracts"]
        print(f"Prop firm: {args.prop_firm} | Risk: ${risk_usd:.2f}/trade | Max contracts: {max_contracts}")

    df_1m = None
    if args.use_1m:
        df_1m = pd.read_parquet(_root / "data" / f"{sym_file.replace('_5m','_1m')}.parquet")

    print(f"Loaded {len(df):,} bars ({df.index.min().date()} -> {df.index.max().date()})")
    if args.use_1m:
        print(f"  + {len(df_1m):,} 1m bars for intrabar execution")
    print(f"  Entry: {args.entry} | SL: {args.sl} | Queen: {args.queen_bps}bps | Runner: {args.runner_bps}bps")
    print(f"  Risk ceiling: {args.max_risk_bps}bps | Volume gate: {args.min_vol_mult}x | Sessions: {args.session_sweeps}")
    print()

    tdf, stats = run_ict_v3_backtest(
        df, df_1m=df_1m if args.use_1m else None,
        entry_model=args.entry, sl_model=args.sl,
        use_htf_filter=args.htf_filter,
        queen_bps=args.queen_bps, runner_mfe_bps=args.runner_bps,
        point_value=pv, comm_per_contract=comm,
        max_wait_bars=args.max_wait_bars, max_daily_trades=args.max_daily_trades,
        max_risk_bps=args.max_risk_bps, min_volume_mult=args.min_vol_mult,
        use_session_sweeps=args.session_sweeps,
        risk_usd=risk_usd, max_contracts=max_contracts,
        use_1m_execution=args.use_1m,
    )

    if stats["total_trades"] == 0:
        print("No trades."); return

    print("=" * 85)
    print(f"  ICT v3 — {args.symbol} ({args.start} -> {args.end})")
    print("=" * 85)
    print(f"Trades:        {stats['total_trades']}")
    print(f"Win Rate:      {stats['win_rate']:.1f}%")
    print(f"Profit Factor: {stats['profit_factor']:.2f}")
    print(f"Net PnL:       ${stats['net_pnl']:,.2f}")
    print(f"Avg Win:       ${stats['avg_win']:.2f}")
    print(f"Avg Loss:      ${stats['avg_loss']:.2f}")
    print(f"Payoff:        {stats['payoff_ratio']:.2f}:1")
    print(f"Max DD:        ${stats['max_dd']:,.2f}")
    print(f"Avg Contracts: {stats['avg_contracts']:.1f}")
    print()

    if "sweep_source" in tdf.columns:
        print("Sweep Sources:")
        for src, cnt in tdf["sweep_source"].value_counts().items():
            wr = len(tdf[(tdf["sweep_source"] == src) & (tdf["net_pnl_usd"] > 0)]) / cnt * 100
            print(f"  {src:<12} {cnt:>5}  WR={wr:.1f}%")

    print("\nExit Reasons:")
    for reason, cnt in tdf["exit_reason"].value_counts().items():
        print(f"  {reason:<20} {cnt:>5}  ({cnt/len(tdf)*100:.1f}%)")

    # Save
    out_dir = _root / "reports"
    out_dir.mkdir(exist_ok=True)
    stamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    tdf.to_csv(out_dir / f"ict_v3_{stamp}.csv", index=False)
    print(f"\nSaved to reports/ict_v3_{stamp}.csv")


if __name__ == "__main__":
    main()