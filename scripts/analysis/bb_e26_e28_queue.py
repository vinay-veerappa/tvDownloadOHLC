"""E26-E28 experiment queue — E22 (overnight long-only BB) validation battery.

  E26  NQ cross-check    — does the overnight long-only edge hold on NQ 09-26?
                           (overnight personality differs per NQSTATS memories;
                           MNQ-style $2/pt point value for sizing consistency)
  E27  Prop firm sim     — E22's ES 532-trade series through PropFirmSimulator
                           (ADR-021: the ONLY sanctioned viability evaluator).
                           1xMES $5/pt scaled to Apex/TopStep/FTMO 50K profiles.
  E28  Overnight split   — E22 restricted to first half (19:00-24:00) vs second
                           half (00:00-08:00) — where does the edge concentrate?

Usage:
  .\\.venv\\Scripts\\python.exe scripts/analysis/bb_e26_e28_queue.py
"""
import sys
import warnings

sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")

import numpy as np
import pandas as pd

from scripts.analysis.bb_e16_e21_queue import (
    BBE16Strategy,
    VariantConfig,
    load_nt,
)
from scripts.analysis.range_strategy_comparison import BacktestEngine, build_day_context
from scripts.trading_framework.ml.prop_firm_simulator import (
    FIRM_PROFILES,
    PropFirmSimulator,
)

warnings.filterwarnings("ignore", category=FutureWarning)

E22 = VariantConfig("E22", "E16 + overnight 19:00-08:00", hour_start=19, hour_end=8)
SESSIONS = ["GLOBEX", "ASIA", "LONDON", "NY_AM", "NY_MIDDAY", "NY_PM"]


def run_series(sym: str, cfg: VariantConfig, pt_val: float) -> pd.DataFrame:
    """Run one variant on one symbol; return per-trade frame with session tags."""
    df1, df5 = load_nt(sym)
    df_daily = df1.resample("D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    tr = pd.concat([
        df_daily["high"] - df_daily["low"],
        (df_daily["high"] - df_daily["close"].shift(1)).abs(),
        (df_daily["low"] - df_daily["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    daily_atr = tr.rolling(10, min_periods=1).mean()

    strat = BBE16Strategy(cfg, symbol=sym)
    engine = BacktestEngine(sym, tick_size=0.25, entry_mode="market")
    engine.pt_val_per_leg = pt_val  # 1x micro: MES $5, MNQ $2

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
        for sess in SESSIONS:
            after_time = None
            for _ in range(3):
                sig = strat.detect_signal(ctx, sess, after_time=after_time)
                if sig is None:
                    break
                sig.metadata["strategy_name"] = strat.name
                tr_res = engine.simulate_trade(sig, ctx)
                if tr_res is None:
                    break
                tr_res.strategy_name = strat.name
                d = tr_res.__dict__.copy()
                d["exit_ts"] = pd.Timestamp(tr_res.exit_time)
                d["entry_ts"] = pd.Timestamp(tr_res.entry_time)
                trades.append(d)
                after_time = tr_res.exit_time
    return pd.DataFrame(trades)


def summarize(tdf: pd.DataFrame, label: str) -> dict:
    if tdf.empty:
        return {"label": label, "trades": 0, "wr": 0, "pf": 0, "net": 0, "dd": 0}
    pnl = tdf["total_pnl_dollars"]
    cum = pnl.cumsum()
    dd = (cum - cum.cummax()).min()
    gp, gl = pnl[pnl > 0].sum(), abs(pnl[pnl < 0].sum())
    return {
        "label": label, "trades": len(tdf),
        "wr": round((pnl > 0).mean() * 100, 1),
        "pf": round(gp / gl, 2) if gl > 0 else 999.0,
        "net": round(pnl.sum()), "dd": round(abs(dd)),
        "avg_r": round(tdf["r_multiple"].mean(), 3),
    }


# ============================================================================
def main():
    # ------------------------------------------------------------------ E26
    print("=" * 78)
    print("E26 — NQ cross-check (E22 overnight config, MNQ $2/pt)")
    print("=" * 78)
    nq = run_series("NQ", E22, pt_val=2.0)
    es = run_series("ES", E22, pt_val=5.0)
    for label, tdf in [("ES E22", es), ("NQ E22", nq)]:
        s = summarize(tdf, label)
        print(f"  {s['label']:<8} {s['trades']:>4} trades  WR{s['wr']:5.1f}%  PF{s['pf']:5.2f}  "
              f"Net${s['net']:>6.0f}  DD${s['dd']:>5.0f}  avgR{s.get('avg_r', 0):+.3f}")
    if not nq.empty:
        nq_by_hy = nq.copy()
        nq_by_hy["hy"] = pd.to_datetime(nq_by_hy["date"]).dt.strftime("%Y") + np.where(
            pd.to_datetime(nq_by_hy["date"]).dt.month <= 6, "H1", "H2")
        g = nq_by_hy.groupby("hy")["total_pnl_dollars"].agg(["count", "sum"])
        print("  NQ by half-year:", {i: (int(r["count"]), int(r["sum"])) for i, r in g.iterrows()})
    nq.to_csv("data/derived/bb_e26_nq_e22_trades.csv", index=False)

    # ------------------------------------------------------------------ E27
    print("\n" + "=" * 78)
    print("E27 — Prop firm simulation on ES E22 (ADR-021 PropFirmSimulator)")
    print("=" * 78)
    # Simulator input contract: pnl_pct (% of account) + exit_time.
    # Our series is 1xMES $5/pt; convert dollar P&L to % of each profile's account
    # is done inside _to_dollar_pnl via account_size — so feed pnl_pct relative to
    # the GENERIC 50k base and let the profile-specific account_size rescale.
    # NOTE: pnl_pct = dollar_pnl / account_size * 100. The simulator multiplies
    # back by profile.account_size, so a FIXED dollar series must be expressed
    # against the account the dollars were earned on. We earned them on a micro
    # account — scale honestly: report micro results AND a 10x-scaled variant
    # (10xMES, the realistic eval sizing for $3k targets).
    for scale, contracts in [(1, "1xMES"), (10, "10xMES")]:
        td = pd.DataFrame({
            "exit_time": es["exit_ts"],
            "pnl_pct": es["total_pnl_dollars"] / 50_000.0 * 100.0 * scale,
        }).reset_index(drop=True)
        sim = PropFirmSimulator(account_size=50_000.0, point_value=5.0)
        print(f"\n  --- sizing: {contracts} ---")
        for key in ["apex_50k", "topstep_50k", "ftmo_50k"]:
            det = sim.run_deterministic(td, FIRM_PROFILES[key])
            mc = sim.run_monte_carlo(td, FIRM_PROFILES[key], n_simulations=5000)
            print(f"  {FIRM_PROFILES[key].name:<14} pass {mc.pass_rate_pct:5.1f}% (grade {mc.grade})  "
                  f"blow {mc.blow_rate_pct:5.1f}%  det-passed {det.passed}  "
                  f"det-DD ${det.max_drawdown_used:,.0f}  days {det.trading_days}")

    # ------------------------------------------------------------------ E28
    print("\n" + "=" * 78)
    print("E28 — Overnight block half-split (first 19-24h vs second 00-08h ET)")
    print("=" * 78)
    first = es[pd.to_datetime(es["entry_ts"]).dt.hour >= 19]
    second = es[pd.to_datetime(es["entry_ts"]).dt.hour < 8]
    for label, tdf in [("E22 first-half 19-24h", first), ("E22 second-half 00-08h", second)]:
        s = summarize(tdf, label)
        print(f"  {s['label']:<24} {s['trades']:>4} trades  WR{s['wr']:5.1f}%  PF{s['pf']:5.2f}  "
              f"Net${s['net']:>6.0f}  DD${s['dd']:>5.0f}  avgR{s.get('avg_r', 0):+.3f}")
    # hour detail within block
    es2 = es.copy()
    es2["eh"] = pd.to_datetime(es2["entry_ts"]).dt.hour
    g = es2.groupby("eh")["total_pnl_dollars"].agg(["count", "sum", "mean"])
    print("\n  Per-hour within block (n, net$, avg$):")
    for h, r in g.iterrows():
        print(f"    h{h:02d}  n={int(r['count']):>3}  net={r['sum']:+7.0f}  avg={r['mean']:+6.2f}")

    print("\nSaved data/derived/bb_e26_nq_e22_trades.csv")


if __name__ == "__main__":
    main()