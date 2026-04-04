"""
ADR-009 Verification: Pipeline benchmark.

Usage:
    python scripts/tools/benchmark_pipeline.py [NQ1]
"""
import sys
import time


def main():
    symbol = sys.argv[1] if len(sys.argv) > 1 else "NQ1"
    t0 = time.perf_counter()

    from scripts.trading_framework.config.config_loader import load_config
    from scripts.libs.data.loader import DataLoader
    from scripts.libs.features.feature_registry import FeatureRegistry

    config = load_config("scripts/trading_framework/config/sessions.yaml")
    loader = DataLoader(config)

    t1 = time.perf_counter()
    df = loader.load_enriched(symbol)
    t2 = time.perf_counter()

    reg = FeatureRegistry(config)
    df = reg.ensure_features(df, [
        "vwap", "ib_high", "chop_score", "ema_9", "bb_pct_b", "kc_mid",
        "atr_14", "above_vwap",
    ])
    t3 = time.perf_counter()

    total = t3 - t0
    load_t = t2 - t1
    feat_t = t3 - t2

    print("=" * 56)
    print(f"  Symbol:          {symbol}")
    print(f"  Bars loaded:     {len(df):,}")
    print(f"  Sessions:        {df['trading_date'].nunique():,}")
    print(f"  Columns:         {len(df.columns)}")
    print("-" * 56)
    print(f"  load_enriched:   {load_t:.2f}s")
    print(f"  ensure_features: {feat_t:.2f}s")
    print(f"  TOTAL:           {total:.2f}s")
    print("=" * 56)
    result = "PASS (<10s)" if total < 10 else "FAIL (>10s)"
    print(f"  ADR-009 verdict: {result}")
    print("=" * 56)

    # Spot checks
    print("\n--- Spot checks ---")
    if "chop_regime" in df.columns:
        print("chop_regime:", df["chop_regime"].value_counts().to_dict())
    else:
        print("chop_regime: (column absent — internals not loaded)")
    if "vwap" in df.columns:
        print("vwap tail:  ", df["vwap"].dropna().tail(2).to_dict())
    if "ib_formed" in df.columns:
        print("ib_formed bars:", df["ib_formed"].sum())
    else:
        print("ib_formed: (column absent)")
    print("all columns:", sorted(df.columns.tolist()))


if __name__ == "__main__":
    main()
