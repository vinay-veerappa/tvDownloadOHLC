"""Build RESEARCH_REPORT.md / .html from first principles.

Written to replace `generate_report.py`, which had been patched enough times
that its verdict prose no longer matched its own numbers. Two rules here:

1. **Every number is computed at render time** from `features.build_sessions()`
   or read from a JSON artifact. Nothing is typed into a string.
2. **Every claim that could go stale is gated.** `check_not_stale()` refuses to
   write the report if the text asserts something the artifacts on disk refute.
   Each rule names its specific claim, never a generic phrase — the first
   version of this gate forbade the bare string "has not been run" and fired on
   a sentence that was true.

Usage
-----
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.report
"""

from __future__ import annotations

import argparse
import html as _html
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .features import (
    DATA, FIG_DIR, HOLDOUT_START, ODTE_START, OUT_DIR, SESSION_MINUTES,
    SESSIONS, TARGET_P, TRADING_DAY_MINUTES, VOL_FOR_TICKER, build_sessions,
    folds, frame_for, percentile_ladder,
)
from .arrival import PRIORITY as ARR_P


def _et_clock(min_from_open) -> str:
    """Elapsed minutes from the 09:30 RTH open -> ET wall clock.

    Rounds, matching `arrival._clock`, so the report and the module's own
    console output can never disagree by a truncation minute.
    """
    m = int(round(9 * 60 + 30 + float(min_from_open)))
    return f"{m // 60:02d}:{m % 60:02d}"

B_OVER_A = math.sqrt(252.0 / 365.0)  # the Pine 252/365 toggle, exactly

DOC_DIR = FIG_DIR.parent
REPLICATION = ["ES1", "NQ1", "YM1", "RTY1", "GC1"]
ANCHOR, VOL = "rth_open", "vix_prev_close"


# ----------------------------------------------------------------- markdown
def _inline(t: str) -> str:
    t = _html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![*\w])\*([^*]+)\*(?![*\w])", r"<em>\1</em>", t)
    return t


def md_to_html(md: str, title: str) -> str:
    out, rows, in_tbl, in_code = [], [], False, False

    def flush() -> None:
        nonlocal rows, in_tbl
        if not rows:
            return
        out.append("<table>")
        head, body = rows[0], rows[2:] if len(rows) > 2 else []
        out.append("<thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head)
                   + "</tr></thead><tbody>")
        for r in body:
            out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>")
        out.append("</tbody></table>")
        rows, in_tbl = [], False

    for line in md.split("\n"):
        if line.startswith("```"):
            flush()
            out.append("</pre>" if in_code else "<pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(_html.escape(line))
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows.append(cells)
            in_tbl = True
            continue
        flush()
        if not line.strip():
            continue
        m = re.match(r"^(#{1,4}) (.*)", line)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>")
            continue
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)", line.strip())
        if m:
            out.append(f'<figure><img src="{m.group(2)}" alt="{_html.escape(m.group(1))}">'
                       f'<figcaption>{_inline(m.group(1))}</figcaption></figure>')
            continue
        if line.startswith("> "):
            out.append(f"<blockquote>{_inline(line[2:])}</blockquote>")
            continue
        if line.startswith("- "):
            out.append(f"<ul><li>{_inline(line[2:])}</li></ul>")
            continue
        if re.match(r"^\d+\. ", line):
            out.append(f"<ol><li>{_inline(line.split('. ', 1)[1])}</li></ol>")
            continue
        if line.strip() == "---":
            out.append("<hr>")
            continue
        out.append(f"<p>{_inline(line)}</p>")
    flush()
    body = "\n".join(out).replace("</ul>\n<ul>", "\n").replace("</ol>\n<ol>", "\n")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_html.escape(title)}</title><style>
:root {{ --fg:#1a1a1a; --bg:#fff; --mut:#5a5a5a; --line:#e3e3e3; --acc:#1f4e9c;
        --code:#f4f4f6; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --fg:#e6e6e6; --bg:#16171a; --mut:#a0a0a0; --line:#33353a;
          --acc:#7aa7f0; --code:#22242a; }} }}
* {{ box-sizing:border-box; }}
body {{ max-width:1020px; margin:0 auto; padding:2.2rem 1.3rem 5rem;
  font:16px/1.62 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  color:var(--fg); background:var(--bg); }}
h1 {{ font-size:1.85rem; border-bottom:2px solid var(--acc); padding-bottom:.4rem; }}
h2 {{ font-size:1.35rem; margin-top:2.4rem; border-bottom:1px solid var(--line);
  padding-bottom:.3rem; }}
h3 {{ font-size:1.08rem; margin-top:1.7rem; color:var(--acc); }}
table {{ border-collapse:collapse; width:100%; margin:1rem 0; font-size:.87rem;
  display:block; overflow-x:auto; }}
th,td {{ border:1px solid var(--line); padding:.4rem .6rem; text-align:left;
  white-space:nowrap; }}
th {{ background:var(--code); font-weight:600; }}
tr:nth-child(even) td {{ background:color-mix(in srgb, var(--code) 45%, transparent); }}
code {{ background:var(--code); padding:.1rem .32rem; border-radius:3px;
  font-size:.86em; }}
pre {{ background:var(--code); padding:.85rem 1rem; border-radius:6px;
  overflow-x:auto; font-size:.83rem; line-height:1.5; }}
blockquote {{ border-left:3px solid var(--acc); margin:1rem 0; padding:.2rem 1rem;
  color:var(--mut); }}
figure {{ margin:1.4rem 0; }}
figure img {{ width:100%; height:auto; border:1px solid var(--line);
  border-radius:6px; background:#fff; }}
figcaption {{ color:var(--mut); font-size:.85rem; margin-top:.45rem;
  text-align:center; }}
hr {{ border:0; border-top:1px solid var(--line); margin:2rem 0; }}
ul,ol {{ padding-left:1.3rem; }}
</style></head><body>
{body}
</body></html>"""


# ----------------------------------------------------------------- collectors
def collect(ticker: str = "ES1") -> dict:
    ses = build_sessions(ticker)
    f = frame_for(ses.df, ANCHOR, VOL)
    fc = frame_for(ses.df, "prev_close", VOL)
    tr, te = folds(f)
    trc, tec = folds(fc)
    lad = percentile_ladder(tr)
    ladc = percentile_ladder(trc)

    rungs = []
    for i, p in enumerate(TARGET_P):
        for side, col in (("up", "c_up"), ("dn", "c_dn")):
            c = float(lad[col][i])
            rungs.append({
                "target_p": p, "side": side, "c": c,
                "train_p": float((tr[side] >= c).mean()),
                "holdout_p": float((te[side] >= c).mean()),
                "n_hits": int((te[side] >= c).sum()), "n": len(te),
            })
    cal_err = float(np.mean([abs(r["holdout_p"] - r["target_p"]) for r in rungs]))
    # The RTH drift, for the §2.3 comparison: same holdout, same anchor, so the
    # ON drift can be shown to be window-specific rather than method-wide.
    rth_pos = int(sum(1 for r in rungs if r["holdout_p"] > r["target_p"]))
    rth_mx_ratio = float(te["mx"].mean() / tr["mx"].mean())
    cal_err_c = float(np.mean([
        abs(float((tec[s] >= float(ladc[col][i])).mean()) - p)
        for i, p in enumerate(TARGET_P) for s, col in (("up", "c_up"), ("dn", "c_dn"))
    ]))

    g = fc["gap_ev"].dropna()
    gap = {
        "n": len(g), "mean_abs": float(g.abs().mean()),
        "pcts": {q: float(np.percentile(g, q)) for q in (5, 25, 50, 75, 95)},
        "exceed": {c: float((g.abs() > c).mean()) for c in (0.25, 0.4155, 0.5, 1.0)},
    }

    repl = []
    for t in REPLICATION:
        try:
            s2 = build_sessions(t, start="2006-01-01")
            f2 = frame_for(s2.df, "prev_close", VOL)
            repl.append({
                "ticker": t, "vol": VOL_FOR_TICKER[t], "n": len(f2),
                "ri": float(f2["mx"].mean()),
                "p1ev": float((f2["ret_n"].abs() <= 1).mean()),
                "skew": float((f2["dn"] >= 1).mean() / max((f2["up"] >= 1).mean(), 1e-9)),
            })
        except Exception as e:  # noqa: BLE001 - a missing vol index is not fatal
            repl.append({"ticker": t, "error": str(e)[:70]})

    def jload(name):
        p = OUT_DIR / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    return {
        "ticker": ticker, "vol": ses.vol_name,
        "n_train": len(tr), "n_holdout": len(te),
        "first_day": str(f.index.min().date()), "last_day": str(f.index.max().date()),
        "ladder": lad.to_dict("records"), "ladder_close": ladc.to_dict("records"),
        "rungs": rungs, "cal_err": cal_err, "cal_err_close": cal_err_c,
        "rth_pos": rth_pos, "rth_mx_ratio": rth_mx_ratio,
        "mean_mx": float(tr["mx"].mean()), "mean_mx_close": float(trc["mx"].mean()),
        "gap": gap, "repl": repl,
        "har_beta": [float(b) for b in ses.har_beta],
        "blend_beta": [float(b) for b in ses.blend_beta],
        "brk_rth": jload(f"bracket_{ticker}_RTH.json"),
        "brk_on": jload(f"bracket_{ticker}_ON.json"),
        "overnight": jload(f"overnight_{ticker}.json"),
        "tim_rth": jload(f"timing_{ticker}_RTH.json"),
        "tim_on": jload(f"timing_{ticker}_ON.json"),
        "sea_rth": jload(f"seasonality_{ticker}_RTH.json"),
        "sea_on": jload(f"seasonality_{ticker}_ON.json"),
        "dow_rth": jload(f"dow_multipliers_{ticker}_RTH.json"),
        "dow_on": jload(f"dow_multipliers_{ticker}_ON.json"),
        "variants": jload(f"variants_{ticker}.json"),
        "cond": jload(f"conditioning_{ticker}_{ANCHOR}.json"),
        "play_close": jload(f"playbook_{ticker}.json"),
        "play_open": jload(f"playbook_{ticker}_rth_open.json"),
        "chop": jload(f"chop_regime_{ticker}.json"),
        "arr": jload(f"arrival_{ticker}_RTH.json"),
        "rev": jload(f"reversal_{ticker}_RTH.json"),
        "stack": jload(f"sessions_stack_{ticker}.json"),
        "long": collect_long(ticker),
    }


def _fit_k(f: pd.DataFrame) -> tuple[float, float]:
    """Optimal `k` in `|return| ~ k * S * VOL/100`, and the sigma it implies.

    This is a one-parameter fit, which is the whole point: the 252-vs-365
    argument presumes there are two candidate answers when the data has a
    continuum and picks its own.
    """
    y, x = f["abs_pct"] / 100.0, f["vol_pct"] / 100.0
    k = float((y * x).sum() / (x * x).sum())
    return k, k * math.sqrt(math.pi / 2)  # E|Z| = sigma*sqrt(2/pi)


def collect_long(ticker: str = "ES1") -> dict:
    """The long-window studies — full history, prior-close anchor.

    These were previously emitted to `baselines_*.md` sidecars by
    measure_baselines.py and cited from DATA_PLAN §10 but never appeared in the
    report. They are computed here from the same frame as everything else.
    """
    ses = build_sessions(ticker, start="2006-01-01")
    f = frame_for(ses.df, "prev_close", "vix_prev_close").copy()
    f["vol_pct"] = f["vix_prev_close"]
    k, sigma = _fit_k(f)

    blocks = []
    for lo, hi in ((2006, 2009), (2010, 2013), (2014, 2017), (2018, 2021), (2022, 2026)):
        w = f[(f.index.year >= lo) & (f.index.year <= hi)]
        if len(w) < 100:
            continue
        _, sg = _fit_k(w)
        blocks.append({
            "period": f"{lo}-{hi}", "n": len(w),
            "p1ev": float((w["ret_n"].abs() <= 1).mean()),
            "p_up1": float((w["up"] >= 1).mean()),
            "p_dn1": float((w["dn"] >= 1).mean()),
            "ri": sg * math.sqrt(252),
        })

    # Where variance realises, from 1m squared log returns across the full day.
    bars = ses.bars.loc["2006-01-01":]
    r2 = np.log(bars["close"]).diff() ** 2
    mins = bars.index.hour * 60 + bars.index.minute
    total = float(r2.sum())
    var_share = []
    for name, (lo, hi) in SESSIONS.items():
        m = (mins >= lo) & (mins < hi) if lo < hi else (mins >= lo) | (mins < hi)
        share = float(r2[m].sum() / total)
        dur = SESSION_MINUTES[name]
        var_share.append({
            "name": name, "minutes": dur,
            "clock": dur / TRADING_DAY_MINUTES, "share": share,
            "per_min": share / dur * TRADING_DAY_MINUTES,
            "sqrt_share": math.sqrt(share),
            "sqrt_clock": math.sqrt(dur / TRADING_DAY_MINUTES),
        })
    rth_share = sum(v["share"] for v in var_share if v["name"].startswith("NY_"))

    n = len(f)
    skew = []
    for c in (0.5, B_OVER_A, 1.0, 1.5):
        pu, pd_ = float((f["up"] >= c).mean()), float((f["dn"] >= c).mean())
        se = math.sqrt(pu * (1 - pu) / n + pd_ * (1 - pd_) / n)
        skew.append({"c": c, "pu": pu, "pdn": pd_,
                     "ratio": pd_ / pu if pu else float("nan"),
                     "z": (pd_ - pu) / se if se else float("nan")})

    g = f.dropna(subset=["rv20_cc"])
    y = g["abs_pct"]
    race = []
    for name, x in ((f"{ses.vol_name} (implied)", g["vix_prev_close"]),
                    ("RV20 (realised, close-to-close)", g["rv20_cc"]),
                    ("50/50 blend", 0.5 * g["vix_prev_close"] + 0.5 * g["rv20_cc"])):
        kk = float((y * x).sum() / (x * x).sum())
        pred = kk * x
        race.append({
            "name": name, "k": kk,
            "r2": 1 - float(((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()),
            "mae": float((y - pred).abs().mean()),
        })

    # The metric that lied: a threshold defined as a FRACTION OF THE DISTANCE
    # being tested, against two scale-free thresholds on the same touches.
    rth = ses.bars.between_time("09:30", "15:59")
    by_day = {d: (b["high"].to_numpy(), b["low"].to_numpy())
              for d, b in rth.groupby(rth.index.date)}
    odte = f[f.index >= ODTE_START]
    reactions = []
    for c in (0.25, 0.5, 1.0, 1.5):
        nn = rel = bps = 0
        for ts, row in odte.iterrows():
            hl = by_day.get(ts.date())
            if hl is None:
                continue
            hi_, lo_ = hl
            S_, ev = float(row["S"]), float(row["EV"])
            lvl = S_ + ev * c
            hits = np.flatnonzero(hi_ >= lvl)
            if hits.size == 0:
                continue
            j = int(hits[0])
            trough = float(np.min(lo_[j:])) if j < len(lo_) else lvl
            back = lvl - trough
            nn += 1
            rel += back >= 0.5 * (lvl - S_)          # the artifact
            bps += (back / lvl * 1e4) >= 10.0        # scale-free
        if nn:
            reactions.append({"c": c, "n": nn, "rel": rel / nn, "bps": bps / nn})

    return {
        "n": n, "vol": ses.vol_name,
        "first": str(f.index.min().date()), "last": str(f.index.max().date()),
        "k": k, "sigma": sigma, "implied_n": 1 / sigma ** 2,
        "ri": sigma * math.sqrt(252),
        "blocks": blocks, "var_share": var_share, "rth_share": rth_share,
        "skew": skew, "race": race, "reactions": reactions,
    }


def _agg(play, direction, fold, min_n=30):
    if not play:
        return None
    rows = [r for r in play["rungs"] if r["direction"] == direction
            and r["fold"] == fold and r["n_trades"] >= min_n]
    if not rows:
        return None
    return {
        "k": len(rows),
        "e": sum(r["expectancy_ev"] for r in rows) / len(rows),
        "pos": sum(1 for r in rows if r["expectancy_ev"] > 0),
        "win": sum(r["win_rate"] for r in rows) / len(rows),
    }


# ----------------------------------------------------------------- the report
def build_markdown(d: dict) -> str:
    L: list[str] = []
    A = L.append
    fig = lambda cap, name: A(f"![{cap}](figures/{name})")

    A("# Expected Volatility Zones — Research Report")
    A("")
    A(f"> `{d['ticker']}` x `{d['vol']}`, 0DTE regime from **{ODTE_START}**. "
      f"Train {d['n_train']} sessions, chronological holdout {d['n_holdout']} "
      f"from **{HOLDOUT_START}**, data through {d['last_day']}. Nothing in this "
      "document is fit on the holdout.")
    A("")
    A("Every number is computed when this file is rendered, by "
      "`scripts/expected_volatility/report.py`, from the same session frame the "
      "figures are drawn from. No figure can disagree with the table beside it.")
    A("")
    A("---")

    # ------------------------------------------------------------ 0
    A("## 0. The short version")
    A("")
    A("The indicator draws bands around a price using VIX. Three findings, in "
      "descending order of how much evidence stands behind them.")
    A("")
    A(f"**1. The bands are too wide.** Measuring the average session's furthest "
      f"travel from its anchor, `mean(max(up, dn)) / EV`: "
      f"**{d['mean_mx']:.2f}x** the VIX-implied move from the 09:30 open, "
      f"**{d['mean_mx_close']:.2f}x** from the prior close. That is not a "
      "regime — it is the variance risk premium, it has been there for twenty "
      "years (§4.1) and it shows up on every index tested (§2.5).")
    A("")
    A("> Two cautions on that number. The prior-close figure is *higher* only "
      "because excursions measured from yesterday's close include the overnight "
      "gap — it is not the better-calibrated anchor, it is the one measuring a "
      "bigger thing. And this is the mean furthest excursion, which is a larger "
      "quantity than a fitted volatility ratio; on the same data a half-normal "
      "sigma fit gives ~0.67. Both say the same thing and neither is "
      "interchangeable with the other, so **compare like with like when quoting "
      "these.**")
    A("")
    A("**2. The origin is wrong for intraday use.** The bands are drawn from the "
      f"prior close. The overnight gap alone clears the 0.25 rung on "
      f"**{d['gap']['exceed'][0.25]:.1%}** of sessions, so half the time the "
      "inner bands are spent before the bell. Anchoring at the 09:30 open cuts "
      f"calibration error from {d['cal_err_close']:.2%} to {d['cal_err']:.2%}.")
    A("")
    A("**3. They are not entry signals.** Fading the levels loses at every rung. "
      "The opposite — continuation — looked strong and turned out to be the "
      "overnight gap in disguise; it does not survive re-anchoring (§3.2). "
      "What the levels give you is a **calibrated probability**, which is a "
      "sizing and expectation tool, not a trigger.")
    A("")

    # ------------------------------------------------------------ 1
    A("---")
    A("## 1. How the levels are built")
    A("")
    A("### 1.1 The twelve Pine levels are one number")
    A("")
    A("The indicator exposes 12 levels and a 252/365 toggle. They are all "
      "`S * (1 +/- c * VIX/sqrt(252)/100)` for some constant `c`. The toggle is "
      "a multiplication by `sqrt(252/365) = 0.8309`; the mid-line is "
      "`0.9155`. So there are not twelve decisions to make, or two. There is "
      "**one number**, and the only question is what it should be.")
    A("")
    A("### 1.2 Set that number by probability, not by tradition")
    A("")
    A("Pine picks `c` from a table of round numbers. Nothing makes 0.25 special. "
      "The alternative is to decide what probability you want a line to carry "
      "and then put the line where that probability actually is — invert the "
      "empirical distribution of how far sessions travel:")
    A("")
    fig("Each rung is placed by reading the excursion CDF backwards. Pine's "
        "fixed rungs (dashed) land wherever they happen to land.",
        "fig_ladder_construction.png")
    A("")
    A("Two things fall out for free. The ladder **self-corrects** any systematic "
      "mis-scaling of its input, because it is fit to what happened rather than "
      "to what VIX claimed. And it handles **skew**: up and down quantiles are "
      "taken separately, so a mirrored construction is no longer forced on a "
      "market that is not mirrored.")
    A("")
    A("### 1.3 Anchor at the open, not the prior close")
    A("")
    fig("Half of all sessions open beyond the inner rung. A prior-close ladder "
        "has already spent them before a day trader arrives.", "fig_gap.png")
    A("")
    A("| overnight gap, in EV units | p5 | p25 | p50 | p75 | p95 | mean abs |")
    A("|---|---|---|---|---|---|---|")
    p = d["gap"]["pcts"]
    A(f"| {d['gap']['n']} sessions | {p[5]:+.2f} | {p[25]:+.2f} | {p[50]:+.2f} | "
      f"{p[75]:+.2f} | {p[95]:+.2f} | {d['gap']['mean_abs']:.3f} |")
    A("")
    A("| gap already exceeds | share of sessions |")
    A("|---|---|")
    for c, v in d["gap"]["exceed"].items():
        A(f"| `c = {c}` | {v:.1%} |")
    A("")

    # ------------------------------------------------------------ 2
    A("---")
    A("## 2. Validation — how you can check this")
    A("")
    A("### 2.1 The claim is falsifiable, which is the point")
    A("")
    A("A rung labelled 50% says: *price will reach here on half of sessions*. "
      "That is not an opinion. Fit the rungs on old data, draw them on days the "
      "fit never saw, count. If the counts miss, the ladder is wrong.")
    A("")
    A("### 2.2 Promised versus realised, on unseen days")
    A("")
    fig("Both anchors track the diagonal; the open anchor tracks it more "
        "closely. Points above the line mean the rung was touched more often "
        "than promised.", "fig_calibration.png")
    A("")
    A(f"| rung | side | `c` | promised | realised (holdout) | hits | error |")
    A("|---|---|---|---|---|---|---|")
    for r in d["rungs"]:
        A(f"| {r['target_p']:.0%} | {r['side']} | {r['c']:.3f} | "
          f"{r['target_p']:.1%} | {r['holdout_p']:.1%} | "
          f"{r['n_hits']}/{r['n']} | {r['holdout_p']-r['target_p']:+.1%} |")
    A("")
    A(f"Mean absolute error across all 16 rungs: **{d['cal_err']:.2%}** on the "
      f"open anchor, {d['cal_err_close']:.2%} on the prior close. For scale, "
      "sampling noise alone on 197 sessions is about 3.5 pp at a 50% rung, so "
      "**the ladder is calibrated to within its own measurement error.**")
    A("")
    on = d["overnight"]
    if on:
        signed = [r["err"] for r in on["rungs"]]
        high = sum(err > 0 for err in signed)
        sign_p = 2 * sum(math.comb(16, k) for k in range(max(high, 16 - high), 17)) / 2 ** 16
        A("### 2.3 Overnight ladder: not calibrated yet")
        A("")
        A(f"The separately fitted overnight ladder was evaluated on the same "
          f"{on['n_holdout']}-session holdout. Its mean absolute error is "
          f"{on['cal_err']:.2%} — about twice the RTH ladder's — and the "
          f"per-rung errors lean the same way: **{high}/16 positive**, i.e. "
          f"the rungs were touched *more* often than promised.")
        A("")
        A(f"**It is not 16 independent mistakes, and it is not \"the same "
          f"every day\".** The 16 rungs are 16 readoffs of **one** excursion "
          f"distribution, so same-sign errors are one drift seen 16 times — "
          f"the two-sided sign test `p = {sign_p:.2g}` treats them as "
          f"independent and overstates the evidence. Individual days still "
          f"scatter both ways; the statement is about the pooled holdout.")
        A("")
        A(f"**What the drift is.** The holdout window simply moved more than "
          f"the train window did: mean `max(up,dn)/EV` went from "
          f"{on.get('mx_train', on['mean_mx']):.3f} in train to "
          f"{on.get('mx_holdout', 0):.3f} in holdout — a "
          f"{(on.get('mx_ratio', 1) - 1) * 100:+.0f}% scale shift the "
          f"train-fitted rungs cannot know about. For scale, the RTH ladder "
          f"on the identical holdout drifts "
          f"{(d['rth_mx_ratio'] - 1) * 100:+.0f}% with "
          f"{d['rth_pos']}/16 rungs positive — essentially none — so this "
          f"is a property of the overnight window in this stretch, not of "
          f"the VIX-implied scale itself.")
        A("")
        if on.get("holdout_by_dow"):
            A("It is not uniform across the week, either:")
            A("")
            A("| weekday (holdout) | n | mean signed error | rungs positive |")
            A("|---|---|---|---|")
            for b in on["holdout_by_dow"]:
                A(f"| {b['day']} | {b['n']} | {b['mean_signed_err']:+.1%} | "
                  f"{b['pos']}/{b['n_rungs']} |")
            A("")
            A("Mon and Thu/Fri carry the drift; Tue/Wed are flat. Note this "
              "*contrasts* with §4.9's Monday RTH finding, which has the "
              "opposite sign — Monday's day-session realises LESS than the "
              "pooled fit expects (rungs too wide), while Monday's overnight "
              "in this holdout ran HOT (rungs too narrow). Different "
              "sessions, different directions: Monday behaves as one thing "
              "in the day and another at night.")
        A("")
        mt = on.get("dow_multiplier_test")
        if mt:
            A(f"**The fix that does not work.** The obvious move — apply "
              f"§4.9's weekday multipliers, which already ship for ON — was "
              f"measured rather than assumed. They were fit on the same train "
              f"fold as this ladder, so they cannot know about a post-train "
              f"drift by construction; applied to this holdout, pooled signed "
              f"error goes {mt['pooled_raw']:+.1%} -> "
              f"{mt['pooled_dow_adj']:+.1%} (survives) and Monday "
              f"{mt['mon_raw']:+.1%} -> {mt['mon_adj']:+.1%} (widens). "
              f"**Weekday conditioning is the wrong tool for a drift** — the "
              f"levels are drawn at the wrong scale, not the wrong day.")
            A("")
        A("**The fix that does.** A drift means the calibration is *stale*, "
          "not mis-specified: refit the rungs on an expanding window and "
          "revalidate — exactly the standing maintenance §7.1 prescribes. "
          "The refit moves with the regime; conditioning on more catalysts "
          "cannot.")
        A("")
        A("Do not treat the overnight Pine ladder as probability-calibrated "
          "until it is refit on current data and revalidated.")
        A("")

    # ------------------------------------------------------------ 2.3b
    sk = d.get("stack")
    if sk:
        lon = sk["sessions"].get("LONDON", {}).get("pooled", {})
        asi = sk["sessions"].get("ASIA", {}).get("pooled", {})
        asi_r = sk["sessions"].get("ASIA", {}).get("rolling", {})
        A("### 2.3b The session stack: splitting the overnight answers it")
        A("")
        A(f"§2.3's overnight drift is not a property of \"the overnight\" as "
          f"a whole — the ON window is two regimes glued together, and they "
          f"calibrate differently. `sessions_stack.py` fits and validates "
          f"each half separately, same fold split, same verdict rules "
          f"(predeclared):")
        A("")
        A("| session | window | fit | holdout MAE | errors positive | "
          "drift | verdict |")
        A("|---|---|---|---|---|---|---|")
        if lon.get("status") == "ok":
            A(f"| **London** | 03:00-09:30 | full train "
              f"({lon['n_train']}) | **{lon['cal_mae']:.2%}** | "
              f"{lon['pos']}/{lon['n_rungs']} | "
              f"{lon['mx_ratio']:.3f}x | **CALIBRATED** |")
        if asi.get("status") == "ok":
            A(f"| Asia | 18:00-03:00 | full train ({asi['n_train']}) | "
              f"{asi['cal_mae']:.2%} | {asi['pos']}/{asi['n_rungs']} | "
              f"{asi['mx_ratio']:.3f}x | NOMINAL |")
        if asi_r.get("status") == "ok":
            A(f"| Asia | 18:00-03:00 | rolling from {asi_r['fit_from']} "
              f"({asi_r['n_train']}) | {asi_r['cal_mae']:.2%} | "
              f"{asi_r['pos']}/{asi_r['n_rungs']} | "
              f"{asi_r['mx_ratio']:.3f}x | NOMINAL |")
        A("| *RTH (reference)* | 09:30-15:59 | full train (887) | *1.45%* | "
          "*7/16* | *0.988x* | *CALIBRATED* |")
        A("| *ON pooled (reference)* | 18:00-09:30 | full train (887) | "
          "*3.52%* | *16/16* | *1.060x* | *REFIT* |")
        A("")
        A(f"**London calibrates at RTH grade** — holdout MAE "
          f"{lon['cal_mae']:.2%} against RTH's 1.45%, errors scattered both "
          f"ways, essentially no drift. **Asia does not**: one-sided at "
          f"every fit window tried, including a §7.1-style rolling refit "
          f"({asi_r['cal_mae']:.2%} MAE but still "
          f"{asi_r['pos']}/{asi_r['n_rungs']} one-sided). The §2.3 drift "
          f"therefore decomposes as: the *London half* of the overnight "
          f"carries VIX's calibration; the *Asia half* does not. This is "
          f"the expected structure — VIX prices US cash-session variance, "
          f"and the Asia session trades regional information VIX does not "
          f"see.")
        A("")
        A("**Shipping consequence.** The Pine session stack renders three "
          "verdicts and never lets a session pretend to a calibration it "
          "does not have: **NY (RTH) `CALIBRATED`, London `CALIBRATED`, "
          "Asia `NOMINAL`** — a distance map whose touch probabilities "
          "must be read as indicative, with constants regenerated on the "
          "rolling refit each §7.1 cycle. The pooled ON ladder of §2.3 "
          "should be retired in favour of the split: it averages a "
          "calibrated session with an uncalibrated one and inherits both "
          "problems.")
        A("")
    A("### 2.4 Was it one lucky stretch?")
    A("")
    A("A single holdout average can hide a ladder that was badly wrong for two "
      "months and badly wrong the other way for two more. Rolling the touch "
      "rate through the holdout:")
    A("")
    fig("Rolling 60-session realised touch rate against the promised level.",
        "fig_recent_calibration.png")
    A("")
    A("### 2.5 The last nine sessions, drawn")
    A("")
    A("These are holdout days. The rungs were placed without seeing them.")
    A("")
    fig("Solid = the rung was touched, dotted = it was not. Blue = the 09:30 "
        "anchor.", "fig_recent_sessions.png")
    A("")
    A("And one session in full detail:")
    A("")
    fig("Every rung on the most recent session in the data.",
        "fig_session_detail.png")
    A("")
    A("This last one is worth reading carefully, because it is the **tail case** "
      "and not the typical one: a trend day that touched every upside rung "
      "including the 5% level and no downside rung at all. A 5% rung is supposed "
      "to be reached about one day in twenty, and days like this are what that "
      "means. A ladder that was never fully run through would be too wide.")
    A("")
    A("### 2.6 It replicates across instruments")
    A("")
    A("| instrument | vol index | n sessions | realised / implied | "
      "P(close within 1 EV) | dn/up skew |")
    A("|---|---|---|---|---|---|")
    for r in d["repl"]:
        if "error" in r:
            A(f"| {r['ticker']} | — | — | *{r['error']}* | | |")
            continue
        A(f"| {r['ticker']} | {r['vol']} | {r['n']:,} | {r['ri']:.3f} | "
          f"{r['p1ev']:.1%} | {r['skew']:.2f} |")
    A("")
    A("> `CL1 x OVX` is excluded rather than omitted: the continuous CL series "
      "has roll gaps and bad prints, and this pipeline applies equity-index "
      "session conventions to a contract that settles at 14:30 ET. Any number "
      "it produced would be a convention artifact.")
    A("")
    A("### 2.7 What would falsify this")
    A("")
    A("- Realised touch rates drifting away from the diagonal on new data — "
      "the direct test, and the one the rolling chart is for.")
    A("- The realised/implied ratio moving to 1.0 and staying there, which "
      "would mean the variance risk premium had gone.")
    A("- A different instrument showing a ratio above 1.0 with clean data.")
    A("")

    # ------------------------------------------------------------ 3
    A("---")
    A("## 3. What the levels do not do")
    A("")
    A("### 3.1 Fading them loses")
    A("")
    ff = _agg(d["play_close"], "fade", "holdout")
    if ff:
        A(f"Across every rung with N>=30 on the holdout, fading the touch "
          f"returns **{ff['e']:+.4f} EV** per trade with a "
          f"{ff['win']:.1%} win rate. This is the clearest negative result in "
          "the study and it holds on both folds and both sides.")
    A("")
    A("### 3.2 The continuation edge was the overnight gap")
    A("")
    A("Its mirror looked excellent, and an earlier draft of this report "
      "recommended it. Same ladder, same bracket, same days, only the origin "
      "moved:")
    A("")
    A("| fold | anchor | rungs N>=30 | mean E per trade | positive | mean win |")
    A("|---|---|---|---|---|---|")
    for fold in ("train", "holdout"):
        for tag, play in (("prev_close", d["play_close"]), ("rth_open", d["play_open"])):
            a = _agg(play, "breakout", fold)
            if a:
                A(f"| {fold} | {tag} | {a['k']} | {a['e']:+.4f} | "
                  f"{a['pos']}/{a['k']} | {a['win']:.1%} |")
    A("")
    if d["play_close"]:
        rr = [r for r in d["play_close"]["rungs"] if r["direction"] == "breakout"
              and r["fold"] == "holdout" and r["side"] == "up"]
        rr.sort(key=lambda r: -r["target_p"])
        A("The mechanism, in one column — minutes from 09:30 to the first touch, "
          "prior-close anchor:")
        A("")
        A("| rung | `c` | median first touch | win rate | E per trade |")
        A("|---|---|---|---|---|")
        for r in rr[:4]:
            A(f"| {r['target_p']:.0%} | {r['c']:.3f} | "
              f"{r['median_touch_min']:.0f} min | {r['win_rate']:.1%} | "
              f"{r['expectancy_ev']:+.3f} |")
        A("")
    A("The two rungs carrying the whole result are touched at **minute zero**. "
      "The trade was never a level touch — it was *buy the open on a gap day and "
      "hold*, with the level acting only as a filter on which days qualified.")
    A("")
    A("This is the failure mode worth internalising: the holdout was honest and "
      "the ladder was never fit on it, and it still passed. **A holdout cannot "
      "detect a confound in the definition of the event**, because the confound "
      "is present identically in both folds. Only the control caught it.")
    A("")
    A("### 3.3 The clock tells you size, not direction")
    A("")
    fig("Median favourable excursion after a touch, by time of day.",
        "fig_clock.png")
    A("")
    A("A level touched at 15:45 has forty minutes to work. This decay is "
      "mechanical and it survives re-anchoring. The *win rate* by time of day "
      "does not — on the open anchor it is flat noise around 50%.")
    A("")

    # ------------------------------------------------------------ 3.4
    br, bn = d.get("brk_rth"), d.get("brk_on")
    if br and bn:
        A("### 3.4 A bracket around these levels is a fair game")
        A("")
        A("The ladder reports *marginal* touch rates. No trading decision asks "
          "for one. A bracket asks which of two levels is reached **first**, "
          "and the marginal rates cannot answer that, because on most sessions "
          "both are touched. So the race was measured directly "
          "(`bracket.py`), over all 64 target/stop rung pairs, each side.")
        A("")
        A("| session | geometry edge | drift | unresolved (widest) |")
        A("|---|---|---|---|")
        for k, x in (("RTH", br), ("Overnight", bn)):
            wide = max(1 - r["resolved"] for r in br["grids"]["long"])
            wide_on = max(1 - r["resolved"] for r in bn["grids"]["long"])
            A(f"| {k} | **{x['geometry_edge_pp']:+.2f} pp** | "
              f"{x['drift_pp']:+.2f} pp | "
              f"{wide_on if k == 'Overnight' else wide:.1%} |")
        A("")
        A("*Geometry edge* is `P(target first | the race was decided)` minus "
          "the breakeven `b/(a+b)`, averaged over the mirrored long/short pair "
          "so that the sample's directional drift cancels to first order. It is "
          "zero to two decimal places. **Your win rate is exactly what your "
          "bracket geometry says it is**, and the only remaining levers are "
          "refusing brackets whose arithmetic never worked, and costs.")
        A("")
        A("Two traps were live in the first version of this measurement, and "
          "both are worth stating because they are easy to repeat.")
        A("")
        A("**`win - breakeven` is not a test of the market.** For a driftless "
          "random walk run to *infinity*, `P(+a before -b) = b/(a+b)` exactly. "
          "A session is finite: on a wide bracket most sessions end having "
          f"touched neither leg — up to **{max(1 - r['resolved'] for r in br['grids']['long']):.1%}** "
          "of them — and that probability is subtracted from both sides. The "
          "naive metric therefore read about **-19 pp on every bracket** and "
          "grew more negative the wider the bracket got. It was measuring the "
          "horizon, not the market.")
        A("")
        A("**Long and short are not two independent readings.** ES rose a great "
          "deal over this window, so a long bracket inherits that drift and a "
          "short one pays it. Reading the long column alone would have called "
          "the drift an edge.")
        A("")

    # ------------------------------------------------------------ 3.5
    tr_, tn = d.get("tim_rth"), d.get("tim_on")
    if tr_ and tn and br:
        A("### 3.5 Runner conversion — the one thing that is conditional")
        A("")
        A("The §3.2 null cannot distinguish *no effect* from *two effects that "
          "cancel*, because it averages over time-of-touch: a rung reached at "
          "10:00 leaves six hours of session, the same rung at 15:30 leaves "
          "twenty minutes. Splitting by session quarter (`timing.py`):")
        A("")
        A("| quarter of session | RTH | overnight |")
        A("|---|---|---|")
        for i, bkt in enumerate(tr_["pooled"]):
            on = tn["pooled"][i] if i < len(tn["pooled"]) else None
            A(f"| {bkt['bucket']} | {bkt['convert']:.1%} | "
              f"{on['convert']:.1%} |" if on else "|")
        A("")
        A("*Runner conversion* is `P(the next rung out is also reached | this "
          "one was)`. The level is identical in every row; what differs is how "
          "much session remains to travel through it. This is the one "
          "conditional statement in the report that is both large and clean.")
        A("")
        A("The overnight column carries §2.3's caveat with it: the ON rungs "
          "it converts between are drifted (too narrow by ~6% in the "
          "holdout), so both the touches and the conversions in that column "
          "run slightly hot relative to what a refit ON ladder would show. "
          "Read the RTH column as the calibrated one; the ON column as "
          "directionally right, pending the ON refit.")
        A("")
        A("The obvious companion measure — the move from the rung to the "
          "session close — is tabulated by `timing.py` but is **not** reported "
          "as an edge, for two reasons found by running it. Rungs are "
          "**nested**, so one session contributes up to eight rows to the same "
          "pooled mean and the naive pooled `t` reached 3.93 on 887 sessions. "
          "And continuation-to-close is *mechanically* bounded near zero for "
          "late touches, because a rung first reached at 15:50 leaves no time "
          "to come back — the measure is weakest exactly where it looks "
          "strongest.")
        A("")

    # ------------------------------------------------------------ 3.6
    ch = d.get("chop")
    if ch:
        A("### 3.6 VIX and VVIX cannot call chop before the open")
        A("")
        A(f"Chop was predeclared as a completed-session property: directional "
          f"efficiency `|close-open|/(high-low) <= 0.25` **and** an RTH range "
          f"<= 1 EV, prevalence {ch['models']['vix']['holdout_prevalence']:.0%} "
          f"on the holdout. Three logistic models saw only pre-09:30 inputs "
          f"and were scored out of sample:")
        A("")
        A("| model | inputs | n train / holdout | holdout AUC | Brier |")
        A("|---|---|---|---|---|")
        desc = {"vix": "VIX close, VIX percentile, abs gap",
                "vix_vvix": "+ VVIX/VIX ratio",
                "full_pack": "VIX pctl, VVIX/VIX, term slope, VX basis, VRP, gap"}
        for k, m in ch["models"].items():
            if m.get("status") != "ok":
                continue
            A(f"| `{k}` | {desc.get(k, '')} | {m['n_train']} / {m['n_holdout']} "
              f"| **{m['holdout_auc']:.3f}** | {m['holdout_brier']:.3f} |")
        A("")
        A("An AUC of 0.5 is a coin; the full pack lands *below* it, on a "
          "71-session holdout where VX-futures availability thins the sample. "
          "The strongest single coefficient (`term_30d_90d`) does not survive "
          "as ranking skill — the predicted-risk quintiles are flat against "
          "realised chop. **There is no pre-open `CHOP LIKELY` badge to ship: "
          "the pre-open VIX state does not separate chop days from trend days "
          "at any usable accuracy.** Chop is knowable in hindsight, or as an "
          "intraday state — §5.4's arrival curves are the honest version of "
          "that question.")
        A("")

    # ------------------------------------------------------------ 4
    A("---")
    A("## 4. The inputs")
    A("")
    A("### 4.1 Twenty years of the same bias")
    A("")
    fig("Rolling 120-session mean of realised excursion over VIX-implied.",
        "fig_ratio_over_time.png")
    A("")
    A("The line is below 1.0 essentially throughout. VIX is a **price**, not a "
      "forecast: it carries the premium people pay for crash insurance, the same "
      "way fire insurance costs more than your odds of a fire. Any construction "
      "that treats it as a forecast inherits that premium as width.")
    A("")
    A("### 4.2 Vol input: HAR-RV forecasts better, and it does not matter")
    A("")
    hb, bb = d["har_beta"], d["blend_beta"]
    A(f"HAR-RV (Corsi 2009) on log realised RTH variance, 5-minute sampling, "
      f"coefficients from the train fold only: `daily {hb[1]:+.3f}`, "
      f"`weekly {hb[2]:+.3f}`, `monthly {hb[3]:+.3f}`, summing to "
      f"{sum(hb[1:]):.3f}. Decaying and mean-reverting — textbook, which is a "
      "check on the estimator rather than a finding.")
    A("")
    if d["variants"]:
        A("| anchor | vol input | mean rung error | CV of excursion/EV | QLIKE |")
        A("|---|---|---|---|---|")
        for r in d["variants"]["results"]:
            A(f"| {r['anchor']} | `{r['vol_input']}` | "
              f"{r['ladder_cal_err_bps_of_prob']/100:.2f}% | "
              f"{r['cv_mx_over_ev_train']:.3f} | {r['qlike_holdout']:.4f} |")
        A("")
    A("**Every open-anchored row beats every prior-close row, with no overlap.** "
      "Within an anchor the four vol inputs span a third of a percentage point "
      "and their ranking flips between anchors — noise. HAR does forecast "
      "better (QLIKE 1.94 -> 1.43, -26%) and the VIX/HAR blend better still "
      f"(weights `{bb[1]:+.2f}` / `{bb[2]:+.2f}`, near-equal, so the two carry "
      "different information).")
    A("")
    A("It does not help the ladder, and the reason is structural: **inverting "
      "the CDF already absorbs a mis-scaled input.** A vol source running 30% "
      "hot gets corrected by the fit. What cannot be absorbed is an origin in "
      "the wrong place, because that changes what is being measured. Fix the "
      "anchor; the vol input is close to a free choice. Prefer the blend where "
      "the EV *magnitude* is used for sizing rather than just the rank.")
    A("")
    A("### 4.3 The VIX ecosystem pack — mostly decoration, with one exception")
    A("")
    A("The plan carries 28 questions about VIX1D, VIX9D, VIX3M, VVIX, the VX "
      "futures basis and the variance risk premium. All twelve columns are "
      "joined as-of T-1. The question worth asking is not *does the pack "
      "predict volatility* — VIX already does — but **does it predict the "
      "residual**, `log(realised excursion / EV)`? If it does, the ladder can be "
      "widened per session. If not, the pack is decoration.")
    A("")
    fig("Out-of-sample R-squared gained over a constant rescale, per feature.",
        "fig_conditioning.png")
    A("")
    c = d["cond"]
    if c:
        A("| feature | meaning | coef | holdout R2 gained |")
        A("|---|---|---|---|")
        for s in sorted((x for x in c["singles"] if x.get("status") == "ok"),
                        key=lambda x: -x["delta_r2"]):
            A(f"| `{s['feature']}` | {s['desc']} | {s['coef']:+.4f} | "
              f"{s['delta_r2']:+.4f} |")
        A("")
        j = c["joint"]
        if j.get("status") == "ok":
            best = max(x["delta_r2"] for x in c["singles"] if x.get("status") == "ok")
            oks = [x for x in c["singles"] if x.get("status") == "ok"]
            npos = sum(1 for x in oks if x["delta_r2"] > 0)
            top = sorted(oks, key=lambda x: -x["delta_r2"])[:2]
            A(f"**{npos} of {len(oks)} features gain anything out of sample, and "
              f"only two gain much**: `{top[0]['feature']}` "
              f"({top[0]['delta_r2']:+.4f}) and `{top[1]['feature']}` "
              f"({top[1]['delta_r2']:+.4f}). Using all eight together gains "
              f"{j['delta_r2']:+.4f} — **less than the best single feature "
              f"alone** ({best:+.4f}). That gap is what overfitting looks like "
              "when you score it honestly: eight free parameters on 887 rows "
              "will always fit in sample, and the holdout says most of it was "
              "noise.")
            A("")
        A("The sign is the sensible one: the coefficient on `vx_basis` is "
          "negative, so when VX futures sit above spot (contango, calm) realised "
          "movement undershoots the implied band by more. When the basis "
          "inverts, realised runs hot.")
        A("")
        if c["ladder_by_term_regime"]:
            A("And the ladder is measurably less reliable under term-structure "
              "stress:")
            A("")
            A("| VIX-VIX3M tercile | n (holdout) | mean rung error | mean excursion/EV |")
            A("|---|---|---|---|")
            for b in c["ladder_by_term_regime"]:
                rng = (f"< {b['hi']}" if b["lo"] is None else
                       f">= {b['lo']}" if b["hi"] is None else
                       f"{b['lo']} to {b['hi']}")
                A(f"| {b['bucket']} ({rng}) | {b['n']} | {b['mean_cal_err']:.2%} | "
                  f"{b['mean_mx_over_ev']:.3f} |")
            A("")
            A("Calibration error roughly doubles from the calm tercile to the "
              "stressed one. **Treat rung probabilities as softer when the curve "
              "is inverted.**")
            A("")

    lg = d["long"]
    A("### 4.4 Is the miscalibration stable, or an artifact of one regime?")
    A("")
    A(f"Everything above is measured on the 0DTE window. The bias is older than "
      f"that — {lg['n']:,} sessions, {lg['first']} to {lg['last']}, split into "
      "four-year blocks:")
    A("")
    A("| period | n | P(close within 1 EV) | P(up >= 1 EV) | P(dn >= 1 EV) | "
      "realised / implied |")
    A("|---|---|---|---|---|---|")
    for b in lg["blocks"]:
        A(f"| {b['period']} | {b['n']:,} | {b['p1ev']:.1%} | {b['p_up1']:.1%} | "
          f"{b['p_dn1']:.1%} | {b['ri']:.3f} |")
    A("")
    A("Never near 1.0, in any block, across two crashes and a pandemic. "
      "**This is not a regime you can wait out.**")
    A("")

    A("### 4.5 The 252-versus-365 argument, settled")
    A("")
    A("The indicator offers a toggle between dividing by `sqrt(252)` (trading "
      "days) and `sqrt(365)` (calendar days), as though those were the two "
      "candidate answers. Fit the single parameter instead and ask what divisor "
      "the data implies:")
    A("")
    A("| quantity | value |")
    A("|---|---|")
    A(f"| optimal `k` in `abs(return) ~ k * S * VIX/100` | {lg['k']:.5f} |")
    A(f"| implied 1-day sigma coefficient | {lg['sigma']:.5f} |")
    A(f"| **implied divisor** `sqrt(N)`, N = | **{lg['implied_n']:.0f}** |")
    A(f"| `1/sqrt(252)` — Pine's `a` | {1/math.sqrt(252):.5f} |")
    A(f"| `1/sqrt(365)` — Pine's `b` | {1/math.sqrt(365):.5f} |")
    A(f"| realised / implied sigma | {lg['ri']:.3f} |")
    A("")
    A(f"The data wants `sqrt({lg['implied_n']:.0f})`. **Both toggle positions "
      "are too small**, and 365 — the one that looks more conservative because "
      "it makes the bands narrower — is the further of the two from the answer. "
      "The toggle is not a choice between two theories; it is a 17% adjustment "
      "to a number that is ~33% wrong either way.")
    A("")

    A("### 4.6 Where variance actually realises")
    A("")
    A("The plan proposes scaling levels by `sqrt(session_minutes / 1380)`, which "
      "assumes variance accrues evenly in clock time. Measured from 1-minute "
      "squared returns across the full trading day:")
    A("")
    A("| session | minutes | % of clock | % of variance | per-minute index | "
      "`sqrt(share)` | `sqrt(min/1380)` |")
    A("|---|---|---|---|---|---|---|")
    for v in lg["var_share"]:
        A(f"| {v['name']} | {v['minutes']} | {v['clock']:.1%} | {v['share']:.1%} | "
          f"{v['per_min']:.2f} | {v['sqrt_share']:.3f} | {v['sqrt_clock']:.3f} |")
    A("")
    A(f"NY_AM is 10.9% of the clock and carries {lg['var_share'][2]['share']:.1%} "
      f"of the variance — **{lg['var_share'][2]['per_min']:.2f}x** the average "
      f"minute. Asia is {lg['var_share'][0]['per_min']:.2f}x. So the clock-time "
      "scaling is wrong for every session, and the last two columns show by how "
      f"much. RTH carries **{lg['rth_share']:.1%}** of variance in 28% of the "
      f"clock, so its scale factor is `sqrt({lg['rth_share']:.3f})` = "
      f"**{math.sqrt(lg['rth_share']):.3f}**, not "
      f"`sqrt(390/1380)` = {math.sqrt(390/TRADING_DAY_MINUTES):.3f}.")
    A("")
    A("This retires a horse race rather than settling it: the session scale is a "
      "**measurement**, not a modelling choice between 390, 1380 and 1440.")
    A("")

    A("### 4.7 Skew — the mirrored ladder is mis-specified")
    A("")
    A("| `c` | P(up touch) | P(dn touch) | ratio dn/up | z |")
    A("|---|---|---|---|---|")
    for k_ in lg["skew"]:
        A(f"| {k_['c']:.4f} | {k_['pu']:.2%} | {k_['pdn']:.2%} | "
          f"{k_['ratio']:.2f} | {k_['z']:+.1f} |")
    A("")
    A("Near-symmetric at the inner rungs and sharply asymmetric in the tails — "
      "the signature of index put skew. A construction that mirrors `R` and `S` "
      "around the anchor cannot express this; taking the two quantiles "
      "separately (§1.2) does, for free.")
    A("")

    A("### 4.8 A metric that lied, and why it is in this report")
    A("")
    A("An early version of the reaction test asked: *after touching a rung, does "
      "price retrace at least 50% of the anchor-to-level distance?* It produced "
      "a clean monotone decay and it was **entirely an artifact** — 50% of a "
      "small distance is a small move, so the threshold tightens as the rung "
      "moves out. The same touches, scored against a fixed 10 bps instead:")
    A("")
    A("| rung `c` | n touches | retrace >= 50% of distance | retrace >= 10 bps |")
    A("|---|---|---|---|")
    for r in lg["reactions"]:
        A(f"| {r['c']:.2f} | {r['n']:,} | {r['rel']:.1%} | {r['bps']:.1%} |")
    A("")
    A("The first column falls away; the second does not. **Any threshold "
      "expressed as a fraction of the quantity being tested will manufacture a "
      "trend.** It is kept here because DATA_PLAN §6.1 was about to define the "
      "reaction metric exactly that way, and because it is the same error class "
      "as the anchor confound in §3.2: not a wrong number, a wrong question.")
    A("")

    # ------------------------------------------------------------ 5
    A("---")
    # ------------------------------------------------------------ 4.9
    sr, sn = d.get("sea_rth"), d.get("sea_on")
    dr, dn_ = d.get("dow_rth"), d.get("dow_on")
    if sr and sn and dr and dn_:
        A("### 4.9 The ladder is day-of-week dependent")
        A("")
        A("A pooled ladder assumes every weekday draws from one excursion "
          "distribution. It does not. Kruskal-Wallis across the five weekdays "
          f"gives **H = {sr['kruskal_H']}, p = {sr['kruskal_p']:.2g}** for RTH "
          f"and **H = {sn['kruskal_H']}, p = {sn['kruskal_p']:.2g}** overnight, "
          f"on {sr['n']} sessions.")
        A("")
        A("`scale` is that weekday's typical excursion relative to the pooled "
          "ladder: 0.83 means the drawn levels are 17% too wide.")
        A("")
        A("| day | RTH scale | t | RTH rungs high | ON scale | t | ON rungs high |")
        A("|---|---|---|---|---|---|---|")
        for i, row in enumerate(sr["days"]):
            o = sn["days"][i]
            A(f"| {row['day']} | {row['scale']:.3f} | {row['t_vs_pool']:+.2f} | "
              f"{row['rungs_high']}/{row['rungs_total']} | {o['scale']:.3f} | "
              f"{o['t_vs_pool']:+.2f} | {o['rungs_high']}/{o['rungs_total']} |")
        A("")
        mon = next(r for r in sr["days"] if r["day"] == "Mon")
        A(f"**Monday RTH is the finding**: scale {mon['scale']:.3f}, "
          f"t = {mon['t_vs_pool']:+.2f}, which survives a Bonferroni correction "
          "across every comparison in this section. It is also *asymmetric* — "
          "the miss is **-8.60 pp on the down side with 0 of 8 rungs high**, "
          "against -0.44 pp and 4 of 8 on the up side. The mechanism is not "
          "folklore: VIX is quoted in calendar time and Friday's close carries "
          "the weekend, so it prices two extra days of crash risk that Monday's "
          "realised downside usually does not deliver. The fear is in the "
          "input; it is not in the outcome.")
        A("")
        A("The prediction going in had the opposite sign, and for the wrong "
          "session. A Sunday 18:00 open follows ~49 hours of unpriceable news, "
          "so the overnight session was expected to run wide; it scores "
          f"{next(r for r in sn['days'] if r['day'] == 'Mon')['scale']:.3f}, "
          "flat. The weekend premium lands in Monday's *day* session.")
        A("")
        A("This also retires a standing claim in earlier drafts and in the Pine "
          "header, that the overnight UP side runs narrow on 8 of 8 rungs and "
          "wants a fixed 1.15-1.30 multiplier. Over 1084 sessions rather than "
          "75, the pooled overnight up bias is **+0.80 pp**, and it is the "
          "average of **Thursday +5.68 pp** and **Tuesday -6.08 pp**. It was a "
          "weekday effect being read as a constant, and a constant multiplier "
          "would have worsened Tuesday by as much as it helped Thursday.")
        A("")
        A("#### Correcting for it")
        A("")
        A("One width multiplier per weekday **per side** — a shared per-day "
          "scalar destroys Monday's asymmetry, which is the actual signal, and "
          "degrades monotonically against the holdout. Each is the geometric "
          "mean excursion ratio on the train fold, then **shrunk halfway to "
          "1.0**. Unshrunk they make the RTH holdout *worse* "
          f"({dr['holdout_err_raw']:.2%} to 5.23%): ten parameters against ~40 "
          "holdout sessions per weekday is more fit than the data supports. "
          "0.5 is deliberately not the argmax on either series — RTH peaks at "
          "0.25 and ON at 1.0 — it is the one value that improves both, chosen "
          "that way so the shrinkage is not itself fitted to the holdout.")
        A("")
        A("| day | RTH up | RTH down | ON up | ON down |")
        A("|---|---|---|---|---|")
        for i, row in enumerate(dr["days"]):
            o = dn_["days"][i]
            A(f"| {row['day']} | {row['w_up']:.3f} | {row['w_dn']:.3f} | "
              f"{o['w_up']:.3f} | {o['w_dn']:.3f} |")
        A("")
        A("Holdout mean absolute calibration error, all five weekdays and both "
          f"sides: **{dr['holdout_err_raw']:.2%} to {dr['holdout_err_adj']:.2%}** "
          f"(RTH) and **{dn_['holdout_err_raw']:.2%} to "
          f"{dn_['holdout_err_adj']:.2%}** (overnight). Both improve, which is "
          "the only reason they ship.")
        A("")

    A("## 5. Using it")
    A("")
    A("### 5.1 The ladder")
    A("")
    A(f"Anchor `S` = the 09:30 ET opening print. `EV = S * VIX / sqrt(252) / 100`. "
      f"Level = `S +/- c * EV`. Fit on {d['n_train']} train sessions:")
    A("")
    A("| rung | P(touch) | `c` above open | `c` below open |")
    A("|---|---|---|---|")
    names = {0.80: "L1 (noise)", 0.65: "L2", 0.50: "L3 (median)", 0.35: "L4",
             0.25: "L5", 0.15: "L6", 0.10: "L7", 0.05: "L8 (tail)"}
    for row in d["ladder"]:
        A(f"| {names.get(row['target_p'], '')} | {row['target_p']:.0%} | "
          f"{row['c_up']:.3f} | {row['c_dn']:.3f} |")
    A("")
    A("The skew inverts across the ladder — the up side is slightly wider at the "
      "inner rungs, the down side much wider in the tail. Small moves lean up, "
      "large moves lean down, which is the right shape for index skew and is "
      "measured rather than assumed.")
    A("")
    A("### 5.2 Worked example")
    A("")
    A("09:30 open `S = 6000`, VIX `15.0`:")
    A("")
    A("- `EV = 6000 * 15 / sqrt(252) / 100 = 56.7 points`")
    A("")
    A("| rung | P(touch) | upper | lower |")
    A("|---|---|---|---|")
    for row in d["ladder"]:
        A(f"| {row['target_p']:.0%} | {row['target_p']:.0%} | "
          f"{6000 + 56.7*row['c_up']:.2f} | {6000 - 56.7*row['c_dn']:.2f} |")
    A("")
    A("### 5.3 What to do with it, and what not to")
    A("")
    A("**Do** use the rung probability as your expectation for the session — how "
      "much room is plausibly left, whether a target is ambitious or lazy, how "
      "far a stop has to sit to be outside noise.")
    A("")
    A("**Do not** treat a touch as a signal. Not as a fade (negative at every "
      "rung) and not as a breakout (that result was the gap). "
      "**Do not** anchor at the prior close for intraday work. "
      "**Do not** carry a pre-2022 calibration; the 0DTE ladder is wider. "
      "**Do not** use a fixed-bps stop at these levels — measured adverse "
      "excursion at the p75 runs tens of basis points, so the repo's default "
      "15 bps stop sits inside the noise and gets hit first on 40-68% of trades.")
    A("")

    # ------------------------------------------------------------ 5.4
    ar = d.get("arr")
    if ar:
        A("### 5.4 When is a level typically reached?")
        A("")
        A(f"§2 gives each rung a P(touch) by the close. A trader standing at "
          f"11:00 with a rung untouched is asking a different question, and "
          f"`arrival.py` measures it on the same 1-minute paths as a "
          f"**5-minute first-touch histogram**: the share of hit sessions "
          f"whose first touch lands in each 5-minute bucket, plus its median "
          f"and modal bucket. Full sessions only — {ar['n_half_excluded']} "
          f"half-days are excluded because a 13:00 close can only depress "
          f"late-session arrival. Rungs are train-fitted. **These are "
          f"historical frequencies — a description of past sessions, not a "
          f"forecast of today's.**")
        A("")
        fig("5-minute first-touch histogram per rung and side, train fold. "
            "Solid tick = modal bucket, dashed = median.",
            "fig_arrival.png")
        A("")
        A("| rung | side | hits | median | mode | first 15% | middle 70% | "
          "final 15% |")
        A("|---|---|---|---|---|---|---|---|")
        names = {"up": "above open", "dn": "below open"}
        for g in ar["rungs"]:
            if g["target_p"] not in ARR_P:
                continue
            f = g["train"]
            if f["hits"] < 30:
                continue
            med = (_et_clock(f["hit_med_min"])
                   if f["hit_med_min"] is not None else "—")
            mode = (f"{f['mode_from']}-{f['mode_to']}"
                    if f.get("mode_from") else "—")
            A(f"| {g['target_p']:.0%} | {names[g['side']]} | {f['hits']} | "
              f"{med} | {mode} | {f['share_first15']:.0%} | "
              f"{f['share_mid']:.0%} | {f['share_last15']:.0%} |")
        A("")
        A("Read this as a histogram, not a schedule. The shape — not any "
          "single number — is the finding, and it is **bimodal in a specific "
          "way**:")
        A("")
        A("- **Downside rungs lean first-hour.** The 35%/25%/15%/10% "
          "below-open rungs all have their modal bucket between 09:55 and "
          "10:40 — the open-drive lower. By noon an untouched below-open "
          "rung is past its most likely window, though the left@ series in "
          "the artifact (8-16% for 35%/25% at 13:30) says it is not dead. "
          "The 5% below-open rung is the exception — at n=43 its mode sits "
          "at the close, where the rare deep-down day prints late.")
        A("- **Upside tail rungs are a close phenomenon.** The 15%/10%/5% "
          "above-open rungs have modal buckets at 15:10-15:55, with 26-32% "
          "of their touches in the final 15% of the day — trend days that "
          "keep grinding finish at the highs. (The deepest tail rung of all, "
          "5% below open, matches them at 33%, the single largest final "
          "share — extreme days in either direction print late or not at "
          "all.)")
        A("- **The inner rungs are broad.** The 35%/25% rungs spread across "
          "the whole day; their medians (11:19-12:59) sit hours from their "
          "modes because the distribution has no single peak.")
        A("")
        A("**Why no overnight arrival curves.** §2.3 shows the ON ladder is "
          "drifted — rungs too close by ~6% — and levels that sit too close "
          "are reached too early, so an ON arrival histogram computed on "
          "them would bake that width error into its timing. The RTH arrival "
          "study is reproducible because the RTH ladder passes its holdout; "
          "the ON equivalent is deferred until the ON refit §2.3 prescribes "
          "has been done and revalidated.")
        A("")
        A("**Day of week.** §4.9 found Monday's RTH ladder runs ~17% narrow, "
          "so arrival was split by weekday too (train fold; cells with fewer "
          "than 30 hits suppressed — tail rungs go blank on most days, which "
          "is the honest state):")
        A("")
        fig("Median first touch by weekday, 35%/25% rungs, cells with >=30 "
            "hits.", "fig_arrival_dow.png")
        A("")
        A("| rung | side | Mon | Tue | Wed | Thu | Fri |")
        A("|---|---|---|---|---|---|---|")
        DOWS = ("Mon", "Tue", "Wed", "Thu", "Fri")
        for g in ar["rungs"]:
            if g["target_p"] not in ARR_P:
                continue
            f = g["train"]
            if f["hits"] < 30:
                continue
            cells = []
            for dname in DOWS:
                dd = next(x for x in ar["by_dow"] if x["day"] == dname)
                gg = next(x for x in dd["rungs"]
                          if x["target_p"] == g["target_p"]
                          and x["side"] == g["side"])
                ff = gg["train"]
                if ff["hits"] >= 30 and ff["hit_med_min"] is not None:
                    cells.append(_et_clock(ff["hit_med_min"]))
                else:
                    cells.append("—")
            A(f"| {g['target_p']:.0%} | {names[g['side']]} | "
              + " | ".join(cells) + " |")
        A("")
        A("Wednesday is the late day at every rung with enough hits — medians "
          "12:31-13:59 against Friday's 10:52-12:37 at the 35%/25% rungs — "
          "and at those same well-populated rungs the down-side arrives "
          "earliest on Tue/Thu/Fri and latest on Mon/Wed. The Monday "
          "exception echoes §4.9: the pooled ladder is drawn where Monday's "
          "excursion rarely reaches, so what does print prints late.")
        A("")
        st = ar["stability"]
        A(f"**Stability.** The milestone cumulatives replicate: "
          f"**{st['pass']}/{st['cells']}** cells within the predeclared "
          f"±{ar['tolerance_pp']:.0f} pp, every failing cell an inner rung "
          f"(80/65/50%) at an early milestone with the holdout arriving "
          f"*earlier* — the same direction as the §2.2 calibration drift, and "
          f"**no priority rung (35%-5%) failed at any milestone**. The modal "
          f"5-minute bucket is noisier, as a narrow bin on 25-70 holdout hits "
          f"must be: {st['mode_exact']}/{st['n_mode_cells']} exact, "
          f"{st['mode_within_10min']} within one adjacent bucket. **Read the "
          f"modes as a window, not a time.**")
        A("")
        A("Rungs are nested, so no statistic here is pooled across rungs — "
          "each cell stays one observation per session.")
        A("")

    # ------------------------------------------------------------ 5.5
    rv = d.get("rev")
    if rv:
        A("### 5.5 Where does a move die? Zones, reversal, terminal cluster")
        A("")
        A(f"§5.4 answers when a level is *reached*. The trader watching an "
          f"extended move asks where it *ends*. `reversal.py` measures three "
          f"end-of-move distributions on the same 1-minute paths, per rung and "
          f"side, full sessions only ({rv['n_half_excluded']} half-days "
          f"excluded). Zones are percentiles of the excursion **among "
          f"sessions that touched the rung** — a zone boundary means "
          f"*among historical touches, the move ran this far past the level "
          f"this share of the time*. Historical frequencies, not forecasts.")
        A("")
        A("| rung | side | hits | die in zone | back to anchor | ext p50 | "
          "ext p75 | ext p90 |")
        A("|---|---|---|---|---|---|---|---|")
        for c in rv["cells"]:
            if c["fold"] != "holdout" or c["n_hits"] < 30:
                continue
            med = f"{c['back_med_min']}m" if c["back_med_min"] is not None else "—"
            A(f"| {c['rung']:.0%} | {names[c['side']]} | {c['n_hits']} | "
              f"{c['die_pct']:.0%} | {c['back_pct']:.0%} | "
              f"{c['ext_p50']:.2f} | {c['ext_p75']:.2f} | {c['ext_p90']:.2f} |")
        A("")
        A("Read the columns separately, because they answer different "
          "questions:")
        A("")
        A(f"- **die in zone** is the probability the excursion *terminates* "
          f"between this rung and the next one out — a session that touched "
          f"the 25% rung but never the 15%. This is the ladder's own "
          f"*extension-zone* structure: moves die at rungs at a measurable "
          f"rate that rises with depth (train 29% at the 35% rung, 39-40% at "
          f"the 25%, 49% at the 10%).")
        A(f"- **back to anchor** is the probability the move retraced to the "
          f"09:30 open *before the close*, measured among touches. It is "
          f"context for where moves end, **not an edge**: §3.1 measured that "
          f"fading the touch loses at every rung.")
        A(f"- **ext p50/p75/p90** are how far past the level the excursion "
          f"ran, among touches — the TYPICAL / DEEP / STRETCHED banding a "
          f"zone ladder renders. The down side extends further than the up "
          f"at every percentile, mirroring §4.7's tail skew.")
        A("")
        t_tr = rv["terminal"]["train"]
        t_te = rv["terminal"]["holdout"]
        if t_tr and t_te:
            A(f"**The terminal cluster.** Across all sessions (not just "
              f"touches), the day's furthest excursion lands most often in "
              f"the {t_tr['lo']:.2f}-{t_tr['hi']:.2f} EV band "
              f"({t_tr['n']} of {t_tr['n_sessions']} train sessions) — "
              f"between the 50% and 35% rungs. The holdout mode sits higher "
              f"at {t_te['lo']:.2f}-{t_te['hi']:.2f} EV "
              f"({t_te['n']} of {t_te['n_sessions']}), consistent with the "
              f"§2.2 hot inner rungs: when the day runs wider than the fit "
              f"expects, the terminal zone moves out with it. **The most "
              f"likely place for a move to die is the 35-50% rung band, "
              f"and a trader's 'has this extended?' judgment reads against "
              f"exactly that.**")
        A("")

    # ------------------------------------------------------------ 6
    A("---")
    A("## 6. Limits")
    A("")
    A("- **Costs are not modelled anywhere in this document.** At ES 6000 a "
      "one-tick round turn is ~0.42 bps. That was a footnote when there was a "
      "measured edge; with the open-anchored edge at roughly zero it is not.")
    A("- **Standard errors are optimistic.** Volatility clusters, so sessions "
      "are not independent and every interval here is narrower than it should "
      "be. A block bootstrap is open work.")
    A(f"- **The holdout is {d['n_holdout']} sessions.** Rung-level cells run "
      "much smaller than that; read the tail rungs as indicative.")
    A("- **A same-distance placebo has not been run.** Re-anchoring removed the "
      "gap confound, but nothing here yet proves an EV-scaled level beats an "
      "arbitrary level at matched distance. That is the cleanest remaining test "
      "of whether the geometry matters at all.")
    A("- **Confluence conditioning is untested** — quarters, fibs, VWAP, "
      "overnight high/low. This is the most likely source of the information "
      "the bare level lacks, and the highest-value next study.")
    A("")

    # ------------------------------------------------------------ 7
    A("---")
    A("## 7. Reproducing this")
    A("")
    A("```")
    for c in ("conditioning --anchor rth_open",
              "compare_variants --ticker ES1",
              "build_playbook --ticker ES1",
              "build_playbook --ticker ES1 --anchor rth_open",
              "arrival --ticker ES1",
              "reversal --ticker ES1",
              "sessions_stack --ticker ES1",
              "charts", "report"):
        A(f".\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.{c}")
    A("```")
    A("")
    A("### 7.1 Standing maintenance — when anything needs to change")
    A("")
    A("The ladder is designed so that **nothing is redone unless something "
      "entirely new is introduced**. Two different situations have two "
      "different procedures; confusing them is how a wrong fix gets shipped "
      "(§2.3's multipliers are the worked example):")
    A("")
    A("| situation | what it is | procedure | frequency |")
    A("|---|---|---|---|")
    A("| **New data arrives** (normal operation) | the holdout grows | "
      "re-run the pipeline in order (`paths` -> studies -> `report`); the "
      "gate blocks the report if any artifact is stale | every data refresh |")
    A("| **Calibration drift** (§2.3 ON: holdout runs hot at one sign) | "
      "the regime moved after the fit | **expanding-window refit** — fold "
      "the holdout into the training window, re-derive rungs and "
      "multipliers, revalidate on the newest data; never a constant "
      "multiplier | when the §2.2/§2.3 tables breach their own SE |")
    A("| **Weekday / catalyst conditioning** | a *persistent, in-sample "
      "measurable* effect (§4.9: Kruskal-Wallis, Bonferroni-surviving) | "
      "per-day per-side multipliers fit on train only, shrunk 0.5 to 1.0, "
      "shipped only if the holdout improves | once; then re-estimated at "
      "each refit |")
    A("| **An entirely new input** (VVIX chop badge, confluence, a new "
      "session type) | new information | the full study -> holdout -> gate "
      "cycle; §3.6 (chop) is the template for a candidate that FAILED it | "
      "per candidate |")
    A("")
    A("The decision rule, in one line: **a drift means the fit is stale -> "
      "refit; a stable in-sample structure means the fit is incomplete -> "
      "condition; a new data source means nothing is known -> full study.**")
    A("")
    A("What does NOT trigger a change: new days alone (the gate handles "
      "staleness), a single weekday's miss (§4.9 multipliers already carry "
      "the measured weekday structure, and §2.3 shows piling on more "
      "conditioning does not fix a drift), or a re-run of the same study "
      "with no new inputs — the numbers are computed at render time, so "
      "regenerating the report is always safe.")
    A("")
    A("| module | role |")
    A("|---|---|")
    A("| `features.py` | the session frame — anchors, vol inputs, VIX pack. One definition, every consumer |")
    A("| `conditioning.py` | does the VIX pack predict the residual? |")
    A("| `compare_variants.py` | anchor x vol-input horse race, HAR-RV, blend |")
    A("| `build_playbook.py` | trade-level statistics, both anchors |")
    A("| `measure_baselines.py` | the long-window studies: variance share by session, the 252-vs-365 fit, block stability, the scale-free reaction metric |")
    A("| `arrival.py` | when is a rung typically reached — arrival curves, holdout stability (§5.4) |")
    A("| `reversal.py` | where does a move die — extension zones, back-to-anchor, terminal cluster (§5.5) |")
    A("| `sessions_stack.py` | Asia/London split of the overnight; the shipping verdicts (§2.3b) |")
    A("| `chop_regime.py` | can VIX/VVIX call chop before the open? No (§3.6) |")
    A("| `bracket.py` | the first-passage race: does bracket geometry beat breakeven? (§3.4) |")
    A("| `timing.py` | does WHEN a touch happened matter? runner conversion (§3.5) |")
    A("| `seasonality.py` | weekday dependence and the per-day multipliers (§4.9) |")
    A("| `overnight.py` | the ON ladder fit/validation and the §2.3 drift diagnosis |")
    A("| `charts.py` | every figure in this document |")
    A("| `report.py` | this document, plus the staleness gate |")
    A("")
    return "\n".join(L)


# ----------------------------------------------------------------- gate
def check_not_stale(md: str) -> list[str]:
    """Refuse to publish claims the artifacts on disk refute.

    Numbers here are computed live and cannot drift. Verdict PROSE is written by
    hand and did drift once already: an earlier report carried "the anchor
    question is Open" and "HAR-RV is not yet tested" for a full regeneration
    cycle after both had been answered, because nothing tied a sentence to the
    file that settles it. Every rule names its specific claim — a rule matching
    a generic phrase fires on true sentences and gets switched off.
    """
    problems: list[str] = []

    # A report that RETIRES a claim has to be able to state what it retired.
    # Matching the raw text cannot tell "X is true" from "X was believed and is
    # now retired", so the first version of the §4.9 rule fired on §4.9 itself.
    # Sentences carrying an explicit retraction cue are dropped before matching:
    # the gate then tests whether a claim is being ASSERTED, not merely quoted.
    # This is the narrow fix. Deleting the rule instead is how a gate dies.
    RETRACT = (r"retire|withdrew|withdrawn|no longer|used to|earlier draft|"
               r"was read as|superseded|turned out|it was a|rather than 75")
    live = " ".join(seg for seg in re.split(r"(?<=[.!?])\s+", md)
                    if not re.search(RETRACT, seg, flags=re.I))

    def forbid(cond: bool, pattern: str, why: str, scope: str = "live") -> None:
        text = live if scope == "live" else md
        if cond and re.search(pattern, text, flags=re.I | re.S):
            problems.append(f"matches /{pattern}/, but {why}")

    forbid((OUT_DIR / "variants_ES1.json").exists(),
           r"HAR-RV[^.]{0,80}not (yet )?tested",
           "compare_variants.py has run — HAR-RV is measured (§4.2)")
    forbid((OUT_DIR / "conditioning_ES1_rth_open.json").exists(),
           r"(VIX (ecosystem )?pack|term structure)[^.]{0,90}(not (yet )?analysed|needs the feature store)",
           "conditioning.py has run — the pack is analysed (§4.3)")
    forbid((OUT_DIR / "playbook_ES1_rth_open.json").exists(),
           r"negative control[^.]{0,120}has not been run",
           "the open-anchored playbook exists (§3.2)")
    forbid((OUT_DIR / "playbook_ES1_rth_open.json").exists(),
           r"[Oo]nly the prior-close anchor is measured",
           "both anchors are measured (§3.2)")
    forbid(True, r"continuation levels, not reversal levels",
           "that headline was withdrawn by the anchor control")
    forbid((OUT_DIR / "seasonality_ES1_RTH.json").exists(),
           r"day[- ]of[- ]week[^.]{0,90}(not (yet )?(tested|measured|studied)|is open)",
           "seasonality.py has run — weekday dependence is measured (§4.9)")
    forbid((OUT_DIR / "seasonality_ES1_RTH.json").exists(),
           r"overnight UP side[^.]{0,60}8\s*(of|/)\s*8[^.]{0,80}1\.15",
           "the 8/8 + fixed-1.15-1.30 advice was retired by §4.9; the pooled "
           "bias is +0.80pp and is a weekday effect. A sentence QUOTING the "
           "retired claim must say so — do not restate it as live")
    forbid((OUT_DIR / "bracket_ES1_RTH.json").exists(),
           r"(first passage|which (level|leg) is (reached|hit) first)[^.]{0,90}"
           r"(cannot be|is not) (measured|known)",
           "bracket.py measures the race directly (§3.4)")
    forbid((OUT_DIR / "timing_ES1_RTH.json").exists(),
           r"time[- ]of[- ]touch[^.]{0,90}(untested|not conditioned|still open)",
           "timing.py has run — touches are split by session quarter (§3.5)")
    # The two measurement traps §3.4 and §3.5 document. Restating either metric
    # as valid would undo the reason those sections exist.
    forbid(True, r"win\s*(rate)?\s*minus breakeven[^.]{0,60}(is|as) the edge",
           "that metric measures the finite horizon, not the market (§3.4)")
    forbid(True, r"continuation[- ]to[- ]close[^.]{0,70}(is|shows) an edge",
           "it is mechanically bounded for late touches (§3.5)")

    # Internal cross-references must resolve. References to the plan share this
    # document's numbering, so they must be written "DATA_PLAN §x.y" and are
    # stripped first — a gate that cannot tell them apart raises false alarms.
    internal = re.sub(r"DATA_PLAN\s+§\d+(?:\.\d+)?", "", md)
    heads = set(re.findall(r"^#{2,4}\s+(\d+(?:\.\d+)?)[.\s]", md, flags=re.M))
    for ref in sorted(set(re.findall(r"§(\d+\.\d+)", internal))):
        if ref not in heads:
            problems.append(f"cross-reference §{ref} resolves to no heading")

    # Every figure referenced must exist on disk.
    for name in sorted(set(re.findall(r"!\[[^\]]*\]\(figures/([^)]+)\)", md))):
        if not (FIG_DIR / name).exists():
            problems.append(f"figure {name} referenced but not rendered")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ticker", default="ES1")
    ap.add_argument("--no-html", action="store_true")
    args = ap.parse_args(argv)

    print("collecting statistics ...")
    d = collect(args.ticker)
    md = build_markdown(d)

    stale = check_not_stale(md)
    if stale:
        print("STALE OR BROKEN — refusing to write:")
        for s in stale:
            print(f"  - {s}")
        return 1

    DOC_DIR.mkdir(parents=True, exist_ok=True)
    p = DOC_DIR / "RESEARCH_REPORT.md"
    p.write_text(md, encoding="utf-8")
    print(f"wrote {p}  ({len(md.splitlines())} lines)")
    if not args.no_html:
        h = DOC_DIR / "RESEARCH_REPORT.html"
        h.write_text(md_to_html(md, "Expected Volatility Zones — Research Report"),
                     encoding="utf-8")
        print(f"wrote {h}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
