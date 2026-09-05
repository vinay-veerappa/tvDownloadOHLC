"""Per-session performance, keyed on the FROZEN session partition.

WHICH SESSIONS CARRY THE EDGE is the question this answers, and until now the
data could not answer it: `session_tagger`'s legacy labels are RTH-only, so
GLOBEX, ASIA and LONDON all collapsed into "pre_market". Three of the six
sessions this bot trades were unlabelled, not merely unreported.

Every rate here is computed on the SAME partition (config/trading_defaults.json
-> sessions.windows), which is validated to tile the day exactly once. That is
what makes the rows sum to the total: an overlapping session set would double
count trades, and a gapped one would drop them while the total still looked
right -- the worse of the two, because nothing looks wrong.

SCALE-FREE COLUMNS ONLY for the comparison itself. EV_R and PF do not move when
position size does, so two sessions are comparable even if one was traded with a
different contract count. Dollars are reported beside them, never as the ranking
key -- the same reasoning as section 7.2's Combined Edge correction.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from scripts.trading_framework.config.defaults import session_windows


def _minutes(ts: pd.Series) -> np.ndarray:
    t = pd.to_datetime(ts, errors="coerce", utc=False)
    if getattr(t.dt, "tz", None) is not None:
        t = t.dt.tz_convert("America/New_York")
    return (t.dt.hour * 60 + t.dt.minute).to_numpy()


def label_trades_by_session(trades: pd.DataFrame,
                            time_col: str = "entry_time") -> pd.Series:
    """Which frozen session did each trade ENTER in?

    Entry, not exit, deliberately: the session is a property of the setup, and
    an ASIA entry that runs into LONDON is still an ASIA trade. A trade labelled
    by its exit would credit the edge to whichever session the stop happened to
    land in.
    """
    if trades is None or trades.empty or time_col not in trades.columns:
        return pd.Series(dtype="object")
    mins = _minutes(trades[time_col])
    out = np.full(len(trades), "", dtype=object)
    for w in session_windows():
        if w.wraps:
            mask = (mins >= w.start_min) | (mins < w.end_min)
        else:
            mask = (mins >= w.start_min) & (mins < w.end_min)
        out[mask] = w.name
    return pd.Series(out, index=trades.index, name="session_name")


def session_stats(trades: pd.DataFrame, *,
                  time_col: str = "entry_time",
                  r_col: Optional[str] = None) -> pd.DataFrame:
    """One row per session that produced at least one trade, plus ALL."""
    if trades is None or trades.empty:
        return pd.DataFrame()

    df = trades.copy()
    df["_session"] = label_trades_by_session(df, time_col)

    pnl = None
    for c in ("total_pnl_usd", "pnl_usd", "realized_pnl"):
        if c in df.columns:
            pnl = pd.to_numeric(df[c], errors="coerce")
            break
    pts = None
    for c in ("total_points", "points"):
        if c in df.columns:
            pts = pd.to_numeric(df[c], errors="coerce")
            break
    if r_col and r_col in df.columns:
        r = pd.to_numeric(df[r_col], errors="coerce")
    elif pnl is not None:
        # R in the absence of a recorded initial risk: normalise each trade by
        # the MEAN ABSOLUTE loss of the set. Stated as an approximation because
        # it is one -- a per-trade initial risk is the correct denominator and
        # is not in this frame.
        losses = pnl[pnl < 0].abs()
        denom = losses.mean() if len(losses) else np.nan
        r = pnl / denom if denom and denom > 0 else pd.Series(np.nan, index=df.index)
    else:
        r = pd.Series(np.nan, index=df.index)
    df["_r"] = r

    rows = []
    order = [w.name for w in session_windows()]

    def _row(label: str, sub: pd.DataFrame) -> dict:
        n = len(sub)
        wins = sub["_r"] > 0 if sub["_r"].notna().any() else None
        if pnl is not None:
            p = pd.to_numeric(sub[pnl.name], errors="coerce") if pnl.name in sub else None
        else:
            p = None
        if p is None:
            p = pd.Series(dtype=float)
        gp = p[p > 0].sum() if len(p) else np.nan
        gl = -p[p < 0].sum() if len(p) else np.nan
        return {
            "session": label,
            "trades": n,
            "share_%": np.nan,           # filled after the total is known
            "win_%": (100.0 * (p > 0).mean() if len(p) else np.nan),
            "PF": (gp / gl if gl and gl > 0 else np.nan),
            "EV_R": sub["_r"].mean(),
            "points": (pd.to_numeric(sub[pts.name], errors="coerce").sum()
                       if pts is not None and pts.name in sub else np.nan),
            "pnl_$": (p.sum() if len(p) else np.nan),
        }

    for name in order:
        sub = df[df["_session"] == name]
        if len(sub):
            rows.append(_row(name, sub))
    if not rows:
        return pd.DataFrame()
    rows.append(_row("ALL", df))

    out = pd.DataFrame(rows)
    total = out.loc[out["session"] == "ALL", "trades"].iloc[0]
    out["share_%"] = 100.0 * out["trades"] / total if total else np.nan
    return out


def render_session_breakdown(trades: pd.DataFrame, *,
                             time_col: str = "entry_time") -> str:
    """A markdown table. Returns a stated reason, never an empty string."""
    stats = session_stats(trades, time_col=time_col)
    if stats.empty:
        return ("### Per-session breakdown\n\n"
                "_Not available: the trade frame is empty or carries no "
                "`{}` column._\n".format(time_col))

    L = ["### Per-session breakdown",
         "",
         "Keyed on the frozen session partition "
         "(`config/trading_defaults.json` -> `sessions.windows`). Rows sum to "
         "ALL because that partition tiles the day exactly once. **Rank on "
         "`EV_R` and `PF`, not on `pnl_$`** -- only the first two are "
         "invariant to position size.",
         "",
         "| Session | Trades | Share | Win% | PF | EV_R | Points | P&L $ |",
         "|---|---:|---:|---:|---:|---:|---:|---:|"]

    def f(v, spec="{:.2f}"):
        return "--" if v is None or (isinstance(v, float) and not np.isfinite(v)) \
            else spec.format(v)

    for _, r in stats.iterrows():
        bold = r["session"] == "ALL"
        name = "**{}**".format(r["session"]) if bold else r["session"]
        L.append("| {} | {} | {} | {} | {} | {} | {} | {} |".format(
            name, int(r["trades"]), f(r["share_%"], "{:.1f}%"),
            f(r["win_%"], "{:.1f}"), f(r["PF"]), f(r["EV_R"]),
            f(r["points"], "{:.1f}"), f(r["pnl_$"], "{:,.0f}")))

    zero = [w.name for w in session_windows()
            if w.name not in set(stats["session"])]
    if zero:
        L += ["", "_No trades in: {}. A session absent from the table above "
                  "took zero trades; it is not a missing measurement._"
                  .format(", ".join(zero))]
    return "\n".join(L) + "\n"
