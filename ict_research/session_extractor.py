from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
import pandas as pd
import numpy as np
from config import SESSION_TIMES

@dataclass
class TradingDay:
    # ═══ EXISTING FIELDS (keep all as-is) ═══
    date: date
    
    # Asia (19:30 - 02:30)
    asia_high: float = np.nan
    asia_low: float = np.nan
    asia_open: float = np.nan
    asia_close: float = np.nan
    asia_mid: float = np.nan
    asia_range: float = np.nan
    
    # London (02:30 - 08:00)
    london_high: float = np.nan
    london_low: float = np.nan
    london_open: float = np.nan
    london_close: float = np.nan
    london_mid: float = np.nan
    london_range: float = np.nan
    london_high_time: datetime = None
    london_low_time: datetime = None
    london_high_first: bool = None
    
    # NY (09:30 - 16:00)
    ny_open: float = np.nan
    ny_high: float = np.nan
    ny_low: float = np.nan
    ny_close: float = np.nan
    ny_high_time: datetime = None
    ny_low_time: datetime = None
    ny_hit_high_first: bool = None
    
    # RTH Gap
    prev_settle: float = np.nan
    rth_gap: float = np.nan
    rth_gap_pct: float = np.nan
    
    # Key Levels
    prev_day_high: float = np.nan
    prev_day_low: float = np.nan
    prev_day_mid: float = np.nan
    prev_week_high: float = np.nan
    prev_week_low: float = np.nan
    
    # Overnight range (18:00 - 09:30)
    overnight_high: float = np.nan
    overnight_low: float = np.nan
    overnight_mid: float = np.nan
    
    # Midnight reference (00:00 ET)
    midnight_open: float = np.nan
    
    # Hourly references
    hour_7_8_mid: float = np.nan
    hour_2_3_mid: float = np.nan
    
    # 08:00 open (pre-market)
    eight_am_open: float = np.nan

    # ═══ NEW: Additional Session Ranges ═══
    
    # NY AM (09:30-12:00) — already have ny_* but those are full RTH
    ny_am_high: float = np.nan
    ny_am_low: float = np.nan
    ny_am_open: float = np.nan
    ny_am_close: float = np.nan
    ny_am_mid: float = np.nan
    ny_am_range: float = np.nan
    
    # Lunch (12:00-13:30)
    lunch_high: float = np.nan
    lunch_low: float = np.nan
    lunch_open: float = np.nan
    lunch_close: float = np.nan
    lunch_mid: float = np.nan
    lunch_range: float = np.nan
    
    # NY PM ICT (13:30-16:00)
    ny_pm_high: float = np.nan
    ny_pm_low: float = np.nan
    ny_pm_open: float = np.nan
    ny_pm_close: float = np.nan
    ny_pm_mid: float = np.nan
    ny_pm_range: float = np.nan
    ny_pm_high_time: datetime = None
    ny_pm_low_time: datetime = None
    ny_pm_high_first: bool = None
    pm_close_location: float = np.nan  # 0=closed at PM low, 100=closed at PM high
    
    # P12 (18:00-06:00)
    p12_high: float = np.nan
    p12_low: float = np.nan
    p12_mid: float = np.nan
    p12_range: float = np.nan
    
    # ═══ NEW: CBDR ═══
    
    # Classic CBDR (14:00-20:00 — previous day PM into current globex)
    cbdr_classic_high: float = np.nan
    cbdr_classic_low: float = np.nan
    cbdr_classic_mid: float = np.nan
    cbdr_classic_range: float = np.nan
    
    # Asia CBDR (19:30-00:00)
    cbdr_asia_high: float = np.nan
    cbdr_asia_low: float = np.nan
    cbdr_asia_mid: float = np.nan
    cbdr_asia_range: float = np.nan
    
    # CBDR sigma levels (computed from cbdr_asia by default)
    # Store as dict or individual fields — individual is easier for CSV
    cbdr_sigma_up_0_5: float = np.nan
    cbdr_sigma_up_1: float = np.nan
    cbdr_sigma_up_1_5: float = np.nan
    cbdr_sigma_up_2: float = np.nan
    cbdr_sigma_up_2_5: float = np.nan
    cbdr_sigma_up_3: float = np.nan
    cbdr_sigma_up_4: float = np.nan
    cbdr_sigma_dn_0_5: float = np.nan
    cbdr_sigma_dn_1: float = np.nan
    cbdr_sigma_dn_1_5: float = np.nan
    cbdr_sigma_dn_2: float = np.nan
    cbdr_sigma_dn_2_5: float = np.nan
    cbdr_sigma_dn_3: float = np.nan
    cbdr_sigma_dn_3: float = np.nan
    cbdr_sigma_dn_4: float = np.nan

    # ═══ NEW: FLOUT (Asian Range starting at 20:00) ═══
    flout_high: float = np.nan
    flout_low: float = np.nan
    flout_mid: float = np.nan
    flout_range: float = np.nan
    
    # ═══ NEW: Time-Based Opens ═══
    globex_open: float = np.nan
    london_open_price: float = np.nan   # Price at 02:30
    open_0730: float = np.nan           # Price at 07:30
    rth_open_price: float = np.nan      # Price at 09:30 (same as ny_open but explicit)
    pm_open_price: float = np.nan       # Price at 13:30
    
    # ═══ NEW: OTE Zones ═══
    ote_bull_62: float = np.nan         # ON_L + ON_range * 0.62
    ote_bear_62: float = np.nan         # ON_H - ON_range * 0.62
    ote_bull_79: float = np.nan
    ote_bear_79: float = np.nan
    
    # ═══ NEW: Extended Previous Periods ═══
    prev_week_close: float = np.nan
    prev_week_mid: float = np.nan
    weekly_open: float = np.nan
    prev_month_high: float = np.nan
    prev_month_low: float = np.nan
    prev_month_close: float = np.nan
    monthly_open: float = np.nan
    
    # ═══ NEW: NY PM Manipulation (Asia Prediction Model) ═══
    manip_pm: str = None                # BULLISH/BEARISH/BOTH/NONE
    pattern_pm: str = None              # PM_PARTIAL_UP/DOWN/ENGULFS/INSIDE
    is_judas_pm: bool = None
    globex_pos_vs_pm_mid: str = None    # ABOVE/BELOW
    globex_gap: float = np.nan          # 18:00 open - 16:00 close
    globex_gap_pct: float = np.nan
    
    # ═══ NEW: Additional Position Classifications ═══
    london_open_vs_asia_mid: str = None    # ABOVE_ASIA_MID / BELOW_ASIA_MID
    asia_open_vs_prev_close: str = None    # Did Asia gap up or down
    london_open_vs_midnight: str = None
    ny_open_vs_overnight_mid: str = None
    ny_open_vs_midnight: str = None
    pm_open_vs_am_mid: str = None
    pm_open_vs_lunch_mid: str = None

    # ═══ NEW: Percentage Ranges (Normalized) ═══
    asia_range_pct: float = np.nan       # asia_range / globex_open * 100
    london_range_pct: float = np.nan
    ny_am_range_pct: float = np.nan
    ny_pm_range_pct: float = np.nan
    lunch_range_pct: float = np.nan
    overnight_range_pct: float = np.nan
    cbdr_asia_range_pct: float = np.nan
    p12_range_pct: float = np.nan
    cbdr_range_pct_of_price: float = np.nan

    # ═══ NEW: Percent Distances & Sweeps ═══
    london_sweep_up_pct: float = np.nan   # (london_high - asia_high) / asia_mid * 100
    london_sweep_dn_pct: float = np.nan
    london_high_from_ny_open_pct: float = np.nan
    london_low_from_ny_open_pct: float = np.nan
    asia_high_from_ny_open_pct: float = np.nan
    asia_low_from_ny_open_pct: float = np.nan
    pdh_from_ny_open_pct: float = np.nan
    pdl_from_ny_open_pct: float = np.nan
    
    # ═══ NEW: CBDR Sigma Reach (how far did price actually go?) ═══
    cbdr_upside_sigmas: float = np.nan  # Max sigmas reached above CBDR high
    cbdr_downside_sigmas: float = np.nan
    cbdr_hit_up_0_5: bool = None
    cbdr_hit_up_1: bool = None
    cbdr_hit_up_1_5: bool = None
    cbdr_hit_up_2: bool = None
    cbdr_hit_up_2_5: bool = None
    cbdr_hit_up_3: bool = None
    cbdr_hit_up_4: bool = None
    cbdr_hit_dn_0_5: bool = None
    cbdr_hit_dn_1: bool = None
    cbdr_hit_dn_1_5: bool = None
    cbdr_hit_dn_2: bool = None
    cbdr_hit_dn_2_5: bool = None
    cbdr_hit_dn_3: bool = None
    cbdr_hit_dn_4: bool = None

def get_ohlc_in_range(df: pd.DataFrame, start_time: time, end_time: time) -> pd.DataFrame:
    """Helper to slice df by time range for the trading day"""
    # Note: df is already cut to trading day [18:00 prev -> 17:00 curr]
    # We can filter by time.
    # Logic:
    # If start < end (e.g. 09:30 to 16:00): simple filter
    # If start > end (e.g. 19:30 to 02:30): 
    #   Take 19:30-23:59 AND 00:00-02:30
    
    if df.empty:
        return df
        
    times = df.index.time
    
    if start_time < end_time:
        mask = (times >= start_time) & (times < end_time)
        return df[mask]
    else:
        # Crosses midnight
        # For a trading day defined as 18:00 D-1 to 17:00 D:
        # 19:30 is on D-1 (hours >= 18)
        # 02:30 is on D (hours < 18)
        # So we want parts of the DF where time >= 19:30 OR time < 02:30
        mask = (times >= start_time) | (times < end_time)
        return df[mask]

def extract_session_stats(df_day: pd.DataFrame, prev_day_stats: dict = None, prev_week_stats: dict = None, prev_month_stats: dict = None) -> TradingDay:
    """
    Extract stats for a single trading day dataframe.
    df_day index must be DatetimeIndex in NY time.
    prev_day_stats: dict with keys 'high', 'low', 'close'
    """
    if df_day.empty:
        return None
        
    t_date = df_day['trading_date'].iloc[0]
    stats = TradingDay(date=t_date)
    
    # --- 1. Asia (19:30 - 02:30) ---
    asia_df = get_ohlc_in_range(df_day, SESSION_TIMES['ASIA'][0], SESSION_TIMES['ASIA'][1])
    if not asia_df.empty:
        stats.asia_high = asia_df['high'].max()
        stats.asia_low = asia_df['low'].min()
        stats.asia_open = asia_df['open'].iloc[0]
        stats.asia_close = asia_df['close'].iloc[-1]
        stats.asia_mid = (stats.asia_high + stats.asia_low) / 2
        stats.asia_range = stats.asia_high - stats.asia_low
        
    # --- 2. London (02:30 - 08:00) ---
    london_df = get_ohlc_in_range(df_day, SESSION_TIMES['LONDON'][0], SESSION_TIMES['LONDON'][1])
    if not london_df.empty:
        stats.london_high = london_df['high'].max()
        stats.london_low = london_df['low'].min()
        stats.london_open = london_df['open'].iloc[0]
        stats.london_close = london_df['close'].iloc[-1]
        stats.london_mid = (stats.london_high + stats.london_low) / 2
        stats.london_range = stats.london_high - stats.london_low
        
        idx_max = london_df['high'].idxmax()
        idx_min = london_df['low'].idxmin()
        stats.london_high_time = idx_max
        stats.london_low_time = idx_min
        stats.london_high_first = idx_max < idx_min

    # --- 3. NY (09:30 - 16:00) ---
    ny_df = get_ohlc_in_range(df_day, SESSION_TIMES['NY_AM'][0], SESSION_TIMES['NY_PM'][1])
    if not ny_df.empty:
        stats.ny_open = ny_df['open'].iloc[0]
        stats.ny_high = ny_df['high'].max()
        stats.ny_low = ny_df['low'].min()
        
        # Settle
        settle_bar = df_day.at_time(SESSION_TIMES['NY_CLOSE'])
        stats.ny_close = settle_bar['close'].iloc[0] if not settle_bar.empty else ny_df['close'].iloc[-1]
        
        idx_max = ny_df['high'].idxmax()
        idx_min = ny_df['low'].idxmin()
        stats.ny_high_time = idx_max
        stats.ny_low_time = idx_min
        
        if stats.london_high is not None and stats.london_low is not None:
             cross_high = ny_df[ny_df['high'] >= stats.london_high].index.min()
             cross_low = ny_df[ny_df['low'] <= stats.london_low].index.min()
             if pd.notna(cross_high) and pd.notna(cross_low):
                 stats.ny_hit_high_first = cross_high < cross_low
             elif pd.notna(cross_high):
                 stats.ny_hit_high_first = True
             elif pd.notna(cross_low):
                 stats.ny_hit_high_first = False
    
    # --- 4. Overnight ---
    on_df = get_ohlc_in_range(df_day, SESSION_TIMES['GLOBEX_OPEN'], SESSION_TIMES['PRE_MARKET'][1])
    if not on_df.empty:
        stats.overnight_high = on_df['high'].max()
        stats.overnight_low = on_df['low'].min()
        stats.overnight_mid = (stats.overnight_high + stats.overnight_low) / 2
        
    # --- 5. RTH Gap & Prev Day Context ---
    if prev_day_stats:
        stats.prev_settle = prev_day_stats.get('close', np.nan)
        if pd.notna(stats.prev_settle) and pd.notna(stats.ny_open):
            stats.rth_gap = stats.ny_open - stats.prev_settle
            stats.rth_gap_pct = (stats.rth_gap / stats.prev_settle) * 100
        
        stats.prev_day_high = prev_day_stats.get('high', np.nan)
        stats.prev_day_low = prev_day_stats.get('low', np.nan)
        if pd.notna(stats.prev_day_high) and pd.notna(stats.prev_day_low):
             stats.prev_day_mid = (stats.prev_day_high + stats.prev_day_low) / 2

    # --- 6. References ---
    mid_bar = df_day.at_time(SESSION_TIMES['MIDNIGHT_OPEN'])
    if not mid_bar.empty: stats.midnight_open = mid_bar['open'].iloc[0]
        
    h78_df = get_ohlc_in_range(df_day, SESSION_TIMES['HOUR_7_8'][0], SESSION_TIMES['HOUR_7_8'][1])
    if not h78_df.empty: stats.hour_7_8_mid = (h78_df['high'].max() + h78_df['low'].min()) / 2
        
    h23_df = get_ohlc_in_range(df_day, SESSION_TIMES['HOUR_2_3'][0], SESSION_TIMES['HOUR_2_3'][1])
    if not h23_df.empty: stats.hour_2_3_mid = (h23_df['high'].max() + h23_df['low'].min()) / 2

    eight_bar = df_day.at_time(SESSION_TIMES['PRE_MARKET'][0])
    if not eight_bar.empty: stats.eight_am_open = eight_bar['open'].iloc[0]

    # ═══ NEW: Additional Measurements ═══

    # NEW: NY AM specifically (09:30-12:00)
    ny_am_df = get_ohlc_in_range(df_day, SESSION_TIMES['NY_AM'][0], SESSION_TIMES['NY_AM'][1])
    if not ny_am_df.empty:
        stats.ny_am_high = ny_am_df['high'].max()
        stats.ny_am_low = ny_am_df['low'].min()
        stats.ny_am_open = ny_am_df['open'].iloc[0]
        stats.ny_am_close = ny_am_df['close'].iloc[-1]
        stats.ny_am_mid = (stats.ny_am_high + stats.ny_am_low) / 2
        stats.ny_am_range = stats.ny_am_high - stats.ny_am_low
    
    # NEW: Lunch (12:00-13:30)
    lunch_df = get_ohlc_in_range(df_day, SESSION_TIMES['LUNCH'][0], SESSION_TIMES['LUNCH'][1])
    if not lunch_df.empty:
        stats.lunch_high = lunch_df['high'].max()
        stats.lunch_low = lunch_df['low'].min()
        stats.lunch_open = lunch_df['open'].iloc[0]
        stats.lunch_close = lunch_df['close'].iloc[-1]
        stats.lunch_mid = (stats.lunch_high + stats.lunch_low) / 2
        stats.lunch_range = stats.lunch_high - stats.lunch_low
    
    # NEW: NY PM ICT (13:30-16:00)
    ny_pm_df = get_ohlc_in_range(df_day, SESSION_TIMES['NY_PM_ICT'][0], SESSION_TIMES['NY_PM_ICT'][1])
    if not ny_pm_df.empty:
        stats.ny_pm_high = ny_pm_df['high'].max()
        stats.ny_pm_low = ny_pm_df['low'].min()
        stats.ny_pm_open = ny_pm_df['open'].iloc[0]
        stats.ny_pm_close = ny_pm_df['close'].iloc[-1]
        stats.ny_pm_mid = (stats.ny_pm_high + stats.ny_pm_low) / 2
        stats.ny_pm_range = stats.ny_pm_high - stats.ny_pm_low
        stats.ny_pm_high_time = ny_pm_df['high'].idxmax()
        stats.ny_pm_low_time = ny_pm_df['low'].idxmin()
        stats.ny_pm_high_first = stats.ny_pm_high_time < stats.ny_pm_low_time
        if stats.ny_pm_range > 0:
            stats.pm_close_location = (stats.ny_pm_close - stats.ny_pm_low) / stats.ny_pm_range * 100
    
    # NEW: P12 (18:00-06:00)
    p12_df = get_ohlc_in_range(df_day, SESSION_TIMES['P12'][0], SESSION_TIMES['P12'][1])
    if not p12_df.empty:
        stats.p12_high = p12_df['high'].max()
        stats.p12_low = p12_df['low'].min()
        stats.p12_mid = (stats.p12_high + stats.p12_low) / 2
        stats.p12_range = stats.p12_high - stats.p12_low
    
    # NEW: CBDR Asia (19:30-00:00)
    cbdr_asia_df = get_ohlc_in_range(df_day, SESSION_TIMES['CBDR_ASIA'][0], SESSION_TIMES['CBDR_ASIA'][1])
    if not cbdr_asia_df.empty:
        stats.cbdr_asia_high = cbdr_asia_df['high'].max()
        stats.cbdr_asia_low = cbdr_asia_df['low'].min()
        stats.cbdr_asia_mid = (stats.cbdr_asia_high + stats.cbdr_asia_low) / 2
        stats.cbdr_asia_range = stats.cbdr_asia_high - stats.cbdr_asia_low
        
        # Compute sigma levels
        r = stats.cbdr_asia_range
        if r > 0:
            for sigma in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]:
                s_name = str(sigma).replace('.', '_')
                setattr(stats, f'cbdr_sigma_up_{s_name}', stats.cbdr_asia_high + sigma * r)
                setattr(stats, f'cbdr_sigma_dn_{s_name}', stats.cbdr_asia_low - sigma * r)

    # NEW: FLOUT (20:00 - 00:00)
    flout_df = get_ohlc_in_range(df_day, SESSION_TIMES['FLOUT'][0], SESSION_TIMES['FLOUT'][1])
    if not flout_df.empty:
        stats.flout_high = flout_df['high'].max()
        stats.flout_low = flout_df['low'].min()
        stats.flout_mid = (stats.flout_high + stats.flout_low) / 2
        stats.flout_range = stats.flout_high - stats.flout_low
    
    # NEW: Time-based opens
    globex_bar = df_day.at_time(SESSION_TIMES['GLOBEX_OPEN'])
    if not globex_bar.empty:
        stats.globex_open = globex_bar['open'].iloc[0]
    
    london_open_bar = df_day.at_time(SESSION_TIMES['LONDON_OPEN'])
    if not london_open_bar.empty:
        stats.london_open_price = london_open_bar['open'].iloc[0]
    
    bar_0730 = df_day.at_time(SESSION_TIMES['OPEN_0730'])
    if not bar_0730.empty:
        stats.open_0730 = bar_0730['open'].iloc[0]
    
    rth_bar = df_day.at_time(SESSION_TIMES['RTH_OPEN'])
    if not rth_bar.empty:
        stats.rth_open_price = rth_bar['open'].iloc[0]
    
    pm_bar = df_day.at_time(SESSION_TIMES['PM_OPEN'])
    if not pm_bar.empty:
        stats.pm_open_price = pm_bar['open'].iloc[0]
    
    # NEW: OTE zones
    if pd.notna(stats.overnight_high) and pd.notna(stats.overnight_low):
        on_range = stats.overnight_high - stats.overnight_low
        stats.ote_bull_62 = stats.overnight_low + on_range * 0.62
        stats.ote_bear_62 = stats.overnight_high - on_range * 0.62
        stats.ote_bull_79 = stats.overnight_low + on_range * 0.79
        stats.ote_bear_79 = stats.overnight_high - on_range * 0.79
    
    # NEW: Globex gap
    if pd.notna(stats.globex_open) and pd.notna(stats.ny_close):
        # Note: ny_close is from CURRENT day. We need PREV day close.
        # This should use prev_day_stats['close'] (same as prev_settle)
        if prev_day_stats and pd.notna(prev_day_stats.get('close')):
            stats.globex_gap = stats.globex_open - prev_day_stats['close']
            stats.globex_gap_pct = stats.globex_gap / prev_day_stats['close'] * 100
    
    # NEW: Extended prev period levels
    if prev_week_stats:
        stats.prev_week_close = prev_week_stats.get('close', np.nan)
        stats.prev_week_mid = prev_week_stats.get('mid', np.nan)
        stats.weekly_open = prev_week_stats.get('weekly_open', np.nan)
        # Note: prev_week_high/low already exist in TradingDay
    
    if prev_month_stats:
        stats.prev_month_high = prev_month_stats.get('high', np.nan)
        stats.prev_month_low = prev_month_stats.get('low', np.nan)
        stats.prev_month_close = prev_month_stats.get('close', np.nan)
        stats.monthly_open = prev_month_stats.get('monthly_open', np.nan)
    
    # ═══ NEW: Calculations for Additional Items ═══
    # 1. London Open Position vs Asia Mid
    if pd.notna(stats.london_open) and pd.notna(stats.asia_mid):
        stats.london_open_vs_asia_mid = "ABOVE_ASIA_MID" if stats.london_open > stats.asia_mid else "BELOW_ASIA_MID"
        
    # 2. Percentage Normalization (using Globex Open or Asia Open as ref)
    ref_price = stats.globex_open if pd.notna(stats.globex_open) else stats.asia_open
    
    if pd.notna(ref_price) and ref_price > 0:
        # Range Percentages
        if pd.notna(stats.asia_range): stats.asia_range_pct = stats.asia_range / ref_price * 100
        if pd.notna(stats.london_range): stats.london_range_pct = stats.london_range / ref_price * 100
        if pd.notna(stats.ny_am_range): stats.ny_am_range_pct = stats.ny_am_range / ref_price * 100
        if pd.notna(stats.ny_pm_range): stats.ny_pm_range_pct = stats.ny_pm_range / ref_price * 100
        if pd.notna(stats.lunch_range): stats.lunch_range_pct = stats.lunch_range / ref_price * 100
        if pd.notna(stats.overnight_high) and pd.notna(stats.overnight_low):
            stats.overnight_range_pct = (stats.overnight_high - stats.overnight_low) / ref_price * 100
        if pd.notna(stats.cbdr_asia_range): stats.cbdr_asia_range_pct = stats.cbdr_asia_range / ref_price * 100
        if pd.notna(stats.p12_range): stats.p12_range_pct = stats.p12_range / ref_price * 100
        if pd.notna(stats.cbdr_asia_range) and pd.notna(stats.cbdr_asia_mid) and stats.cbdr_asia_mid > 0:
            stats.cbdr_range_pct_of_price = stats.cbdr_asia_range / stats.cbdr_asia_mid * 100 # Specific request

        # Sweep Percentages (relative to Asia Mid usually, or ref_price)
        # Request: (london_high - asia_high) / asia_mid * 100
        asia_mid_ref = stats.asia_mid if pd.notna(stats.asia_mid) and stats.asia_mid > 0 else ref_price
        
        if pd.notna(stats.london_high) and pd.notna(stats.asia_high):
            sweep = stats.london_high - stats.asia_high
            if sweep > 0: stats.london_sweep_up_pct = sweep / asia_mid_ref * 100
            
        if pd.notna(stats.london_low) and pd.notna(stats.asia_low):
            sweep = stats.asia_low - stats.london_low
            if sweep > 0: stats.london_sweep_dn_pct = sweep / asia_mid_ref * 100

        # Level Distances from NY Open
        if pd.notna(stats.ny_open) and stats.ny_open > 0:
            if pd.notna(stats.london_high): stats.london_high_from_ny_open_pct = (stats.london_high - stats.ny_open) / stats.ny_open * 100
            if pd.notna(stats.london_low): stats.london_low_from_ny_open_pct = (stats.london_low - stats.ny_open) / stats.ny_open * 100
            if pd.notna(stats.asia_high): stats.asia_high_from_ny_open_pct = (stats.asia_high - stats.ny_open) / stats.ny_open * 100
            if pd.notna(stats.asia_low): stats.asia_low_from_ny_open_pct = (stats.asia_low - stats.ny_open) / stats.ny_open * 100
            if pd.notna(stats.prev_day_high): stats.pdh_from_ny_open_pct = (stats.prev_day_high - stats.ny_open) / stats.ny_open * 100
            if pd.notna(stats.prev_day_low): stats.pdl_from_ny_open_pct = (stats.prev_day_low - stats.ny_open) / stats.ny_open * 100

    # 3. Additional Position Classifications
    if pd.notna(stats.asia_open) and pd.notna(stats.prev_settle):
        stats.asia_open_vs_prev_close = "ABOVE" if stats.asia_open > stats.prev_settle else "BELOW"
        
    if pd.notna(stats.london_open) and pd.notna(stats.midnight_open):
        stats.london_open_vs_midnight = "ABOVE" if stats.london_open > stats.midnight_open else "BELOW"

    if pd.notna(stats.ny_open) and pd.notna(stats.overnight_mid):
        stats.ny_open_vs_overnight_mid = "ABOVE" if stats.ny_open > stats.overnight_mid else "BELOW"
        
    if pd.notna(stats.ny_open) and pd.notna(stats.midnight_open):
        stats.ny_open_vs_midnight = "ABOVE" if stats.ny_open > stats.midnight_open else "BELOW"
        
    if pd.notna(stats.ny_pm_open):
        if pd.notna(stats.ny_am_mid):
            stats.pm_open_vs_am_mid = "ABOVE" if stats.ny_pm_open > stats.ny_am_mid else "BELOW"
        if pd.notna(stats.lunch_mid):
            stats.pm_open_vs_lunch_mid = "ABOVE" if stats.ny_pm_open > stats.lunch_mid else "BELOW"

    return stats
