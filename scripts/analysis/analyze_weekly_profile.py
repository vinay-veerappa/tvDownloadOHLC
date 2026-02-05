import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta

# Configuration
DATA_DIR = r"c:\Users\vinay\tvDownloadOHLC\data"
OUTPUT_DIR = r"c:\Users\vinay\tvDownloadOHLC\data\derived"
TICKER_FILE_1D = "NQ1_1d.parquet"
TICKER_FILE_1H = "NQ1_1h.parquet"
LIVE_FILE = "live_storage_-NQ.parquet" 
LIVE_DIR = r"c:\Users\vinay\tvDownloadOHLC\data\live"
TICKER = "NQ1"

def get_nfp_fridays(start_year, end_year):
    nfp_dates = set()
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            for day in range(1, 8):
                try:
                    d = datetime(year, month, day)
                    if d.weekday() == 4:
                        nfp_dates.add(pd.Timestamp(d).date())
                        break
                except ValueError:
                    continue
    return nfp_dates

def analyze_weekly_profile():
    print(f"--- Analyzing Weekly Profile for {TICKER} ---")
    
    path_1d = os.path.join(DATA_DIR, TICKER_FILE_1D)
    path_1h = os.path.join(DATA_DIR, TICKER_FILE_1H)
    path_live = os.path.join(LIVE_DIR, LIVE_FILE)
    
    if not os.path.exists(path_1d) or not os.path.exists(path_1h):
        print("Error: Missing data files.")
        return

    df_1d = pd.read_parquet(path_1d)
    df_1h = pd.read_parquet(path_1h)
    
    df_live_1h = pd.DataFrame()
    if os.path.exists(path_live):
        try:
            df_live = pd.read_parquet(path_live)
            if not isinstance(df_live.index, pd.DatetimeIndex):
                if 'time' in df_live.columns:
                     df_live['datetime'] = pd.to_datetime(df_live['time'], unit='ms', utc=True)
                     df_live.set_index('datetime', inplace=True)
            
            if df_live.index.tz is None:
                df_live.index = df_live.index.tz_localize('UTC')
            df_live.index = df_live.index.tz_convert('US/Eastern')
            
            df_live_1h = df_live.resample('1h').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            print(f"DEBUG: Loaded {len(df_live_1h)} hours from Live Storage Parquet.")
        except Exception as e:
            print(f"Warning: Failed to load live data: {e}")

    for i, df in enumerate([df_1d, df_1h]):
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'time' in df.columns:
                 df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
                 df = df.set_index('datetime')
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        df.index = df.index.tz_convert('US/Eastern')
        df.sort_index(inplace=True)
        if i == 0: df_1d = df
        else: df_1h = df
        
    if not df_live_1h.empty:
        df_1h = pd.concat([df_1h, df_live_1h])
        df_1h = df_1h[~df_1h.index.duplicated(keep='last')]
        df_1h.sort_index(inplace=True)

    last_date = df_1d.index[-1]
    current_year, current_week, _ = last_date.isocalendar()
    df_1d['year'] = df_1d.index.year
    df_1d['week'] = df_1d.index.isocalendar().week

    today_date = last_date.date()
    nfp_set = get_nfp_fridays(today_date.year, today_date.year)
    days_to_fri = (4 - last_date.weekday()) % 7 
    this_friday = today_date + timedelta(days=days_to_fri)
    is_nfp_week = this_friday in nfp_set
    nfp_date = this_friday.isoformat() if is_nfp_week else None
    
    df_1h['year'] = df_1h.index.year
    df_1h['week'] = df_1h.index.isocalendar().week
    curr_week_1h = df_1h[(df_1h['year'] == current_year) & (df_1h['week'] == current_week)]
    
    anchors = {"sunday": None, "tuesday": None}
    
    if not curr_week_1h.empty:
        sunday_data = curr_week_1h[curr_week_1h.index.dayofweek == 6]
        if not sunday_data.empty:
            anchors["sunday"] = {
                "high": float(sunday_data['high'].max()),
                "low": float(sunday_data['low'].min()),
                "open": float(sunday_data['open'].iloc[0]),
                "close": float(sunday_data['close'].iloc[-1])
            }
        tues_data = curr_week_1h[curr_week_1h.index.dayofweek == 1]
        if not tues_data.empty:
            anchors["tuesday"] = {
                "high": float(tues_data['high'].max()),
                "low": float(tues_data['low'].min()),
                "close": float(tues_data['close'].iloc[-1])
            }
    
    # 4. Profile Logic & Narrative
    curr_price = float(df_1d['close'].iloc[-1])
    open_of_week = anchors["sunday"]["open"] if (anchors["sunday"] and "open" in anchors["sunday"]) else df_1d['open'].iloc[0]
    
    # HTF Context (EMA & Prev Week)
    prev_week_mask = (df_1d.index.isocalendar().week == current_week - 1) & (df_1d.index.year == current_year)
    prev_week_data = df_1d[prev_week_mask]
    pwh = float(prev_week_data['high'].max()) if not prev_week_data.empty else 0.0
    pwl = float(prev_week_data['low'].min()) if not prev_week_data.empty else 0.0
        
    df_weekly = df_1d.resample('W-FRI').agg({'close':'last'})
    df_weekly['ema5'] = df_weekly['close'].ewm(span=5, adjust=False).mean()
    prev_weekly_ema = float(df_weekly['ema5'].iloc[-2]) if len(df_weekly) >= 2 else 0.0
    ema_dist_pct = ((curr_price - prev_weekly_ema) / prev_weekly_ema) * 100 if prev_weekly_ema > 0 else 0.0
    
    df_monthly = df_1d.resample('ME').agg({'high':'max', 'low':'min'})
    pm_mid = 0.0
    if len(df_monthly) >= 2:
        prev_month = df_monthly.iloc[-2]
        pm_mid = (prev_month['high'] + prev_month['low']) / 2

    narrative_parts = []
    if is_nfp_week:
        narrative_parts.append(f"It is NFP Week ({nfp_date}). Historical data suggests heavy consolidation and order flow manipulation until the Friday news release.")

    if pm_mid > 0:
        rel = "above" if curr_price > pm_mid else "below"
        prox = "close to" if abs(curr_price - pm_mid) < (pm_mid * 0.002) else ""
        narrative_parts.append(f"Price is currently trading {prox} {rel} the Previous Month Mid-point ({pm_mid:.0f}).")

    if prev_weekly_ema > 0:
        ema_rel = "above" if curr_price > prev_weekly_ema else "below"
        ema_state = "overextended" if abs(ema_dist_pct) > 2.2 else "respecting"
        narrative_parts.append(f"We are {ema_state} {ema_rel} the Weekly EMA(5) ({prev_weekly_ema:.0f}).")

    profile_type = "Developing"
    if anchors["tuesday"]:
        tue_h = anchors["tuesday"]["high"]
        tue_l = anchors["tuesday"]["low"]
        if curr_price > tue_h:
            profile_type = "Expansion (Bullish)"
            narrative_parts.append("Breach of Tuesday High suggests a Classic Buy Week expansion is underway.")
        elif curr_price < tue_l:
            profile_type = "Expansion (Bearish)"
            narrative_parts.append("Breach of Tuesday Low suggests a Classic Sell Week expansion is underway.")
        else:
            profile_type = "Consolidation (Inside Tuesday)"
            narrative_parts.append("Price remains inside the Tuesday range, suggesting a mid-week sweep or NFP consolidation period.")

    open_rel = "above" if curr_price > open_of_week else "below"
    narrative_parts.append(f"Trading {open_rel} the Weekly Open ({open_of_week:.0f}).")

    narrative = " ".join(narrative_parts) if narrative_parts else "Monitoring weekly development."
    bias = "BULLISH" if curr_price > open_of_week else "BEARISH"

    output = {
        "timestamp": datetime.now().isoformat(),
        "ticker": TICKER,
        "profile": {
            "status": profile_type,
            "narrative": narrative,
            "bias_direction_est": bias,
            "current_price": curr_price,
            "open_of_week": float(open_of_week),
            "in_nfp_week": is_nfp_week,
            "nfp_friday_date": nfp_date
        },
        "anchors": anchors,
        "htf_context": {
            "pwh": pwh,
            "pwl": pwl,
            "prev_month_mid": float(pm_mid),
            "weekly_ema5": prev_weekly_ema,
            "dist_from_ema_pct": round(ema_dist_pct, 2)
        }
    }
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"weekly_profile_{TICKER}.json")
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"Saved Weekly Profile analysis to {out_path}")
    print(f"Profile: {profile_type}")
    print(f"Narrative: {narrative}")

if __name__ == "__main__":
    analyze_weekly_profile()
