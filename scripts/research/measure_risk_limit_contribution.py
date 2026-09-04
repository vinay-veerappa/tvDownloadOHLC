r"""How much of the reported edge is the RISK LIMITS rather than the strategy?

WHY. The research pipeline's default engine (`--engine nt8_parity`, ADR-024) on a
clean out-of-sample NQ1 window reported profit factor 31.6, Sharpe 9.38, win rate
76.3% -- from 38 trades with $75,794 gross profit against only $2,395 gross loss.
That is not an edge, it is a defect signature.

The suspicion is arithmetic, from the execution policy the run record now stores:
`daily_max_loss = 400.0` with 2 NQ contracts at $20/point means a single ~10-point
adverse move ends the trading day, because `NT8ParityEngine` gates new entries on
`hit_daily_max = (daily_pnl <= -self.daily_max_loss)`. Losing days are therefore
CAPPED at roughly $400 while winning days run uncapped. $2,395 / $400 is about six
losing days -- close enough to be worth measuring rather than assuming.

If that is what is happening, the profit factor is a property of the risk manager,
not of the signal, and it will not survive relaxing the limit. NT8 would only
reproduce it with byte-identical RiskManagerBase settings, which is exactly the
kind of silent configuration divergence this whole workstream is about.

WHAT THIS MEASURES. The same signals and the same bars through the same engine,
varying ONE risk limit at a time, plus an "all relaxed" arm that shows what the
raw signal does. Per-day P&L is reported alongside, because the aggregate profit
factor is precisely the statistic that hides an asymmetric daily cap.

Run:
  set PYTHONIOENCODING=utf-8
  .venv\Scripts\python.exe -m scripts.research.measure_risk_limit_contribution
  .venv\Scripts\python.exe -m scripts.research.measure_risk_limit_contribution --params-from <run_record.json>
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from scripts.libs_py.data.loader import DataLoader
from scripts.trading_framework.config.config_loader import load_config
from scripts.trading_framework.core.nt8_parity_backtester import NT8ParityBacktester
from scripts.trading_framework.strategies.registry import get_strategy

# The policy the pipeline actually ran under, as recorded in run_record.json's
# `executionPolicy`. Reproduced here rather than re-derived from config, so this
# measurement is anchored to the run it is explaining.
BASELINE_POLICY = {
    "account_size": 50000.0,
    "max_trades_per_day": 3,
    "max_consecutive_losers": 2,
    "pause_minutes": 30,
    "hard_stop_losers": 3,
    "daily_max_loss": 400.0,
    "contracts": 2,
}
BASELINE_RISK = {
    "ticker": "NQ1",
    "queen_bps": 10.0,
    "runner_bps": 30.0,
    "earliest_entry_hhmm": 945,
    "latest_entry_hhmm": 1530,
    "flatten_hhmm": 1555,
    "filter_lunch": True,
}

# "Off" values, not merely large ones, so an arm cannot be quietly still-binding.
UNLIMITED = {
    "daily_max_loss": 1e12,
    "max_trades_per_day": 10_000,
    "max_consecutive_losers": 10_000,
    "hard_stop_losers": 10_000,
}


def summarise(trades: pd.DataFrame, account_size: float) -> dict:
    if trades is None or trades.empty:
        return {"trades": 0}
    pnl = trades["total_pnl_usd"].to_numpy(dtype=float)
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    gp, gl = wins.sum(), -losses.sum()

    day = pd.to_datetime(trades["exit_time"]).dt.date
    daily = trades.groupby(day)["total_pnl_usd"].sum()
    down = daily[daily < 0]

    return {
        "trades": int(len(trades)),
        "win_rate_pct": 100.0 * float((pnl > 0).mean()),
        "gross_profit": float(gp),
        "gross_loss": float(gl),
        "net": float(pnl.sum()),
        "profit_factor": float(gp / gl) if gl > 0 else float("inf"),
        "avg_win": float(wins.mean()) if wins.size else 0.0,
        "avg_loss": float(losses.mean()) if losses.size else 0.0,
        "trading_days": int(daily.size),
        "losing_days": int(down.size),
        "worst_day": float(daily.min()) if daily.size else 0.0,
        "best_day": float(daily.max()) if daily.size else 0.0,
        "mean_losing_day": float(down.mean()) if down.size else 0.0,
        "_daily": daily,
    }


def run_arm(signals, df, policy: dict, risk: dict) -> dict:
    engine = NT8ParityBacktester(**policy)
    result = engine.run(signals, df, {**risk, **{k: v for k, v in policy.items()
                                                 if k != "account_size"}})
    trades = result.get("trades_detailed", pd.DataFrame())
    out = summarise(trades, policy["account_size"])
    out["_alignment"] = result.get("signal_alignment", {})
    return out


def report_daily_cap_bite(s: dict, cap: float) -> str:
    """How close are losing days to the cap? That is the whole question."""
    daily = s.get("_daily")
    if daily is None or daily.empty:
        return "no days"
    down = daily[daily < 0]
    if down.empty:
        return "NO losing days at all"
    near = int((down <= -cap * 0.9).sum())
    return ("{} losing day(s), {} of them at/below 90% of the ${:,.0f} cap "
            "(mean losing day ${:,.0f}, worst ${:,.0f})".format(
                len(down), near, cap, down.mean(), down.min()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default="NQ1")
    ap.add_argument("--strategy", default="mean_reversion")
    ap.add_argument("--oos-start", default="2024-01-01")
    ap.add_argument("--params-from", default=None,
                    help="run_record.json to take strategy params and policy from")
    ap.add_argument("--params", default=None, help="JSON dict of strategy params")
    args = ap.parse_args()

    policy = dict(BASELINE_POLICY)
    risk = dict(BASELINE_RISK)
    params = {"bb_period": 43, "bb_std": 1.7063515345656386,
              "sl_atr_mult": 1.5226420470168263}

    if args.params_from:
        rec = json.load(open(args.params_from, encoding="utf-8"))
        params = rec["strategy"]["params"] or params
        ep = rec.get("executionPolicy") or {}
        for k in policy:
            if k in ep:
                policy[k] = ep[k]
        for k in risk:
            if k in ep:
                risk[k] = ep[k]
        print(f"policy and params taken from {args.params_from}")
    if args.params:
        params = json.loads(args.params)

    risk["ticker"] = args.ticker

    df = DataLoader(load_config()).load_enriched(args.ticker)
    cut = pd.Timestamp(args.oos_start)
    if df.index.tz is not None and cut.tz is None:
        cut = cut.tz_localize(df.index.tz)
    df_report = df[df.index >= cut]

    strategy = get_strategy(args.strategy, args.ticker)
    all_signals = strategy.generate_signals(df, params)
    st = pd.to_datetime(all_signals["signal_time"])
    signals = all_signals[(st >= df_report.index[0]) & (st <= df_report.index[-1])]

    print(f"{args.ticker} {args.strategy}  params={params}")
    print(f"report window: {len(df_report):,} bars "
          f"({df_report.index[0]} -> {df_report.index[-1]})")
    print(f"signals in window: {len(signals):,}\n")

    arms = [("baseline (as the pipeline ran it)", {}),
            ("daily_max_loss OFF", {"daily_max_loss": UNLIMITED["daily_max_loss"]}),
            ("max_trades_per_day OFF", {"max_trades_per_day": UNLIMITED["max_trades_per_day"]}),
            ("consecutive-loser rules OFF",
             {"max_consecutive_losers": UNLIMITED["max_consecutive_losers"],
              "hard_stop_losers": UNLIMITED["hard_stop_losers"]}),
            ("ALL risk limits OFF", dict(UNLIMITED))]

    results = []
    hdr = (f"{'arm':38} | {'trades':>7} | {'WR%':>6} | {'PF':>8} | "
           f"{'net $':>12} | {'gross loss $':>13} | {'days':>5} | {'loss days':>9}")
    print(hdr)
    print("-" * len(hdr))
    for name, override in arms:
        s = run_arm(signals, df_report, {**policy, **override}, risk)
        results.append((name, s))
        if not s.get("trades"):
            print(f"{name:38} | {'0':>7} |" + " " * 10 + "no trades")
            continue
        pf = s["profit_factor"]
        print(f"{name:38} | {s['trades']:>7} | {s['win_rate_pct']:>5.1f}% | "
              f"{pf:>8.2f} | {s['net']:>12,.0f} | {s['gross_loss']:>13,.0f} | "
              f"{s['trading_days']:>5} | {s['losing_days']:>9}")

    base = results[0][1]
    print("\n--- does the daily cap explain the gross loss? ---")
    print("baseline:", report_daily_cap_bite(base, policy["daily_max_loss"]))
    if base.get("trades"):
        implied = base["gross_loss"] / policy["daily_max_loss"]
        print(f"gross loss / cap = {base['gross_loss']:,.0f} / "
              f"{policy['daily_max_loss']:,.0f} = {implied:.1f} cap-equivalents "
              f"against {base['losing_days']} actual losing day(s)")

    no_cap = results[1][1]
    if base.get("trades") and no_cap.get("trades"):
        print("\n--- what survives with the cap removed? ---")
        print(f"profit factor {base['profit_factor']:.2f} -> {no_cap['profit_factor']:.2f}")
        print(f"gross loss    ${base['gross_loss']:,.0f} -> ${no_cap['gross_loss']:,.0f}")
        print(f"net           ${base['net']:,.0f} -> ${no_cap['net']:,.0f}")
        if no_cap["profit_factor"] < base["profit_factor"] * 0.5:
            print("\n  *** The reported profit factor is largely a property of the")
            print("      daily loss limit, not of the signal. NT8 will only reproduce")
            print("      it with identical RiskManagerBase settings. ***")

    allo = results[-1][1]
    if allo.get("trades"):
        print("\n--- the raw signal, with no risk manager at all ---")
        print(f"{allo['trades']} trades, WR {allo['win_rate_pct']:.1f}%, "
              f"PF {allo['profit_factor']:.2f}, net ${allo['net']:,.0f}, "
              f"avg win ${allo['avg_win']:,.0f} vs avg loss ${allo['avg_loss']:,.0f}")
        print("This is the number a strategy comparison should be ranking on.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
