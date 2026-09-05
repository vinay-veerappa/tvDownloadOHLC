"""What separated the winners from the losers -- on either side, same report.

Section 11 item 12. Three questions, in the order they are worth asking:

  1. WHERE did the losses come from -- session, exit reason, trade ordinal.
     Answerable from the trade list alone, so it works today on both sides.
  2. HOW did the losers behave -- did they go against you immediately (a bad
     entry) or run to target and come back (a bad exit)? Needs MAE/MFE.
  3. WHICH CRITERION was wrong -- the gate values on winners against the gate
     values on losers. Needs the decision log, and this is the one that finds a
     LOGICAL error rather than a sizing or timing one.

QUESTION 3 IS THE POINT AND IT IS WHY THE DECISION LOG EXISTS. A win rate tells
you a strategy is bad. "Winners entered with ADX median 24.8, losers with 15.9,
and the gate is set at 15" tells you which line to change. Nothing derivable
from a trade list can produce that sentence, because the trade list does not
record what the strategy was looking at.

MAE IS NOT OPTIONAL FOR QUESTION 2 AND IS NOT IN THE BRIDGE PAYLOAD TODAY.
`nt_backtest` iterates `SystemPerformance.AllTrades` -- where `Trade.MaeCurrency`
and `Trade.MfeCurrency` are both available -- and projects neither. The bridge's
own account-level path even carries a note saying MAE/MFE require exactly these
Trade objects. The fields are one line each; see section 5.2. Until they land,
question 2 reports what is missing instead of guessing, because an absent MAE
and a zero MAE are opposite findings.

THE JOIN. A decision log row and a fill are joined on `signal_name`, which is
`Execution.Name` on the NT8 side. Nearest-entry-time is the fallback and is
reported AS a fallback with its match distance: a decision is a BAR time and a
fill can be the next bar's open, so a nearest-time join is approximate by
construction and quietly mismatches under a cap or a queue. Unmatched rows are
COUNTED, never dropped -- a join that silently loses half the trades produces a
confident report about the half that matched.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from scripts.trading_framework.reporting.decision_log import gate_roster
from scripts.trading_framework.reporting.session_breakdown import (
    label_trades_by_session,
)

#: Below this many trades on a side, a median comparison is noise wearing a
#: number -- the same threshold and the same reasoning as `trade_ordinal.py`.
MIN_SAMPLE_PER_SIDE = 10

_PNL_COLS = ("total_pnl_usd", "pnl_usd", "realized_pnl", "profitCurrency")
_MAE_COLS = ("mae_usd", "maeCurrency", "mae_points", "maePoints")
_MFE_COLS = ("mfe_usd", "mfeCurrency", "mfe_points", "mfePoints")
_EXIT_COLS = ("exit_reason", "exitName", "exit_name")


def _first(df: pd.DataFrame, names) -> Optional[str]:
    return next((c for c in names if c in df.columns), None)


def _prep(trades: pd.DataFrame, time_col: str) -> Optional[pd.DataFrame]:
    if trades is None or trades.empty:
        return None
    pnl_col = _first(trades, _PNL_COLS)
    if pnl_col is None or time_col not in trades.columns:
        return None
    df = trades.copy()
    df["_pnl"] = pd.to_numeric(df[pnl_col], errors="coerce")
    df = df[df["_pnl"].notna()]
    if df.empty:
        return None
    t = pd.to_datetime(df[time_col], errors="coerce")
    if getattr(t.dt, "tz", None) is not None:
        t = t.dt.tz_convert("America/New_York")
    df["_entry"] = t
    df["_won"] = df["_pnl"] > 0
    df["_session"] = label_trades_by_session(df, time_col)
    exit_col = _first(df, _EXIT_COLS)
    df["_exit_reason"] = (df[exit_col].astype(str) if exit_col else "(not recorded)")
    # WHICH COLUMN WAS FOUND DETERMINES THE UNIT, so record it. `mae_usd` is
    # dollars and `mae_points` is points, and the two differ by the point value
    # -- 2 for MNQ, 20 for NQ. A table headed "Median MAE" with no unit invites
    # exactly the 10x confusion that put $20/pt P&L beside a $2/pt prop sim in
    # one run (section 1.3).
    for tag, names in (("_mae", _MAE_COLS), ("_mfe", _MFE_COLS)):
        c = _first(df, names)
        df[tag] = pd.to_numeric(df[c], errors="coerce") if c else np.nan
        df.attrs["{}_col".format(tag)] = c or ""
    if "exit_time" in df.columns:
        xt = pd.to_datetime(df["exit_time"], errors="coerce")
        if getattr(xt.dt, "tz", None) is not None:
            xt = xt.dt.tz_convert("America/New_York")
        df["_minutes"] = (xt - df["_entry"]).dt.total_seconds() / 60.0
    else:
        df["_minutes"] = np.nan
    return df


def loss_sources(trades: pd.DataFrame, *,
                 time_col: str = "entry_time") -> pd.DataFrame:
    """Question 1. Where the money went, by session and exit reason.

    Grouped on BOTH because they answer different things: a session tells you
    when not to trade, an exit reason tells you which mechanic is wrong. A
    strategy losing only on `Stop loss` in `NY_LUNCH` is a session problem; one
    losing on `time` everywhere is an exit problem.
    """
    df = _prep(trades, time_col)
    if df is None:
        return pd.DataFrame()
    rows = []
    for (sess, reason), sub in df.groupby(["_session", "_exit_reason"], observed=True):
        rows.append({
            "session": sess or "(unlabelled)",
            "exit_reason": reason,
            "trades": len(sub),
            "win_%": 100.0 * sub["_won"].mean(),
            "pnl_$": sub["_pnl"].sum(),
            "avg_$": sub["_pnl"].mean(),
        })
    return (pd.DataFrame(rows).sort_values("pnl_$").reset_index(drop=True))


def excursion_profile(trades: pd.DataFrame, *,
                      time_col: str = "entry_time") -> dict:
    """Question 2. Did the losers ever go your way?

    `losers_that_ran` is the number of losing trades whose MFE exceeded the
    average winner's P&L -- trades that WERE winners and were given back. That
    is an exit defect and no amount of entry filtering fixes it. Its opposite,
    losers with an MFE near zero, is an entry defect.
    """
    df = _prep(trades, time_col)
    if df is None:
        return {"available": False, "reason": "no trades, or no P&L column"}
    if df["_mae"].isna().all() and df["_mfe"].isna().all():
        return {"available": False,
                "reason": ("no MAE/MFE was measured for these trades. On the "
                           "PYTHON side, `simulate_bars_v1` does not return "
                           "excursions at all -- the adapter used to fabricate "
                           "zeros, which read as a measurement; it now emits NaN "
                           "(section 11 item 14). On the NT8 side they exist on "
                           "`Trade` and the bridge fields are added but not "
                           "deployed (section 5.6). An absent MAE and a zero MAE "
                           "are opposite findings, so nothing is inferred here.")}
    # A DEAD COLUMN IS NOT A MEASUREMENT. Measured 2026-09-05 on the live
    # `mean_reversion` run: `mae_points` and `mfe_points` are present and 0.0 on
    # all 16 trades, including 11 that exited on a stop. Reporting "median MAE
    # 0.0" from that reads as a finding about the strategy when it is a finding
    # about the pipeline -- the same shape as an alarm wired to a dead output.
    if ((df["_mae"].fillna(0) == 0).all() and (df["_mfe"].fillna(0) == 0).all()
            and len(df) > 1):
        return {"available": False,
                "reason": ("the MAE and MFE columns are present and identically "
                           "ZERO on all {} trades, which no real trade set "
                           "produces. The excursion stage is not populating "
                           "them; treat the columns as dead rather than as a "
                           "measurement.".format(len(df)))}
    win, loss = df[df["_won"]], df[~df["_won"]]
    avg_win = win["_pnl"].mean() if len(win) else np.nan
    mae_col = df.attrs.get("_mae_col", "")
    unit = ("$" if mae_col.endswith(("usd", "Currency"))
            else "pts" if mae_col.endswith(("points", "Points")) else "?")
    ran = (int((loss["_mfe"].abs() > abs(avg_win)).sum())
           if len(loss) and np.isfinite(avg_win) else 0)
    return {
        "available": True,
        "winners": len(win),
        "losers": len(loss),
        "avg_win_$": avg_win,
        "median_mae_winners": win["_mae"].median(),
        "median_mae_losers": loss["_mae"].median(),
        "median_mfe_losers": loss["_mfe"].median(),
        "losers_that_ran": ran,
        "mae_column": mae_col,
        "mae_unit": unit,
        "median_minutes_winners": win["_minutes"].median(),
        "median_minutes_losers": loss["_minutes"].median(),
    }


def gate_values_by_outcome(decisions: pd.DataFrame, trades: pd.DataFrame, *,
                           time_col: str = "entry_time") -> pd.DataFrame:
    """Question 3. Which criterion separated the winners from the losers.

    One row per gate: the median value it measured on winning entries against
    losing ones, and the threshold it was compared to. A `separation` far from
    zero on a gate whose threshold sits between the two medians is a gate set
    at the wrong level -- which is a LOGICAL error, and the only kind of finding
    here that names a line to change.

    A gate is reported only when both outcome groups clear MIN_SAMPLE_PER_SIDE.
    A median over four trades is not a finding.
    """
    empty = pd.DataFrame(columns=["gate", "threshold", "median_winners",
                                  "median_losers", "separation", "n_win", "n_loss"])
    if decisions is None or decisions.empty or trades is None or trades.empty:
        return empty
    ent = decisions[(decisions["decision"] == "ENTRY") & (decisions["gate"] != "")].copy()
    if ent.empty:
        return empty
    joined = _join(ent, trades, time_col)
    if joined is None or joined.empty:
        return empty
    joined["_v"] = pd.to_numeric(joined["gate_value"], errors="coerce")
    # Never rely on `_won` arriving as bool: see the cast in `_join`.
    joined["_won"] = joined["_won"].fillna(False).astype(bool)
    rows = []
    for name, sub in joined.groupby("gate"):
        w = sub.loc[sub["_won"], "_v"].dropna()
        l = sub.loc[~sub["_won"], "_v"].dropna()
        if len(w) < MIN_SAMPLE_PER_SIDE or len(l) < MIN_SAMPLE_PER_SIDE:
            continue
        thr = pd.to_numeric(sub["gate_threshold"], errors="coerce").median()
        rows.append({"gate": name, "threshold": thr,
                     "median_winners": w.median(), "median_losers": l.median(),
                     "separation": w.median() - l.median(),
                     "n_win": len(w), "n_loss": len(l)})
    if not rows:
        return empty
    out = pd.DataFrame(rows)
    return (out.reindex(out["separation"].abs().sort_values(ascending=False).index)
            .reset_index(drop=True))


def _join(entries: pd.DataFrame, trades: pd.DataFrame,
          time_col: str) -> Optional[pd.DataFrame]:
    """Decision rows to fills. Returns the frame with `_won` attached."""
    tr = _prep(trades, time_col)
    if tr is None:
        return None
    have_names = ("signal_name" in entries.columns
                  and entries["signal_name"].astype(str).str.len().gt(0).any())
    name_col = next((c for c in ("signal_name", "entry_name", "entryName")
                     if c in tr.columns), None)
    if have_names and name_col:
        m = entries.merge(tr[[name_col, "_won", "_pnl"]].rename(
            columns={name_col: "signal_name"}), on="signal_name", how="inner")
        m.attrs["join"] = "signal_name"
        m.attrs["unmatched"] = int(entries["seq"].nunique()
                                   - m["seq"].nunique()) if "seq" in m else 0
        return m
    # Fallback: nearest entry time. Approximate BY CONSTRUCTION -- a decision is
    # a bar time and a fill can be the next bar's open.
    # BOTH keys are forced to nanosecond resolution. pandas refuses a merge_asof
    # across resolutions ("incompatible merge keys ... us and ms"), and the two
    # sides genuinely differ: a decision timestamp is parsed from ISO text while
    # a trade timestamp comes from the engine's own frame.
    e = entries.copy()
    e["_bar"] = (pd.to_datetime(e["bar_time"], errors="coerce", utc=True)
                 .astype("datetime64[ns, UTC]"))
    t = tr.copy()
    t["_key"] = (pd.to_datetime(t["_entry"], errors="coerce", utc=True)
                 .astype("datetime64[ns, UTC]"))
    e = e.sort_values("_bar")
    t = t.sort_values("_key")
    m = pd.merge_asof(e, t[["_key", "_won", "_pnl"]], left_on="_bar",
                      right_on="_key", direction="nearest",
                      tolerance=pd.Timedelta("15min"))
    m.attrs["join"] = "nearest entry time (within 15min)"
    m.attrs["unmatched"] = int(m["_won"].isna().sum())
    m = m[m["_won"].notna()].copy()
    # CAST BACK TO BOOL. merge_asof with a tolerance introduces NaN, which
    # promotes the column to object -- and `~` on a non-bool Series is BITWISE,
    # so `~df["_won"]` silently becomes -1/-2 instead of raising. Used as a
    # positional mask that would have selected the wrong rows rather than
    # failing, which is the worse of the two outcomes.
    m["_won"] = m["_won"].astype(bool)
    return m


def render_win_loss(trades: pd.DataFrame, decisions: Optional[pd.DataFrame] = None, *,
                    time_col: str = "entry_time") -> str:
    """ASCII only -- a cp1252 console cannot encode an em-dash or a <= sign."""
    L = ["### What separated the winners from the losers", ""]
    df = _prep(trades, time_col)
    if df is None:
        return ("### What separated the winners from the losers\n\n_Not "
                "available: the trade frame is empty or carries no `{}` / P&L "
                "column._\n".format(time_col))
    L.append("{} trades, {} winners ({:.1f}%), net ${:,.0f}.".format(
        len(df), int(df["_won"].sum()), 100.0 * df["_won"].mean(), df["_pnl"].sum()))

    # A STOP-LOSS EXIT THAT BOOKED A PROFIT IS NOT A TRADE, it is a geometry
    # defect: a stop on the WRONG SIDE of entry is hit immediately and pays.
    # Surfaced first because every number below it is computed over these rows
    # too, so a reader who does not know they are there reads a fiction.
    nonsense = df[df["_won"] & df["_exit_reason"].str.contains(
        "stop", case=False, na=False)]
    if not nonsense.empty:
        L += ["", "**{} trade(s) exited on a STOP and booked a PROFIT** "
                  "(${:,.0f} total). A stop on the wrong side of entry is filled "
                  "immediately and pays out; these are geometry defects, not "
                  "trades, and they inflate every figure below. Cross-check the "
                  "`signal_geometry` criterion in the promotion checklist."
                  .format(len(nonsense), nonsense["_pnl"].sum())]

    # THE FUNNEL GAP. The decision log records the HUNTER's gates. The engine
    # applies its own -- an entry window, a per-day trade cap, a
    # consecutive-loser pause, a daily loss limit -- and none of them is in the
    # log. Measured on `mean_reversion`: 3,188 hunter entries became 16 trades,
    # a 200:1 reduction the log does not explain. Naming the gap beats leaving a
    # reader to notice that two numbers in one report disagree by two orders of
    # magnitude.
    if decisions is not None and not decisions.empty:
        n_ent = int(decisions.loc[decisions["decision"] == "ENTRY", "seq"].nunique())
        if n_ent > len(df):
            L += ["", "The decision log records {:,} hunter entr(ies) and this "
                      "trade set has {:,}. The difference is the ENGINE's own "
                      "gates -- entry window, per-day cap, consecutive-loser "
                      "pause, daily loss limit -- which are not instrumented "
                      "(section 11 item 13). Rejections below are the hunter's "
                      "only.".format(n_ent, len(df))]

    src = loss_sources(trades, time_col=time_col)
    if not src.empty:
        L += ["", "#### 1. Where the losses came from", "",
              "Sorted worst first. Session says WHEN not to trade; exit reason "
              "says WHICH mechanic is wrong.", "",
              "| Session | Exit reason | Trades | Win% | P&L$ | Avg$ |",
              "|---|---|---:|---:|---:|---:|"]
        for _, r in src.head(15).iterrows():
            L.append("| {} | `{}` | {} | {:.1f} | {:,.0f} | {:,.0f} |".format(
                r["session"], r["exit_reason"], int(r["trades"]), r["win_%"],
                r["pnl_$"], r["avg_$"]))

    ex = excursion_profile(trades, time_col=time_col)
    L += ["", "#### 2. How the losers behaved", ""]
    if not ex.get("available"):
        L.append("_Not available: {}_".format(ex["reason"]))
    else:
        def f(v, spec="{:,.1f}"):
            return "--" if v is None or not np.isfinite(v) else spec.format(v)
        L += ["| | Winners | Losers |", "|---|---:|---:|",
              "| Trades | {} | {} |".format(ex["winners"], ex["losers"]),
              "| Median MAE ({}) | {} | {} |".format(
                  ex.get("mae_unit", "?"), f(ex["median_mae_winners"]),
                  f(ex["median_mae_losers"])),
              "| Median minutes held | {} | {} |".format(
                  f(ex["median_minutes_winners"]), f(ex["median_minutes_losers"])),
              "",
              "{} losing trade(s) had an MFE above the average winner "
              "(${}) -- those were winners given back, which is an EXIT defect "
              "and no entry filter fixes it.".format(
                  ex["losers_that_ran"], f(ex["avg_win_$"], "{:,.0f}"))]

    L += ["", "#### 3. Which criterion was wrong", ""]
    gv = gate_values_by_outcome(decisions, trades, time_col=time_col) \
        if decisions is not None else pd.DataFrame()
    if gv.empty:
        if decisions is None or decisions.empty:
            L.append("_Not available: no decision log. This is the only section "
                     "that can name a LINE to change, and it needs the strategy "
                     "to report its criteria (STRATEGY_WORKFLOW.md section 5.1)._")
        else:
            L.append("_No gate cleared {} entries on both sides of the outcome "
                     "split. A median over fewer is noise wearing a number._"
                     .format(MIN_SAMPLE_PER_SIDE))
    else:
        L += ["Median gate value on winning entries against losing ones. A large "
              "`separation` with the threshold sitting BETWEEN the two medians is "
              "a gate set at the wrong level.", "",
              "| Gate | Threshold | Median winners | Median losers | Separation | n win | n loss |",
              "|---|---:|---:|---:|---:|---:|---:|"]
        for _, r in gv.iterrows():
            def g(v):
                return "--" if v is None or not np.isfinite(v) else "{:,.3g}".format(v)
            L.append("| `{}` | {} | {} | {} | {} | {} | {} |".format(
                r["gate"], g(r["threshold"]), g(r["median_winners"]),
                g(r["median_losers"]), g(r["separation"]),
                int(r["n_win"]), int(r["n_loss"])))

    if decisions is not None and not decisions.empty:
        roster = gate_roster(decisions)
        if not roster.empty:
            top = roster.iloc[0]
            L += ["", "Most frequent sole blocker: `{}` ({} setup(s) blocked by "
                      "it alone).".format(top["gate"], int(top["blocked_alone"]))]
    return "\n".join(L) + "\n"
