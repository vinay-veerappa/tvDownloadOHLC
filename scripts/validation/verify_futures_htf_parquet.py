"""
Verify futures HTF daily parquet files against yfinance and (for NQ) TradingView CSV.

Usage:
    python scripts/validation/verify_futures_htf_parquet.py [--days 200] [--symbol NQ1]

Compares close prices for the last N trading days across:
  - parquet  : data/<SYM>_1d.parquet  (built from yfinance via stream_chart.py)
  - yfinance : pulled fresh from Yahoo Finance at runtime
  - tv       : data/TV_OHLC/ CSV      (NQ only; exported from TradingView)
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

# ── resolve repo root & add to path ──────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "streaming"))

from stream_chart import get_trade_date_for_timestamp  # noqa: E402

# ── config ────────────────────────────────────────────────────────────────────
FUTURES = {
    "NQ1": {"yf": "NQ=F",  "schwab": "/NQ"},
    "ES1": {"yf": "ES=F",  "schwab": "/ES"},
    "YM1": {"yf": "YM=F",  "schwab": "/YM"},
    "RTY1": {"yf": "RTY=F", "schwab": "/RTY"},
    "CL1": {"yf": "CL=F",  "schwab": "/CL"},
    "GC1": {"yf": "GC=F",  "schwab": "/GC"},
}

# TradingView daily CSVs available in the repo (symbol → filename)
TV_CSV_MAP = {
    "NQ1": "CME_MINI_NQ1!, 1D_43d53.csv",
}

DATA_DIR = REPO_ROOT / "data"
TV_DIR   = DATA_DIR / "TV_OHLC"


# ── helpers ───────────────────────────────────────────────────────────────────

def load_parquet(sym: str, schwab_sym: str, n: int) -> pd.DataFrame:
    path = DATA_DIR / f"{sym}_1d.parquet"
    pq = pd.read_parquet(path).reset_index()
    pq["datetime"] = pd.to_datetime(pq["datetime"], utc=True)
    pq["trade_date"] = pq["datetime"].apply(
        lambda ts: pd.Timestamp(get_trade_date_for_timestamp(ts.to_pydatetime(), schwab_sym))
    )
    return (
        pq.rename(columns={"close": "pq_close"})[["trade_date", "pq_close"]]
        .sort_values("trade_date")
        .tail(n)
        .reset_index(drop=True)
    )


def load_yfinance(yf_sym: str, n: int) -> pd.DataFrame:
    # fetch slightly more than n days to account for non-trading days
    hist = yf.Ticker(yf_sym).history(period="1y", interval="1d", auto_adjust=False, actions=False)
    df = hist.reset_index()[["Date", "Close"]].copy()
    # yfinance stamps are one calendar day ahead of trade-date convention
    df["trade_date"] = (
        pd.to_datetime(df["Date"])
        .dt.tz_convert("America/New_York")
        .dt.tz_localize(None)
        .dt.normalize()
        - pd.Timedelta(days=1)
    )
    return (
        df.rename(columns={"Close": "yf_close"})[["trade_date", "yf_close"]]
        .sort_values("trade_date")
        .tail(n)
        .reset_index(drop=True)
    )


def load_tv(sym: str, n: int) -> pd.DataFrame | None:
    csv_name = TV_CSV_MAP.get(sym)
    if not csv_name:
        return None
    path = TV_DIR / csv_name
    if not path.exists():
        print(f"  [TV] CSV not found: {path}")
        return None
    raw = pd.read_csv(path)
    raw["trade_date"] = (
        pd.to_datetime(raw["time"], unit="s", utc=True)
        .dt.tz_convert("America/New_York")
        .dt.normalize()
        .dt.tz_localize(None)
    )
    return (
        raw.rename(columns={"close": "tv_close"})[["trade_date", "tv_close"]]
        .sort_values("trade_date")
        .tail(n)
        .reset_index(drop=True)
    )


def match_stats(series_a: pd.Series, series_b: pd.Series) -> dict:
    diff = (pd.to_numeric(series_a, errors="coerce") - pd.to_numeric(series_b, errors="coerce")).abs().dropna()
    if diff.empty:
        return {"rows": 0, "matches": 0, "pct": "n/a", "mean_diff": "n/a", "max_diff": "n/a"}
    return {
        "rows":      int(diff.shape[0]),
        "matches":   int((diff == 0).sum()),
        "pct":       f"{100 * (diff == 0).mean():.1f}%",
        "mean_diff": round(float(diff.mean()), 2),
        "max_diff":  round(float(diff.max()), 2),
    }


def run_symbol(sym: str, cfg: dict, n: int, verbose: bool) -> None:
    print(f"\n{'═' * 64}")
    print(f"  {sym}  ({cfg['yf']})  — last {n} trading days")
    print(f"{'═' * 64}")

    pq_df = load_parquet(sym, cfg["schwab"], n)
    yf_df = load_yfinance(cfg["yf"], n)
    tv_df = load_tv(sym, n)

    # merge on trade_date
    merged = pq_df.merge(yf_df, on="trade_date", how="outer")
    if tv_df is not None:
        merged = merged.merge(tv_df, on="trade_date", how="outer")
    merged = merged.sort_values("trade_date").reset_index(drop=True)

    # diff columns
    merged["pq_vs_yf"] = (
        pd.to_numeric(merged["pq_close"], errors="coerce")
        - pd.to_numeric(merged["yf_close"], errors="coerce")
    ).round(2)
    if tv_df is not None:
        merged["pq_vs_tv"] = (
            pd.to_numeric(merged["pq_close"], errors="coerce")
            - pd.to_numeric(merged["tv_close"], errors="coerce")
        ).round(2)
        merged["yf_vs_tv"] = (
            pd.to_numeric(merged["yf_close"], errors="coerce")
            - pd.to_numeric(merged["tv_close"], errors="coerce")
        ).round(2)

    if verbose:
        print(merged.to_string(index=False))
        print()

    # summary
    cols_present = ["pq_close", "yf_close"] + (["tv_close"] if tv_df is not None else [])
    pairs = [("pq_close", "yf_close")]
    if tv_df is not None:
        pairs += [("pq_close", "tv_close"), ("yf_close", "tv_close")]

    for lhs, rhs in pairs:
        stats = match_stats(merged[lhs], merged[rhs])
        flag = "✅" if stats["matches"] == stats["rows"] else ("⚠️ " if stats["pct"] >= "90" else "❌")
        print(
            f"  {flag} {lhs:12s} vs {rhs:12s} | "
            f"rows={stats['rows']:3d}  matches={stats['matches']:3d}  ({stats['pct']})  "
            f"mean_diff={stats['mean_diff']}  max_diff={stats['max_diff']}"
        )

    # flag any dates present in parquet but missing from yfinance (or vice-versa)
    pq_dates = set(merged.dropna(subset=["pq_close"])["trade_date"])
    yf_dates = set(merged.dropna(subset=["yf_close"])["trade_date"])
    only_pq = sorted(pq_dates - yf_dates)
    only_yf = sorted(yf_dates - pq_dates)
    if only_pq:
        print(f"  ⚠️  Dates in parquet but NOT in yfinance: {[str(d.date()) for d in only_pq[-5:]]}")
    if only_yf:
        print(f"  ℹ️  Dates in yfinance but NOT in parquet: {[str(d.date()) for d in only_yf[-5:]]}")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Verify futures HTF daily parquet vs yfinance (and TV for NQ).")
    parser.add_argument("--days",   type=int, default=200, help="Number of trailing trading days to check (default: 200)")
    parser.add_argument("--symbol", type=str, default=None, help="Restrict to one symbol, e.g. NQ1")
    parser.add_argument("--verbose", action="store_true", help="Print full row-by-row table")
    args = parser.parse_args()

    symbols = {args.symbol: FUTURES[args.symbol]} if args.symbol else FUTURES

    print(f"\nFutures HTF Parquet Verification — {args.days} days — {pd.Timestamp.now().date()}")
    for sym, cfg in symbols.items():
        try:
            run_symbol(sym, cfg, args.days, args.verbose)
        except Exception as exc:
            print(f"\n  ❌ {sym}: {exc}")

    print(f"\n{'─' * 64}\nDone.\n")


if __name__ == "__main__":
    main()
