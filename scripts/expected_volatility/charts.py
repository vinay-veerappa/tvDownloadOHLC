"""Figures for the Expected Volatility report, including the validation set.

Every figure is drawn from the same `features.build_sessions()` frame the
numbers come from, so a chart cannot disagree with the table beside it.

The validation figures (`recent_sessions`, `recent_calibration`,
`session_detail`) are the answer to "how do we know any of this is true". The
ladder makes a falsifiable claim — *this rung is touched 50% of the time* — so
validation is not a matter of opinion: draw the rungs on days the ladder never
saw, count the touches, and compare to what was promised.

Usage
-----
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.charts
"""

from __future__ import annotations

import argparse
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from zoneinfo import ZoneInfo

from .features import (
    DATA, FIG_DIR, HOLDOUT_START, ODTE_START, TARGET_P, _read, _to_et,
    build_sessions, folds, frame_for, percentile_ladder,
)

ET = ZoneInfo("America/New_York")
UP, DN, ACC, MUT, BG = "#1b7f4b", "#b3341f", "#1f4e9c", "#7a7a7a", "#ffffff"
plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linestyle": ":",
    "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold",
    "figure.dpi": 130,
})


def _save(fig, name: str) -> str:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / name
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  {path.name}")
    return name


# --------------------------------------------------------------------------
def fig_calibration(ses) -> str:
    """THE validation chart: promised P(touch) vs realised, on the holdout."""
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.2), sharey=True)
    for ax, anchor in zip(axes, ("prev_close", "rth_open")):
        f = frame_for(ses.df, anchor, "vix_prev_close")
        tr, te = folds(f)
        lad = percentile_ladder(tr)
        ax.plot([0, 1], [0, 1], color=MUT, lw=1, ls="--", label="perfect")
        for side, col, c in (("up", "c_up", UP), ("dn", "c_dn", DN)):
            xs, ys = [], []
            for i, p in enumerate(TARGET_P):
                xs.append(p)
                ys.append(float((te[side] >= lad[col][i]).mean()))
            ax.plot(xs, ys, "o-", color=c, ms=5, lw=1.4, label=f"{side} rungs")
            err = np.mean([abs(a - b) for a, b in zip(xs, ys)])
        ax.set_xlabel("promised P(touch)")
        ax.set_title(f"{anchor}   (n={len(te)} holdout sessions)")
        ax.set_xlim(0, 0.9)
        ax.set_ylim(0, 0.9)
        ax.legend(frameon=False, fontsize=8)
    axes[0].set_ylabel("realised P(touch), holdout")
    fig.suptitle("Ladder calibration — fit on train, measured on days it never saw",
                 fontsize=11, fontweight="bold", y=1.02)
    return _save(fig, "fig_calibration.png")


def fig_ladder_construction(ses) -> str:
    """How a rung is placed: invert the excursion CDF at the target."""
    f = frame_for(ses.df, "rth_open", "vix_prev_close")
    tr, _ = folds(f)
    lad = percentile_ladder(tr)
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    for side, col, c, lbl in (("up", "c_up", UP, "upside"), ("dn", "c_dn", DN, "downside")):
        xs = np.linspace(0, 2.2, 400)
        ys = [(tr[side] >= x).mean() for x in xs]
        ax.plot(xs, ys, color=c, lw=1.8, label=f"P(excursion >= c), {lbl}")
        for i, p in enumerate(TARGET_P):
            cc = lad[col][i]
            ax.plot([cc, cc], [0, p], color=c, lw=0.7, alpha=0.45)
            ax.plot([0, cc], [p, p], color=c, lw=0.7, alpha=0.45)
            ax.plot([cc], [p], "o", color=c, ms=4)
    for m, lbl in ((0.25, "Pine 0.25"), (0.5, "0.5"), (1.0, "1.0"), (1.5, "1.5")):
        ax.axvline(m, color=MUT, lw=0.9, ls="--", alpha=0.7)
        ax.text(m, 0.93, lbl, rotation=90, fontsize=7, color=MUT,
                ha="right", va="top")
    ax.set_xlabel("c  (level = S * (1 +/- c * VIX/sqrt(252)/100))")
    ax.set_ylabel("P(touch)")
    ax.set_xlim(0, 2.0)
    ax.set_ylim(0, 1.0)
    ax.set_title("The ladder IS the excursion CDF, read backwards\n"
                 "dashed = Pine's fixed rungs, which land at arbitrary probabilities")
    ax.legend(frameon=False, fontsize=8)
    return _save(fig, "fig_ladder_construction.png")


def fig_gap(ses) -> str:
    """Why the anchor matters, in one picture."""
    f = frame_for(ses.df, "prev_close", "vix_prev_close").dropna(subset=["gap_ev"])
    g = f["gap_ev"]
    fig, ax = plt.subplots(figsize=(7.6, 4.0))
    ax.hist(g.clip(-2, 2), bins=70, color=ACC, alpha=0.75, edgecolor="none")
    for c, lbl in ((0.25, "c=0.25"), (0.50, "c=0.50"), (1.0, "c=1.0")):
        pct = float((g.abs() > c).mean()) * 100
        for sgn in (-1, 1):
            ax.axvline(sgn * c, color=DN if c == 0.25 else MUT, lw=1.1, ls="--")
        ax.text(c, ax.get_ylim()[1] * (0.95 - 0.11 * [0.25, 0.5, 1.0].index(c)),
                f"  |gap| > {lbl.split('=')[1]}  on {pct:.1f}% of days",
                fontsize=8, color=DN if c == 0.25 else MUT, va="top")
    ax.set_xlabel("overnight gap (09:30 open - prior close), in EV units")
    ax.set_ylabel("sessions")
    ax.set_title("The overnight gap has already spent the inner rungs\n"
                 f"n={len(g)} sessions since {ODTE_START}")
    return _save(fig, "fig_gap.png")


def fig_ratio_over_time(ticker: str = "ES1") -> str:
    """Miscalibration is not a recent accident."""
    bars = _to_et(_read(DATA / f"{ticker}_1m.parquet"))
    vol = _to_et(_read(DATA / "VIX_1d.parquet"))
    pre16 = bars.between_time("00:00", "15:59")
    settle = pre16.groupby(pre16.index.date)["close"].last()
    rth = bars.between_time("09:30", "15:59")
    g = rth.groupby(rth.index.date)
    s = pd.DataFrame({"high": g["high"].max(), "low": g["low"].min(),
                      "bars": g["close"].size()})
    s = s[s["bars"] >= 200]
    s["S"] = settle.shift(1).reindex(s.index)
    s["vix"] = pd.Series(vol["close"].to_numpy(),
                         index=pd.DatetimeIndex(vol.index).date).shift(1).reindex(s.index)
    s = s.dropna(subset=["S", "vix"])
    s["EV"] = s["S"] * s["vix"] / math.sqrt(252) / 100
    s["mx"] = np.maximum(s["high"] - s["S"], s["S"] - s["low"]) / s["EV"]
    s.index = pd.DatetimeIndex(s.index)
    roll = s["mx"].rolling(120).mean()

    fig, ax = plt.subplots(figsize=(9.5, 3.8))
    ax.plot(roll.index, roll.values, color=ACC, lw=1.2)
    ax.axhline(1.0, color=DN, lw=1.2, ls="--")
    ax.text(roll.index[40], 1.02, "what VIX implies", color=DN, fontsize=8)
    ax.axhline(float(s["mx"].mean()), color=MUT, lw=1, ls=":")
    ax.axvline(pd.Timestamp(ODTE_START), color=UP, lw=1.2)
    ax.text(pd.Timestamp(ODTE_START), ax.get_ylim()[1] * 0.97, "  0DTE era",
            color=UP, fontsize=8, va="top")
    ax.set_ylabel("realised / implied\n(120-session mean)")
    ax.set_title("Realised excursion has been below VIX-implied for 20 years — "
                 "not a regime, a risk premium")
    return _save(fig, "fig_ratio_over_time.png")


def fig_clock(ses) -> str:
    """How much room is left after a touch, by time of day."""
    f = frame_for(ses.df, "rth_open", "vix_prev_close")
    tr, _ = folds(f)
    lad = percentile_ladder(tr)
    c = float(lad["c_up"][list(TARGET_P).index(0.35)])
    rth = ses.bars.between_time("09:30", "15:59")
    rows = []
    for ts, r in tr.iterrows():
        day = ts.date()
        b = rth[rth.index.date == day]
        if b.empty or not np.isfinite(r["EV"]) or r["EV"] <= 0:
            continue
        lvl = r["S"] + r["EV"] * c
        hi = b["high"].to_numpy()
        hit = np.flatnonzero(hi >= lvl)
        if hit.size == 0:
            continue
        i = int(hit[0])
        mfe = float(np.max(b["high"].to_numpy()[i:]) - lvl)
        rows.append({"bucket": (570 + i) // 30 * 30, "mfe": mfe / lvl * 1e4})
    d = pd.DataFrame(rows)
    gg = d.groupby("bucket")["mfe"]
    med, n = gg.median(), gg.size()
    labels = [f"{int(b)//60:02d}:{int(b)%60:02d}" for b in med.index]

    fig, ax = plt.subplots(figsize=(8.0, 3.8))
    ax.bar(range(len(med)), med.values, color=ACC, alpha=0.85)
    for i, (v, k) in enumerate(zip(med.values, n.values)):
        ax.text(i, v + 1.2, f"n={k}", ha="center", fontsize=7, color=MUT)
    ax.set_xticks(range(len(med)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("median MFE after touch (bps)")
    ax.set_title(f"A level touched late has no session left to run into\n"
                 f"upper c={c:.3f} rung, open anchor, train fold")
    return _save(fig, "fig_clock.png")


def fig_conditioning(cond: dict) -> str:
    """Which of the twelve VIX-pack columns actually earn their place."""
    ok = [s for s in cond["singles"] if s.get("status") == "ok"]
    ok.sort(key=lambda s: s["delta_r2"])
    fig, axes = plt.subplots(1, 2, figsize=(9.8, 3.9),
                             gridspec_kw={"width_ratios": [2, 1]})
    ax = axes[0]
    cols = [UP if s["delta_r2"] > 0 else MUT for s in ok]
    ax.barh(range(len(ok)), [s["delta_r2"] for s in ok], color=cols, alpha=0.85)
    ax.set_yticks(range(len(ok)))
    ax.set_yticklabels([s["feature"] for s in ok], fontsize=8)
    ax.axvline(0, color="#000000", lw=0.8)
    ax.set_xlabel("out-of-sample R2 gained over a constant rescale")
    npos = sum(1 for x in ok if x["delta_r2"] > 0)
    ax.set_title(f"VIX pack: {npos} of {len(ok)} features positive, "
                 "all of them together worse than the best one")
    j = cond.get("joint", {})
    if j.get("status") == "ok":
        ax.axvline(j["delta_r2"], color=DN, lw=1.2, ls="--")
        ax.text(j["delta_r2"], len(ok) - 0.6, f" all 8 jointly ({j['delta_r2']:+.4f})",
                color=DN, fontsize=7.5, va="top")

    ax2 = axes[1]
    reg = cond.get("ladder_by_term_regime", [])
    if reg:
        ax2.bar(range(len(reg)), [r["mean_cal_err"] * 100 for r in reg],
                color=[UP, "#c98a1a", DN][: len(reg)], alpha=0.85)
        ax2.set_xticks(range(len(reg)))
        ax2.set_xticklabels([f"T{r['bucket']}\nn={r['n']}" for r in reg], fontsize=8)
        ax2.set_ylabel("mean rung error (pp)")
        ax2.set_title("Ladder degrades under\nterm-structure stress")
    return _save(fig, "fig_conditioning.png")


# ----------------------------------------------------- validation on real days
def _ladder_levels(ses, n_days: int):
    f = frame_for(ses.df, "rth_open", "vix_prev_close")
    tr, te = folds(f)
    lad = percentile_ladder(tr)
    recent = te.tail(n_days)
    return lad, recent


def fig_recent_sessions(ses, n_days: int = 9) -> str:
    """The ladder drawn on the most recent sessions it never saw."""
    lad, recent = _ladder_levels(ses, n_days)
    rth = ses.bars.between_time("09:30", "15:59")
    show = [0.50, 0.25, 0.10]
    idx = [list(TARGET_P).index(p) for p in show]

    ncol = 3
    nrow = int(np.ceil(len(recent) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(11.5, 2.7 * nrow), squeeze=False)
    for k, (ts, r) in enumerate(recent.iterrows()):
        ax = axes[k // ncol][k % ncol]
        b = rth[rth.index.date == ts.date()]
        if b.empty:
            ax.axis("off")
            continue
        ax.plot(b.index, b["close"], color="#222222", lw=0.8)
        S, EV = r["S"], r["EV"]
        ax.axhline(S, color=ACC, lw=1.1)
        for i, p in zip(idx, show):
            for side, col, c in (("up", "c_up", UP), ("dn", "c_dn", DN)):
                lvl = S + EV * lad[col][i] * (1 if side == "up" else -1)
                touched = (b["high"].max() >= lvl) if side == "up" else (b["low"].min() <= lvl)
                ax.axhline(lvl, color=c, lw=0.9,
                           ls="-" if touched else ":",
                           alpha=0.95 if touched else 0.45)
                ax.text(b.index[-1], lvl, f" {p:.0%}", fontsize=6.5, color=c,
                        va="center", ha="left",
                        fontweight="bold" if touched else "normal")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=ET))
        ax.set_xticks([b.index[0], b.index[len(b) // 2], b.index[-1]])
        ax.tick_params(labelsize=7)
        ax.set_title(f"{ts.date()}   VIX {r['vix_prev_close']:.1f}   "
                     f"EV {EV:.0f} pts", fontsize=8.5)
    for k in range(len(recent), nrow * ncol):
        axes[k // ncol][k % ncol].axis("off")
    fig.suptitle("The ladder on the most recent sessions — solid = touched, "
                 "dotted = not.  These days are in the holdout: the rungs were "
                 "placed without seeing them.",
                 fontsize=10, fontweight="bold", y=1.005)
    return _save(fig, "fig_recent_sessions.png")


def fig_session_detail(ses) -> str:
    """One recent session, every rung, with the intraday path."""
    lad, recent = _ladder_levels(ses, 1)
    ts, r = list(recent.iterrows())[-1]
    b = ses.bars.between_time("09:30", "15:59")
    b = b[b.index.date == ts.date()]
    S, EV = r["S"], r["EV"]
    fig, ax = plt.subplots(figsize=(9.5, 5.0))
    ax.plot(b.index, b["close"], color="#222222", lw=1.0, zorder=3)
    ax.fill_between(b.index, b["low"], b["high"], color=MUT, alpha=0.18, lw=0)
    ax.axhline(S, color=ACC, lw=1.4, zorder=2)
    ax.text(b.index[0], S, " 09:30 open (anchor)", color=ACC, fontsize=8, va="bottom")
    for i, p in enumerate(TARGET_P):
        for side, col, c in (("up", "c_up", UP), ("dn", "c_dn", DN)):
            lvl = S + EV * lad[col][i] * (1 if side == "up" else -1)
            hit = (b["high"].max() >= lvl) if side == "up" else (b["low"].min() <= lvl)
            ax.axhline(lvl, color=c, lw=1.0 if hit else 0.7,
                       ls="-" if hit else ":", alpha=0.95 if hit else 0.4, zorder=1)
            ax.text(b.index[-1], lvl,
                    f"  {p:.0%} {'TOUCHED' if hit else ''}", fontsize=7.5,
                    color=c, va="center",
                    fontweight="bold" if hit else "normal")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=ET))
    ax.set_title(f"{ts.date()} — open {S:.2f}, VIX {r['vix_prev_close']:.2f}, "
                 f"EV {EV:.1f} pts.  High {b['high'].max():.2f} / "
                 f"low {b['low'].min():.2f}")
    ax.set_ylabel("ES price")
    return _save(fig, "fig_session_detail.png")


def fig_recent_calibration(ses, window: int = 60) -> str:
    """Rolling out-of-sample calibration: does it hold up recently, or did one
    lucky holdout carry it?"""
    f = frame_for(ses.df, "rth_open", "vix_prev_close")
    tr, te = folds(f)
    lad = percentile_ladder(tr)
    fig, ax = plt.subplots(figsize=(9.5, 4.0))
    for i, p in ((list(TARGET_P).index(x), x) for x in (0.65, 0.50, 0.25)):
        hit = ((te["up"] >= lad["c_up"][i]) | (te["dn"] >= lad["c_dn"][i]))
        hit_up = (te["up"] >= lad["c_up"][i]).astype(float)
        roll = hit_up.rolling(window, min_periods=window // 2).mean()
        line, = ax.plot(roll.index, roll.values, lw=1.4, label=f"{p:.0%} rung (up)")
        ax.axhline(p, color=line.get_color(), lw=0.9, ls="--", alpha=0.6)
    ax.set_ylabel(f"realised touch rate\n({window}-session rolling)")
    ax.set_ylim(0, 1)
    ax.legend(frameon=False, fontsize=8, ncol=3)
    ax.set_title("Does the calibration hold through the holdout, or was it one "
                 "lucky stretch?\ndashed = promised probability")
    return _save(fig, "fig_recent_calibration.png")


def _et(min_from_open: int) -> str:
    m = (9 * 60 + 30 + int(min_from_open))
    return f"{m // 60:02d}:{m % 60:02d}"


def fig_arrival(arr: dict) -> str:
    """THE arrival histogram: 5-minute first-touch mass, per rung and side.

    Train fold (the holdout is too thin for 5-minute bins). Bars are the share
    of hit sessions whose first touch landed in that 5-minute bucket; the
    solid line marks the modal bucket, the dashed line the median.
    """
    edges = arr["edges"]
    rows = [g for g in arr["rungs"] if g["target_p"] in
            (0.35, 0.25, 0.15, 0.10, 0.05)]
    fig, axes = plt.subplots(len(rows), 2, figsize=(9.8, 1.55 * len(rows)),
                             sharex=True, squeeze=False)
    for r, g in enumerate(rows):
        for c, (side, colr) in enumerate((("up", UP), ("dn", DN))):
            ax = axes[r][c]
            mass = g["train"]["mass"]
            ax.bar([e - 2.5 for e in edges], mass, width=4.6, color=colr,
                   alpha=0.8, edgecolor="none")
            if g["train"]["mode_min"] is not None:
                ax.axvline(g["train"]["mode_min"], color="#222222", lw=1.2)
            if g["train"]["hit_med_min"] is not None:
                ax.axvline(g["train"]["hit_med_min"], color=MUT, lw=1.0,
                           ls="--")
            if r == 0:
                ax.set_title(f"{side}", fontsize=9)
            if c == 0:
                ax.set_ylabel(f"{g['target_p']:.0%}", fontsize=8.5,
                              rotation=0, ha="right", va="center")
            ax.set_ylim(0, max(0.16, max(m for m in mass if m) * 1.25))
    ticks = list(range(30, 391, 60))
    for ax in axes[-1]:
        ax.set_xticks(ticks)
        ax.set_xticklabels([_et(t) for t in ticks], fontsize=7.5)
        ax.set_xlabel("ET")
    fig.suptitle("When is a rung first touched?  5-minute buckets, share of "
                 "hit sessions (train)\nsolid = modal bucket, dashed = median. "
                 "Down rungs cluster at the open; up tails cluster at the close.",
                 fontsize=10, fontweight="bold", y=1.005)
    return _save(fig, "fig_arrival.png")


def fig_arrival_dow(arr: dict) -> str:
    """Median arrival by weekday, for the rungs with enough hits per day."""
    days = [d for d in arr["by_dow"] if d["n_train"] > 0]
    labels = [d["day"] for d in days]
    show = [(t, s) for t in (0.35, 0.25) for s in ("up", "dn")]
    fig, axes = plt.subplots(1, 2, figsize=(9.8, 3.6), sharey=True)
    for ax, side in zip(axes, ("up", "dn")):
        series = []
        for t, s in show:
            if s != side:
                continue
            ys = []
            for d in days:
                g = next(x for x in d["rungs"]
                         if x["target_p"] == t and x["side"] == s)
                f = g["train"]
                ys.append(f["hit_med_min"] if f["hits"] >= 30 and
                          f["hit_med_min"] is not None else np.nan)
            series.append((t, ys))
        w = 0.38
        for k, (t, ys) in enumerate(series):
            ax.bar(np.arange(len(labels)) + (k - 0.5) * w, ys, width=w,
                   color=UP if side == "up" else DN, alpha=0.8,
                   label=f"{t:.0%} rung")
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels)
        ax.legend(frameon=False, fontsize=8)
        ax.set_title(f"{side} rungs", fontsize=9)
    yt = list(range(60, 391, 60))
    axes[0].set_yticks(yt)
    axes[0].set_yticklabels([_et(t) for t in yt], fontsize=8)
    axes[0].set_ylabel("median first touch (ET)")
    fig.suptitle("Median arrival by weekday (train; cells with >=30 hits only)",
                 fontsize=10, fontweight="bold", y=1.02)
    return _save(fig, "fig_arrival_dow.png")


def build_all(ticker: str = "ES1") -> dict:
    import json
    print("rendering figures ...")
    ses = build_sessions(ticker)
    figs = {
        "calibration": fig_calibration(ses),
        "ladder": fig_ladder_construction(ses),
        "gap": fig_gap(ses),
        "ratio": fig_ratio_over_time(ticker),
        "clock": fig_clock(ses),
        "recent_sessions": fig_recent_sessions(ses),
        "session_detail": fig_session_detail(ses),
        "recent_calibration": fig_recent_calibration(ses),
    }
    cpath = DATA / "expected_volatility" / f"conditioning_{ticker}_rth_open.json"
    if cpath.exists():
        figs["conditioning"] = fig_conditioning(
            json.loads(cpath.read_text(encoding="utf-8")))
    apath = DATA / "expected_volatility" / f"arrival_{ticker}_RTH.json"
    if apath.exists():
        arr = json.loads(apath.read_text(encoding="utf-8"))
        figs["arrival"] = fig_arrival(arr)
        figs["arrival_dow"] = fig_arrival_dow(arr)
    return figs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ticker", default="ES1")
    args = ap.parse_args(argv)
    figs = build_all(args.ticker)
    print(f"\n{len(figs)} figures -> {FIG_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
