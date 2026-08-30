"""E34 — Measured Move ("Little RZY") falsification battery.

Standalone trend class (SEPARATE from BB reversion). Tests the Marci measured-move
strategy family against the same falsification standards that retired BB reversion
(BB_EXPERIMENTS.md E01-E33).

Arms:
  E34      base: MM strategy, all sessions, ES 5m, market entry (fresh: no session gate)
  E34c     + Bollinger context: only early ordinals (1-2) near band extreme in trend dir
  E34d     structure-limit: max_age_bars tightened (crisp vs stale lines)
  MMRaw    falsification ladder: entry bars EXCHANGE for fixed 1xATR SL/TP exits
           (E32 convention: if MMRaw beats E34, the entry isn't the edge)
  CTRL+    E34 on an UP random-walk regime sample (sanity: short side should bleed)
  NQ       E34 NQ cross-check (E26 convention: expect no transfer)
  Portfolio: E34 vs Supertrend head-to-head + daily-return correlation

Usage:
  .\\.venv\\Scripts\\python.exe scripts/analysis/mm_e34_battery.py                 # full battery
  .\\.venv\\Scripts\\python.exe scripts/analysis/mm_e34_battery.py --only E34 MMRaw
"""
from __future__ import annotations

import argparse
import sys
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional

sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")

import numpy as np
import pandas as pd

from scripts.analysis.bb_e16_e21_queue import load_nt
from scripts.analysis.range_strategy_comparison import (
    BacktestEngine,
    TradeSignal,
    build_day_context,
)
from scripts.libs_py.price_action.trendline_structure import (
    TrendlineStructureParams,
    _atr,
    _di_components,
    find_pivot_highs,
    find_pivot_lows,
)
from scripts.strategies.measured_move.core.measured_move import (
    MeasuredMoveStrategy,
    bb_context_flags,
)

warnings.filterwarnings("ignore", category=FutureWarning)

SESSIONS = ("GLOBEX", "ASIA", "LONDON", "NY_AM", "NY_MIDDAY", "NY_PM")


def daily_atr_of(df1: pd.DataFrame) -> pd.Series:
    d = df1.resample("D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    tr = pd.concat([d["high"] - d["low"], (d["high"] - d["close"].shift(1)).abs(),
                    (d["low"] - d["close"].shift(1)).abs()], axis=1).max(axis=1)
    return tr.rolling(10, min_periods=1).mean()


@dataclass
class MMConfig:
    eid: str
    label: str
    engine_params: Dict = field(default_factory=dict)
    min_distinct_anchors: int = 2
    tp_mode: str = "measured"          # "measured" (tp1 proj tp2 2x) | "fixed_atr" (MMRaw arm)
    fixed_atr_mult: float = 1.0
    only_ordinals: Optional[tuple] = None   # E34c: (1, 2, 3) etc
    near_band_req: bool = False        # E34c: require %B extreme in trend direction
    dir_filter: Optional[str] = None   # "LONG"/"SHORT" — one-direction isolation arms


# ---------------------------------------------------------------------------
# Signal scan per session (5m bars), zero-lookahead, then engine simulation
# ---------------------------------------------------------------------------
def scan_mm_signals(bars5: pd.DataFrame, params: TrendlineStructureParams,
                    cfg: MMConfig, bb_flag: Optional[pd.DataFrame] = None) -> list:
    """Run engine on a session's 5m bars; filter by config; return TradeSignals."""
    if bars5 is None or len(bars5) < 60:
        return []
    raw = scan_engine(bars5, params)
    out = []
    for s in raw:
        if cfg.only_ordinals and s.ordinal not in cfg.only_ordinals:
            continue
        if cfg.dir_filter and s.direction != cfg.dir_filter:
            continue
        if cfg.near_band_req and bb_flag is not None:
            row = bb_flag.loc[s.entry_time] if s.entry_time in bb_flag.index else None
            if row is None or pd.isna(row.get("bb_pct_b", np.nan)):
                continue
            pb = float(row["bb_pct_b"])
            hi_thr = float(row.get("pb_hi_thr", np.nan))
            lo_thr = float(row.get("pb_lo_thr", np.nan))
            if pd.isna(hi_thr) or pd.isna(lo_thr):
                continue
            if s.direction == "SHORT" and not (pb >= hi_thr):
                continue
            if s.direction == "LONG" and not (pb <= lo_thr):
                continue
        sig = TradeSignal(
            direction=s.direction,
            entry_price=s.entry_price,
            stop_loss=s.stop_loss,
            tp1_price=s.tp1_price,
            tp2_price=s.tp2_price,
            risk_points=abs(s.entry_price - s.stop_loss),
            entry_time=s.entry_time,
            session_name="SCAN",
            metadata={
                "strategy_name": cfg.eid,
                "ordinal": s.ordinal,
                "dist_atr": s.dist_atr,
            },
        )
        out.append(sig)
    return out


def scan_engine(bars5: pd.DataFrame, params: TrendlineStructureParams) -> list:
    """Direct scan with tp2. The strategy class accepts proj_mult; here we pass
    through the engine list directly (already TradeSignal-adjacent dataclass)."""
    from scripts.libs_py.price_action.trendline_structure import scan_trendline_structures
    return scan_trendline_structures(bars5, params)


# ---------------------------------------------------------------------------
# Session simulation (mirrors BacktestEngine.simulate_trade 2-leg convention but
# keeps the signal's own SL/TP; runs on the session's 5m bars directly)
# ---------------------------------------------------------------------------
def simulate_session(bars5: pd.DataFrame, sig) -> Optional[dict]:
    """5m-bar simulation: fill at next bar open; SL/TP1(scale 50%+BE)/TP2 checks.

    SL is evaluated ONLY on bar j>=i0+1 bars (post-entry), never on the entry bar
    itself, and the session carry does not strand a position: exit EOD close.
    """
    i0 = bars5.index.get_loc(sig.entry_time)
    if i0 is None or i0 + 1 >= len(bars5):
        return None
    is_long = sig.direction == "LONG"
    entry = float(bars5["open"].iloc[i0 + 1])
    sl = float(sig.stop_loss)
    tp1 = float(sig.tp1_price)
    tp2 = float(sig.tp2_price)
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    if is_long and tp1 <= entry:
        return None
    if not is_long and tp1 >= entry:
        return None

    t1_hit = False
    leg1 = 0.0
    leg2 = 0.0
    exit_price = None
    exit_reason = None
    exit_time = None

    for j in range(i0 + 1, len(bars5)):
        h = float(bars5["high"].iloc[j])
        l = float(bars5["low"].iloc[j])
        if is_long:
            if l <= sl:
                # pre-TP1 stop: BOTH legs lose full risk
                leg1 = -risk if not t1_hit else leg1
                leg2 = -risk if not t1_hit else 0.0
                exit_price = sl
                exit_reason = "SL"
                exit_time = bars5.index[j]
                break
            if not t1_hit and h >= tp1:
                t1_hit = True
                leg1 = tp1 - entry
                sl = entry
            if h >= tp2:
                leg2 = tp2 - entry
                exit_price = tp2
                exit_reason = "TP2"
                exit_time = bars5.index[j]
                break
        else:
            if h >= sl:
                leg1 = -risk if not t1_hit else leg1
                leg2 = -risk if not t1_hit else 0.0
                exit_price = sl
                exit_reason = "SL"
                exit_time = bars5.index[j]
                break
            if not t1_hit and l <= tp1:
                t1_hit = True
                leg1 = entry - tp1
                sl = entry
            if l <= tp2:
                leg2 = entry - tp2
                exit_price = tp2
                exit_reason = "TP2"
                exit_time = bars5.index[j]
                break

    if exit_price is None:
        exit_price = float(bars5["close"].iloc[-1])
        exit_time = bars5.index[-1]
        exit_reason = "EOD"
        move = (exit_price - entry) if is_long else (entry - exit_price)
        leg2 = move
        if not t1_hit:
            # pre-TP1 EOD: both legs carry the move (full-size position held)
            leg1 = move
        # post-TP1: leg1 already banked; stopped-at-BE runner leg is 0 unless
        # price slid below entry — approximate with move (BE stop exits exactly 0
        # only if stop touched; 5m close-based approximation)

    pnl_pts = leg1 * 0.5 + leg2 * 0.5
    return {
        "strategy_name": sig.metadata["strategy_name"],
        "date": str(bars5.index[i0].date()),
        "direction": sig.direction,
        "entry_time": sig.entry_time,
        "exit_time": exit_time,
        "exit_reason": exit_reason,
        "entry_price": entry,
        "stop_loss": float(sig.stop_loss),
        "tp1_price": tp1,
        "risk_points": risk,
        "leg1_pnl": leg1,
        "leg2_pnl": leg2,
        "total_pnl_points": pnl_pts,
        "total_pnl_dollars": pnl_pts * 5.0,   # ES micro $5/pt
        "r_multiple": pnl_pts / risk if risk > 0 else 0.0,
        "ordinal": sig.metadata.get("ordinal", 0),
        "dist_atr": sig.metadata.get("dist_atr", np.nan),
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_arm(sym: str, cfg: MMConfig, df1_cache: Dict[str, pd.DataFrame],
            df5_cache: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    df1, df5 = df1_cache[sym], df5_cache[sym]
    pt_val = 5.0 if sym == "ES" else 2.0
    params = TrendlineStructureParams(**{
        **dict(
            pivot_lookback=3, touch_buf_atr=0.10, stop_buf_atr=0.25,
            invalid_buf_atr=0.10, max_age_bars=60, proj_mult=1.0,
            proj_min_atr=0.5, min_risk_bps=2.0, max_risk_bps=15.0,
            atr_period=14, di_period=14, di_edge=0.0,
            use_trend_gate=True, require_directional_bar=True,
        ),
        **cfg.engine_params,
    })

    df1["trade_date"] = df1.index.date
    evening = df1.index.hour >= 18
    df1.loc[evening, "trade_date"] = (df1.loc[evening].index + pd.Timedelta(days=1)).date
    unique_dates = sorted(df1["trade_date"].unique())
    daily_atr = daily_atr_of(df1)

    rows = []
    for t_date in unique_dates:
        ts = pd.Timestamp(t_date)
        if ts.weekday() >= 5 or ts.year < 2025:
            continue
        # context bars = prior evening 18:00 through today 16:00 (futures day)
        start = pd.Timestamp(f"{(ts - pd.Timedelta(days=1)).date()} 18:00:00")
        end = pd.Timestamp(f"{ts.date()} 16:00:00")
        bars5 = df5.loc[start:end]
        if len(bars5) < 80:
            continue

        bb_flag = bb_context_flags(bars5) if cfg.near_band_req else None
        sigs = scan_mm_signals(bars5, params, cfg, bb_flag=bb_flag)

        # one position at a time within the day
        busy_until = None
        for sig in sigs:
            if sig.entry_time.hour * 60 + sig.entry_time.minute > 16 * 60:
                continue
            if busy_until is not None and sig.entry_time <= busy_until:
                continue
            if cfg.tp_mode == "fixed_atr":
                atr5 = _atr(bars5["high"], bars5["low"], bars5["close"], 14)
                a = float(atr5.loc[sig.entry_time]) if not np.isnan(atr5.loc[sig.entry_time]) else np.nan
                if np.isnan(a) or a <= 0:
                    continue
                is_long = sig.direction == "LONG"
                entry0 = sig.entry_price
                sig.stop_loss = entry0 - cfg.fixed_atr_mult * a if is_long else entry0 + cfg.fixed_atr_mult * a
                sig.tp1_price = entry0 + cfg.fixed_atr_mult * a if is_long else entry0 - cfg.fixed_atr_mult * a
                sig.tp2_price = entry0 + 2 * cfg.fixed_atr_mult * a if is_long else entry0 - 2 * cfg.fixed_atr_mult * a
                sig.risk_points = abs(sig.tp1_price - entry0)
            res = simulate_session(bars5, sig)
            if res is not None:
                res["total_pnl_dollars"] = res["total_pnl_points"] * pt_val
                rows.append(res)
                busy_until = res["exit_time"]

    return pd.DataFrame(rows)


def summarize(tdf) -> dict:
    """Accepts a trade DataFrame OR a daily PnL Series."""
    if tdf is None or len(tdf) == 0:
        return dict(trades=0, wr=0.0, pf=0.0, net=0.0, dd=0.0, avg_r=0.0)
    if isinstance(tdf, pd.Series):
        pnl = tdf
    else:
        pnl = tdf["total_pnl_dollars"]
    cum = pnl.cumsum()
    dd = (cum - cum.cummax()).min()
    gp = pnl[pnl > 0].sum()
    gl = abs(pnl[pnl < 0].sum())
    avg_r = round(tdf["r_multiple"].mean(), 3) if isinstance(tdf, pd.DataFrame) and "r_multiple" in tdf else 0.0
    return dict(
        trades=len(tdf),
        wr=round((pnl > 0).mean() * 100, 1),
        pf=round(gp / gl, 2) if gl > 0 else 999.0,
        net=round(pnl.sum()),
        dd=round(abs(dd)),
        avg_r=avg_r,
    )


def print_row(eid: str, label: str, s: dict) -> None:
    print(f"  {eid:<8} {label:<38} {s['trades']:>5}  WR{s['wr']:5.1f}%  PF{s['pf']:5.2f}  "
          f"Net${s['net']:>7.0f}  DD${s['dd']:>5.0f}  avgR{s['avg_r']:+.3f}")


# ---------------------------------------------------------------------------
def build_arms() -> List[MMConfig]:
    return [
        MMConfig("E34", "BASE All sessions, DI gate"),
        MMConfig("E34L", "BASE long-only", dir_filter="LONG"),
        MMConfig("E34S", "BASE short-only", dir_filter="SHORT"),
        MMConfig("E34b", "First-2 ordinals only", only_ordinals=(1, 2)),
        MMConfig("E34c", "Near-band extreme context", near_band_req=True, only_ordinals=(1, 2, 3)),
        MMConfig("E34d", "Relaxed DI (edge<0, both dirs)", engine_params={"di_edge": -10.0}),
        MMConfig("MMRaw", "Falsification: fixed 1xATR exits", tp_mode="fixed_atr"),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--skip-portfolio", action="store_true")
    args = ap.parse_args()

    only = set(args.only) if args.only else None

    print("Loading NT MergeBA ES + NQ...")
    df1_es, df5_es = load_nt("ES")
    df1_nq, df5_nq = load_nt("NQ")
    df1c = {"ES": df1_es, "NQ": df1_nq}
    df5c = {"ES": df5_es, "NQ": df5_nq}

    arms = build_arms()
    results: Dict[str, Dict[str, dict]] = {}
    trade_frames: Dict[str, pd.DataFrame] = {}

    for cfg in arms:
        if only and cfg.eid not in only:
            continue
        key = cfg.eid
        if key.startswith("MMRaw"):
            sym = "ES"
        elif key == "NQ" or key.startswith("E34") is False and key == "NQ":
            sym = "NQ"
        else:
            sym = "ES"
        tdf = run_arm(sym, cfg, df1c, df5c)
        trade_frames[key] = tdf
        s = summarize(tdf)
        results.setdefault(sym, {})[cfg.eid] = s
        # per-direction split
        if len(tdf):
            sl = tdf[tdf["direction"] == "LONG"]
            ss = tdf[tdf["direction"] == "SHORT"]
            print(f"\n{cfg.eid} — {cfg.label} [{sym}]")
            print_row(cfg.eid, cfg.label, s)
            if len(sl):
                sr = summarize(sl)
                print(f"    LONG  {sr['trades']:>5}  WR{sr['wr']:5.1f}%  PF{sr['pf']:5.2f}  Net${sr['net']:>7.0f}  DD${sr['dd']:>5.0f}")
            if len(ss):
                sr = summarize(ss)
                print(f"    SHORT {sr['trades']:>5}  WR{sr['wr']:5.1f}%  PF{sr['pf']:5.2f}  Net${sr['net']:>7.0f}  DD${sr['dd']:>5.0f}")
        else:
            print(f"\n{cfg.eid} — {cfg.label} [{sym}]: 0 trades")

    # ordinal breakdown on E34
    if "E34" in trade_frames and len(trade_frames["E34"]):
        tdf = trade_frames["E34"]
        print("\n" + "=" * 84)
        print("E34 ordinal breakdown (Marci hypothesis: 1st/2nd strongest, later exhausted)")
        print("=" * 84)
        for o in sorted(tdf["ordinal"].unique()):
            sub = tdf[tdf["ordinal"] == o]
            s = summarize(sub)
            print(f"  ordinal {o}: {s['trades']:>4} tr  WR{s['wr']:5.1f}%  PF{s['pf']:5.2f}  Net${s['net']:>7.0f}")

    # NQ cross-check arm
    if only is None or "NQ" in only:
        cfg_nq = MMConfig("NQ", "E34 config on NQ cross-check")
        tdf_nq = run_arm("NQ", cfg_nq, df1c, df5c)
        trade_frames["NQ"] = tdf_nq
        s = summarize(tdf_nq)
        results.setdefault("NQ", {})["NQ"] = s
        print("\n" + "=" * 84)
        print("E26-convention NQ cross-check (E34 config on NQ)")
        print("=" * 84)
        print_row("NQ", "E34 config on NQ", s)

    # Supertrend head-to-head + portfolio correlation
    if not args.skip_portfolio and (only is None or "PORT" in only):
        print("\n" + "=" * 84)
        print("Portfolio: E34 vs Supertrend(14,2) trail 1.5xATR head-to-head + correlation")
        print("=" * 84)
        from scripts.analysis.bb_e33_e31_final import run_st_trades, summarize as st_summarize
        df1, df5 = df1_es, df5_es
        df1["trade_date"] = df1.index.date
        evening = df1.index.hour >= 18
        df1.loc[evening, "trade_date"] = (df1.loc[evening].index + pd.Timedelta(days=1)).date
        unique_dates = sorted(df1["trade_date"].unique())
        st_t = run_st_trades(df1, df5, unique_dates)
        e34_t = trade_frames.get("E34", pd.DataFrame())

        s_st = st_summarize(st_t["total_pnl_dollars"]) if len(st_t) else dict(trades=0, wr=0, pf=0, net=0, dd=0)
        cal = pd.date_range("2025-01-01", "2026-08-31", freq="D").date
        if len(e34_t):
            e34_daily = e34_t.groupby(pd.to_datetime(e34_t["exit_time"]).dt.date)["total_pnl_dollars"].sum().reindex(cal, fill_value=0.0)
            st_daily = st_t.groupby(pd.to_datetime(st_t["exit_time"]).dt.date)["total_pnl_dollars"].sum().reindex(cal, fill_value=0.0)
            corr = e34_daily.corr(st_daily)
            comb = e34_daily + st_daily
            print(f"  ST alone : WR{s_st['wr']:5.1f}%  PF{s_st['pf']:5.2f}  Net${s_st['net']:>7.0f}  DD${s_st['dd']:>5.0f}")
            print(f"  E34 daily: WR{summarize(e34_daily)['wr']:5.1f}%  PF{summarize(e34_daily)['pf']:5.2f}  Net${summarize(e34_daily)['net']:>7.0f}")
            print(f"  Combined : WR{summarize(comb)['wr']:5.1f}%  PF{summarize(comb)['pf']:5.2f}  Net${summarize(comb)['net']:>7.0f}  DD${summarize(comb)['dd']:>5.0f}")
            print(f"  Daily-return correlation E34 vs ST: {corr:+.3f}")

    # save trades
    out_dir = "data/derived"
    for k, tdf in trade_frames.items():
        if len(tdf):
            safe = k.replace("/", "_")
            tdf.to_csv(f"{out_dir}/mm_e34_{safe}_trades.csv", index=False)
    print(f"\nSaved trade files to {out_dir}/mm_e34_*_trades.csv")


if __name__ == "__main__":
    main()