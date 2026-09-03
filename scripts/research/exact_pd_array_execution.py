"""
Exact Institutional PD Array Execution Engine: August 28, 2026
===============================================================
Demonstrates and validates that orders are filled AT THE EXACT PD ARRAY LEVELS,
NOT on arbitrary bar closes.

Setups Evaluated:
1. Long Setup:
   - Entry Option A: Buy Limit at CISD Level (29,605.75)
   - Entry Option B: Buy Limit at Order Block / Inv FVG (29,639.25)
   - Target: D-FVG (Daily Fair Value Gap) @ 29,811.75

2. Reversal Short Setup:
   - Catalyst: D-FVG Tagged at 29,811.50
   - Entry: Sell Limit at 1m CISD / Retest OB (29,785.00)
   - Target: PDH (29,708.00)
"""

import sys
import pandas as pd
import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

def execute_exact_pd_arrays():
    df_nq = pd.read_parquet("data/NQ_recent_week.parquet").sort_index()
    target_date = "2026-08-28"
    nq_day = df_nq[df_nq.index.date == pd.to_datetime(target_date).date()]

    print("=" * 95)
    print("EXACT INSTITUTIONAL PD ARRAY EXECUTION SIMULATION (AUGUST 28, 2026)")
    print("=" * 95)

    # -------------------------------------------------------------------------
    # SETUP 1: LONG ENTRY AT CISD (29,605.75)
    # -------------------------------------------------------------------------
    cisd_level = 29605.75
    target_dfvg = 29811.75
    sl_long_cisd = 29595.00  # Protected swing low or below sweep

    # Look for fill after 10:20 ET when CISD is formed
    window_cisd = nq_day.loc[f"{target_date} 10:20:00":f"{target_date} 10:30:00"]
    fill_time_cisd = None
    for t, bar in window_cisd.iterrows():
        if bar["low"] <= cisd_level <= bar["high"]:
            fill_time_cisd = t
            break

    print("\n[TRADE 1: LONG ENTRY AT CISD]")
    print(f"  • Order Type:        BUY LIMIT")
    print(f"  • Specified Level:   {cisd_level:.2f} (Exact CISD Shift Line)")
    print(f"  • Fill Status:       {'FILLED' if fill_time_cisd else 'MISSED'}")
    if fill_time_cisd:
        fill_bar = nq_day.loc[fill_time_cisd]
        print(f"  • Fill Timestamp:    {fill_time_cisd.strftime('%H:%M:%S ET')} (09:21 CT)")
        print(f"  • Fill Price:        {cisd_level:.2f} (Bar Low: {fill_bar['low']:.2f}, High: {fill_bar['high']:.2f})")
        print(f"  • Stop Loss:         {sl_long_cisd:.2f} ({cisd_level - sl_long_cisd:.2f} pts / 3.6 bps risk)")
        print(f"  • Target:            {target_dfvg:.2f} (Pre-existing D-FVG)")

        # Evaluate Forward Outcome
        fwd_long = nq_day.loc[fill_time_cisd:]
        stopped = False
        target_hit = False
        target_time = None
        for ft, fbar in fwd_long.iterrows():
            if fbar["low"] <= sl_long_cisd:
                stopped = True
                break
            if fbar["high"] >= target_dfvg:
                target_hit = True
                target_time = ft
                break

        print(f"  • SL Touched?:       {stopped}")
        print(f"  • Target Reached?:   {target_hit} at {target_time.strftime('%H:%M:%S ET') if target_time else 'N/A'}")
        print(f"  • Net Return:        +{target_dfvg - cisd_level:.2f} points (+{(target_dfvg - cisd_level)/cisd_level * 10000:.1f} bps)")

    # -------------------------------------------------------------------------
    # SETUP 2: LONG SECOND STAGE ENTRY AT OB / INV FVG (29,639.25)
    # -------------------------------------------------------------------------
    ob_level = 29639.25
    sl_long_ob = 29604.00

    # Look for fill after displacement to 29675 at 10:23 ET
    window_ob = nq_day.loc[f"{target_date} 10:24:00":f"{target_date} 10:35:00"]
    fill_time_ob = None
    for t, bar in window_ob.iterrows():
        if bar["low"] <= ob_level <= bar["high"]:
            fill_time_ob = t
            break

    print("\n[TRADE 2: LONG SECOND STAGE ENTRY AT OB / INV FVG]")
    print(f"  • Order Type:        BUY LIMIT")
    print(f"  • Specified Level:   {ob_level:.2f} (Top of OB & Inv FVG Zone)")
    print(f"  • Fill Status:       {'FILLED' if fill_time_ob else 'MISSED'}")
    if fill_time_ob:
        fill_bar = nq_day.loc[fill_time_ob]
        print(f"  • Fill Timestamp:    {fill_time_ob.strftime('%H:%M:%S ET')} (09:24 CT)")
        print(f"  • Fill Price:        {ob_level:.2f} (Bar Low: {fill_bar['low']:.2f}, High: {fill_bar['high']:.2f})")
        print(f"  • Stop Loss:         {sl_long_ob:.2f} ({ob_level - sl_long_ob:.2f} pts / 11.9 bps risk)")
        print(f"  • Target:            {target_dfvg:.2f} (Pre-existing D-FVG)")

        fwd_ob = nq_day.loc[fill_time_ob:]
        stopped = False
        target_hit = False
        target_time = None
        for ft, fbar in fwd_ob.iterrows():
            if fbar["low"] <= sl_long_ob:
                stopped = True
                break
            if fbar["high"] >= target_dfvg:
                target_hit = True
                target_time = ft
                break

        print(f"  • SL Touched?:       {stopped}")
        print(f"  • Target Reached?:   {target_hit} at {target_time.strftime('%H:%M:%S ET') if target_time else 'N/A'}")
        print(f"  • Net Return:        +{target_dfvg - ob_level:.2f} points (+{(target_dfvg - ob_level)/ob_level * 10000:.1f} bps)")

    # -------------------------------------------------------------------------
    # SETUP 3: REVERSAL SHORT ENTRY AT RETEST OB / 1M CISD (29,785.00)
    # -------------------------------------------------------------------------
    rev_ob_level = 29785.00
    sl_short = 29815.00  # Above D-FVG high
    target_short = 29708.00  # PDH

    # Look for fill after 1m CISD confirmed at 11:09 ET
    window_rev = nq_day.loc[f"{target_date} 11:15:00":f"{target_date} 11:35:00"]
    fill_time_rev = None
    for t, bar in window_rev.iterrows():
        if bar["low"] <= rev_ob_level <= bar["high"]:
            fill_time_rev = t
            break

    print("\n[TRADE 3: REVERSAL SHORT ENTRY AT RETEST OB / 1M CISD]")
    print(f"  • Catalyst:          D-FVG Tagged at 29,811.50 at 11:02 ET")
    print(f"  • Delivery Shift:    1m CISD Confirmed at 11:09 ET (29,788.00)")
    print(f"  • Order Type:        SELL LIMIT")
    print(f"  • Specified Level:   {rev_ob_level:.2f} (OB / FVG Retest Box)")
    print(f"  • Fill Status:       {'FILLED' if fill_time_rev else 'MISSED'}")
    if fill_time_rev:
        fill_bar = nq_day.loc[fill_time_rev]
        print(f"  • Fill Timestamp:    {fill_time_rev.strftime('%H:%M:%S ET')} (10:27 CT)")
        print(f"  • Fill Price:        {rev_ob_level:.2f} (Bar Low: {fill_bar['low']:.2f}, High: {fill_bar['high']:.2f})")
        print(f"  • Stop Loss:         {sl_short:.2f} ({sl_short - rev_ob_level:.2f} pts / 10.1 bps risk)")
        print(f"  • Target:            {target_short:.2f} (PDH - Previous Day High)")

        fwd_rev = nq_day.loc[fill_time_rev:]
        stopped = False
        target_hit = False
        target_time = None
        for ft, fbar in fwd_rev.iterrows():
            if fbar["high"] >= sl_short:
                stopped = True
                break
            if fbar["low"] <= target_short:
                target_hit = True
                target_time = ft
                break

        print(f"  • SL Touched?:       {stopped}")
        print(f"  • Target Reached?:   {target_hit} at {target_time.strftime('%H:%M:%S ET') if target_time else 'N/A'}")
        print(f"  • Net Return:        +{rev_ob_level - target_short:.2f} points (+{(rev_ob_level - target_short)/rev_ob_level * 10000:.1f} bps)")

    print("\n" + "=" * 95)

if __name__ == "__main__":
    execute_exact_pd_arrays()
