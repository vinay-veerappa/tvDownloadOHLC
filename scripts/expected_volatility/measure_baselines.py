"""Measured baselines for the Expected Volatility zone construction.

Answers the questions in `docs/indicators/ExpectedVolatility/DATA_PLAN.md` §10
that are decidable from data already on disk, *before* the `sessions.parquet`
feature store is built. Every number in DATA_PLAN §10 is produced by this file.

The construction under test (Pine, ported in `scripts/libs_py/expected_volatility`):

    a = VIX / sqrt(252) / 100
    level(c) = S * (1 +/- c * a)          S = prior close < 16:00 ET

so every rung of the ladder is one constant ``c`` (DATA_PLAN §1.3). This script
measures whether that construction is *calibrated*, whether it is *symmetric*,
and where the variance it is trying to forecast actually realises.

Sections
--------
A  calibration          P(|close - S| <= c*EV) vs the Normal it implies
B  touch rates          P(touch) per rung, vs driftless-BM reflection
C  single-parameter fit optimal k in |return| ~ k*S*VIX/100  (DATA_PLAN §2 Q8)
D  variance shares      where variance realises per session (DATA_PLAN §2 Q17)
E  stability            is the miscalibration a regime artifact?
F  skew                 is the mirrored R/S ladder specified correctly?
G  vol input            VIX vs realised vol vs blend      (DATA_PLAN §2 Q7)
I  invariance           is P(reversal|touch) flat in VIX? (the correct test)
J  percentile ladder    levels placed at target P(touch), not fixed SD multiples
K  reaction per rung    scale-free reaction on the percentile ladder

Section H (a fixed-% placebo ladder) is deliberately absent: the naive version
is confounded, because the two ladders select different day-populations
conditional on touch. Section I is the properly specified form of that
question. A clean placebo needs a within-day matched design — see DATA_PLAN
§10.4.

Usage
-----
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.measure_baselines
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.measure_baselines \\
        --ticker NQ1 --start 2010 --write

Per the repo bps/percentage standard, all price magnitudes are reported as
percentages or as unitless multiples of the expected move — never as points.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from .features import build_sessions as _build_sessions
from .features import frame_for as _frame_for

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
OUT_DIR = DATA / "expected_volatility"

# Ticker -> vol index, mirroring MARKET_VOL_PAIRS in
# scripts/libs_py/expected_volatility/settlements.py (Pine's branch table).
VOL_FOR_TICKER: dict[str, str] = {
    "ES1": "VIX",
    "NQ1": "VXN",
    "RTY1": "RVX",
    "YM1": "VXD",
    "CL1": "OVX",
    "GC1": "GVZ",
}

# The 12 Pine rungs collapsed to one constant each (DATA_PLAN §1.3).
B_OVER_A = math.sqrt(252.0 / 365.0)  # 0.8309097177
MID_OVER_A = (1.0 + B_OVER_A) / 2.0  # 0.9154548588
PINE_C = tuple(
    round(m * f, 6)
    for m in (0.25, 0.5, 1.0, 1.5)
    for f in (B_OVER_A, MID_OVER_A, 1.0)
)

# Session windows in ET, minutes-from-midnight, per DATA_PLAN §3.1.
# These are CME equity-index conventions; for CL/GC they are indicative only.
SESSIONS: dict[str, tuple[int, int]] = {
    "Asia (18:00-03:00)": (1080, 180),
    "London (03:00-09:30)": (180, 570),
    "NY_AM (09:30-12:00)": (570, 720),
    "NY_PM (12:00-16:00)": (720, 960),
    "Settlement (16:00-17:00)": (960, 1020),
}
SESSION_MINUTES = {
    "Asia (18:00-03:00)": 540,
    "London (03:00-09:30)": 390,
    "NY_AM (09:30-12:00)": 150,
    "NY_PM (12:00-16:00)": 240,
    "Settlement (16:00-17:00)": 60,
}
TRADING_DAY_MINUTES = 1380

# Target touch probabilities for the percentile ladder (§10.5). Levels are
# placed by INVERTING the empirical excursion CDF, so each rung carries a known
# P(touch) by construction instead of an inherited SD multiple.
TARGET_P: tuple[float, ...] = (0.80, 0.65, 0.50, 0.35, 0.25, 0.15, 0.10, 0.05)

# The 0DTE break. 2022-05-13 is both the VIX1D inception and the start of the
# measured regime shift (§10.3), so the vol-source common window and the
# tradeable regime coincide.
ODTE_START = "2022-05-13"
REGIMES: dict[str, tuple[str, str]] = {
    "all": ("2006-01-01", "2100-01-01"),
    "pre2022": ("2006-01-01", "2021-12-31"),
    "odte": (ODTE_START, "2100-01-01"),
}


def _read_parquet(path: Path) -> pd.DataFrame:
    """Load a parquet, failing fast and loudly (per .agents/AGENTS.md)."""
    if not path.exists():
        raise FileNotFoundError(f"required input missing: {path}")
    df = pd.read_parquet(path)
    if df.empty:
        raise ValueError(f"input is empty: {path}")
    return df


def _to_et(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df.index, pd.DatetimeIndex):
        df = df.set_index(pd.to_datetime(df.iloc[:, 0]))
    idx = df.index
    df.index = (
        idx.tz_convert("America/New_York")
        if idx.tz is not None
        else idx.tz_localize("UTC").tz_convert("America/New_York")
    )
    df.columns = [str(c).lower() for c in df.columns]
    return df.sort_index()


@dataclass
class Frame:
    """One row per RTH session, with the as-of anchor and vol read."""

    bars: pd.DataFrame  # 1m ET bars, full trading day
    sessions: pd.DataFrame  # per-RTH-session outcomes
    ticker: str
    vol_name: str


def build_frame(ticker: str, start: str) -> Frame:
    """Adapter over `features.build_sessions` — this module no longer defines
    the session frame.

    It used to. Two independent definitions of "what is the anchor, what is the
    vol read, when is it known" sat in this file and in `features.py`, and the
    report compared numbers produced by one against numbers produced by the
    other. They were verified bit-identical across all 1084 sessions at the time
    of the merge, which is exactly why this is worth collapsing: agreement today
    is a property of the current code, not a guarantee, and nothing would have
    reported the day they diverged.

    The column aliases below preserve this module's original names so sections
    A-K are untouched.
    """
    ses = _build_sessions(ticker, start=start)
    s = _frame_for(ses.df, "prev_close", "vix_prev_close")
    s["vol"] = s["vix_prev_close"]   # this module's name for the vol read
    s["rv20"] = s["rv20_cc"]         # close-to-close 20d, section G's estimator
    s = s.dropna(subset=["S", "vol"])
    if s.empty:
        raise ValueError(f"no usable sessions for {ticker} from {start}")
    return Frame(bars=ses.bars, sessions=s, ticker=ticker, vol_name=ses.vol_name)


def _fit_k(f: Frame) -> tuple[float, float]:
    """Optimal k in |return| ~ k * S * VOL/100, and the sigma it implies."""
    y = f.sessions["abs_pct"] / 100.0
    x = f.sessions["vol"] / 100.0
    k = float((y * x).sum() / (x * x).sum())
    sigma = k * math.sqrt(math.pi / 2)  # E|Z| = sigma*sqrt(2/pi)
    return k, sigma


def section_a(f: Frame, out: list[str]) -> None:
    s = f.sessions
    out.append("### A. Calibration — `P(|close - S| <= c*EV)` vs the implied Normal\n")
    out.append("| `c` | empirical | Normal | gap |")
    out.append("|---|---|---|---|")
    for c in (0.25, 0.5, B_OVER_A, 1.0, 1.5, 2.0):
        emp = float((s["ret_n"].abs() <= c).mean())
        th = 2 * norm.cdf(c) - 1
        out.append(f"| {c:.4f} | {emp:.1%} | {th:.1%} | {emp - th:+.1%} |")
    out.append("")


def section_b(f: Frame, out: list[str]) -> None:
    s = f.sessions
    out.append("### B. Touch rate per rung (one-sided BM reflection as reference)\n")
    out.append("| `c` | P(up touch) | P(dn touch) | P(either) | BM one-sided |")
    out.append("|---|---|---|---|---|")
    for c in sorted(set(PINE_C) | {2.0}):
        pu = float((s["up"] >= c).mean())
        pd_ = float((s["dn"] >= c).mean())
        pe = float((s["mx"] >= c).mean())
        bm = 2 * (1 - norm.cdf(c))
        out.append(f"| {c:.4f} | {pu:.1%} | {pd_:.1%} | {pe:.1%} | {bm:.1%} |")
    out.append("")


def section_c(f: Frame, out: list[str]) -> None:
    k, sigma = _fit_k(f)
    out.append("### C. Single-parameter fit — the 252-vs-365 question (§2 Q8)\n")
    out.append("| quantity | value |")
    out.append("|---|---|")
    out.append(f"| optimal `k` in `abs(return) ~ k*S*VOL/100` | {k:.5f} |")
    out.append(f"| implied 1-day sigma coefficient | {sigma:.5f} |")
    out.append(f"| implied divisor `sqrt(N)`, N | {1 / sigma**2:.0f} |")
    out.append(f"| `1/sqrt(252)` (Pine `a`) | {1 / math.sqrt(252):.5f} |")
    out.append(f"| `1/sqrt(365)` (Pine `b`) | {1 / math.sqrt(365):.5f} |")
    out.append(
        f"| **realised / implied sigma** | **{sigma * math.sqrt(252):.3f}** |"
    )
    out.append("")


def section_d(f: Frame, out: list[str], start: str) -> None:
    bars = f.bars.loc[start:]
    idx = bars.index
    r2 = np.log(bars["close"]).diff() ** 2
    mins = idx.hour * 60 + idx.minute
    total = float(r2.sum())
    out.append("### D. Where variance actually realises (1m realised variance)\n")
    out.append(
        "| session | minutes | % of clock | % of variance | per-min index | "
        "`sqrt(share)` | `sqrt(min/1380)` |"
    )
    out.append("|---|---|---|---|---|---|---|")
    shares: dict[str, float] = {}
    for name, (lo, hi) in SESSIONS.items():
        mask = (mins >= lo) & (mins < hi) if lo < hi else (mins >= lo) | (mins < hi)
        share = float(r2[mask].sum() / total)
        shares[name] = share
        dur = SESSION_MINUTES[name]
        out.append(
            f"| {name} | {dur} | {dur / TRADING_DAY_MINUTES:.1%} | {share:.1%} | "
            f"{share / dur * TRADING_DAY_MINUTES:.2f} | {math.sqrt(share):.3f} | "
            f"{math.sqrt(dur / TRADING_DAY_MINUTES):.3f} |"
        )
    rth_share = shares["NY_AM (09:30-12:00)"] + shares["NY_PM (12:00-16:00)"]
    out.append("")
    out.append(
        f"RTH (390 min = {390 / TRADING_DAY_MINUTES:.1%} of the clock) carries "
        f"**{rth_share:.1%}** of variance -> the correct RTH scale factor is "
        f"`sqrt({rth_share:.3f})` = **{math.sqrt(rth_share):.3f}**, not "
        f"`sqrt(390/1380)` = {math.sqrt(390 / TRADING_DAY_MINUTES):.3f}.\n"
    )


def section_e(f: Frame, out: list[str]) -> None:
    s = f.sessions
    out.append("### E. Is the miscalibration stable, or a regime artifact?\n")
    out.append(
        "| period | n | P(\\|ret\\| <= 1 EV) | P(up>=1) | P(dn>=1) | realised/implied |"
    )
    out.append("|---|---|---|---|---|---|")
    for lo, hi in ((2006, 2009), (2010, 2013), (2014, 2017), (2018, 2021), (2022, 2026)):
        w = s[(s.index.year >= lo) & (s.index.year <= hi)]
        if len(w) < 100:
            continue
        sub = Frame(f.bars, w, f.ticker, f.vol_name)
        _, sigma = _fit_k(sub)
        out.append(
            f"| {lo}-{hi} | {len(w)} | {(w['ret_n'].abs() <= 1).mean():.1%} | "
            f"{(w['up'] >= 1).mean():.1%} | {(w['dn'] >= 1).mean():.1%} | "
            f"{sigma * math.sqrt(252):.3f} |"
        )
    out.append("")


def section_f(f: Frame, out: list[str]) -> None:
    s = f.sessions
    n = len(s)
    out.append("### F. Skew — is the mirrored R/S ladder specified correctly?\n")
    out.append("| `c` | P(up touch) | P(dn touch) | ratio dn/up | z |")
    out.append("|---|---|---|---|---|")
    for c in (0.5, B_OVER_A, 1.0, 1.5):
        pu = float((s["up"] >= c).mean())
        pdn = float((s["dn"] >= c).mean())
        se = math.sqrt(pu * (1 - pu) / n + pdn * (1 - pdn) / n)
        z = (pdn - pu) / se if se else float("nan")
        ratio = pdn / pu if pu else float("nan")
        out.append(f"| {c:.4f} | {pu:.2%} | {pdn:.2%} | {ratio:.2f} | {z:+.1f} |")
    out.append("")


def section_g(f: Frame, out: list[str]) -> None:
    s = f.sessions.dropna(subset=["rv20"])
    y = s["abs_pct"]
    out.append("### G. Vol input horse race (§2 Q7), long window\n")
    out.append("| input | `k` | R2 | MAE (%) |")
    out.append("|---|---|---|---|")
    for name, x in (
        (f"{f.vol_name} (implied)", s["vol"]),
        ("RV20 (realised)", s["rv20"]),
        ("0.5*implied + 0.5*RV20", 0.5 * s["vol"] + 0.5 * s["rv20"]),
    ):
        k = float((y * x).sum() / (x * x).sum())
        pred = k * x
        r2 = 1 - float(((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum())
        out.append(f"| {name} | {k:.5f} | {r2:.3f} | {float((y - pred).abs().mean()):.4f} |")
    out.append("")
    out.append(
        f"`corr(normalised excursion, {f.vol_name})` = {s['up'].corr(s['vol']):+.3f} "
        f"(0 => the vol scaling is correctly specified in shape); "
        f"`corr(..., RV20)` = {s['up'].corr(s['rv20']):+.3f}.\n"
    )


def _touch_reactions(
    bars: pd.DataFrame, sess: pd.DataFrame, c: float, horizon: int, thr: float
) -> tuple[int, float]:
    """First-touch of the up level, then retracement toward the anchor.

    Reaction is measured as a fraction of the anchor->level distance, so it is
    scale-free and comparable across rungs (bps/percentage standard).
    """
    rth = bars.between_time("09:30", "15:59")
    wanted = set(sess.index.date)
    touched = reacted = 0
    for day, b in rth.groupby(rth.index.date):
        if day not in wanted:
            continue
        row = sess.loc[pd.Timestamp(day)]
        level = float(row["S"] + row["EV"] * c)
        anchor = float(row["S"])
        if level <= anchor:
            continue
        hi = b["high"].to_numpy()
        hits = np.flatnonzero(hi >= level)
        if hits.size == 0:
            continue
        touched += 1
        seg = b["low"].to_numpy()[hits[0] : hits[0] + horizon]
        if seg.size and (level - seg.min()) / (level - anchor) >= thr:
            reacted += 1
    return touched, (reacted / touched if touched else float("nan"))


def section_i(
    f: Frame, out: list[str], horizon: int = 60, thr: float = 0.5
) -> None:
    s = f.sessions
    q = pd.qcut(s["vol"], 5, labels=["Q1 low", "Q2", "Q3", "Q4", "Q5 high"])
    out.append(
        f"### I. Is `P(reversal | touch at c)` invariant to {f.vol_name}? "
        "(the correct normalisation test)\n"
    )
    out.append(
        f"Reversal = retraced >= {thr:.0%} of the anchor->level distance within "
        f"{horizon} min of first touch. If the vol scaling is correctly "
        "specified these rows are flat.\n"
    )
    for c in (0.25, 0.5):
        out.append(f"**c = {c}**\n")
        out.append(
            f"| {f.vol_name} quintile | range | N touch | P(touch) | P(reversal) |"
        )
        out.append("|---|---|---|---|---|")
        for label in ["Q1 low", "Q2", "Q3", "Q4", "Q5 high"]:
            sub = s[q == label]
            n, p = _touch_reactions(f.bars, sub, c, horizon, thr)
            rng = f"{sub['vol'].min():.1f}-{sub['vol'].max():.1f}"
            out.append(
                f"| {label} | {rng} | {n} | {n / len(sub):.1%} | "
                f"{p:.1%} |" if n else f"| {label} | {rng} | 0 | 0.0% | n/a |"
            )
        out.append("")


def percentile_ladder(sess: pd.DataFrame, targets=TARGET_P) -> pd.DataFrame:
    """Invert the empirical excursion CDF: c such that P(touch) == target.

    Up and down are computed separately, so the ladder is asymmetric wherever
    the underlying is (§10.2 measures a real skew in ES/NQ).
    """
    return pd.DataFrame(
        {
            "target_p": list(targets),
            "c_up": [float(sess["up"].quantile(1 - p)) for p in targets],
            "c_dn": [float(sess["dn"].quantile(1 - p)) for p in targets],
        }
    )


def _reactions(
    bars: pd.DataFrame, sess: pd.DataFrame, c: float, horizon: int
) -> tuple[int, float, float, float]:
    """First touch of the up level, then retracement, measured three ways.

    ``rel`` (retrace >= 50% of the anchor->level distance) is **not comparable
    across rungs** — 50% of a small distance is a small move, so it falls
    mechanically as ``c`` grows. It is reported only to show that artifact.
    ``bps`` and ``ev`` are scale-free and are the ones to read.
    """
    rth = bars.between_time("09:30", "15:59")
    by_day = {d: (b["high"].to_numpy(), b["low"].to_numpy()) for d, b in rth.groupby(rth.index.date)}
    n = rel = bps = ev = 0
    for ts, row in sess.iterrows():
        day = ts.date()
        if day not in by_day:
            continue
        hi, lo = by_day[day]
        anchor, exp_move = float(row["S"]), float(row["EV"])
        level = anchor + exp_move * c
        if level <= anchor:
            continue
        hits = np.flatnonzero(hi >= level)
        if hits.size == 0:
            continue
        n += 1
        seg = lo[hits[0] : hits[0] + horizon]
        if seg.size == 0:
            continue
        drop = level - seg.min()
        if drop / (level - anchor) >= 0.5:
            rel += 1
        if drop / level * 10_000 >= 10:  # 10 bps, the repo's T1 bracket
            bps += 1
        if drop / exp_move >= 0.25:
            ev += 1
    if not n:
        return 0, float("nan"), float("nan"), float("nan")
    return n, rel / n, bps / n, ev / n


def section_j(f: Frame, out: list[str]) -> None:
    s = f.sessions
    pre = s[s.index < ODTE_START]
    odte = s[s.index >= ODTE_START]
    out.append("### J. Percentile ladder — levels placed at target `P(touch)`\n")
    out.append(
        "`c` is the quantile of the normalised excursion, so each rung carries a "
        "known touch probability *by construction*. Up and down are separate, so "
        "the ladder is asymmetric where the instrument is.\n"
    )
    out.append(
        "| target P(touch) | pre-0DTE `c_up` | pre-0DTE `c_dn` | 0DTE `c_up` | 0DTE `c_dn` |"
    )
    out.append("|---|---|---|---|---|")
    lp, lo_ = percentile_ladder(pre), percentile_ladder(odte)
    for i, p in enumerate(TARGET_P):
        out.append(
            f"| {p:.0%} | {lp['c_up'][i]:.3f} | {lp['c_dn'][i]:.3f} | "
            f"{lo_['c_up'][i]:.3f} | {lo_['c_dn'][i]:.3f} |"
        )
    out.append("")
    out.append("Pine's fixed rungs, and the touch probability they actually deliver:\n")
    out.append("| `c` (Pine) | P(up touch) pre-0DTE | P(up touch) 0DTE | P(dn touch) 0DTE |")
    out.append("|---|---|---|---|")
    for c in sorted(set(PINE_C)):
        out.append(
            f"| {c:.4f} | {(pre['up'] >= c).mean():.1%} | "
            f"{(odte['up'] >= c).mean():.1%} | {(odte['dn'] >= c).mean():.1%} |"
        )
    out.append("")


def section_k(f: Frame, out: list[str], horizon: int = 60) -> None:
    odte = f.sessions[f.sessions.index >= ODTE_START]
    lad = percentile_ladder(odte)
    out.append("### K. Reaction per percentile rung (0DTE era), scale-free\n")
    out.append(
        f"Retracement within {horizon} min of first touch. `rel` is the "
        "scale-**dependent** metric, shown only to expose the artifact; read "
        "`>=10 bps` and `>=0.25 EV`.\n"
    )
    out.append(
        "| target | `c_up` | N touch | P(touch) | rel >=50% (artifact) | >=10 bps | >=0.25 EV |"
    )
    out.append("|---|---|---|---|---|---|---|")
    for i, p in enumerate(TARGET_P):
        c = lad["c_up"][i]
        n, rel, bps, ev = _reactions(f.bars, odte, c, horizon)
        out.append(
            f"| {p:.0%} | {c:.3f} | {n} | {n / len(odte):.1%} | {rel:.1%} | "
            f"{bps:.1%} | {ev:.1%} |"
        )
    out.append("")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ticker", default="ES1", choices=sorted(VOL_FOR_TICKER))
    ap.add_argument("--start", default="2006-01-01")
    ap.add_argument(
        "--variance-start",
        default="2010-01-01",
        help="section D needs dense overnight 1m coverage; earlier years are thin",
    )
    ap.add_argument("--horizon", type=int, default=60, help="reaction window, minutes")
    ap.add_argument("--threshold", type=float, default=0.5, help="reversal fraction")
    ap.add_argument(
        "--regime",
        default="all",
        choices=sorted(REGIMES),
        help="restrict sections A-I to a regime; J/K always show both (default: all)",
    )
    ap.add_argument("--write", action="store_true", help="write markdown to data/")
    args = ap.parse_args(argv)

    f = build_frame(args.ticker, args.start)
    lo, hi = REGIMES[args.regime]
    if args.regime != "all":
        sub = f.sessions[(f.sessions.index >= lo) & (f.sessions.index <= hi)]
        if sub.empty:
            raise ValueError(f"regime {args.regime!r} selects no sessions for {args.ticker}")
        f = Frame(f.bars, sub, f.ticker, f.vol_name)
    s = f.sessions
    out: list[str] = [
        f"# Measured baselines — {f.ticker} x {f.vol_name}",
        "",
        f"{len(s)} RTH sessions, {s.index.min().date()} -> {s.index.max().date()} "
        f"(regime: {args.regime}). "
        f"Anchor = prior close < 16:00 ET; vol = prior {f.vol_name} close (as-of, "
        "no lookahead). Generated by "
        "`scripts/expected_volatility/measure_baselines.py`.",
        "",
    ]
    section_a(f, out)
    section_b(f, out)
    section_c(f, out)
    section_d(f, out, args.variance_start)
    section_e(f, out)
    section_f(f, out)
    section_g(f, out)
    section_i(f, out, args.horizon, args.threshold)
    section_j(f, out)
    section_k(f, out, args.horizon)

    report = "\n".join(out)
    sys.stdout.reconfigure(encoding="utf-8")
    print(report)
    if args.write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        suffix = "" if args.regime == "all" else f"_{args.regime}"
        dest = OUT_DIR / f"baselines_{f.ticker}_{f.vol_name}{suffix}.md"
        dest.write_text(report, encoding="utf-8")
        print(f"\nwrote {dest}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
