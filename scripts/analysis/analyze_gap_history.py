import json
import pandas as pd
import numpy as np
import os
import sys
import sqlite3
import pytz
from datetime import datetime, timedelta

# Add utils to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))
try:
    from fused_data_loader import load_fused_data
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', 'utils'))
    from fused_data_loader import load_fused_data

GAP_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'derived', 'rth_gaps.json')
DB_PATH = "c:/Users/vinay/tvDownloadOHLC/web/prisma/dev.db"

def analyze_gap_history(ticker="NQ1"):
    ticker_clean = ticker.replace("1", "")
    print(f"[{ticker}] Starting Full Gap Analysis...")
    
    if not os.path.exists(GAP_FILE):
        print(f"[{ticker}] Error: Gap file not found at {GAP_FILE}")
        return

    with open(GAP_FILE, 'r') as f:
        all_gaps = json.load(f)
        
    gaps = all_gaps.get(ticker, [])
    if not gaps:
        print(f"[{ticker}] No gaps found in master file.")
        return

    gaps_df = pd.DataFrame(gaps)
    
    print(f"[{ticker}] Loading 1m Price Data...")
    df_1m = load_fused_data(ticker, timeframe="1m", require_historical=True)
    if 'datetime' in df_1m.columns:
        df_1m['datetime'] = pd.to_datetime(df_1m['datetime'], utc=True)
        df_1m.set_index('datetime', inplace=True)
    try:
        df_1m = df_1m.tz_convert('US/Eastern')
    except:
        df_1m = df_1m.tz_localize('UTC').tz_convert('US/Eastern')
        
    # Load VIX and VVIX for Context
    print(f"[{ticker}] Loading Volatility Data (VIX/VVIX)...")
    vix_df = load_fused_data("VIX", timeframe="1m", require_historical=True)
    vvix_df = load_fused_data("VVIX", timeframe="1d", require_historical=True)
    
    # Load Economic Events for News Context
    print(f"[{ticker}] Fetching US 8:30 AM High-Impact News...")
    news_days = {}
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            EXCLUDE_KEYWORDS = ["German", "French", "Spanish", "Italian", "Eurozone", "UK ", "JPY", "AUD", "CAD", "CNY", "Swiss", "ECB President", "EU ", "Australian", "British", "Canadian", "Japanese", "Chinese"]
            query = "SELECT datetime, name FROM EconomicEvent WHERE impact = 'HIGH'"
            events_df = pd.read_sql_query(query, conn)
            conn.close()
            
            if not events_df.empty:
                local_tz = pytz.timezone('US/Eastern')
                for _, row in events_df.iterrows():
                    dt_raw, name = row['datetime'], row['name']
                    if any(kw in name for kw in EXCLUDE_KEYWORDS): continue
                    if isinstance(dt_raw, str): dt_utc = pd.to_datetime(dt_raw).tz_localize('UTC')
                    else: dt_utc = pd.to_datetime(dt_raw, unit='ms').tz_localize('UTC')
                    dt_local = dt_utc.astimezone(local_tz)
                    if dt_local.hour == 11 and dt_local.minute == 30: # Proxy for 8:30 AM
                        d_str = str(dt_local.date())
                        if d_str not in news_days: news_days[d_str] = []
                        news_days[d_str].append(name)
        except Exception as e: print(f"Error loading news: {e}")

    # Process Volatility Indices
    vix_at_open = {}
    if not vix_df.empty:
        if 'datetime' in vix_df.columns:
            vix_df['datetime'] = pd.to_datetime(vix_df['datetime'], utc=True)
            vix_df.set_index('datetime', inplace=True)
        try: vix_df = vix_df.tz_convert('US/Eastern')
        except: vix_df = vix_df.tz_localize('UTC').tz_convert('US/Eastern')
        # Robust daily VIX: Take first available price of each day (usually 09:30)
        vix_daily = vix_df.groupby(vix_df.index.date)['close'].first()
        for d, val in vix_daily.items(): vix_at_open[str(d)] = val
            
    vvix_by_date = {}
    if not vvix_df.empty:
        if 'datetime' in vvix_df.columns:
            vvix_df['datetime'] = pd.to_datetime(vvix_df['datetime'], utc=True)
            vvix_df.set_index('datetime', inplace=True)
        # Handle timezone for daily data if needed, then group
        vvix_daily = vvix_df.groupby(vvix_df.index.date)['close'].last()
        for d, val in vvix_daily.items(): vvix_by_date[str(d)] = val
            
    # Calculate ATR (14-day)
    print(f"[{ticker}] Calculating ATR-14 for Relative Risk...")
    daily_ohlc = df_1m.resample('D').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
    daily_ohlc['prev_close'] = daily_ohlc['close'].shift(1)
    daily_ohlc['tr'] = pd.concat([abs(daily_ohlc['high'] - daily_ohlc['low']), abs(daily_ohlc['high'] - daily_ohlc['prev_close']), abs(daily_ohlc['low'] - daily_ohlc['prev_close'])], axis=1).max(axis=1)
    daily_ohlc['atr'] = daily_ohlc['tr'].rolling(window=14).mean()
    atr_map = {str(ts.date()): val for ts, val in daily_ohlc['atr'].items()}

    price_mini = df_1m[['open', 'high', 'low', 'close']].copy()
    day_groups = {str(k): v for k, v in price_mini.groupby(price_mini.index.date)}
    sorted_dates = sorted(day_groups.keys())
    date_map = {curr: prev for prev, curr in zip(sorted_dates, sorted_dates[1:])}
    
    results = []
    
    for idx, row in gaps_df.iterrows():
        date_str, gap_type, prev_close, gap_size, open_price = row['date'], row['gap_direction'], row['prev_close_price'], abs(row['gap_size']), row['curr_open_price']
        if date_str not in day_groups: continue
        day_data = day_groups[date_str]
        
        # Context
        gap_pct = (gap_size / prev_close) * 100.0 if prev_close else 0
        day_news = news_days.get(date_str, [])
        is_news_day = len(day_news) > 0
        news_name = ", ".join(day_news) if day_news else "None"
        dt_obj = pd.Timestamp(date_str)
        day_of_week = dt_obj.day_name()
        
        vix_val = vix_at_open.get(date_str, None)
        vol_regime = "Low VIX" if vix_val and vix_val < 15 else "Normal VIX" if vix_val and vix_val < 25 else "High VIX" if vix_val else "Unknown"
        vvix_val = vvix_by_date.get(date_str, None)
        vvix_regime = "Low VVIX" if vvix_val and vvix_val < 90 else "Normal VVIX" if vvix_val and vvix_val < 110 else "High VVIX" if vvix_val else "Unknown"
        atr_val = atr_map.get(date_str, None)
        atr_pct = (atr_val / open_price) * 100.0 if atr_val and open_price else None
        
        rth_start = (dt_obj + pd.Timedelta(hours=9, minutes=30)).tz_localize("US/Eastern")
        day_rth = day_data[day_data.index >= rth_start]
        if day_rth.empty: continue
        
        session_open, session_close = day_rth.iloc[0]['open'], day_rth.iloc[-1]['close']
        day_direction = "Bullish" if session_close > session_open else "Bearish"

        is_filled, time_to_fill = False, None
        retrace_pts, fakeout_pts = 0.0, 0.0
        
        if gap_type == "UP":
            fill_mask = day_rth['low'] <= prev_close
            retrace_pts = max(0, open_price - day_rth['low'].min())
            if fill_mask.any():
                is_filled, first_fill = True, day_rth[fill_mask].index[0]
                time_to_fill = (first_fill - rth_start).total_seconds() / 60.0
                fakeout_pts = day_rth[day_rth.index <= first_fill]['high'].max() - open_price
            else: fakeout_pts = day_rth['high'].max() - open_price
        else:
            fill_mask = day_rth['high'] >= prev_close
            retrace_pts = max(0, day_rth['high'].max() - open_price)
            if fill_mask.any():
                is_filled, first_fill = True, day_rth[fill_mask].index[0]
                time_to_fill = (first_fill - rth_start).total_seconds() / 60.0
                fakeout_pts = open_price - day_rth[day_rth.index <= first_fill]['low'].min()
            else: fakeout_pts = open_price - day_rth['low'].min()
            
        retrace_pct = 100.0 if is_filled else (retrace_pts / gap_size) * 100.0 if gap_size > 0 else 0
        fakeout_pct = (fakeout_pts / gap_size) * 100.0 if gap_size > 0 else 0
        extension_pts = (day_rth['high'].max() - open_price) if gap_type == "UP" else (open_price - day_rth['low'].min())
        extension_ratio = (extension_pts / gap_size) if gap_size > 0 else 0
        trend_continuation = (gap_type == "UP" and session_close > open_price) or (gap_type == "DOWN" and session_close < open_price)

        open_type, prev_day_bias = "Unknown", "Unknown"
        near_side_broken, far_side_broken = False, False
        if date_str in date_map:
            p_date = date_map[date_str]
            if p_date in day_groups:
                p_rth = day_groups[p_date][(day_groups[p_date].index >= (pd.Timestamp(p_date) + pd.Timedelta(hours=9, minutes=30)).tz_localize("US/Eastern")) & (day_groups[p_date].index <= (pd.Timestamp(p_date) + pd.Timedelta(hours=16, minutes=15)).tz_localize("US/Eastern"))]
                if not p_rth.empty:
                    p_high, p_low = p_rth['high'].max(), p_rth['low'].min()
                    prev_day_bias = "Bullish" if p_rth.iloc[-1]['close'] > p_rth.iloc[0]['open'] else "Bearish"
                    if open_price > p_high: open_type = "OBR (Above)"
                    elif open_price < p_low: open_type = "OBR (Below)"
                    else: open_type = "IBR"
                    if gap_type == "UP": near_side_broken, far_side_broken = day_rth['low'].min() < p_high, day_rth['low'].min() < p_low
                    else: near_side_broken, far_side_broken = day_rth['high'].max() > p_low, day_rth['high'].max() > p_high

        retrace_price_pct = (retrace_pts / open_price) * 100.0 if open_price > 0 else 0
        fakeout_price_pct = (fakeout_pts / open_price) * 100.0 if open_price > 0 else 0
        extension_price_pct = (extension_pts / open_price) * 100.0 if open_price > 0 else 0

        results.append({
            "date": date_str, "day": day_of_week, "gap_dir": gap_type, "prev_close": prev_close,
            "vol_regime": vol_regime, "vvix_regime": vvix_regime, "atr_pct_val": atr_pct, "gap_pct": gap_pct,
            "is_news_day": is_news_day, "news_name": news_name, "is_filled": is_filled, "time_to_fill": time_to_fill,
            "day_direction": day_direction, "prev_day_bias": prev_day_bias, "open_type": open_type,
            "near_side_broken": near_side_broken, "far_side_broken": far_side_broken,
            "retrace_pct": retrace_pct, "fakeout_pct": fakeout_pct, "trend_continuation": trend_continuation,
            "extension_ratio": extension_ratio, "retrace_price_pct": retrace_price_pct,
            "fakeout_price_pct": fakeout_price_pct, "extension_price_pct": extension_price_pct,
            "days_to_fill": 0 if is_filled else None
        })
        
    for res in results:
        if res['is_filled']: continue
        target, g_dir, start_date = res['prev_close'], res['gap_dir'], res['date']
        try: start_idx = sorted_dates.index(start_date)
        except ValueError: continue
        for offset in range(1, 61):
            if start_idx + offset >= len(sorted_dates): break
            future_day = day_groups[sorted_dates[start_idx + offset]]
            if (g_dir == "UP" and future_day['low'].min() <= target) or (g_dir == "DOWN" and future_day['high'].max() >= target):
                res['days_to_fill'] = offset
                break
                
    df_res = pd.DataFrame(results)
    
    def get_stats(series, precision=1):
        if series.empty: return "N/A"
        return f"Mean: {series.mean():.{precision}f} | Med: {series.median():.{precision}f} | Mode: {series.round(precision).mode().iloc[0] if not series.empty else 0:.{precision}f}"

    # Generate Markdown Report Content
    output = [
        f"# 📊 Consolidated RTH Gap Analysis Report: {ticker_clean}",
        f"\n**Date:** {datetime.now().strftime('%B %d, %Y')}",
        f"**Ticker:** {ticker} ({ticker_clean})",
        f"**Data Range:** {df_res['date'].min()} to {df_res['date'].max()} ({len(df_res)} Sessions)",
        f"**Script:** `scripts/analysis/analyze_gap_history.py`",
        "\n## 1. Executive Summary",
        f"This analysis investigates the behavior of **Regular Trading Hours (RTH) Gaps** for {ticker_clean}. Key findings show that {ticker_clean} gaps fill approximately {df_res['is_filled'].mean()*100:.1f}% of the time, with defense probabilities shifting significantly based on ATR and VIX regimes.",
        "\n---",
        "\n## 2. Terminology: Reversion vs. Defense",
        "\n| Term | Strategy | Market Context | Bias Edge |",
        "| :--- | :--- | :--- | :--- |",
        "| **Reversion Favored** | **Trade for the Fill**. Fade the gap move back to yesterday's close. | Low ATR, Low VVIX. | **High Fill Rate**. |",
        "| **Defense Favored** | **Trade for Continuation**. Bet on the gap holding (The 'Moat'). | High ATR, High VVIX. | **High Defense Rate**. |",
        "\n---",
        "\n## 3. Daily Bias Inference: Morning Checklist",
        "Use this logic gate every morning at 09:30 ET:",
        "\n### STEP 1: Check the Environment",
        f"*   **Volatility**: Is VVIX > 110 or is ATR High? (If yes -> **Defense Favored**).",
        f"*   **News**: Is there an 8:30 AM US News release (NFP/CPI)? (If yes -> **Expect wider volatility before fill**).",
        "\n### STEP 2: Measure the Gap Size",
        "*   **Gap < 0.15%**: High probability **Reversion** (Treat as noise).",
        "*   **Gap 0.15% - 0.45%**: The **Conflict Zone**. Lean on Volatility/Context filters.",
        "*   **Gap > 0.45%**: High probability **Defense** (Expect Trend Continuation).",
        "\n### STEP 3: The 15-Minute Execution Filter",
        "*   **The Moat Check**: If Yesterday's Extreme (High/Low) holds for the first 15m, the **Defense** bias is confirmed.",
        "\n---",
        "\n## 4. Statistical Breakdown",
        "\n### A. Fill Probabilities by Size",
    ]

    # Calculate Gap Buckets
    def get_bucket_stats(df):
        buckets = [0, 0.07, 0.15, 0.25, 0.45, 100]
        labels = ["Very Small (<0.07%)", "Small (0.07-0.15%)", "Medium (0.15-0.25%)", "Large (0.25-0.45%)", "Very Large (>0.45%)"]
        df['bucket'] = pd.cut(df['gap_pct'], bins=buckets, labels=labels)
        b_stats = df.groupby('bucket', observed=False).agg({'is_filled': 'mean', 'date': 'count'})
        b_stats.columns = ['Fill Rate', 'Days']
        b_stats['Fill Rate'] = (b_stats['Fill Rate'] * 100).round(1).astype(str) + "%"
        return b_stats

    bucket_stats = get_bucket_stats(df_res)
    output.append(bucket_stats[['Days', 'Fill Rate']].to_markdown() + "\n")
    
    output.append("### B. Day of Week Analysis")
    dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    df_res['day'] = pd.Categorical(df_res['day'], categories=dow_order, ordered=True)
    day_stats = df_res.groupby('day', observed=False).agg({'is_filled': 'mean', 'time_to_fill': 'median', 'date': 'count'})
    day_stats.columns = ['Fill Rate', 'Med Time (min)', 'Count']
    day_stats['Fill Rate'] = (day_stats['Fill Rate'] * 100).round(1).astype(str) + "%"
    output.append(day_stats[['Count', 'Fill Rate', 'Med Time (min)']].to_markdown() + "\n")

    output.append("## 5. MAE / MFE Precision (Stats Trader View)")
    output.append(f"Treating the gap as a 'Range' to be broken or filled.\n")
    output.append(f"### A. The 'Fakeout' Move (MFE before Fill)")
    output.append(f"How much 'heat' do you take *in the gap direction* before the fill actually happens?")
    output.append(f"- **Median Fakeout**: {df_res['fakeout_pct'].median():.1f}% of Gap Size.")
    output.append(f"- **Mean Fakeout**: {df_res['fakeout_pct'].mean():.1f}%.")
    
    output.append(f"\n### B. Retracement Depth (MAE for Trend / Progress for Fill)")
    output.append(f"How much of the gap actually gets filled on average?")
    output.append(f"- **Median Retrace**: {df_res['retrace_pct'].median():.1f}% (i.e. Full Fill is the median outcome).")
    output.append(f"- **Mean Retrace**: {df_res['retrace_pct'].mean():.1f}%.")
    
    output.append(f"\n### C. Total Extension (MFE for Trend)")
    output.append(f"How much does price run *beyond* the open by the end of the session?")
    output.append(f"- **Median Extension**: {get_stats(df_res['extension_ratio'] * 100)}")
    
    output.append("\n### D. Pure Price Percentage Levels (Move / Index Price %)")
    output.append(f"- **MAE (Retrace Pct)**: {get_stats(df_res['retrace_price_pct'], 2)}%")
    output.append(f"- **MFE (Fakeout Pct)**: {get_stats(df_res['fakeout_price_pct'], 2)}%")
    output.append(f"- **MFE (Total Session Ext)**: {get_stats(df_res['extension_price_pct'], 2)}%\n")

    output.append("## 6. Trend & Bias Correlation Analysis")
    bias_stats = df_res.groupby(['prev_day_bias', 'gap_dir'], observed=False).agg({'is_filled': 'mean', 'date': 'count'})
    bias_stats.columns = ['Fill Rate', 'Days']
    bias_stats['Fill Rate'] = (bias_stats['Fill Rate'] * 100).round(1).astype(str) + "%"
    output.append("\n### Impact of Previous Day Bias")
    output.append(bias_stats.to_markdown())
    
    output.append("\n### ATR Volatility Correlation")
    if 'atr_pct_val' in df_res.columns:
        df_res['atr_bucket'] = pd.qcut(df_res['atr_pct_val'], 3, labels=["Low ATR", "Normal ATR", "High ATR"])
        atr_stats = df_res.groupby('atr_bucket', observed=False).agg({'is_filled': 'mean', 'gap_pct': 'mean', 'date': 'count'})
        atr_stats.columns = ['Fill Rate', 'Avg Gap %', 'Days']
        atr_stats['Fill Rate'] = (atr_stats['Fill Rate'] * 100).round(1).astype(str) + "%"
        output.append(atr_stats.to_markdown() + "\n")

    output.append("## 7. RTH Open Types & Boundary Defense")
    open_stats = df_res.groupby('open_type', observed=False).agg({'is_filled': 'mean', 'near_side_broken': 'mean', 'far_side_broken': 'mean', 'date': 'count'})
    open_stats.columns = ['Fill Rate', 'Near Side', 'Far Side', 'Days']
    for col in ['Fill Rate', 'Near Side', 'Far Side']: open_stats[col] = (open_stats[col] * 100).round(1).astype(str) + "%"
    output.append(open_stats[['Days', 'Fill Rate', 'Near Side', 'Far Side']].to_markdown() + "\n")

    output.append("## 8. Volatility Regime Impact")
    vix_stats = df_res.groupby('vol_regime', observed=False).agg({'is_filled': 'mean', 'date': 'count'})
    vix_stats.columns = ['Fill Rate', 'Days']
    vix_stats['Fill Rate'] = (vix_stats['Fill Rate'] * 100).round(1).astype(str) + "%"
    output.append(vix_stats.to_markdown() + "\n")

    output.append("## 9. 8:30 AM News Impact")
    news_stats = df_res.groupby('is_news_day', observed=False).agg({'gap_pct': 'mean', 'is_filled': 'mean', 'date': 'count'})
    news_stats.columns = ['Avg Gap %', 'Fill Rate', 'Days']
    news_stats.index = ['No News', '8:30 News']
    news_stats['Fill Rate'] = (news_stats['Fill Rate'] * 100).round(1).astype(str) + "%"
    output.append(news_stats.to_markdown() + "\n")
    
    output.append("### Specific News Type Breakdown")
    if not df_res[df_res['is_news_day']].empty:
        news_items = []
        for kw in ["CPI", "NFP", "Retail Sales", "GDP", "Unemployment Rate"]:
            subset = df_res[df_res['news_name'].str.contains(kw, case=False, na=False)]
            if not subset.empty:
                news_items.append({
                    "Event Type": kw,
                    "Days": len(subset),
                    "Avg Gap": f"{subset['gap_pct'].mean():.2f}%",
                    "Fill Rate": f"{subset['is_filled'].mean()*100:.1f}%"
                })
        if news_items:
            output.append(pd.DataFrame(news_items).to_markdown(index=False) + "\n")

    output.append("## 10. Deferred Fill Analysis (IPDA Windows)")
    unfilled = df_res[~df_res['is_filled']].copy()
    if not unfilled.empty:
        n = len(unfilled)
        output.append(f"- **IPDA 20-Day (Short Term)**: {(unfilled['days_to_fill'] <= 20).sum() / n * 100:.1f}%")
        output.append(f"- **IPDA 40-Day (Med Term)**: {(unfilled['days_to_fill'] <= 40).sum() / n * 100:.1f}%")
        output.append(f"- **IPDA 60-Day (Long Term)**: {(unfilled['days_to_fill'] <= 60).sum() / n * 100:.1f}%\n")
        
        output.append("### Deferred Fill Probabilities by Creation Day")
        dow_deferred = []
        for d in dow_order:
            d_unfilled = unfilled[unfilled['day'] == d]
            if not d_unfilled.empty:
                cnt = len(d_unfilled)
                f1 = (d_unfilled['days_to_fill'] == 1).sum() / cnt * 100
                f3 = (d_unfilled['days_to_fill'] <= 3).sum() / cnt * 100
                dow_deferred.append({"Creation Day": d, "Unfilled": cnt, "Fill Day 1": f"{f1:.1f}%", "3-Day Cum": f"{f3:.1f}%"})
        if dow_deferred:
            output.append(pd.DataFrame(dow_deferred).to_markdown(index=False) + "\n")

        friday_unfilled = unfilled[unfilled['day'] == 'Friday']
        if not friday_unfilled.empty:
            f_rem = len(friday_unfilled)
            f_fill_mon = (friday_unfilled['days_to_fill'] == 1).sum()
            output.append(f"- **Friday Persistence**: If a Friday gap holds, only {f_fill_mon/f_rem*100:.1f}% fill on the subsequent Monday.\n")

    output.append("## 11. Best Practices & Operational Guardrails")
    output.append("1. **Size Filter**: Gaps 0.15% - 0.45% are optimal.\n2. **Regime Respect**: Use caution in High VIX/VVIX regimes.\n3. **15-Minute Moat**: Wait for RTH opening candle confirmation.")
    output.append("\n---\n**Generated by**: `scripts/analysis/analyze_gap_history.py`")

    report_path = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'nqstats', 'rth_breaks', f"{ticker_clean}_GAP_ANALYSIS.md")
    with open(report_path, 'w', encoding='utf-8') as f: f.write("\n".join(output))
    print(f"[{ticker}] Report saved: {report_path}")

if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "NQ1"
    analyze_gap_history(ticker)
