"""
ES / SPX / SPY  Drift Analysis — Unified Levels Edition

Parses `data/options/current/unified_levels_close.txt` (the live scored
unified-levels file) to extract all calculated levels for SPY, SPX, and ES,
then measures the drift between them.

Key drift sources:
  1. EM levels — SPY EM is native (from SPY options straddles/VIX synth);
     SPX EM is native (from SPX options); ES EM is SPY × futures_ratio.
  2. GEX levels (zero gamma, flip, cliff, magnet, walls) — SPY is native;
     SPX is native; ES is SPY × futures_ratio.
  3. The META_FUTURES_RATIO should perfectly scale SPY→ES, but SPX has its
     own independent options chain, so SPX vs SPY is the *real* drift test.

Outputs:
  - Console summary
  - CSV: data/analysis/unified_levels_drift.csv
"""

import json
import re
import os
from datetime import datetime

import pandas as pd
import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
ANALYSIS = os.path.join(DATA, "analysis")
OPTIONS = os.path.join(DATA, "options")


# ─── Parsing helpers ──────────────────────────────────────────────────────

def parse_unified_txt(path: str) -> dict[str, dict]:
    """Parse unified_levels_close.txt into {ticker: {levels: [...], meta: {}}}."""
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().strip().splitlines()

    result = {}
    for line in lines:
        if not line or ":" not in line:
            continue
        parts = line.split(":", 1)
        ticker = parts[0].strip()
        body = parts[1]
        tokens = [t.strip() for t in body.split(",")]
        levels = []
        meta = {}
        for tok in tokens:
            if not tok:
                continue
            if tok.startswith("0:META_"):
                # META token: 0:META_KEY_VALUE  or  0:META_KEY_TEXT
                # Greedy first group so multi-word keys (FUTURES_RATIO,
                # OI_VEL_CW_STATUS) stay intact; value is after the last '_'
                m = re.match(r"0:META_(.+)_(.+)$", tok)
                if m:
                    key, val = m.group(1), m.group(2)
                    # Try to float it
                    try:
                        val = float(val)
                    except ValueError:
                        pass
                    meta[key] = val
            else:
                # Level token: price:filter|significance|label
                m = re.match(r"([\d.]+):([EWAI])\|([PSC])\|(.+)", tok)
                if m:
                    levels.append({
                        "price": float(m.group(1)),
                        "filter": m.group(2),
                        "significance": m.group(3),
                        "label": m.group(4).strip(),
                        "raw": tok,
                    })
        result[ticker] = {"levels": levels, "meta": meta}
    return result


def match_level(levels: list[dict], label: str) -> float | None:
    """Return the price of the first level matching `label`.
    Tries exact match first, then substring."""
    exact = [lv for lv in levels if lv["label"] == label]
    if exact:
        return exact[0]["price"]
    contains = [lv for lv in levels if label in lv["label"]]
    if contains:
        return contains[0]["price"]
    return None


def get_meta(ticker_data: dict, key: str) -> float | None:
    v = ticker_data["meta"].get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


# ─── Level taxonomy ───────────────────────────────────────────────────────

LEVEL_TYPES = [
    "EM HI", "EM LO", "EM85 HI", "EM85 LO",
    "ZERO GEX", "ZERO GEX DA",
    "CLIFF UP", "CLIFF DN",
    "FLIP UP", "FLIP DN",
    "MAGNET",
    "CW", "PW", "MAX", "PIN", "HW",
]


# ─── Main ─────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 80)
    print("=== ES / SPX / SPY  Unified Levels Drift Analysis ===")
    print("=" * 80)

    # --- 1. Parse unified levels ---
    txt_path = os.path.join(OPTIONS, "current", "unified_levels_close.txt")
    if not os.path.exists(txt_path):
        txt_path = os.path.join(OPTIONS, "unified_levels.txt")
    print(f"\n[1] Loading: {txt_path}")
    uni = parse_unified_txt(txt_path)
    print(f"    Tickers: {list(uni.keys())}")

    if "SPY" not in uni or "ES" not in uni:
        print("    ERROR: SPY or ES not found in unified levels")
        return
    has_spx = "SPX" in uni
    if has_spx:
        print("    SPX: present (native SPX levels)")
    else:
        print("    SPX: NOT in unified txt")
        return

    # --- 2. Extract META tokens ---
    print("\n[2] META tokens:")
    for tkr in ("SPY", "SPX", "ES"):
        if tkr not in uni:
            continue
        m = uni[tkr]["meta"]
        ratio = m.get("FUTURES_RATIO")
        basis = m.get("FUTURES_BASIS")
        iv = m.get("IV")
        gex = m.get("GEX_TOTAL")
        vanna = m.get("VANNA")
        print(f"    {tkr}: ratio={ratio}  basis={basis}  IV={iv}  "
              f"GEX={gex}  Vanna={vanna}")

    # --- 3. Compare levels across instruments ---
    futures_ratio = get_meta(uni["SPY"], "FUTURES_RATIO") or 10.0
    spx_basis = get_meta(uni.get("SPX", {}), "FUTURES_BASIS") or 42.0

    print(f"\n[3] Level-by-level comparison  (futures_ratio={futures_ratio:.4f}, "
          f"spx_basis={spx_basis:.2f}):")
    print(f"    {'Label':<18} {'SPY':>10} {'SPX':>10} {'ES':>10} "
          f"{'SPX/SPY':>10} {'ES/SPY':>10} {'ES calc':>10} {'ES drift':>10}")
    print("    " + "-" * 96)

    rows = []
    spy_levels = uni["SPY"]["levels"]
    es_levels = uni["ES"]["levels"]
    spx_levels = uni.get("SPX", {}).get("levels", [])

    for label in LEVEL_TYPES:
        spy_val = match_level(spy_levels, label)
        es_val = match_level(es_levels, label)
        spx_val = match_level(spx_levels, label)

        if spy_val is None and es_val is None and spx_val is None:
            continue

        spx_spy_ratio = spx_val / spy_val if (spx_val and spy_val) else None
        es_spy_ratio = es_val / spy_val if (es_val and spy_val) else None
        es_calc = spy_val * futures_ratio if spy_val else None
        es_drift = es_val - es_calc if (es_val is not None and es_calc is not None) else None

        def fmt(v, w=10):
            return f"{v:>{w}.2f}" if v is not None else f"{'—':>{w}}"

        def fmt_ratio(v):
            return f"{v:>10.4f}" if v is not None else f"{'—':>10}"

        print(f"    {label:<18} {fmt(spy_val)} {fmt(spx_val)} {fmt(es_val)} "
              f"{fmt_ratio(spx_spy_ratio)} {fmt_ratio(es_spy_ratio)} "
              f"{fmt(es_calc)} {fmt(es_drift)}")

        rows.append({
            "label": label,
            "SPY": spy_val,
            "SPX": spx_val,
            "ES": es_val,
            "SPX_SPY_ratio": spx_spy_ratio,
            "ES_SPY_ratio": es_spy_ratio,
            "ES_calc_from_SPY": es_calc,
            "ES_drift": es_drift,
            "futures_ratio": futures_ratio,
        })

    df = pd.DataFrame(rows)

    # --- 4. SPX vs SPY drift (independent options chains) ---
    print("\n[4] SPX vs SPY drift (independent options chains):")
    both = df.dropna(subset=["SPY", "SPX"]).copy()
    if len(both) > 0:
        both["spx_spy10"] = both["SPY"] * 10
        both["spx_minus_spy10"] = both["SPX"] - both["spx_spy10"]
        both["spx_spy_pct_diff"] = (both["SPX"] / both["spx_spy10"] - 1) * 100

        em_rows = both[both["label"].str.startswith("EM")]
        gex_rows = both[~both["label"].str.startswith("EM")]

        print(f"\n    EM levels ({len(em_rows)}):")
        for _, r in em_rows.iterrows():
            print(f"      {r['label']:<18} SPY={r['SPY']:.2f}  SPX={r['SPX']:.2f}  "
                  f"SPX/(SPY×10)={r['SPX']/r['spx_spy10']:.6f}  "
                  f"diff={r['spx_spy_pct_diff']:+.4f}%")

        print(f"\n    GEX/structural levels ({len(gex_rows)}):")
        for _, r in gex_rows.iterrows():
            print(f"      {r['label']:<18} SPY={r['SPY']:.2f}  SPX={r['SPX']:.2f}  "
                  f"SPX/(SPY×10)={r['SPX']/r['spx_spy10']:.6f}  "
                  f"diff={r['spx_spy_pct_diff']:+.4f}%")

        print(f"\n    Summary (SPX vs SPY×10):")
        if len(em_rows) > 0:
            print(f"      EM  mean diff:  {em_rows['spx_spy_pct_diff'].mean():+.4f}%  "
                  f"std={em_rows['spx_spy_pct_diff'].std():.4f}%")
        if len(gex_rows) > 0:
            print(f"      GEX mean diff:  {gex_rows['spx_spy_pct_diff'].mean():+.4f}%  "
                  f"std={gex_rows['spx_spy_pct_diff'].std():.4f}%")
        print(f"      ALL mean diff:  {both['spx_spy_pct_diff'].mean():+.4f}%  "
              f"std={both['spx_spy_pct_diff'].std():.4f}%")
    else:
        print("    No overlapping SPY/SPX levels found")

    # --- 5. ES vs SPY×ratio drift (translation accuracy) ---
    print("\n[5] ES vs SPY×futures_ratio drift (translation accuracy):")
    es_both = df.dropna(subset=["ES_calc_from_SPY", "ES"]).copy()
    if len(es_both) > 0:
        es_both["es_drift_pct"] = es_both["ES_drift"] / es_both["ES_calc_from_SPY"] * 100

        for _, r in es_both.iterrows():
            print(f"      {r['label']:<18} ES={r['ES']:.2f}  "
                  f"SPY×{r['futures_ratio']:.4f}={r['ES_calc_from_SPY']:.2f}  "
                  f"drift={r['ES_drift']:+.2f} pts ({r['es_drift_pct']:+.4f}%)")

        print(f"\n    Summary (ES vs SPY×ratio):")
        print(f"      mean drift: {es_both['ES_drift'].mean():+.2f} pts  "
              f"({es_both['es_drift_pct'].mean():+.4f}%)")
        print(f"      std drift:  {es_both['ES_drift'].std():.2f} pts  "
              f"({es_both['es_drift_pct'].std():.4f}%)")
        print(f"      max |drift|: {es_both['ES_drift'].abs().max():.2f} pts  "
              f"({es_both['es_drift_pct'].abs().max():.4f}%)")
    else:
        print("    No overlapping ES levels found")

    # --- 6. ES vs SPX drift (futures vs cash index) ---
    print("\n[6] ES vs SPX drift (futures vs cash index):")
    es_spx = df.dropna(subset=["ES", "SPX"]).copy()
    if len(es_spx) > 0:
        es_spx["expected_es_from_spx"] = es_spx["SPX"] + spx_basis
        es_spx["es_spx_drift"] = es_spx["ES"] - es_spx["expected_es_from_spx"]
        es_spx["es_spx_drift_pct"] = es_spx["es_spx_drift"] / es_spx["expected_es_from_spx"] * 100

        for _, r in es_spx.iterrows():
            print(f"      {r['label']:<18} ES={r['ES']:.2f}  "
                  f"SPX+{spx_basis:.0f}={r['expected_es_from_spx']:.2f}  "
                  f"drift={r['es_spx_drift']:+.2f} pts ({r['es_spx_drift_pct']:+.4f}%)")

        print(f"\n    Summary (ES vs SPX+basis):")
        print(f"      mean drift: {es_spx['es_spx_drift'].mean():+.2f} pts")
        print(f"      std drift:  {es_spx['es_spx_drift'].std():.2f} pts")
        print(f"      max |drift|: {es_spx['es_spx_drift'].abs().max():.2f} pts")
    else:
        print("    No overlapping ES/SPX levels found")

    # --- 7. Save CSV ---
    out_path = os.path.join(ANALYSIS, "unified_levels_drift.csv")
    df.to_csv(out_path, index=False)
    print(f"\n[7] Saved → {out_path}")

    print("\n" + "=" * 80)
    print("KEY TAKEAWAYS:")
    print("  • SPX vs SPY: The real drift test — SPX has its own options chain.")
    print("    EM levels should scale ~10× but GEX (gamma walls/flip/zero) will")
    print("    differ because SPX OI is independent from SPY OI.")
    print("  • ES vs SPY: Should be near-zero drift if futures_ratio is accurate.")
    print("  • ES vs SPX: Should be ≈ futures_basis (fair value spread).")
    print("=" * 80)


if __name__ == "__main__":
    main()