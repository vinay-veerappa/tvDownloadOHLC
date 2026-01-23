import pandas as pd
import numpy as np
import argparse
import sys
from datetime import datetime, timedelta, time
import os
import sys
import pytz

def get_next_session_context(df, ticker):
    """
    Prepares context for the UPCOMING session using the last completed session data.
    """
    last_date = df.index[-1].date()
    
    # The last "complete" session is today (since it's after 16:00)
    curr_day = df[df.index.date == last_date]
    
    if curr_day.empty: return None

    # Calculate Prior Day stats (which is Today for the perspective of Tomorrow)
    pdh = curr_day['high'].max()
    pdl = curr_day['low'].min()
    pdc = curr_day['close'].iloc[-1]
    
    # Calculate Next Trading Date (skip weekends)
    next_date = last_date + timedelta(days=1)
    if next_date.weekday() == 5: # Saturday -> Monday
        next_date += timedelta(days=2)
    elif next_date.weekday() == 6: # Sunday -> Monday
        next_date += timedelta(days=1)
        
    return {
        'Date': next_date,
        'PDH': pdh,
        'PDL': pdl,
        'PDC': pdc,
        'Midnight_Open': None, # Future
        'Open_0830': None,     # Future
        'Is_Projection': True,
        'Prior_Date': last_date
    }

def get_last_session(df, ticker):
    """
    Retrieves context for the CURRENT session (Today).
    """
    last_date = df.index[-1].date()
    curr_day = df[df.index.date == last_date]
    
    if curr_day.empty: return None

    # PDH/PDL from the day BEFORE last_date
    prior_days = df[df.index.date < last_date]
    if not prior_days.empty:
        prev_date = prior_days.index[-1].date()
        prev_day = df[df.index.date == prev_date]
        pdh = prev_day['high'].max()
        pdl = prev_day['low'].min()
        pdc = prev_day['close'].iloc[-1]
    else:
        pdh = pdl = pdc = None

    # Midnight and 08:30 for Today
    m_open = o_0830 = None
    try:
        m_dt = pd.Timestamp(datetime.combine(last_date, time(0, 0))).tz_localize('US/Eastern')
        o_dt = pd.Timestamp(datetime.combine(last_date, time(8, 30))).tz_localize('US/Eastern')
        
        m_idx = df.index.get_indexer([m_dt], method='pad')[0]
        if abs((df.index[m_idx] - m_dt).total_seconds()) < 300:
            m_open = df['open'].iloc[m_idx]
            
        o_idx = df.index.get_indexer([o_dt], method='pad')[0]
        if abs((df.index[o_idx] - o_dt).total_seconds()) < 300:
            o_0830 = df['open'].iloc[o_idx]
    except:
        pass

    # --- ICT BIAS ANALYSIS (Methods 1-3) ---
    ict_analysis = analyze_ict_bias_logic(df, last_date, pdh, pdl, pdc, m_open)

    return {
        'Date': last_date,
        'PDH': pdh,
        'PDL': pdl,
        'PDC': pdc,
        'Midnight_Open': m_open,
        'Open_0830': o_0830,
        'Last_Close': curr_day['close'].iloc[-1],
        'Is_Projection': False,
        'ict_analysis': ict_analysis
    }

def analyze_ict_bias_logic(df, target_date, pdh, pdl, pdc, m_open):
    """
    Implements ICT Intraday Bias Methods 1, 2, and 3.
    """
    analysis = {
        'method_1_pvh': "Neutral",
        'method_2_midnight_london': "Neutral",
        'method_3_london_confirmation': "Neutral",
        'sweeps': [],
        'bias_score': 0
    }

    try:
        # 1. Method 1: Previous Day Candle Analysis (Reversal/Strength)
        # Check if PDC (Yesterday's close) is above/below PDH/PDL
        p_day_df = df[df.index.date == (target_date - timedelta(days=1))]
        if target_date.weekday() == 0: # Monday
             p_day_df = df[df.index.date == (target_date - timedelta(days=3))]
        
        if not p_day_df.empty:
            ph, pl = p_day_df['high'].max(), p_day_df['low'].min()
            pc = p_day_df['close'].iloc[-1]
            if pc > ph: analysis['method_1_pvh'] = "BULLISH (Closed above PDH)"
            elif pc < pl: analysis['method_1_pvh'] = "BEARISH (Closed below PDL)"
            
            # Reversal Sweep Detection
            if p_day_df['low'].min() < pl and pc > pl:
                analysis['method_1_pvh'] = "BULLISH (Swept PDL and closed above)"
            elif p_day_df['high'].max() > ph and pc < ph:
                analysis['method_1_pvh'] = "BEARISH (Swept PDH and closed below)"

        # 2. Method 2: Midnight to London Range (00:00 - 03:00)
        start_0000 = pd.Timestamp(datetime.combine(target_date, time(0, 0))).tz_localize('US/Eastern')
        end_0300 = pd.Timestamp(datetime.combine(target_date, time(3, 0))).tz_localize('US/Eastern')
        m_l_range = df.loc[start_0000:end_0300]
        
        if not m_l_range.empty:
            ml_h, ml_l = m_l_range['high'].max(), m_l_range['low'].min()
            # Check for sweep between 03:00 and 08:30 (Judas Swing)
            pre_ny = df.loc[end_0300:pd.Timestamp(datetime.combine(target_date, time(8, 30))).tz_localize('US/Eastern')]
            if not pre_ny.empty:
                if pre_ny['high'].max() > ml_h: analysis['sweeps'].append("Midnight-London High Swept")
                if pre_ny['low'].min() < ml_l: analysis['sweeps'].append("Midnight-London Low Swept")
                
                if "Midnight-London High Swept" in analysis['sweeps'] and pre_ny['close'].iloc[-1] < ml_h:
                    analysis['method_2_midnight_london'] = "BEARISH (Judas Swing High)"
                elif "Midnight-London Low Swept" in analysis['sweeps'] and pre_ny['close'].iloc[-1] > ml_l:
                    analysis['method_2_midnight_london'] = "BULLISH (Judas Swing Low)"

        # 3. Method 3: London Session Confirmation
        # Asia Range (18:00 Yesterday - 00:00 Today)
        asia_start = pd.Timestamp(datetime.combine(target_date - timedelta(days=1), time(18, 0))).tz_localize('US/Eastern')
        asia_range = df.loc[asia_start:start_0000]
        if not asia_range.empty:
            ah, al = asia_range['high'].max(), asia_range['low'].min()
            # Did London (03:00-08:30) sweep Asia?
            london_period = df.loc[end_0300:pd.Timestamp(datetime.combine(target_date, time(8, 30))).tz_localize('US/Eastern')]
            if not london_period.empty:
                if london_period['high'].max() > ah and london_period['close'].iloc[-1] < ah:
                    analysis['method_3_london_confirmation'] = "BEARISH (London swept Asia High)"
                elif london_period['low'].min() < al and london_period['close'].iloc[-1] > al:
                    analysis['method_3_london_confirmation'] = "BULLISH (London swept Asia Low)"
    except:
        pass

    return analysis

def main(ticker, next_day=False):
    # Import the unified data loader
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))
    from fused_data_loader import load_fused_data
    
    print(f"\n📊 Loading data for {ticker}...")
    # Use the fused data loader (Live + Historical)
    # For daily analysis, we need HTF levels (Weekly/Monthly), so require_historical=True
    df = load_fused_data(ticker, timeframe="1m", require_historical=True)
    
    if df.empty:
        print(f"Error: No data found for {ticker}")
        return
        
    # Ensure Datetime Index
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
        df.set_index('datetime', inplace=True)
    
    # Convert to Eastern Time
    try:
        df.index = df.index.tz_convert('US/Eastern')
    except:
        try:
            df.index = df.index.tz_localize('UTC').tz_convert('US/Eastern')
        except:
             pass 

    if next_day:
        data = get_next_session_context(df, ticker)
        title_suffix = "(PREP FOR TOMORROW)"
    else:
        data = get_last_session(df, ticker)
        title_suffix = "(CURRENT SESSION)"
    
    
    # HTF Levels (Weekly/Monthly)
    # Resample to Weekly 'W-FRI' (Week ending Friday)
    # target_date is the date we are trading. We want the info from the COMPLETED period just before it.
    
    # 1. Weekly
    df_weekly = df.resample('W-FRI').agg({'high':'max', 'low':'min', 'close':'last', 'open':'first'})
    # Filter for weeks BEFORE target date
    prior_weeks = df_weekly[df_weekly.index.date < data['Date']]
    
    pwh = pwl = pmh = pml = None
    
    if not prior_weeks.empty:
        last_week = prior_weeks.iloc[-1]
        pwh = last_week['high']
        pwl = last_week['low']
        
    # 2. Monthly
    df_monthly = df.resample('ME').agg({'high':'max', 'low':'min', 'close':'last', 'open':'first'})
    prior_months = df_monthly[df_monthly.index.date < data['Date']]
    
    if not prior_months.empty:
        last_month = prior_months.iloc[-1]
        pmh = last_month['high']
        pml = last_month['low']


    print(f"\n💎 ICT CONTEXT SHEET: {ticker} {title_suffix} 💎")
    print(f"Target Date: {data['Date']} (derived from {data.get('Prior_Date', 'Previous Session')})")
    print("-----------------------------------")
    
    print("\n📍 KEY LEVELS (Liquidity):")
    if data['PDH']: print(f"   PDH:  {data['PDH']:.2f}  (Buyside Liquidity)")
    if data['PDL']: print(f"   PDL:  {data['PDL']:.2f}  (Sellside Liquidity)")
    if data['PDC']: print(f"   PDC:  {data['PDC']:.2f}  (Gap Fill / Pivot)")
    print("   --- HTF ---")
    if pwh: print(f"   PWH:  {pwh:.2f} (Prev Week High)")
    if pwl: print(f"   PWL:  {pwl:.2f} (Prev Week Low)")
    if pmh: print(f"   PMH:  {pmh:.2f} (Prev Month High)")
    if pml: print(f"   PML:  {pml:.2f} (Prev Month Low)")
    
    print("\n🕒 TIME LEVELS (Magnets):")
    if data['Midnight_Open']: 
        print(f"   Midnight Open: {data['Midnight_Open']:.2f} (Bias Pivot)")
    elif data.get('Is_Projection'):
        print(f"   Midnight Open: [WAITING] (Opens at 00:00 ET)")
        
    if data['Open_0830']:     
        print(f"   08:30 Open:    {data['Open_0830']:.2f}    (News Pivot)")
    elif data.get('Is_Projection'):
        print(f"   08:30 Open:    [WAITING] (Opens at 08:30 ET)")
    
    if not data.get('Is_Projection'):
        print("\n🌊 BIAS CHECK:")
        if data['Midnight_Open']:
            curr_price = data['Last_Close']
            if curr_price > data['Midnight_Open']:
                print(f"   Current Price is ABOVE Midnight Open -> INTRA-DAY BULLISH CONTEXT")
            else:
                print(f"   Current Price is BELOW Midnight Open -> INTRA-DAY BEARISH CONTEXT")
    else:
        print("\n🔮 PRE-MARKET PLAN:")
        print(f"   - Watch reaction at PDC ({data['PDC']:.2f}) during Globex.")
        print(f"   - Mark PDH ({data['PDH']:.2f}) and PDL ({data['PDL']:.2f}) as primary targets.")
            
    print("\n-----------------------------------")
    print("Stats Insight:")
    print("- PDH/PDL are the 'Draw on Liquidity' for the next session.")
    print("- If Globex stays inside prior range -> Expect range expansion.")
    print("-----------------------------------\n")

    return {
        'context': data,
        'htf': {
            'pwh': pwh, 'pwl': pwl,
            'pmh': pmh, 'pml': pml
        }
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", help="Ticker (e.g. NQ1)")
    parser.add_argument("--next-day", action="store_true", help="Prepare for next trading day")
    args = parser.parse_args()
    main(args.ticker, args.next_day)
