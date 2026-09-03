import pandas as pd
import numpy as np

# Compare the exact mechanics of Python and NinjaScript
parity_items = [
    {
        "Component": "Timeframe Architecture",
        "Python Implementation": "5m Structure (Signals) + 1m Execution (Intrabar Fills)",
        "NinjaTrader (C#) Implementation": "BarsArray[1] (5m) + BarsArray[0] (1m)",
        "Parity Status": "ALIGNED (SecondaryTimeframeMinutes = 5)"
    },
    {
        "Component": "Session Windows",
        "Python Implementation": "Earliest 09:45, Latest 15:30, Flatten 15:55, Lunch 12:00-13:30",
        "NinjaTrader (C#) Implementation": "EarliestEntry = 945, LatestEntry = 1530, FlattenBy = 1555, FilterLunch = true",
        "Parity Status": "ALIGNED"
    },
    {
        "Component": "CISD Detection (State of Delivery)",
        "Python Implementation": "consult_cb(bias, idx): Opposing open over 15-bar lookback + running extreme",
        "NinjaTrader (C#) Implementation": "ConsultCrystalBall(bias, out ep, out oe, out eb): Opposing open over 15 bars",
        "Parity Status": "ALIGNED"
    },
    {
        "Component": "Stop Loss Distance",
        "Python Implementation": "STRICT 5.0 bps (c * 0.0005) hard cap from entry fill price",
        "NinjaTrader (C#) Implementation": "Set to protectedSwing up to MaxRiskBps (15.0 bps) in ICTFVGCISDBot.cs",
        "Parity Status": "MISALIGNED: NT8 was allowing up to 15 bps loss while TP1 was only +10 bps!"
    },
    {
        "Component": "HTF Trend Gate",
        "Python Implementation": "4H EMA(50) (close > 4H EMA50 for Long, < for Short)",
        "NinjaTrader (C#) Implementation": "htfEma = EMA(50) on 5m series (only 250 mins, not 4-Hour!) and UseHtfFilter was default false",
        "Parity Status": "MISALIGNED: NT8 used 5m EMA50 instead of 4H EMA50 (~2,400 bars on 5m)"
    },
    {
        "Component": "External Liquidity Sweep Gate",
        "Python Implementation": "Implicit in 5m CISD reversal from extreme",
        "NinjaTrader (C#) Implementation": "RequireExternalSweep = true requires piercing PDH/PDL, London, Asia, or NY AM within 8 bars",
        "Parity Status": "MISALIGNED: Filters out valid trend continuation CISDs"
    },
    {
        "Component": "Target 1 (Queen)",
        "Python Implementation": "+10.0 bps (c * 0.0010) -> 50% scale out + Breakeven lock (+1 tick)",
        "NinjaTrader (C#) Implementation": "effectiveEntry * 0.0010 -> SetProfitTarget Queen + BreakevenTriggerR",
        "Parity Status": "ALIGNED"
    },
    {
        "Component": "Target 2 (Runner)",
        "Python Implementation": "+30.0 bps (c * 0.0030) fixed institutional runner target",
        "NinjaTrader (C#) Implementation": "Math.Max(TargetRMultiple * riskPoints, queenPts * 3.0) -> If riskPoints was 15 bps, target became 37.5 bps!",
        "Parity Status": "MISALIGNED: In NT8, wide stop expanded runner target beyond 30 bps"
    },
    {
        "Component": "Confirmed Re-entry Protocol",
        "Python Implementation": "If stopped out within 5 bps while HTF holds, re-enter on 1m breakout (60.5% win rate)",
        "NinjaTrader (C#) Implementation": "OnExecutionUpdate arms reentryArmed, CheckForSignal evaluates 1m breakout",
        "Parity Status": "PARTIALLY ALIGNED (Blocked when initial trade lost 15 bps instead of 5 bps)"
    }
]

df_p = pd.DataFrame(parity_items)
print("=" * 110)
print("COMPREHENSIVE PYTHON VS. NINJATRADER 8 (C#) PARITY MATRIX")
print("=" * 110)
for idx, row in df_p.iterrows():
    print(f"\n[{row['Component']}]")
    print(f"  Python:      {row['Python Implementation']}")
    print(f"  NinjaTrader: {row['NinjaTrader (C#) Implementation']}")
    print(f"  STATUS:      {row['Parity Status']}")
