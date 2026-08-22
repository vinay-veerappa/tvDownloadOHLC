"""Run Python IFVG/CISD Variant2 backtest on 1m, 3m, 5m for NQ1 and ES1."""
import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

import pandas as pd
from scripts.libs_py.data.loader import DataLoader
from scripts.trading_framework.config.config_loader import load_config
from scripts.strategies.ifvg_cisd.core.ifvg_cisd_strategy import IFVGCISDStrategy
from scripts.research.run_strategy_filter_ablation import simulate_trade_policy

config = load_config("scripts/trading_framework/config/sessions.yaml")
loader = DataLoader(config)

results = []
for symbol in ["NQ1", "ES1"]:
    print(f"Loading {symbol}...")
    df = loader.load_enriched(symbol)
    df = df[df.index >= "2025-01-01"].copy()
    print(f"  {len(df):,d} bars ({df.index[0].date()} to {df.index[-1].date()})")

    strategy = IFVGCISDStrategy(ticker=symbol)
    point_value = 2.0 if "NQ" in symbol else 5.0
    tick_size = 0.25

    for tf in ["1min", "3min", "5min"]:
        params = {
            "resample_tf": tf,
            "filter_lunch": True,
            "max_trades_per_day": 2,
            "r_mult_tp1": 1.0,
            "r_mult_tp2": 2.5,
            "atr_risk_mult": 1.8,
            "variant": "variant2",
        }
        signals = strategy.hunt(df, params)
        n = len(signals)
        if n == 0:
            results.append({"symbol": symbol, "tf": tf, "signals": 0, "trades": 0, "wr": 0, "pf": 0, "pnl": 0, "maxdd": 0, "sharpe": 0})
            print(f"  {tf}: 0 signals")
            continue
        metrics = simulate_trade_policy(
            signals, df, policy_name="CoverTheQueen_1.0R_2.5R",
            contracts=2, point_value=point_value, commission_per_contract=1.05,
            slippage_ticks=1, tick_size=tick_size, account_size=50000, max_forward_bars=240,
        )
        results.append({
            "symbol": symbol, "tf": tf, "signals": n,
            "trades": metrics["num_trades"], "wr": round(metrics["win_rate_%"], 1),
            "pf": round(metrics["profit_factor"], 2), "pnl": round(metrics["total_net_pnl_usd"], 0),
            "maxdd": round(metrics["max_drawdown_usd"], 0), "sharpe": round(metrics["sharpe_ratio"], 2),
        })
        print(f"  {tf}: {n} signals -> {metrics['num_trades']} trades, WR={metrics['win_rate_%']:.1f}%, PF={metrics['profit_factor']:.2f}, PnL=${metrics['total_net_pnl_usd']:.0f}")

print()
print("=" * 90)
print("PYTHON IFVG/CISD VARIANT2 - CoverTheQueen 1.0R/2.5R (Jan 2025 - Mar 2026)")
print("=" * 90)
df_out = pd.DataFrame(results)
print(df_out.to_string(index=False))
out_path = Path("reports/research/python_cisd_multi_tf.csv")
out_path.parent.mkdir(parents=True, exist_ok=True)
df_out.to_csv(out_path, index=False)
print(f"\nSaved: {out_path}")