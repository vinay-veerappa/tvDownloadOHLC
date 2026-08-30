"""
cboe_validate_now.py — immediate cross-validation of OUR dealer walls vs CBOE
vendor walls, on the same day's data (no history accumulation needed).

What it does per pair:
  SPX (ours, unified_levels snapshot)  <-> _SPX CBOE chain
  SPY                                  <-> SPY CBOE chain
  QQQ                                  <-> QQQ CBOE chain

Checks:
  1. Wall agreement     — our CW/PW strike inside CBOE's top-5 gamma strikes
                          (near-spot +-2% band); rank None = vendor disagrees.
  2. Vendor walls' own placement — raw max-gamma + near-spot max-gamma CW/PW
                          side by side, so definitional differences are visible.

Usage:
  python scripts/options_research/cboe_validate_now.py --date 2026-08-28 --snapshot 1615
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

VENDOR_DIR = REPO_ROOT / "data" / "options" / "vendors"
CHAIN_DIR = VENDOR_DIR / "chains"
UNIFIED_DIR = REPO_ROOT / "data" / "options"

PAIRS = {"SPX": "_SPX", "SPY": "SPY", "QQQ": "QQQ"}
OPT_RE = re.compile(r"^_?([A-Z0-9]+?)(\d{6})([CP])(\d{8})$")


def extract_walls(line: str) -> dict[str, float | None]:
    walls = {"CW": None, "PW": None}
    for tok in line.split(","):
        tok = tok.strip()
        if ":" in tok and not tok[0].isdigit():
            tok = tok.split(":", 1)[1]
        m = re.match(r"^([\d.]+):W\|P\|CW$", tok)
        if m and walls["CW"] is None:
            walls["CW"] = float(m.group(1))
        m = re.match(r"^([\d.]+):W\|P\|PW$", tok)
        if m and walls["PW"] is None:
            walls["PW"] = float(m.group(1))
    return walls


def load_unified(date_str: str, hhmm: str) -> dict:
    p = UNIFIED_DIR / f"unified_levels_{date_str}_{hhmm}.json"
    if not p.exists():
        return {}
    j = json.loads(p.read_text())
    return {x["ticker"]: x["line"] for x in j.get("tickers", [])}


def load_vendor_chain(root: str, day: str | None = None):
    days = sorted(d.name for d in CHAIN_DIR.iterdir() if d.is_dir()) if CHAIN_DIR.exists() else []
    if not days:
        return None
    if day:
        paths = [CHAIN_DIR / day / f"_{root}.json.gz"]
    else:
        paths = sorted((CHAIN_DIR / days[-1]).glob(f"*_{root}.json.gz"))
    for p in paths:
        if p.exists():
            with gzip.open(p, "rt") as f:
                return json.load(f)
    return None


def cboe_strike_gex(payload: dict) -> tuple[float, dict, dict]:
    """Returns spot, {strike: call_gex_$}, {strike: put_gex}."""
    data = payload["data"]
    spot = float(data["current_price"])
    opt_re = re.compile(r"^_?([A-Z0-9]+?)(\d{6})([CP])(\d{8})$")
    cg: dict[float, float] = defaultdict(float)
    pg: dict[float, float] = defaultdict(float)
    for o in data["options"]:
        m = opt_re.match(o["option"])
        if not m:
            continue
        _, _e, cp, strike = m.groups()
        k = int(strike) / 1000.0
        oi = float(o.get("open_interest") or 0)
        gam = float(o.get("gamma") or 0)
        if oi <= 0 or gam == 0:
            continue
        notional = gam * oi * 100 * spot * spot * 0.01
        (cg if cp == "C" else pg)[round(k, 2)] += notional
    return spot, cg, pg


def top_rank(strikes: dict, target: float, spot: float, band: float, top_n=5):
    """Rank of target strike in the gamma ranking (near-spot band)."""
    cands = [(k, abs(v)) for k, v in strikes.items() if abs(k - spot) <= band]
    if not cands:
        return None, 0
    ranked = sorted(cands, key=lambda x: -x[1])
    hit = next((i + 1 for i, (k, _) in enumerate(ranked) if abs(k - target) <= spot * 0.002), None)
    in_top = any(abs(k - target) <= spot * 0.002 for k, _ in ranked[:top_n])
    return hit, (rank if False else len(ranked), in_top)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="20260828")
    ap.add_argument("--snapshot", default="1615")
    ap.add_argument("--band-frac", type=float, default=0.02)
    args = ap.parse_args()

    our = load_unified(args.date, args.snapshot)
    if not our:
        print(f"no unified snapshot {args.date}_{args.snapshot}")
        return 1

    band = None
    for tk_sym, root in (("SPX", "_SPX"), ("SPY", "SPY"), ("QQQ", "QQQ")):
        if tk_sym not in our:
            print(f"{tk_sym}: missing from snapshot")
            continue
        walls = extract_walls(our[tk_sym])
        payload = load_vendor_chain(root)
        if payload is None:
            print(f"{tk_sym}: no vendor chain archived")
            continue
        spot, cg, pg = cboe_strike_gex(payload)
        band = spot * args.band_frac

        print(f"\n=== {tk_sym} vs {root} (spot {spot:.2f}, band ±{band:.0f}) ===")
        print(f"  OUR walls:      CW={walls.get('CW')} PW={walls.get('PW')}")

        for side, gex in (("CW", cg), ("PW", pg)):
            our_lvl = walls.get(side)
            if not gex:
                print(f"  vendor {side}: none")
                continue
            band_gex = {k: v for k, v in gex.items() if abs(k - spot) <= band}
            raw_max = max(gex, key=lambda k: abs(gex[k]))
            band_max = max(band_gex, key=lambda k: abs(band_gex[k])) if band_gex else None
            rank, meta = top_rank(gex, our_lvl, spot, band) if our_lvl else (None, None)
            in_top = meta[1] if meta else False
            near = f"OUR in vendor top-5 band: {in_top}"
            if our_lvl is not None and rank is not None:
                near += f" (rank {rank}/{meta[0]})"
            print(f"  vendor {side}: raw-max {raw_max:.0f} | near-spot max "
                  f"{(f'{band_max:.0f}' if band_gex else '-')} | {near}")
    return 0


if __name__ == "__main__":
    sys.exit(main())