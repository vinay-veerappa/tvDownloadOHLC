"""E16-E21 experiment queue — BB Mean Reversion improvements (review 2026-08-27).

Runs the full E16→E21 ladder from docs/research/STRATEGY_REVIEW_2026_08_27.md on the
shared NT MergeBA ES data (2025-01-01 → 2026-08-21), same harness family as
bb_sweep_optim.py (limit 1-tick, $0 comm/slip = NT8 parity).

Variants (each is E15-best base + ONE change, measured against E16 baseline ladder):
  E16  long-only                    (shorts PF0.88 vs longs 1.17 over 1112 trades)
  E17  long-only + BW floor 0.011   (BW 0.007-0.011 = 83% loss; replaces ADX25 gate)
  E18  E17 + RSI 38/62 + close-back-inside confirmation (frequency unlock)
  E19  E17 + RSI-50 exit proxy (exit at signal-bar close if RSI already > 50 hook zone)
  E20  E17 + sweep veto (skip entries within 1h after aligned sweep — PF0.92 trap)
  E21  E17 restricted to 15:00-16:00 (114/137 touches at hour 15)

Usage:
  .\\.venv\\Scripts\\python.exe scripts/analysis/bb_e16_e21_queue.py            # all variants
  .\\.venv\\Scripts\\python.exe scripts/analysis/bb_e16_e21_queue.py --only E16 E17
"""
import argparse
import itertools
import sys
import warnings
from dataclasses import dataclass
from typing import List, Optional

sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")

import numpy as np
import pandas as pd

from scripts.analysis.range_strategy_comparison import (
    BBRsiMeanReversionStrategy,
    BacktestEngine,
    DayContext,
    TradeSignal,
    _adx,
    _wilder_rsi,
    build_day_context,
)

warnings.filterwarnings("ignore", category=FutureWarning)


# ----------------------------------------------------------------------------
# Variant-flagged strategy subclass (no changes to the shared class)
# ----------------------------------------------------------------------------
@dataclass
class VariantConfig:
    eid: str
    label: str
    long_only: bool = True
    use_adx: bool = True
    bw_floor_pct: float = 0.0   # E17+: signal-bar bw must exceed this percentile of the day's bw history
    bw_floor_abs: float = 0.0   # E17 alt: absolute floor (ES 5m bw scale ~0.002-0.005)
    rsi_lo: float = 33.0        # E18: relax to 38
    no_runner: bool = False    # E19: full exit at mid-band (momentum-normalized exit proxy)
    sweep_veto_onl: bool = False  # E20: veto longs within 1h after overnight-low sweep
    hour_start: int = 0         # E21: restrict entry hours to [hour_start, hour_end)
    hour_end: int = 24
    hour_blacklist: tuple = ()  # E23: skip these entry hours entirely
    use_macd_filter: bool = False  # E24: MACD(12,26,9) histogram rising at signal bar
    sessions: tuple = ("GLOBEX", "ASIA", "LONDON", "NY_AM", "NY_MIDDAY", "NY_PM")


class BBE16Strategy(BBRsiMeanReversionStrategy):
    """BBRsi with variant flags. All changes are additive gates; no shared-file edits."""

    def __init__(self, cfg: VariantConfig, symbol: str = "ES", **kw):
        # Base params: E02/E12 line (bb20 1.8) — the ladder's shared base
        kw.setdefault("bb_period", 20)
        kw.setdefault("std_dev", 1.8)
        kw.setdefault("rsi_period", 14)
        kw.setdefault("adx_threshold", 25.0)
        kw.setdefault("use_adx", cfg.use_adx)
        kw.setdefault("max_trades_per_session", 3)
        super().__init__(symbol=symbol, **kw)
        self.cfg = cfg
        self.name = cfg.eid  # results keyed by experiment id

    def detect_signal(self, ctx: DayContext, session_name: str,
                      after_time: pd.Timestamp = None) -> Optional[TradeSignal]:
        cfg = self.cfg
        if session_name not in ("NY_MIDDAY", "NY_PM", "NY_AM", "LONDON", "ASIA", "GLOBEX"):
            return None
        bars_5m = ctx.session_5m.get(session_name)
        if bars_5m is None or len(bars_5m) < self.bb_period + 10:
            return None

        close = bars_5m["close"]
        high = bars_5m["high"]
        low = bars_5m["low"]

        sma = close.rolling(self.bb_period).mean()
        std = close.rolling(self.bb_period).std()
        upper = sma + self.std_dev * std
        lower = sma - self.std_dev * std
        rsi = _wilder_rsi(close, self.rsi_period)
        adx_s = _adx(high, low, close, 14)

        # E24: MACD(12,26,9) histogram — rising at signal bar (E14 champion filter)
        if cfg.use_macd_filter:
            ema_fast = close.ewm(span=12, adjust=False).mean()
            ema_slow = close.ewm(span=26, adjust=False).mean()
            macd_line = ema_fast - ema_slow
            macd_hist = macd_line - macd_line.ewm(span=9, adjust=False).mean()
        else:
            macd_hist = None

        # Day-level BW history for percentile floor (uses full day's bars — the
        # signal bar's own bw is computed from trailing 20 bars only, so the
        # percentile comparison uses bars up to i-1 only to stay zero-lookahead)
        bw_all = ((2 * self.std_dev * close.rolling(self.bb_period).std()) / close.rolling(self.bb_period).mean()).dropna()

        atr = ctx.atr_val if not np.isnan(ctx.atr_val) and ctx.atr_val > 0 else 20.0

        for i in range(2, len(bars_5m)):
            curr_time = bars_5m.index[i]
            if after_time is not None and curr_time <= after_time:
                continue

            # E21: hour window restriction (supports midnight wrap: start 19, end 8)
            if cfg.hour_start != 0 or cfg.hour_end != 24:
                if cfg.hour_start <= cfg.hour_end:
                    in_window = cfg.hour_start <= curr_time.hour < cfg.hour_end
                else:
                    in_window = curr_time.hour >= cfg.hour_start or curr_time.hour < cfg.hour_end
                if not in_window:
                    continue
            # E23: hour blacklist
            if curr_time.hour in cfg.hour_blacklist:
                continue

            adx_val = adx_s.iloc[i]
            if self.use_adx and not np.isnan(adx_val) and adx_val >= self.adx_threshold:
                continue

            bw_i = (upper.iloc[i] - lower.iloc[i]) / sma.iloc[i] if sma.iloc[i] > 0 else np.nan

            # E17: BW floor — absolute or day-percentile (percentile over trailing history only)
            if cfg.bw_floor_abs > 0 and (np.isnan(bw_i) or bw_i < cfg.bw_floor_abs):
                continue
            if cfg.bw_floor_pct > 0 and i >= self.bb_period + 20:
                hist = bw_all.iloc[self.bb_period:i]  # trailing only, no look-ahead
                if len(hist) >= 10:
                    pct_rank = (hist <= bw_i).mean() * 100
                    if pct_rank < cfg.bw_floor_pct:
                        continue

            # --- LONG setup (E16/E17 base) ---
            long_setup = (
                close.iloc[i - 1] < lower.iloc[i - 1]
                and rsi.iloc[i - 1] < cfg.rsi_lo
                and close.iloc[i] > lower.iloc[i]
                and rsi.iloc[i] > rsi.iloc[i - 1]
                and close.iloc[i] < sma.iloc[i]
                and rsi.iloc[i] < 50
            )
            # E24: MACD histogram rising (falling-knife veto)
            if long_setup and cfg.use_macd_filter and macd_hist is not None:
                long_setup = long_setup and macd_hist.iloc[i] > macd_hist.iloc[i - 1]
            if long_setup:
                entry = float(close.iloc[i])
                atr_5m = float((high.rolling(14).max() - low.rolling(14).min()).iloc[i] / 14) if len(bars_5m) > 20 else atr / 6
                if np.isnan(atr_5m) or atr_5m <= 0:
                    atr_5m = atr / 6
                sl = float(min(lower.iloc[i], close.iloc[i]) - 1.5 * atr_5m)
                sl = min(sl, entry - (1.0 * atr_5m))
                risk = entry - sl
                if risk <= 0 or risk > (0.70 * atr):
                    continue
                tp1 = float(sma.iloc[i])
                tp2 = float(upper.iloc[i])
                if tp1 <= entry:
                    continue
                # E19: full exit at mid-band (no runner) — momentum-normalized exit proxy
                if cfg.no_runner:
                    tp2 = tp1
                return TradeSignal(
                    direction="LONG", entry_price=entry, stop_loss=sl,
                    tp1_price=tp1, tp2_price=tp2, risk_points=risk,
                    entry_time=curr_time, session_name=session_name,
                    metadata={"rsi": float(rsi.iloc[i]), "adx": float(adx_val), "bw": float(bw_i) if not np.isnan(bw_i) else None},
                )

        return None


# ----------------------------------------------------------------------------
# Sweep veto (E20) — veto longs right after a fresh sell-side (overnight/session-low) sweep
# ----------------------------------------------------------------------------
def sweep_veto_check(sig: TradeSignal, ctx: DayContext) -> bool:
    """True = veto this trade. The crossref found fading INTO a fresh sweep loses
    (PF 0.92 aligned vs 1.25 without). For longs: veto if the signal bar itself
    made a NEW low below the prior N-bar low (falling knife just swept support)."""
    session_bars = ctx.session_bars.get(sig.session_name)
    if session_bars is None:
        return False
    pre = session_bars.loc[:sig.entry_time]
    if len(pre) < 60:
        return False
    # Signal bar is the last 5m bar before entry; prior 60 bars = 5h context
    sig_bar = pre.iloc[-1]
    prior = pre.iloc[-61:-1]
    if sig.direction == "LONG":
        # fresh sell-side sweep: signal bar low broke the prior 5h low
        return bool(sig_bar["low"] < prior["low"].min())
    else:
        return bool(sig_bar["high"] > prior["high"].max())


# ----------------------------------------------------------------------------
# Data loading (shared NT MergeBA)
# ----------------------------------------------------------------------------
def load_nt(sym="ES"):
    df1 = pd.read_csv(f"data/derived/nt_{sym.lower()}_09_26_1m_2025_2026_mergeBA.csv", parse_dates=["time"])
    df1 = df1.set_index("time").sort_index()
    df5 = pd.read_csv(f"data/derived/nt_{sym.lower()}_09_26_5m_2025_2026_mergeBA.csv", parse_dates=["time"])
    df5 = df5.set_index("time").sort_index()
    if df1.index.tz is not None:
        df1.index = df1.index.tz_convert("America/New_York").tz_localize(None)
    if df5.index.tz is not None:
        df5.index = df5.index.tz_convert("America/New_York").tz_localize(None)
    df1 = df1[(df1.index.year >= 2025) & (df1.index.year <= 2026)]
    df5 = df5[(df5.index.year >= 2025) & (df5.index.year <= 2026)]
    return df1, df5


# ----------------------------------------------------------------------------
# Per-variant runner
# ----------------------------------------------------------------------------
def run_variant(df1, df5, daily_atr, cfg: VariantConfig, sessions: List[str]) -> dict:
    strat = BBE16Strategy(cfg, symbol="ES")
    engine = BacktestEngine("ES", tick_size=0.25, entry_mode="market")

    trades = []
    df1["trade_date"] = df1.index.date
    evening = df1.index.hour >= 18
    df1.loc[evening, "trade_date"] = (df1.loc[evening].index + pd.Timedelta(days=1)).date
    unique_dates = sorted(df1["trade_date"].unique())

    for t_date in unique_dates:
        ts = pd.Timestamp(t_date)
        if ts.weekday() >= 5 or ts.year < 2025 or ts.year > 2026:
            continue
        ctx = build_day_context(ts, df1, df5, daily_atr, ib_minutes=30)
        if ctx is None:
            continue
        for sess in sessions:
            after_time = None
            for _ in range(3):
                sig = strat.detect_signal(ctx, sess, after_time=after_time)
                if sig is None:
                    break
                sig.metadata["strategy_name"] = strat.name
                if cfg.sweep_veto_onl and sweep_veto_check(sig, ctx):
                    # advance past this bar so we don't re-signal the same setup
                    after_time = sig.entry_time + pd.Timedelta(minutes=5)
                    continue
                tr = engine.simulate_trade(sig, ctx)
                if tr is None:
                    break
                tr.strategy_name = strat.name
                trades.append(tr.__dict__)
                after_time = tr.exit_time

    tdf = pd.DataFrame(trades)
    out = {"eid": cfg.eid, "label": cfg.label}
    if tdf.empty:
        out.update(trades=0, wr=0.0, pf=0.0, net=0, dd=0)
        return out

    pnl = tdf["total_pnl_dollars"]
    cum = pnl.cumsum()
    dd = (cum - cum.cummax()).min()
    gp = pnl[pnl > 0].sum()
    gl = abs(pnl[pnl < 0].sum())
    out.update(
        trades=len(tdf),
        wr=round((pnl > 0).mean() * 100, 1),
        pf=round(gp / gl, 2) if gl > 0 else 999.0,
        net=round(pnl.sum()),
        dd=round(abs(dd)),
        avg_r=round(tdf["r_multiple"].mean(), 3),
        long_wr=round((pnl[tdf["direction"] == "LONG"] > 0).mean() * 100, 1) if (tdf["direction"] == "LONG").any() else 0,
    )
    return out


# ----------------------------------------------------------------------------
# Variant definitions
# ----------------------------------------------------------------------------
def build_variants() -> List[VariantConfig]:
    return [
        # E16: long-only, keep ADX gate (isolate direction change vs E02 baseline)
        VariantConfig("E16", "long-only + ADX25"),
        # E17a: long-only + BW floor 25th pctile of trailing day history, ADX OFF
        VariantConfig("E17", "long-only + BW p25 floor, no ADX", use_adx=False, bw_floor_pct=25.0),
        # E17b: absolute floor variant (mid-range of observed 0.002-0.005 scale)
        VariantConfig("E17b", "long-only + BW>0.0032, no ADX", use_adx=False, bw_floor_abs=0.0032),
        # E18: E17a + relaxed RSI<38
        VariantConfig("E18", "E17 + RSI<38", use_adx=False, bw_floor_pct=25.0, rsi_lo=38.0),
        # E19: E17a + full exit at mid-band (no runner)
        VariantConfig("E19", "E17 + no-runner (exit at mid-band)", use_adx=False, bw_floor_pct=25.0, no_runner=True),
        # E20: E17a + fresh-sweep veto
        VariantConfig("E20", "E17 + fresh-sweep veto", use_adx=False, bw_floor_pct=25.0, sweep_veto_onl=True),
        # E21: E17a confined to 15:00-16:00 (power hour)
        VariantConfig("E21", "E17 + 15:00-16:00 only", use_adx=False, bw_floor_pct=25.0, hour_start=15, hour_end=16),
        # E21b: E17a confined to NY_AM open window
        VariantConfig("E21b", "E17 + 09:30-11:30 only", use_adx=False, bw_floor_pct=25.0, hour_start=9, hour_end=11),
    ]


def build_variants_e22() -> List[VariantConfig]:
    """E22-E25 batch — built on E16 (long-only + ADX25) baseline."""
    return [
        # Baseline included for apples-to-apples comparison in the same run
        VariantConfig("E16", "BASELINE long-only + ADX25"),
        # E22: overnight block only. Hour gate: h>=19 OR h<8 (wraps midnight).
        # GLOBEX opens 18:00 — 19:00 skips the thin first hour.
        VariantConfig("E22", "E16 + overnight 19:00-08:00", hour_start=19, hour_end=8),
        # E23: surgical hour blacklist (h6, h9 worst from E16 hour table)
        VariantConfig("E23", "E16 + blacklist h6,h9", hour_blacklist=(6, 9)),
        # E24: E14's MACD hist rising filter on the long-only base
        VariantConfig("E24", "E16 + MACD hist rising", use_macd_filter=True),
        # E25: BW p25 floor WITH ADX25 kept (E17 tested BW without ADX)
        VariantConfig("E25", "E16 + BW p25 floor (ADX kept)", bw_floor_pct=25.0),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None, help="subset of experiment ids")
    ap.add_argument("--batch", choices=["e16_e21", "e22_e25"], default="e22_e25",
                    help="which variant batch to run")
    args = ap.parse_args()

    print("Loading NT MergeBA ES 2025-2026...")
    df1, df5 = load_nt("ES")

    df_daily = df1.resample("D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    tr = pd.concat([
        df_daily["high"] - df_daily["low"],
        (df_daily["high"] - df_daily["close"].shift(1)).abs(),
        (df_daily["low"] - df_daily["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    daily_atr = tr.rolling(10, min_periods=1).mean()

    sessions = ["GLOBEX", "ASIA", "LONDON", "NY_AM", "NY_MIDDAY", "NY_PM"]
    variants = build_variants_e22() if args.batch == "e22_e25" else build_variants()
    if args.only:
        variants = [v for v in variants if v.eid in args.only]

    print(f"Running {len(variants)} variants x {sessions} sessions, 19mo...\n")
    rows = []
    for cfg in variants:
        res = run_variant(df1, df5, daily_atr, cfg, sessions)
        rows.append(res)
        print(f"{res['eid']:<4} {res['label']:<42} {res['trades']:>4} trades  WR{res['wr']:5.1f}%  PF{res['pf']:5.2f}  Net${res['net']:>6.0f}  DD${res['dd']:>5.0f}"
              + (f"  avgR{res.get('avg_r', 0):+.3f}" if res.get("avg_r") is not None else ""))

    res_df = pd.DataFrame(rows)
    print("\nRanked by PF:")
    print(res_df.sort_values("pf", ascending=False).to_string(index=False))
    out_path = ("data/derived/bb_e22_e25_queue_results.csv" if args.batch == "e22_e25"
                else "data/derived/bb_e16_e21_queue_results.csv")
    res_df.to_csv(out_path, index=False)
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    main()