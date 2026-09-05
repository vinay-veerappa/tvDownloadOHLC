"""Where should the trade cap be? Read it off the data instead of guessing.

A cap is an OUTPUT of analysis, not a frozen input (`trading_defaults.json`
`risk.analysisDerived`). `sessions.yaml` carried `max_trades_per_day: 3` with no
recorded basis, and the frozen document no longer imposes one -- so something has
to produce the number.

This reports, by trade ORDINAL within the day and within the session:

    marginal  -- the Nth trade's own EV_R and win rate. "The 4th trade of the day
                 loses money" is a reason to cap at 3.
    cumulative-- EV_R over trades 1..N. Answers the different question of which
                 cap maximises the total, which is not always the same N.

BOTH, because they disagree. A 4th trade with slightly negative EV still raises
the cumulative total if it is rare, and a marginal-only read would cut it.

A SUGGESTED CAP IS PRINTED WITH ITS SAMPLE SIZE, always. The largest N whose
marginal EV_R is positive is a suggestion drawn from in-sample data; on five
observations it is noise wearing a number. The report says how many trades each
ordinal rests on so the reader can refuse it.

Ordinals are computed on ENTRY ORDER within the calendar day (ET) and within the
frozen session (section 1.3), so "3rd trade of NY_AM" means the same thing in every
report.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from scripts.trading_framework.reporting.session_breakdown import (
    label_trades_by_session,
)

MIN_SAMPLE_FOR_A_CAP = 20


def _prep(trades: pd.DataFrame, time_col: str) -> Optional[pd.DataFrame]:
    if trades is None or trades.empty or time_col not in trades.columns:
        return None
    df = trades.copy()
    t = pd.to_datetime(df[time_col], errors="coerce")
    if getattr(t.dt, "tz", None) is not None:
        t = t.dt.tz_convert("America/New_York")
    df["_entry"] = t
    df["_day"] = t.dt.date
    df["_session"] = label_trades_by_session(df, time_col)

    pnl = None
    for c in ("total_pnl_usd", "pnl_usd", "realized_pnl"):
        if c in df.columns:
            pnl = pd.to_numeric(df[c], errors="coerce")
            break
    if pnl is None:
        return None
    df["_pnl"] = pnl
    losses = pnl[pnl < 0].abs()
    denom = losses.mean() if len(losses) else np.nan
    # Same approximation as the session report, and stated as one: a per-trade
    # initial risk is the correct denominator and is not carried in this frame.
    df["_r"] = pnl / denom if denom and denom > 0 else np.nan

    df = df.sort_values("_entry")
    df["ord_day"] = df.groupby("_day").cumcount() + 1
    df["ord_session"] = df.groupby(["_day", "_session"], observed=True).cumcount() + 1
    return df


def ordinal_stats(trades: pd.DataFrame, *, scope: str = "day",
                  time_col: str = "entry_time") -> pd.DataFrame:
    """One row per ordinal, marginal and cumulative. `scope` is "day" or "session"."""
    df = _prep(trades, time_col)
    if df is None:
        return pd.DataFrame()
    col = "ord_day" if scope == "day" else "ord_session"

    rows = []
    for n in sorted(df[col].unique()):
        at = df[df[col] == n]
        upto = df[df[col] <= n]
        rows.append({
            "n": int(n),
            "trades_at_n": len(at),
            "win_%_at_n": 100.0 * (at["_pnl"] > 0).mean(),
            "EV_R_at_n": at["_r"].mean(),
            "pnl_$_at_n": at["_pnl"].sum(),
            "trades_upto_n": len(upto),
            "EV_R_upto_n": upto["_r"].mean(),
            "pnl_$_upto_n": upto["_pnl"].sum(),
        })
    return pd.DataFrame(rows)


def suggested_cap(stats: pd.DataFrame) -> dict:
    """Largest N with positive marginal EV_R, WITH the evidence for it."""
    if stats.empty:
        return {"cap": None, "reason": "no trades"}
    positive = stats[stats["EV_R_at_n"] > 0]
    if positive.empty:
        return {"cap": 0, "reason": "no ordinal has positive marginal EV_R",
                "sample": int(stats["trades_at_n"].sum())}
    cap = int(positive["n"].max())
    sample = int(stats.loc[stats["n"] == cap, "trades_at_n"].iloc[0])
    best_cum = stats.loc[stats["EV_R_upto_n"].idxmax(), "n"]
    return {
        "cap": cap,
        "sample": sample,
        "trustworthy": sample >= MIN_SAMPLE_FOR_A_CAP,
        "best_cumulative_n": int(best_cum),
        "reason": ("largest ordinal with positive marginal EV_R"
                   if sample >= MIN_SAMPLE_FOR_A_CAP else
                   "largest ordinal with positive marginal EV_R, but it rests on "
                   "{} trade(s) -- below the {} needed to be worth acting on"
                   .format(sample, MIN_SAMPLE_FOR_A_CAP)),
    }


def render_trade_ordinal(trades: pd.DataFrame, *,
                         time_col: str = "entry_time") -> str:
    L = ["### Where to cap trades",
         "",
         "A cap is an **output** of this table, not a frozen setting "
         "(`trading_defaults.json` -> `risk.analysisDerived`). `at n` is the Nth "
         "trade's OWN contribution; `upto n` is the total if you capped there. "
         "They answer different questions and can disagree."]

    any_rows = False
    for scope, label in (("day", "per calendar day"), ("session", "per session")):
        stats = ordinal_stats(trades, scope=scope, time_col=time_col)
        if stats.empty:
            continue
        any_rows = True
        cap = suggested_cap(stats)
        L += ["", "#### Ordinal {}".format(label), "",
              "| N | Trades at N | Win% at N | EV_R at N | P&L$ at N | Trades <=N | EV_R <=N | P&L$ <=N |",
              "|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for _, r in stats.iterrows():
            def f(v, spec="{:.2f}"):
                return "--" if v is None or (isinstance(v, float) and not np.isfinite(v)) \
                    else spec.format(v)
            L.append("| {} | {} | {} | {} | {} | {} | {} | {} |".format(
                int(r["n"]), int(r["trades_at_n"]), f(r["win_%_at_n"], "{:.1f}"),
                f(r["EV_R_at_n"]), f(r["pnl_$_at_n"], "{:,.0f}"),
                int(r["trades_upto_n"]), f(r["EV_R_upto_n"]),
                f(r["pnl_$_upto_n"], "{:,.0f}")))
        if cap.get("cap") is None:
            L += ["", "_No cap suggested: {}._".format(cap["reason"])]
        else:
            verdict = ("**suggested cap {}**".format(cap["cap"])
                       if cap.get("trustworthy") else
                       "cap {} -- **do not act on this yet**".format(cap["cap"]))
            L += ["", "{} ({}). Best cumulative EV_R is at N={}."
                      .format(verdict, cap["reason"], cap["best_cumulative_n"])]
    if not any_rows:
        return ("### Where to cap trades\n\n_Not available: the trade frame is "
                "empty, or carries no `{}` / P&L column._\n".format(time_col))
    return "\n".join(L) + "\n"
