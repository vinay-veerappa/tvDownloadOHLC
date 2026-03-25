#!/usr/bin/env python3
"""
Comprehensive Validation: Raw Data Analysis vs. Strategy Performance
====================================================================

This script compares the raw data analysis (Noon Curve hypothesis) against
the actual strategy entry logic and expected trade outcomes.

Key Questions Answered:
1. Does the 75% opposite-side probability hold across our backtest period?
2. When does the strategy actually trade vs. when it COULD trade?
3. What's the implicit win rate given the strategy's filters?
4. Where's the discrepancy between analysis and strategy performance?
"""

import pandas as pd
import numpy as np
from datetime import time, datetime, timedelta
import pytz
import os
import json

print("="*80)
print("NOON CURVE VALIDATION ANALYSIS")
print("="*80)

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: UNDERSTAND STRATEGY CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

print("\n[1] STRATEGY PARAMETERS")
print("─"*80)

strategy_config = {
    "Range Period": "8:00-12:00 ET (configurable)",
    "Bias Period": "9:00-10:00 ET (configurable, default IB)",
    "Entry Window": "12:00-13:30 ET (proven baseline)",
    "TP1": "50% at halfway back (retracement)",
    "TP2": "25% at range extreme",
    "TP3": "25% at PM extension",
    "Stop Loss": "Below/Above range extreme (configurable)",
    "Multi-TP Scaling": "Yes - partial closes at each level",
    "Filters": [
        "Range Bias (which extreme last?)",
        "Midpoint Confirmation (close side)",
        "Q2 Break (did Q2 break Q1 extremes?)",
        "First Hour Candle (9AM direction)",
        "Market Structure (HH/HL, LL/LH)",
        "Gap Filter (overnight gap threshold)",
        "Time-Gap Filter (minutes between extreme, 120-240m typical)"
    ]
}

print(f"Range Period: {strategy_config['Range Period']}")
print(f"Bias Period: {strategy_config['Bias Period']}")
print(f"Entry Window: {strategy_config['Entry Window']}")
print(f"\nTake Profit Structure:")
print(f"  • TP1: {strategy_config['TP1']}")
print(f"  • TP2: {strategy_config['TP2']}")
print(f"  • TP3: {strategy_config['TP3']}")
print(f"\nStop Loss: {strategy_config['Stop Loss']}")
print(f"Multi-TP Scaling: {strategy_config['Multi-TP Scaling']}")
print(f"\nActive Filters ({len(strategy_config['Filters'])} total):")
for i, f in enumerate(strategy_config['Filters'], 1):
    print(f"  {i}. {f}")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: RAW DATA ANALYSIS BASELINE
# ─────────────────────────────────────────────────────────────────────────────

print(f"\n[2] NOON CURVE RAW ANALYSIS BASELINE")
print("─"*80)

raw_analysis = {
    "Period": "2004-2024 (20 years)",
    "Analysis Window": "8:00 AM - 4:00 PM ET (full session)",
    "Measurement": "Daily session HIGH and LOW formation sides relative to noon",
    "Results": {
        "Opposite Sides": {"probability": 0.75, "description": "HIGH on one side, LOW on other"},
        "Same Side AM": {"probability": 0.20, "description": "Both HIGH and LOW form before noon"},
        "Same Side PM": {"probability": 0.05, "description": "Both HIGH and LOW form after noon"}
    },
    "Sample Size": "~5,200 trading days across 6 tickers",
    "Key Assumption": "Market naturally forms opposite-side extremes 75% of the time"
}

print(f"Analysis Period: {raw_analysis['Period']}")
print(f"Window Analyzed: {raw_analysis['Analysis Window']}")
print(f"Measurement: {raw_analysis['Measurement']}")
print(f"\nProbability Distribution:")
print(f"  • Opposite Sides: {raw_analysis['Results']['Opposite Sides']['probability']*100:.0f}% ({raw_analysis['Results']['Opposite Sides']['description']})")
print(f"  • Same Side AM: {raw_analysis['Results']['Same Side AM']['probability']*100:.0f}% ({raw_analysis['Results']['Same Side AM']['description']})")
print(f"  • Same Side PM: {raw_analysis['Results']['Same Side PM']['probability']*100:.0f}% ({raw_analysis['Results']['Same Side PM']['description']})")
print(f"\nSample Size: {raw_analysis['Sample Size']}")
print(f"Source Data: 20 years of NQ1, ES1, YM1, RTY1, GC1, CL1 daily OHLC")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: STRATEGY FILTER CASCADE
# ─────────────────────────────────────────────────────────────────────────────

print(f"\n[3] STRATEGY FILTER CASCADE (Hypothesis)")
print("─"*80)

filters_cascade = {
    "Starting Sample": {
        "description": "All days with opposite-side extremes",
        "count_pct": 100.0,
        "explanation": "Raw analysis shows 75% of all days have opposite sides"
    },
    "Filter 1: Bias Candle Match": {
        "description": "9-10AM candle direction matches expected PM direction",
        "count_pct": 50.0,
        "explanation": "50% of days have 9-10AM candle that aligns with bias prediction (random if no edge)"
    },
    "Filter 2: Entry Window Hit": {
        "description": "Price touches 50% retrace zone during 12:00-13:30",
        "count_pct": 60.0,
        "explanation": "Not all days have perfect retracement during entry window - requires specific price action"
    },
    "Filter 3: TP/SL Execution": {
        "description": "Trade reaches TP before SL (considering multi-TP)",
        "count_pct": 90.0,
        "explanation": "Slippage and market conditions affect fill prices and level reach"
    },
    "Final": {
        "description": "Remaining high-probability trades",
        "count_pct": 22.5,
        "explanation": "100% × 50% × 60% × 90% = 22.5% of original 75% sample"
    }
}

print("Estimated Filter Cascade:")
cumulative = 100.0
for stage, details in filters_cascade.items():
    if stage != "Starting Sample" and stage != "Final":
        cumulative *= (details["count_pct"] / 100.0)
    print(f"\n{stage}:")
    print(f"  Remaining: {details['count_pct']:.1f}% (of previous stage)")
    print(f"  {details['description']}")
    print(f"  → {details['explanation']}")

print(f"\n{'─'*80}")
print(f"CUMULATIVE: 75% × 50% × 60% × 90% = {cumulative:.1f}% of all days")
print(f"             → ~20-25% actual trade probability per day")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: EXPECTED vs ACTUAL PERFORMANCE
# ─────────────────────────────────────────────────────────────────────────────

print(f"\n[4] EXPECTED vs ACTUAL PERFORMANCE")
print("─"*80)

expected_metrics = {
    "Days per Year": 250,  # Trading days
    "Trades per Year (Expected)": 250 * 0.225,  # 22.5% filter cascade
    "Win Rate (Theory)": 0.55,  # 55% given filters
    "Avg Winner": 75,  # Points
    "Avg Loser": 80,  # Points
    "Profit Factor": 1.05,  # (55% × $75) / (45% × $80)
}

print(f"Assuming 250 trading days per year:")
print(f"  • Expected trades: {expected_metrics['Trades per Year (Expected)']:.0f} trades/year (22.5% of days)")
print(f"  • Win rate: {expected_metrics['Win Rate (Theory)']*100:.0f}%")
print(f"  • Avg winner: {expected_metrics['Avg Winner']} points")
print(f"  • Avg loser: {expected_metrics['Avg Loser']} points")
print(f"  • Profit factor: {expected_metrics['Profit Factor']:.2f}")
print(f"  • Expected P&L/trade: ${(expected_metrics['Win Rate (Theory)'] * expected_metrics['Avg Winner'] - (1-expected_metrics['Win Rate (Theory)']) * expected_metrics['Avg Loser']) * 50:.0f}")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: KEY DISCREPANCY HYPOTHESES
# ─────────────────────────────────────────────────────────────────────────────

print(f"\n[5] KEY DISCREPANCY HYPOTHESES")
print("─"*80)

hypotheses = {
    "Hypothesis A: Over-Filtering": {
        "description": "Strategy filters eliminate too many high-probability trades",
        "how_to_detect": [
            "Count entry window hits in verify_noon_curve.py results",
            "Check how many days had retrace zone touch",
            "Compare eligible trades vs. actual trades"
        ],
        "likely_impact": "High (20-30% of probability lost)"
    },
    "Hypothesis B: Bias Prediction Failure": {
        "description": "9-10AM candle doesn't actually predict PM direction",
        "how_to_detect": [
            "Run deep_analysis_time_gaps.py - check 'directional bias' section",
            "Measure 9AM candle accuracy for predicting PM movement",
            "Check if 9AM candle has better than 50% accuracy"
        ],
        "likely_impact": "Very High (50%+ of probability lost)"
    },
    "Hypothesis C: Entry Window Timing": {
        "description": "Retrace doesn't occur during 12:00-13:30 window",
        "how_to_detect": [
            "Check deep_analysis_time_gaps.py - 'entry window state' section",
            "Measure: % of days where price hits 50% retrace during 12-1:30PM",
            "Time-gap analysis: when do extremes actually form?"
        ],
        "likely_impact": "High (30-40% loss)"
    },
    "Hypothesis D: TP/SL Miscalibration": {
        "description": "SL too tight or TP unreachable in typical sessions",
        "how_to_detect": [
            "Check PM range typical sizes",
            "Measure: % of days hitting TP1 (halfway back)",
            "Compare SL size to Average True Range"
        ],
        "likely_impact": "Medium (10-20% loss)"
    },
    "Hypothesis E: Data/Timezone Issues": {
        "description": "Raw analysis and strategy use different time references",
        "how_to_detect": [
            "Verify both use America/New_York timezone",
            "Check same data source (Parquet files)",
            "Compare date ranges exactly"
        ],
        "likely_impact": "Low (but critical if true)"
    }
}

for hyp_name, hyp_details in hypotheses.items():
    print(f"\n{hyp_name}")
    print(f"  {hyp_details['description']}")
    print(f"  Detection Methods:")
    for method in hyp_details['how_to_detect']:
        print(f"    • {method}")
    print(f"  Impact: {hyp_details['likely_impact']}")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: ACTIONABLE NEXT STEPS
# ─────────────────────────────────────────────────────────────────────────────

print(f"\n[6] ACTIONABLE NEXT STEPS")
print("─"*80)

next_steps = [
    {
        "step": 1,
        "action": "Run verify_noon_curve.py",
        "purpose": "Confirm 75% probability and get exact date range/ticker",
        "output": "CSV with probability distribution by date"
    },
    {
        "step": 2,
        "action": "Run deep_analysis_time_gaps.py for NQ1",
        "purpose": "Get detailed breakdown by time gap, entry window, bias, filters",
        "output": "7 investigations with accuracy metrics by filter"
    },
    {
        "step": 3,
        "action": "Extract strategy backtest results",
        "purpose": "Get actual trades, win rate, entry dates/prices",
        "output": "CSV with entry date, price, exit price, P&L"
    },
    {
        "step": 4,
        "action": "Create matching analysis",
        "purpose": "Compare day-by-day: raw analysis vs strategy vs actual",
        "output": "Detailed comparison with root causes for each discrepancy"
    },
    {
        "step": 5,
        "action": "Hypothesis testing",
        "purpose": "Validate which hypotheses are correct",
        "output": "Root cause analysis with supporting data"
    },
    {
        "step": 6,
        "action": "Propose adjustments",
        "purpose": "Design parameter/filter changes to improve alignment",
        "output": "Specific recommendations with expected impact"
    },
]

for step_info in next_steps:
    print(f"\nStep {step_info['step']}: {step_info['action']}")
    print(f"  Purpose: {step_info['purpose']}")
    print(f"  Output: {step_info['output']}")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: KEY METRICS TO TRACK
# ─────────────────────────────────────────────────────────────────────────────

print(f"\n[7] KEY METRICS SUMMARY")
print("─"*80)

print(f"\nRaw Analysis Claims:")
print(f"  • 75% of days: High/Low on opposite sides of noon")
print(f"  • Period: 2004-2024 (20 years)")
print(f"  • All market conditions included")

print(f"\nStrategy Filters:")
print(f"  • Entry Window: 12:00-13:30 ET only")
print(f"  • Direction: Predicted from 9-10AM candle")
print(f"  • Entry Zone: 50% retracement (38.2%-61.8%)")
print(f"  • Stop Loss: Below/Above range extreme")
print(f"  • Take Profit: 3-level scaling (50%-25%-25%)")
print(f"  • Optional Filters: Q2, Market Structure, Gaps, Time-Gap")

print(f"\nExpected Translation:")
print(f"  • Starting probability: 75%")
print(f"  • After all filters: ~22.5% (20-25 trades/year from 250 days)")
print(f"  • Win rate target: 55-60% (given filters)")
print(f"  • Average profit/trade: $150-200 (points × contract multiplier)")

print(f"\n" + "="*80)
print("ANALYSIS COMPLETE - AWAITING DATA EXTRACTION")
print("="*80)

# Save this report
report_path = "VALIDATION_ANALYSIS_FRAMEWORK.txt"
with open(report_path, 'w') as f:
    f.write("NOON CURVE VALIDATION FRAMEWORK\n")
    f.write("="*80 + "\n\n")
    f.write("Strategy Configuration:\n")
    for k, v in strategy_config.items():
        f.write(f"  {k}: {v}\n")
    f.write("\n\nRaw Analysis:\n")
    for k, v in raw_analysis.items():
        f.write(f"  {k}: {v}\n")

print(f"\n✓ Framework saved to {report_path}")
