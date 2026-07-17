"""
NQStats Classifier Module - Vectorized ALN and Broken Status logic.
Based on NQStats Unified Bias Algorithm.
"""

import pandas as pd
import numpy as np

# ── ALN Pattern metadata (full name + definition + bias + probabilities) ─
# Source: docs/library/nqstats/NQ_SESSIONS_SPEC.md (10-year, n=2,542)
# Used to pass the full human-readable string + pre-computed bias to the LLM
# so the LLM doesn't have to interpret abbreviations or re-derive probabilities.
ALN_PATTERN_META = {
    "LEA": {
        "full_name": "London Engulfs Asia",
        "definition": "London High > Asia High AND London Low < Asia Low. London trades wider than Asia on both sides.",
        "bias": "Neutral (coin flip, no directional edge)",
        "frequency": "22.0%",
        "break_high_pct": 71.5,
        "break_low_pct": 70.4,
        "primary_target": "NONE",
        "primary_target_pct": 0.0,
        "edge_spent_rule": "No edge to spend — 50/50 first break.",
    },
    "AEL": {
        "full_name": "Asia Engulfs London",
        "definition": "London High <= Asia High AND London Low >= Asia Low. London stays inside the Asia range (coiled).",
        "bias": "Coiled (neutral, rare ~7%)",
        "frequency": "6.9%",
        "break_high_pct": 81.1,
        "break_low_pct": 74.9,
        "primary_target": "NONE",
        "primary_target_pct": 0.0,
        "edge_spent_rule": "No edge — NY always breaks a level but direction is ambiguous. Low-first break is a bullish tell (59.8% high follows).",
    },
    "LPEU": {
        "full_name": "London Partial Engulf Up",
        "definition": "London High > Asia High AND London Low >= Asia Low. London breaks up but holds the Asian low.",
        "bias": "Bullish (80.8% NY breaks London High)",
        "frequency": "41.0%",
        "break_high_pct": 80.8,
        "break_low_pct": 65.5,
        "primary_target": "LONDON_HIGH",
        "primary_target_pct": 80.8,
        "edge_spent_rule": "If price is already above London High, the bullish edge is spent.",
    },
    "LPED": {
        "full_name": "London Partial Engulf Down",
        "definition": "London Low < Asia Low AND London High <= Asia High. London breaks down but holds the Asian high.",
        "bias": "Bearish (75.0% NY breaks London Low)",
        "frequency": "30.2%",
        "break_high_pct": 68.6,
        "break_low_pct": 75.0,
        "primary_target": "LONDON_LOW",
        "primary_target_pct": 75.0,
        "edge_spent_rule": "If price is already below London Low, the bearish edge is spent.",
    },
}


def aln_full_string(code: str) -> str:
    """Return the full human-readable ALN pattern string for the LLM.

    Format: 'London Partial Engulf Down — London Low < Asia Low AND London
    High <= Asia High. London breaks down but holds the Asian high. | Bias:
    Bearish (75.0% NY breaks London Low)'

    Falls back to the raw code if unknown.
    """
    meta = ALN_PATTERN_META.get(code)
    if not meta:
        return code
    return (
        f"{meta['full_name']} — {meta['definition']} "
        f"| Bias: {meta['bias']}"
    )


def aln_full_name(code: str) -> str:
    """Return just the full name (e.g. 'London Partial Engulf Down')."""
    meta = ALN_PATTERN_META.get(code)
    return meta["full_name"] if meta else code


def compute_aln_bias(
    code: str,
    broken_status: str,
    spot: float | None = None,
    london_high: float | None = None,
    london_low: float | None = None,
) -> dict:
    """Compute the full ALN bias verdict for the LLM.

    This is the SINGLE SOURCE OF TRUTH for ALN bias. The prompt should not
    re-derive any of this — it should trust these fields.

    Returns:
        dict with keys:
            bias: str — "STRONG BULLISH" / "STRONG BEARISH" / "NEUTRAL / CHOP" / "NEUTRAL / WAIT"
            conviction: str — "HIGH" / "LOW"
            reasoning: str — human-readable one-liner
            primary_target: str — "LONDON_HIGH" / "LONDON_LOW" / "NONE"
            primary_target_pct: float — probability NY breaks the primary target
            break_high_pct: float — probability NY breaks London High
            break_low_pct: float — probability NY breaks London Low
            edge_spent: bool — True if price has already moved beyond the primary target
            edge_spent_note: str — empty or explanation
    """
    meta = ALN_PATTERN_META.get(code)
    if not meta:
        return {
            "bias": "NEUTRAL / WAIT",
            "conviction": "LOW",
            "reasoning": f"{code} + {broken_status} — unknown pattern.",
            "primary_target": "NONE",
            "primary_target_pct": 0.0,
            "break_high_pct": 0.0,
            "break_low_pct": 0.0,
            "edge_spent": False,
            "edge_spent_note": "",
        }

    bh = meta["break_high_pct"]
    bl = meta["break_low_pct"]
    pt = meta["primary_target"]
    pt_pct = meta["primary_target_pct"]

    # Determine bias + conviction from pattern + broken status
    if "Broken/Broken" in broken_status:
        bias = "NEUTRAL / CHOP"
        conviction = "LOW"
        reasoning = f"{meta['full_name']} + both sessions broken — high volatility, no directional edge. Reduce size."
    elif code == "LPEU" and ("Held/Held" in broken_status or "Broken/Held" in broken_status):
        bias = "STRONG BULLISH"
        conviction = "HIGH"
        reasoning = f"{meta['full_name']} + clean structure. {bh}% NY breaks London High."
    elif code == "LPED" and ("Held/Held" in broken_status or "Broken/Held" in broken_status):
        bias = "STRONG BEARISH"
        conviction = "HIGH"
        reasoning = f"{meta['full_name']} + clean structure. {bl}% NY breaks London Low."
    elif code in ("LEA", "AEL"):
        bias = "NEUTRAL / WAIT"
        conviction = "LOW"
        reasoning = f"{meta['full_name']} — no directional edge. Wait for NY to resolve."
    else:
        bias = "NEUTRAL / WAIT"
        conviction = "LOW"
        reasoning = f"{meta['full_name']} + {broken_status} — no high-conviction edge."

    # Edge spent check: has price already moved beyond the primary target?
    edge_spent = False
    edge_spent_note = ""
    if pt == "LONDON_HIGH" and spot is not None and london_high is not None:
        if spot >= london_high:
            edge_spent = True
            edge_spent_note = f"Price ({spot:,.2f}) already at/above London High ({london_high:,.2f}) — bullish edge spent."
    elif pt == "LONDON_LOW" and spot is not None and london_low is not None:
        if spot <= london_low:
            edge_spent = True
            edge_spent_note = f"Price ({spot:,.2f}) already at/below London Low ({london_low:,.2f}) — bearish edge spent."

    return {
        "bias": bias,
        "conviction": conviction,
        "reasoning": reasoning,
        "primary_target": pt,
        "primary_target_pct": pt_pct,
        "break_high_pct": bh,
        "break_low_pct": bl,
        "edge_spent": edge_spent,
        "edge_spent_note": edge_spent_note,
    }

def classify_aln_vectorized(sessions_df: pd.DataFrame) -> pd.Series:
    """
    Classify the ALN Pattern (Asia-London-NY relationship).
    LPEU: London High > Asia High, London Low >= Asia Low (Bullish)
    LPED: London Low < Asia Low, London High <= Asia High (Bearish)
    LEA:  London breaks BOTH Asia extremes (Expansion)
    AEL:  London inside Asia (Consolidation)
    """
    # Columns expected: asia_high, asia_low, london_high, london_low
    ah = sessions_df['asia_high'].values
    al = sessions_df['asia_low'].values
    lh = sessions_df['london_high'].values
    ll = sessions_df['london_low'].values
    
    # Conditions
    lea = (lh > ah) & (ll < al)
    lpeu = (lh > ah) & (ll >= al)
    lped = (ll < al) & (lh <= ah)
    ael = (lh <= ah) & (ll >= al)
    
    # Create result series
    results = pd.Series("Unknown", index=sessions_df.index)
    results[lea] = "LEA"
    results[lpeu] = "LPEU"
    results[lped] = "LPED"
    results[ael] = "AEL"
    
    return results

def get_broken_status_vectorized(sessions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Check if subsequent sessions break prior session ranges.
    - Did London break Asia?
    - Did Pre-NY break London?
    - Did NY_AM break London or Asia?
    """
    # 1. London vs Asia
    ah = sessions_df['asia_high'].values
    al = sessions_df['asia_low'].values
    lh = sessions_df['london_high'].values
    ll = sessions_df['london_low'].values
    
    london_broke_asia = (lh > ah) | (ll < al)
    
    # 2. Pre-NY vs London
    ph = sessions_df['pre-ny_high'].values
    pl = sessions_df['pre-ny_low'].values
    
    preny_broke_london = (ph > lh) | (pl < ll)
    
    # Output labels
    l_vs_a = np.where(london_broke_asia, "Broken", "Held")
    p_vs_l = np.where(preny_broke_london, "Broken", "Held")
    
    # Build combo string Series
    combo = pd.Series(l_vs_a, index=sessions_df.index) + "/" + pd.Series(p_vs_l, index=sessions_df.index)
    
    return pd.DataFrame({
        "london_vs_asia": l_vs_a,
        "preny_vs_london": p_vs_l,
        "broken_status": combo
    }, index=sessions_df.index)

def get_profiler_status_vectorized(sessions_df: pd.DataFrame, prior_close: pd.Series) -> pd.Series:
    """
    Check session alignment relative to Prior Close (P12).
    Asia Status (L/S/N) / London Status (L/S/N)
    """
    ac = sessions_df['asia_close'].values
    lc = sessions_df['london_close'].values
    p12 = prior_close.values
    
    a_status = np.where(ac > p12, "L", np.where(ac < p12, "S", "N"))
    l_status = np.where(lc > p12, "L", np.where(lc < p12, "S", "N"))
    
    return pd.Series(a_status, index=sessions_df.index) + "/" + pd.Series(l_status, index=sessions_df.index)

def classify_noon_curve_vectorized(ohlc: pd.DataFrame) -> pd.Series:
    """
    Check if High-of-Day (HOD) and Low-of-Day (LOD) occur on opposite sides of Noon (12:00 ET).
    Window: 08:00 - 16:00 ET.
    """
    # 1. Filter to RTH window (08:00 - 16:00)
    et_df = ohlc.tz_convert('US/Eastern') if ohlc.index.tz else ohlc
    rth = et_df.between_time("08:00", "16:00")
    
    if rth.empty:
        return pd.Series("Unknown", index=ohlc.index)
        
    # 2. Get HOD and LOD times per day
    daily_groups = rth.groupby(rth.index.date)
    
    hod_times = daily_groups['high'].idxmax()
    lod_times = daily_groups['low'].idxmin()
    
    # 3. Check if they are on opposite sides of 12:00
    noon = pd.Timestamp("12:00").time()
    
    is_hod_am = hod_times.apply(lambda x: x.time() < noon)
    is_lod_am = lod_times.apply(lambda x: x.time() < noon)
    
    opposite = is_hod_am != is_lod_am
    
    # Results per date
    results = pd.Series("Same Side", index=hod_times.index)
    results[opposite] = "Opposite"
    
    # Map back to original index using vectorized reindexing
    # Performance: Avoid list comprehension over ohlc.index.date
    dates = ohlc.index.date
    final_output = results.reindex(dates).values
    
    return pd.Series(final_output, index=ohlc.index)
def get_quadrant_status(df_1m: pd.DataFrame, boxes_df: pd.DataFrame) -> pd.DataFrame:
    """
    High-Performance Vectorized Profiler Quadrant logic.
    Identifies session breakout direction and holding power (True vs False).
    """
    et_df = df_1m.tz_convert('US/Eastern') if df_1m.index.tz else df_1m
    
    box_names = ['asiabox', 'londonbox', 'ny1box', 'ny2box']
    results = pd.DataFrame(index=df_1m.index)
    
    # Pre-calculated evaluations start/end
    eval_config = {
        'asiabox':   {'start': '19:30', 'end': '02:30'},
        'londonbox': {'start': '03:30', 'end': '07:30'},
        'ny1box':    {'start': '08:30', 'end': '11:00'},
        'ny2box':    {'start': '12:30', 'end': '16:00'}
    }
    
    for box_prefix in box_names:
        bh_series = boxes_df[f'{box_prefix}_high']
        bl_series = boxes_df[f'{box_prefix}_low']
        
        # 1. Create evaluation window mask
        cfg = eval_config[box_prefix]
        if cfg['start'] < cfg['end']:
            time_mask = (et_df.index.time >= pd.Timestamp(cfg['start']).time()) & (et_df.index.time < pd.Timestamp(cfg['end']).time())
        else: # AsiaBox is overnight
            time_mask = (et_df.index.time >= pd.Timestamp(cfg['start']).time()) | (et_df.index.time < pd.Timestamp(cfg['end']).time())
        
        # 2. Vectorized Breakout detection
        broke_high = (et_df['high'] > bh_series) & time_mask
        broke_low = (et_df['low'] < bl_series) & time_mask
        
        # 3. Determine first occurrence per day using groupby
        # We find the MIN index (time) where the condition is True
        dates = et_df.index.date
        
        # Use trading dates for grouping (matches sessions.py logic)
        if box_prefix == 'asiabox': 
            start_t = pd.Timestamp(eval_config[box_prefix]['start']).time()
            pm_mask = et_df.index.time >= start_t
            groups = pd.Series(dates, index=et_df.index)
            groups.loc[pm_mask] = groups.loc[pm_mask] + pd.Timedelta(days=1)
        else:
            groups = pd.Series(dates, index=et_df.index)
            
        h_triggers = et_df.index[broke_high].to_series().groupby(groups[broke_high]).min()
        l_triggers = et_df.index[broke_low].to_series().groupby(groups[broke_low]).min()
        
        # 4. Create Status Series for each day
        unique_groups = np.unique(groups.values)
        status_series = pd.Series("None", index=unique_groups)
        
        # Vectorized identification of statuses
        triggered_h = h_triggers.reindex(unique_groups)
        triggered_l = l_triggers.reindex(unique_groups)
        
        has_h = triggered_h.notna()
        has_l = triggered_l.notna()
        
        # First High: has high AND (no low OR high before low)
        first_h = has_h & (~has_l | (triggered_h < triggered_l))
        # First Low: has low AND (no high OR low before high)
        first_l = has_l & (~has_h | (triggered_l < triggered_h))
        
        status_series.loc[first_h & ~has_l] = "LT"
        status_series.loc[first_h & has_l] = "LF"
        status_series.loc[first_l & ~has_h] = "ST"
        status_series.loc[first_l & has_h] = "SF"
        
        # Map back to full index efficiently
        results[f'{box_prefix}_status'] = status_series.reindex(groups.values).values
        
    return results
