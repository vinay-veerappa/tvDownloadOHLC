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


# ── RTH Break Scenario Bias ────────────────────────────────────────────
# Source: NQStats RTH Breaks (10-year, n=2,488)
# YAML: narrative_stats.yaml::rth_breaks
RTH_BREAK_META = {
    "GAP_UP": {
        "label": "Gap Up (open above prior day RTH High)",
        "bias": "BULLISH",
        "hold_pct": 69.9,
        "no_reach_opposite_pct": 88.1,
        "read": "Bullish continuation — 70% chance close holds above pRTH High. Don't fade unless price reclaims pRTH High.",
    },
    "GAP_DOWN": {
        "label": "Gap Down (open below prior day RTH Low)",
        "bias": "BEARISH",
        "hold_pct": 59.5,
        "no_reach_opposite_pct": 90.4,
        "read": "Bearish continuation — 60% chance close holds below pRTH Low. Don't fade unless price reclaims pRTH Low.",
    },
    "INSIDE": {
        "label": "Inside Range (open within prior day RTH)",
        "bias": "NEUTRAL",
        "hold_pct": 0.0,
        "no_reach_opposite_pct": 0.0,
        "one_side_breach_pct": 74.0,
        "no_breach_pct": 17.7,
        "read": "74% chance at least one side is breached. Use ALN bias for direction.",
    },
}


def compute_rth_bias(
    spot: float | None,
    prior_rth_high: float | None,
    prior_rth_low: float | None,
) -> dict:
    """Compute the RTH break scenario bias for the LLM.

    Returns:
        dict with keys:
            scenario: str — "GAP_UP" / "GAP_DOWN" / "INSIDE"
            label: str — human-readable description
            bias: str — "BULLISH" / "BEARISH" / "NEUTRAL"
            hold_pct: float — probability the gap holds (close on same side)
            no_reach_opposite_pct: float — probability price does NOT reach opposite pRTH
            read: str — one-line interpretation for the LLM
            conflict_with_aln: bool — always False; LLM should check against ALN bias externally
    """
    if not spot or not prior_rth_high or not prior_rth_low:
        return {
            "scenario": "INSIDE",
            "label": "Unknown (no pRTH data)",
            "bias": "NEUTRAL",
            "hold_pct": 0.0,
            "no_reach_opposite_pct": 0.0,
            "read": "No prior RTH data available.",
        }

    if spot > prior_rth_high:
        sc = "GAP_UP"
    elif spot < prior_rth_low:
        sc = "GAP_DOWN"
    else:
        sc = "INSIDE"

    meta = RTH_BREAK_META[sc]
    return {
        "scenario": sc,
        "label": meta["label"],
        "bias": meta["bias"],
        "hold_pct": meta["hold_pct"],
        "no_reach_opposite_pct": meta["no_reach_opposite_pct"],
        "read": meta["read"],
    }


# ── Herman Pre-NY Sweep Bias ──────────────────────────────────────────
# Source: Herman study (6,000+ days)
# YAML: narrative_stats.yaml::herman_pre_ny
HERMAN_PRE_NY_META = {
    "BROKE_LONDON_HIGH": {
        "label": "Pre-NY broke London High",
        "bias": "BULLISH",
        "probability": 86.4,
        "dominant": True,
        "read": "DOMINANT bullish signal — overrides ALN. Do not fade.",
    },
    "BROKE_LONDON_LOW": {
        "label": "Pre-NY broke London Low",
        "bias": "BEARISH",
        "probability": 77.9,
        "dominant": True,
        "read": "DOMINANT bearish signal — overrides ALN. Do not fade.",
    },
    "INSIDE": {
        "label": "Pre-NY inside London range",
        "bias": "NEUTRAL",
        "probability": 50.0,
        "dominant": False,
        "read": "50/50 coin flip. Wait for 09:30 open or range break.",
    },
}


def compute_herman_pre_ny_sweep(
    pre_ny: dict | None,
    london_high: float | None,
    london_low: float | None,
) -> dict:
    """Compute the Herman Pre-NY sweep bias for the LLM.

    Args:
        pre_ny: Pre-NY session range dict (must have 'high' and 'low').
        london_high: London session high.
        london_low: London session low.

    Returns:
        dict with keys:
            sweep_result: str — "BROKE_LONDON_HIGH" / "BROKE_LONDON_LOW" / "INSIDE"
            label: str — human-readable description
            bias: str — "BULLISH" / "BEARISH" / "NEUTRAL"
            probability: float — directional probability
            dominant: bool — True if this overrides ALN
            read: str — one-line interpretation for the LLM
    """
    if not pre_ny or not london_high or not london_low:
        return {
            "sweep_result": "INSIDE",
            "label": "No Pre-NY data",
            "bias": "NEUTRAL",
            "probability": 0.0,
            "dominant": False,
            "read": "No Pre-NY sweep data available.",
        }

    pre_ny_high = pre_ny.get("high", 0) if isinstance(pre_ny, dict) else 0
    pre_ny_low = pre_ny.get("low", 0) if isinstance(pre_ny, dict) else 0

    if pre_ny_high > london_high:
        code = "BROKE_LONDON_HIGH"
    elif pre_ny_low < london_low:
        code = "BROKE_LONDON_LOW"
    else:
        code = "INSIDE"

    meta = HERMAN_PRE_NY_META[code]
    return {
        "sweep_result": code,
        "label": meta["label"],
        "bias": meta["bias"],
        "probability": meta["probability"],
        "dominant": meta["dominant"],
        "read": meta["read"],
    }


# ── Herman PL (Pre-London) Continuation Sweep ─────────────────────────
HERMAN_PL_SWEEP_META = {
    "SWEPT_ASIA_HIGH": {
        "label": "Pre-London swept Asia High",
        "bias": "BULLISH",
        "probability": 77.2,
        "read": "77.2% chance London sweeps the high again (continuation).",
    },
    "SWEPT_ASIA_LOW": {
        "label": "Pre-London swept Asia Low",
        "bias": "BEARISH",
        "probability": 69.6,
        "read": "69.6% chance London sweeps the low again (continuation).",
    },
    "INSIDE": {
        "label": "Pre-London inside Asia range",
        "bias": "NEUTRAL",
        "probability": 0.0,
        "read": "No sweep — watch London OR (02:00-03:00) for direction.",
    },
}


def compute_herman_pl_sweep(
    pl: dict | None,
    asia_high: float | None,
    asia_low: float | None,
) -> dict:
    """Compute the Herman Pre-London sweep bias."""
    if not pl or not asia_high or not asia_low:
        return {"sweep_result": "INSIDE", "label": "No PL data", "bias": "NEUTRAL",
                "probability": 0.0, "read": "No Pre-London data available."}
    pl_high = pl.get("high", 0) if isinstance(pl, dict) else 0
    pl_low = pl.get("low", 0) if isinstance(pl, dict) else 0
    if pl_high > asia_high:
        code = "SWEPT_ASIA_HIGH"
    elif pl_low < asia_low:
        code = "SWEPT_ASIA_LOW"
    else:
        code = "INSIDE"
    meta = HERMAN_PL_SWEEP_META[code]
    return {"sweep_result": code, "label": meta["label"], "bias": meta["bias"],
            "probability": meta["probability"], "read": meta["read"]}


# ── Herman London OR Breakout ─────────────────────────────────────────
HERMAN_LONDON_OR_META = {
    "BROKE_HIGH": {"label": "London OR broke HIGH", "bias": "BULLISH",
                   "probability": 76.5, "read": "76.5% bullish continuation from London OR breakout."},
    "BROKE_LOW": {"label": "London OR broke LOW", "bias": "BEARISH",
                  "probability": 73.8, "read": "73.8% bearish continuation from London OR breakout."},
    "INSIDE": {"label": "London OR not yet broken", "bias": "NEUTRAL",
               "probability": 0.0, "read": "London OR (02:00-03:00) not yet broken — waiting for direction."},
}


def compute_herman_london_or(
    spot: float | None,
    or_high: float | None,
    or_low: float | None,
) -> dict:
    """Compute the Herman London OR breakout bias."""
    if not spot or not or_high or not or_low:
        return {"breakout_result": "INSIDE", "label": "No London OR data", "bias": "NEUTRAL",
                "probability": 0.0, "read": "No London OR data available."}
    if spot > or_high:
        code = "BROKE_HIGH"
    elif spot < or_low:
        code = "BROKE_LOW"
    else:
        code = "INSIDE"
    meta = HERMAN_LONDON_OR_META[code]
    return {"breakout_result": code, "label": meta["label"], "bias": meta["bias"],
            "probability": meta["probability"], "read": meta["read"]}


# ── Herman Sweep-Return (mean reversion) ──────────────────────────────
HERMAN_SWEEP_RETURN_META = {
    "LONDON_OPEN": {"label": "02:00-03:00 sweep detected", "return_pct": 72.4,
                    "bias": "REVERSION", "read": "72.4% return to open — fade the sweep of the 02:00 range."},
    "GOLDEN_ZONE": {"label": "08:00-09:00 sweep detected", "return_pct": 79.0,
                    "bias": "REVERSION", "read": "79% return to open — fade the sweep of the 08:00 range (highest reversion)."},
    "NONE": {"label": "No sweep-return setup", "return_pct": 0.0,
             "bias": "NEUTRAL", "read": "No sweep-return setup active."},
}


def compute_herman_sweep_return(
    session_data: dict | None,
    target_high: float | None,
    target_low: float | None,
    window: str = "LONDON_OPEN",
) -> dict:
    """Compute the Herman sweep-return mean reversion bias.

    Args:
        session_data: The sweeping session range dict.
        target_high/target_low: The target range's H/L.
        window: "LONDON_OPEN" (02:00-03:00) or "GOLDEN_ZONE" (08:00-09:00).
    """
    if not session_data or not target_high or not target_low:
        return {"sweep_detected": False, **HERMAN_SWEEP_RETURN_META["NONE"]}
    s_high = session_data.get("high", 0) if isinstance(session_data, dict) else 0
    s_low = session_data.get("low", 0) if isinstance(session_data, dict) else 0
    swept = (s_high > target_high) or (s_low < target_low)
    if swept:
        meta = HERMAN_SWEEP_RETURN_META.get(window, HERMAN_SWEEP_RETURN_META["LONDON_OPEN"])
        return {"sweep_detected": True, **meta}
    return {"sweep_detected": False, **HERMAN_SWEEP_RETURN_META["NONE"]}


# ── Herman Lunch Range ────────────────────────────────────────────────
HERMAN_LUNCH_META = {
    "BROKE_HIGH": {"label": "Lunch range broke HIGH", "bias": "BULLISH",
                   "probability": 53.5, "read": "53.5% high-first break — PM direction bullish. Median 12-14 pts penetration."},
    "BROKE_LOW": {"label": "Lunch range broke LOW", "bias": "BEARISH",
                  "probability": 46.5, "read": "Lunch range broke LOW — PM direction bearish."},
    "INSIDE": {"label": "Lunch range not yet broken", "bias": "NEUTRAL",
               "probability": 0.0, "read": "Lunch range (12:00-13:00) not yet broken — PM expansion pending. Lunch fade reversals ~40% (low probability — don't fade)."},
}


def compute_herman_lunch(
    spot: float | None,
    lunch_high: float | None,
    lunch_low: float | None,
) -> dict:
    """Compute the Herman lunch range breakout bias."""
    if not spot or not lunch_high or not lunch_low:
        return {"breakout_result": "INSIDE", **HERMAN_LUNCH_META["INSIDE"]}
    if spot > lunch_high:
        code = "BROKE_HIGH"
    elif spot < lunch_low:
        code = "BROKE_LOW"
    else:
        code = "INSIDE"
    meta = HERMAN_LUNCH_META[code]
    return {"breakout_result": code, **meta}


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

    ADR-026: a NaN input is NOT a verdict. With the range stamper fixed, the
    London range is NaN until the London window closes, so "Held" on those
    bars asserted a comparison that had not happened. NaN inputs now yield
    "Unknown" rather than a concrete label.
    """
    ah = sessions_df['asia_high'].values
    al = sessions_df['asia_low'].values
    lh = sessions_df['london_high'].values
    ll = sessions_df['london_low'].values

    inputs_known = ~(np.isnan(ah) | np.isnan(al) | np.isnan(lh) | np.isnan(ll))
    london_broke_asia = np.where(inputs_known, (lh > ah) | (ll < al), np.nan)

    # 2. Pre-NY vs London
    ph = sessions_df['pre-ny_high'].values
    pl = sessions_df['pre-ny_low'].values

    inputs_known_p = ~(np.isnan(ph) | np.isnan(pl) | np.isnan(lh) | np.isnan(ll))
    preny_broke_london = np.where(inputs_known_p, (ph > lh) | (pl < ll), np.nan)

    # Output labels: "Unknown" where the inputs are not yet knowable.
    l_vs_a = np.where(np.isnan(london_broke_asia), "Unknown",
                      np.where(london_broke_asia == 1, "Broken", "Held"))
    p_vs_l = np.where(np.isnan(preny_broke_london), "Unknown",
                      np.where(preny_broke_london == 1, "Broken", "Held"))

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
