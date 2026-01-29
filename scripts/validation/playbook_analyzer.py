import pandas as pd
import numpy as np
import pytz
from datetime import time, timedelta
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List

# Metric Container
@dataclass
class DayMetrics:
    date: pd.Timestamp
    
    # Base Session (e.g. Asia or London Context)
    base_high: float
    base_low: float
    base_range: float
    
    # Setup Session (e.g. Pre-London)
    setup_sweeps_high: bool
    setup_sweeps_low: bool
    setup_sweeps_none: bool
    setup_sweeps_both: bool
    
    # Trigger Session (e.g. Opening Range)
    or_high: float
    or_low: float
    or_first_sweep: str  # 'High', 'Low', 'None' (First break of BASE/SETUP range usually? Or simply OR behavior?)
    # Herman's Logic: "Did OR sweep Pre-London High/Low first?" OR "Did OR Breakout relative to ITSELF?"
    # Clarification: Herman says "Did Pre-London sweep Asia Logic".
    # Then "What did OR do?" -> "Did OR sweep PL High or Low?" OR "Did OR sweep Asia High/Low?"
    # The Playbook trees say: "1. OR SWEPT HIGH (of the OR range? No, OR establishes the range)."
    # Wait, "OR Swept High" in the tree usually means "Price broke the OR High".
    # Tree: "1. OR SWEPT HIGH" -> implies during the Expansion Phase, price broke OR High.
    # BUT OR Logic text: "Did Pre-London sweep Asia High? ... Plan: First clean break of PL Low".
    # Let's standardize:
    # 1. Context: Setup vs Base (PL vs Asia).
    # 2. Trigger: Expansion vs OR (London vs OR).
    # We need to capture: Which side of the OR did London break first?
    
    london_first_sweep: str # 'High', 'Low', 'None' (Did London break OR High or OR Low first?)
    london_sweep_time_m: Optional[float]
    london_penetration: Optional[float]
    london_range_expansion: bool

class PlaybookAnalyzer:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        if self.df.index.tz is None:
            self.df.index = self.df.index.tz_localize(pytz.utc).tz_convert("America/New_York")
        else:
            self.df.index = self.df.index.tz_convert("America/New_York")

    def analyze_session(self, 
                       base_start: str, base_end: str, # e.g. 20:00-00:00 (Asia)
                       setup_start: str, setup_end: str, # e.g. 00:00-02:00 (Pre-London)
                       trigger_start: str, trigger_end: str, # e.g. 02:00-03:00 (OR)
                       expansion_start: str, expansion_end: str # e.g. 03:00-05:00 (London)
                       ) -> pd.DataFrame:
        """
        Analyzes a specific session configuration for the entire dataset.
        Returns a DataFrame of DayMetrics.
        """
        results = []
        
        # Grouping Logic: We need to group by "Trading Day". 
        # Since sessions can cross midnight (Asia starts 20:00 prev day), 
        # we index by the date of the TRIGGER session (e.g. 02:00 OR -> Today).
        
        # We'll rely on an iterator that grabs chunks of data.
        # Efficient way: Resample or Iterate days?
        # Let's iterate unique dates derived from trigger session.
        
        # Identify valid trading days (must have data in trigger session)
        trigger_times = self.df.between_time(trigger_start, trigger_end)
        dates = pd.unique(trigger_times.index.date)
        
        print(f"Analyzing {len(dates)} days for session structure...")
        
        for d in dates:
            day_stats = self._process_day(d, base_start, base_end, 
                                        setup_start, setup_end, 
                                        trigger_start, trigger_end, 
                                        expansion_start, expansion_end)
            if day_stats:
                results.append(day_stats)
                
        return pd.DataFrame(results)

    def _process_day(self, date, base_s, base_e, setup_s, setup_e, trig_s, trig_e, exp_s, exp_e):
        # 1. Define timestamps for this Date
        # Handle "Previous Day" starts (e.g. 20:00).
        # We assume 'date' is the day of trigger/expansion.
        # If Base Start > Trigger Start (e.g. 20:00 > 02:00), Base is previous day.
        # Actually simplest heuristic: If hour > 12 and target is morning, it's prev day.
        
        def get_dt(time_str, ref_date, is_prev_day_check=True):
            h, m = map(int, time_str.split(':'))
            dt = pd.Timestamp.combine(ref_date, time(h, m)).tz_localize("America/New_York")
            
            # If we are parsing Base (20:00) relative to Trigger (02:00) on same 'date' obj,
            # 20:00 appears AFTER 02:00. So if time > trigger_time, it must be yesterday.
            # But this depends on the specific flow.
            # Let's anchor everything to the TRIGGER session date.
            
            # Logic: 
            # If session is usually "overnight" (Asia), 20:00 is Prev Day.
            # If session is London, 03:00 is Date.
            # We need a robust mapping.
            return dt

        # Let's parse strictly relative to the Trigger Start (Anchor).
        t_start_dt = pd.Timestamp.combine(date, time(*map(int, trig_s.split(':')))).tz_localize("America/New_York")
        
        # Helper to offset relative to Trigger
        def resolve_time(t_str, anchor_dt):
            h, m = map(int, t_str.split(':'))
            target_dt = pd.Timestamp.combine(anchor_dt.date(), time(h, m)).tz_localize("America/New_York")
            
            # Heuristics for wraparound:
            # If Target is > Anchor + 12h -> It's likely Yesterday (e.g. 20:00 vs 07:00).
            # If Target is < Anchor - 12h -> It's likely Tomorrow (unlikely here).
            # If Target is > Anchor but we know it should be before (Base/Setup) -> Prev Day.
            
            # Let's just explicit logic based on expected order: Base -> Setup -> Trigger -> Expansion
            return target_dt

        # Explicitly construct the timeline for this day
        # We assume standard sequence.
        # 1. Expansion (Last)
        # 2. Trigger (Anchor)
        # 3. Setup (Before Trigger)
        # 4. Base (Before Setup)
        
        # Trigger
        trig_on = t_start_dt
        trig_off = pd.Timestamp.combine(date, time(*map(int, trig_e.split(':')))).tz_localize("America/New_York")
        
        # Base (Asia)
        # e.g. 20:00. If 20:00 > 02:00 (Trigger), subtract 1 day.
        b_s_h = int(base_s.split(':')[0])
        b_s_dt = pd.Timestamp.combine(date, time(b_s_h, int(base_s.split(':')[1]))).tz_localize("America/New_York")
        if b_s_h > 14 and trig_on.hour < 12: # e.g. 20:00 vs 02:00
             b_s_dt -= timedelta(days=1)
        
        b_e_h = int(base_e.split(':')[0])
        b_e_dt = pd.Timestamp.combine(date, time(b_e_h, int(base_e.split(':')[1]))).tz_localize("America/New_York")
        if b_e_h > 14 and trig_on.hour < 12: # End can be 00:00 (0)
             b_e_dt -= timedelta(days=1)
        elif b_e_dt < b_s_dt: # Crosses midnight
             b_e_dt += timedelta(days=1)
             
        # Setup (Pre-London)
        s_s_h = int(setup_s.split(':')[0])
        s_s_dt = pd.Timestamp.combine(date, time(s_s_h, int(setup_s.split(':')[1]))).tz_localize("America/New_York")
        if s_s_h > 14 and trig_on.hour < 12:
            s_s_dt -= timedelta(days=1)
            
        s_e_h = int(setup_e.split(':')[0])
        s_e_dt = pd.Timestamp.combine(date, time(s_e_h, int(setup_e.split(':')[1]))).tz_localize("America/New_York")
        # Setup end usually matches Trigger start or close to it
        if s_e_dt < s_s_dt:
            s_e_dt += timedelta(days=1)
            
        # Expansion (London)
        e_s_h = int(exp_s.split(':')[0])
        e_s_dt = pd.Timestamp.combine(date, time(e_s_h, int(exp_s.split(':')[1]))).tz_localize("America/New_York")
        
        e_e_h = int(exp_e.split(':')[0])
        e_e_dt = pd.Timestamp.combine(date, time(e_e_h, int(exp_e.split(':')[1]))).tz_localize("America/New_York")
        
        # Slice Data
        base_df = self.df[b_s_dt : b_e_dt]
        setup_df = self.df[s_s_dt : s_e_dt]
        trig_df = self.df[trig_on : trig_off]
        exp_df = self.df[e_s_dt : e_e_dt]
        
        if base_df.empty or setup_df.empty or trig_df.empty or exp_df.empty:
            return None
            
        # --- METRICS CALCULATIONS ---
        
        # 1. Base Context
        base_h = base_df['high'].max()
        base_l = base_df['low'].min()
        base_rng = base_h - base_l
        
        # 2. Setup Action
        # Did Setup sweep Base?
        setup_h = setup_df['high'].max()
        setup_l = setup_df['low'].min()
        
        s_sweep_h = setup_h > base_h
        s_sweep_l = setup_l < base_l
        s_sweep_both = s_sweep_h and s_sweep_l
        s_sweep_none = not (s_sweep_h or s_sweep_l)
        
        # 3. Trigger / OR Attributes
        # OR itself has a High/Low
        or_h = trig_df['high'].max()
        or_l = trig_df['low'].min()
        
        # 4. Expansion First Sweep (The "Win/Loss" Logic)
        # Determine if Expansion broke OR High First or OR Low First
        # We iterate expansion candles.
        
        first_sweep = "None"
        sweep_time = None
        penetration = 0.0
        range_exp = False
        
        # Find first candle to break OR bounds
        # Note: We look for > OR_H or < OR_L
        # Using boolean masking is faster but we need finding specific first occurrence
        
        # Potential breaks
        breaks_h = exp_df[exp_df['high'] > or_h]
        breaks_l = exp_df[exp_df['low'] < or_l]
        
        safe_max = pd.Timestamp("2200-01-01").tz_localize("America/New_York")
        first_h_time = breaks_h.index[0] if not breaks_h.empty else safe_max
        first_l_time = breaks_l.index[0] if not breaks_l.empty else safe_max
        
        if first_h_time < first_l_time:
            first_sweep = "High"
            sweep_time = (first_h_time - e_s_dt).total_seconds() / 60.0 # Minutes from Expansion Start
            # Penetration: Max High of Expansion - OR High
            # (Note: Herman uses "Max excursion after valid break". Usually session max)
            penetration = exp_df['high'].max() - or_h
            range_exp = True
        elif first_l_time < first_h_time:
            first_sweep = "Low"
            sweep_time = (first_l_time - e_s_dt).total_seconds() / 60.0
            penetration = or_l - exp_df['low'].min() # Positive penetration means Distance traveled
            range_exp = True
        else:
            first_sweep = "None"
            
        return {
            'date': date,
            'base_range': base_rng,
            'pl_sweeps_high': s_sweep_h,
            'pl_sweeps_low': s_sweep_l,
            'pl_sweeps_both': s_sweep_both,
            'pl_sweeps_none': s_sweep_none,
            'or_high': or_h,
            'or_low': or_l,
            'london_first_sweep': first_sweep,
            'london_sweep_time': sweep_time,
            'london_penetration': penetration
        }
