"""
Level source hold-rate backtest — Phase A/B (see docs/options/LEVEL_TRANSLATION_VENDOR_COMPARISON.md)

Evaluates dealer walls (CW/PW) from multiple sources in unified_levels_*.json
against actual 1m price action:

  Sources per family:
    NQ family:  NQ (RTD-native)  |  QQQ (cash, translated to NQ space)
    ES family:  ES (RTD-native)  |  SPY, SPX (cash, translated to ES space)

  Ground truth: 1m bars from data/live/live_storage_*.parquet (UTC).
  Metrics per wall:
    reach      — was the level touched (within tol) before day end?
    hold       — first touch rejected: post-touch excursion >= touch tolerance
                 without a prior 1m close beyond the level
    break      — first touch then 1m close beyond the level
    mins_to_touch — minutes from print time to first touch

Cash->futures translation uses the ratio at the same print moment
(fut_spot / cash_spot both read from the bars at the snapshot timestamp) —
equivalent to the pipeline's opening anchor for a 09:30 print, and the only
self-consistent choice for historical runs (historical basis_anchors.json is
overwritten daily).

Usage:
  python scripts/options_research/level_source_backtest.py --start 2026-08-13 --end 2026-08-28
  python scripts/options_research/level_source_backtest.py --start 2026-08-13 --families NQ --all-snapshots
"""
from __future__ import annotations

import argparse
import glob
import json
import logging
import re
import sys
from datetime import date, datetime, time as dtime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

log = logging.getLogger(__name__)

UNIFIED_DIR = REPO_ROOT / "data" / "options"
FUT_FILES = {
    "NQ": REPO_ROOT / "data" / "live" / "live_storage_-NQ.parquet",
    "ES": REPO_ROOT / "data" / "live" / "live_storage_-ES.parquet",
}
CASH_FILES = {
    "QQQ": REPO_ROOT / "data" / "live" / "live_storage_QQQ.parquet",
    "SPY": REPO_ROOT / "data" / "live" / "live_storage_SPY.parquet",
    "SPX": REPO_ROOT / "data" / "live" / "live_storage_SPX.parquet",
}

FAMILIES = {
    "NQ": {"NQ": ("NQ", "native"), "QQQ": ("QQQ", "ratio")},
    "ES": {"ES": ("ES", "native"), "SPY": ("SPY", "ratio"), "SPX": ("SPX", "ratio")},
}

TOUCH_TOL_FRAC = 0.0008   # 0.08% of spot = touch tolerance (~24 NQ pts, ~6 ES pts)
EVAL_END = dtime(19, 55)  # UTC — 15:55 ET


def parse_name(path: Path):
    m = re.match(r"unified_levels_(\d{8})_(\d{4})\.json$", path.name)
    if not m:
        return None
    d = datetime.strptime(m.group(1), "%Y%m%d").date()
    t = datetime.strptime(m.group(2), "%H%M").time()
    return d, t


def extract_walls(line: str) -> dict[str, float | None]:
    walls: dict[str, float | None] = {"CW": None, "PW": None}
    for tok in line.split(","):
        tok = tok.strip()
        # First token carries the ticker prefix ("NQ:29920.00:W|P|CW") — strip it.
        if ":" in tok and not tok[0].isdigit():
            tok = tok.split(":", 1)[1]
        m = re.match(r"^([\d.]+):W\|P\|CW", tok)
        if m and walls["CW"] is None:
            walls["CW"] = float(m.group(1))
        m = re.match(r"^([\d.]+):W\|P\|PW", tok)
        if m and walls["PW"] is None:
            walls["PW"] = float(m.group(1))
    return walls


def load_bars(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"])
        df = df.copy()
        df["ts"] = ts.dt.tz_localize(None)
        return df.set_index("ts").sort_index()
    df = df.copy()
    df["ts"] = pd.to_datetime(df.index)
    return df.set_index("ts").sort_index()


def spot_at(df: pd.DataFrame, ts: pd.Timestamp) -> float | None:
    if df.empty:
        return None
    idx = df.index.searchsorted(ts)
    if idx >= len(df):
        return None
    return float(df["close"].iloc[idx])


def evaluate_wall(bars: pd.DataFrame, print_ts: pd.Timestamp, level: float,
                  spot: float, horizon: pd.Timestamp) -> dict | None:
    tol = spot * TOUCH_TOL_FRAC
    fwd = bars.loc[(bars.index > print_ts) & (bars.index <= horizon)]
    if fwd.empty:
        return None
    call_side = level >= spot

    if call_side:
        touched = fwd["high"] >= level - tol
    else:
        touched = fwd["low"] <= level + tol

    if not touched.any():
        return {"reach": 0}
    t_idx = touched.idxmax()
    mins_to_touch = (t_idx - print_ts).total_seconds() / 60.0

    post = fwd.loc[t_idx:]
    if call_side:
        broke = bool((post["close"] > level + tol).any())
    else:
        broke = bool((post["close"] < level - tol).any())

    if call_side:
        excursion = float(post["low"].min())
        held = (not broke) and (level - excursion) >= tol
    else:
        excursion = float(post["high"].max())
        held = (not broke) and (excursion - level) >= tol

    return {
        "reach": 1,
        "broke": int(broke),
        "held": int(bool(held)),
        "mins_to_touch": mins_to_touch,
        "post_excursion": excursion,
    }


def run(start: str, end: str, families: list[str], snapshot: str | None,
        all_snapshots: bool) -> pd.DataFrame | None:
    files = [Path(f) for f in sorted(glob.glob(str(UNIFIED_DIR / "unified_levels_*.json")))]
    files = [f for f in files if re.match(r"unified_levels_\d{8}_\d{4}\.json$", f.name)]
    bar_cache: dict[str, pd.DataFrame] = {}
    rows: list[dict] = []

    for p in files:
        nm = parse_name(p)
        if not nm:
            continue
        d, t = nm
        ds = d.isoformat()
        if not (start <= ds <= end):
            continue
        if not all_snapshots and snapshot and t.strftime("%H%M") != snapshot:
            continue
        try:
            j = json.loads(p.read_text())
        except Exception:
            continue
        tk = {x["ticker"]: x for x in j.get("tickers", [])}
        if not tk:
            continue

        print_ts = pd.Timestamp.combine(d, t)

        # Futures spots at print time.
        fut_spots: dict[str, float] = {}
        for fam in families:
            if fam not in FAMILIES:
                continue
            if fam not in bar_cache:
                try:
                    bar_cache[fam] = load_bars(FUT_FILES[fam])
                except Exception as e:
                    log.warning("no bars for %s: %s", fam, e)
                    continue
            sp = spot_at(bar_cache[fam], print_ts)
            if sp:
                fut_spots[fam] = sp

        for fam, sources in FAMILIES.items():
            if fam not in families or fam not in fut_spots:
                continue
            fut_spot = fut_spots[fam]
            bars = bar_cache[fam]
            day_end = pd.Timestamp.combine(d, EVAL_END)
            if print_ts >= day_end:
                continue

            for src, (price_sym, mode) in sources.items():
                entry = tk.get(src)
                if not entry:
                    continue
                walls = extract_walls(entry["line"])

                if mode == "ratio":
                    cash_entry = tk.get(price_sym)
                    if not cash_entry:
                        continue
                    cash_walls = extract_walls(cash_entry["line"])
                    if price_sym not in bar_cache:
                        try:
                            bar_cache[price_sym] = load_bars(CASH_FILES[price_sym])
                        except Exception:
                            continue
                    cash_spot = spot_at(bar_cache[price_sym], print_ts)
                    if not cash_spot or cash_spot <= 0:
                        continue
                    ratio = fut_spot / cash_spot
                else:
                    cash_walls = walls
                    ratio = 1.0

                for side in ("CW", "PW"):
                    lvl_cash = cash_walls.get(side)
                    if not lvl_cash:
                        continue
                    lvl_fut = lvl_cash * ratio if mode == "ratio" else lvl_cash
                    res = evaluate_wall(bars, print_ts, lvl_fut, fut_spot, day_end)
                    if res is None:
                        continue
                    rows.append({
                        "date": ds,
                        "time": t.strftime("%H:%M"),
                        "family": fam,
                        "source": src,
                        "side": side,
                        "level": round(lvl_fut, 2),
                        "spot": round(fut_spot, 2),
                        **res,
                    })

    if not rows:
        return None
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for (fam, source, side), g in df.groupby(["family", "source", "side"]):
        n = len(g)
        reached = int(g["reach"].sum())
        r = g[g["reach"] == 1]
        out.append({
            "family": fam,
            "source": source,
            "side": side,
            "n": n,
            "reach_rate": round(reached / n, 3) if n else None,
            "hold_rate": round(float(r["held"].mean()), 3) if len(r) else None,
            "break_rate": round(float(r["broke"].mean()), 3) if len(r) else None,
            "avg_mins_to_touch": round(float(r["mins_to_touch"].mean()), 1) if len(r) else None,
        })
    return pd.DataFrame(out).sort_values(["family", "side", "source"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-08-13")
    ap.add_argument("--end", default="2026-08-28")
    ap.add_argument("--families", nargs="+", default=["NQ", "ES"],
                    choices=["NQ", "ES"])
    ap.add_argument("--snapshot", default="0930", help="HHMM snapshot per day")
    ap.add_argument("--all-snapshots", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)

    df = run(args.start, args.end, args.families,
             None if args.all_snapshots else args.snapshot, args.all_snapshots)
    if df is None:
        print("No rows — check date range / data availability.")
        return
    s = summarize(df)
    print(s.to_string(index=False))
    out = UNIFIED_DIR / f"level_source_backtest_{args.start}_{args.end}"
    out = out.with_suffix(".csv")
    df.to_csv(out, index=False)
    print(f"\nrows: {len(df)} -> {out}")


if __name__ == "__main__":
    main()