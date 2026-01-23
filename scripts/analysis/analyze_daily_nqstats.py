import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import argparse

# Add project root to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

from scripts.utils.fused_data_loader import load_fused_data

# --- SESSION DEFINITIONS (US/Eastern) ---
SESSIONS = {
    'Asia': {'start': time(18, 0), 'end': time(2, 0)},
    'London': {'start': time(3, 0), 'end': time(8, 0)},
    'Pre-NY': {'start': time(8, 0), 'end': time(9, 30)},
    'NY_AM': {'start': time(9, 30), 'end': time(12, 0)},
}

def get_session_data(df, session_name, target_date):
    """Extract data for a specific session on a specific date range."""
    s_config = SESSIONS[session_name]
    
    # Session might span across two dates (e.g. Asia 18:00 - 02:00)
    if s_config['start'] > s_config['end']:
        start_dt = datetime.combine(target_date - timedelta(days=1), s_config['start'])
        end_dt = datetime.combine(target_date, s_config['end'])
    else:
        start_dt = datetime.combine(target_date, s_config['start'])
        end_dt = datetime.combine(target_date, s_config['end'])
        
    # Localize/Convert to ET if needed
    try:
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC').tz_convert('US/Eastern')
        else:
            df.index = df.index.tz_convert('US/Eastern')
    except:
        pass
        
    mask = (df.index >= pd.Timestamp(start_dt).tz_localize('US/Eastern')) & \
           (df.index < pd.Timestamp(end_dt).tz_localize('US/Eastern'))
    
    return df[mask]

def classify_aln(asia_df, london_df):
    """Classify ALN pattern based on Asia-London range comparison."""
    if asia_df.empty or london_df.empty:
        return "Unknown"
        
    ah, al = asia_df['high'].max(), asia_df['low'].min()
    lh, ll = london_df['high'].max(), london_df['low'].min()
    
    if lh > ah and ll < al: return "LEA"   # London Expanded Asia
    if lh > ah and ll >= al: return "LPEU" # London Positive Expansion Up
    if ll < al and lh <= ah: return "LPED" # London Positive Expansion Down
    return "AEL" # Asia Expanded London (Inside Day)

def get_broken_status(asia_df, london_df, preny_df):
    """Check if subsequent sessions broke prior session ranges."""
    status = []
    
    # 1. Did London break Asia?
    if not asia_df.empty and not london_df.empty:
        ah, al = asia_df['high'].max(), asia_df['low'].min()
        lh, ll = london_df['high'].max(), london_df['low'].min()
        london_broke = "Broken" if (lh > ah or ll < al) else "Held"
    else:
        london_broke = "Unknown"
        
    # 2. Did Pre-NY break London?
    if not london_df.empty and not preny_df.empty:
        lh, ll = london_df['high'].max(), london_df['low'].min()
        ph, pl = preny_df['high'].max(), preny_df['low'].min()
        preny_broke = "Broken" if (ph > lh or pl < ll) else "Held"
    else:
        preny_broke = "Unknown"
        
    return f"{london_broke}/{preny_broke}"

def get_profiler_status(asia_df, london_df, prior_close):
    """Check if close is above/below prior day close (P12)."""
    if prior_close is None: return "N/N"
    
    a_status = "N"
    if not asia_df.empty:
        a_status = "L" if asia_df['close'].iloc[-1] > prior_close else "S"
        
    l_status = "N"
    if not london_df.empty:
        l_status = "L" if london_df['close'].iloc[-1] > prior_close else "S"
        
    return f"{a_status}/{l_status}"

def main():
    parser = argparse.ArgumentParser(description="NQStats Daily Analysis")
    parser.add_argument("--ticker", default="NQ1", help="Ticker (NQ1, ES1, etc.)")
    parser.add_argument("--date", help="Analysis date (YYYY-MM-DD), default Today")
    parser.add_argument("--markdown", action="store_true", help="Output in Markdown format")
    parser.add_argument("--discord", action="store_true", help="Send report to Discord")
    parser.add_argument("--channel", default="data_gap_reports", help="Discord channel name")
    args = parser.parse_args()
    
    target_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else datetime.now().date()
    
    # 1. Load Data
    df = load_fused_data(args.ticker, timeframe="1m", require_historical=True)
    if df.empty:
        print("❌ Error: No data available for analysis.")
        return

    # 2. Get Sessions
    asia = get_session_data(df, 'Asia', target_date)
    london = get_session_data(df, 'London', target_date)
    preny = get_session_data(df, 'Pre-NY', target_date)
    
    # 3. Get Prior Close (P12)
    prior_df = df[df.index.date < target_date]
    prior_close = None
    if not prior_df.empty:
        prior_close_dt = datetime.combine(target_date - timedelta(days=1), time(16, 0))
        if target_date.weekday() == 0: 
            prior_close_dt = datetime.combine(target_date - timedelta(days=3), time(16, 0))
            
        try:
             closest_bar = df.index.get_indexer([pd.Timestamp(prior_close_dt).tz_localize('US/Eastern')], method='pad')[0]
             prior_close = df['close'].iloc[closest_bar]
        except:
             prior_close = prior_df['close'].iloc[-1]

    # 4. Classify
    aln = classify_aln(asia, london)
    broken = get_broken_status(asia, london, preny)
    status = get_profiler_status(asia, london, prior_close)
    
    combo_key = f"{aln} | {broken} | {status}"
    
    # 5. Determine Bias
    bias = "NEUTRAL / WAIT"
    conviction = "LOW"
    action = "Wait for NY Open (9:30) to establish direction."
    
    if aln == "LPEU" and (broken == "Held/Held" or broken == "Broken/Held") and status == "L/L":
        bias = "STRONG BULLISH"
        conviction = "HIGH"
        action = "Look for Longs on pullbacks to London Mid."
    elif aln == "LPEU" and broken == "Broken/Held" and status == "L/S":
        bias = "STRONG BEARISH (REVERSAL)"
        conviction = "HIGH"
        action = "Look for Shorts on rallies to London Mid."
    elif broken == "Broken/Broken":
        bias = "NEUTRAL / CHOP"
        conviction = "LOW"
        action = "Expect chop. Reduce size or wait."

    # 6. Report
    report_lines = []
    if args.markdown or args.discord:
        report_lines.append(f"### 📊 NQSTATS: {args.ticker} | {target_date}")
        report_lines.append(f"---")
        report_lines.append(f"**Final Bias**: `{bias}` | **Conviction**: `{conviction}`")
        report_lines.append(f"**Action**: {action}")
        report_lines.append(f"\n**Classification**:")
        report_lines.append(f"- ALN: `{aln}`")
        report_lines.append(f"- Broken: `{broken}`")
        report_lines.append(f"- Status: `{status}`")
        report_lines.append(f"\n**🌙 Noon Curve**: 75% chance High/Low on **Opposite Sides** of Noon.")
        
        if not london.empty:
            lh, ll = london['high'].max(), london['low'].min()
            report_lines.append(f"\n**📍 Key Levels**:")
            report_lines.append(f"- London High: `{lh:.2f}`")
            report_lines.append(f"- London Low: `{ll:.2f}`")
            report_lines.append(f"- London Mid: `{(lh+ll)/2:.2f}`")
        
        report_text = "\n".join(report_lines)

    if args.markdown or not args.discord:
        if args.markdown:
            print(report_text)
        else:
            print(f"==========================================")
            print(f"📊 NQSTATS UNIFIED BIAS: {args.ticker} | {target_date}")
            print(f"==========================================\n")
            print(f"Pattern Classification:")
            print(f"  - ALN Pattern: {aln}")
            print(f"  - Broken Status: {broken}")
            print(f"  - Profiler Status: {status}")
            print(f"  - Prior Close (P12): {prior_close:.2f if prior_close else 'N/A'}")
            print(f"  - Combo Key: {combo_key}")
            print(f"\n📢 FINAL BIAS: {bias}")
            print(f"🎯 CONVICTION: {conviction}")
            print(f"📝 ACTION: {action}")
            print(f"\n🌙 NOON CURVE PROBABILITY:")
            print(f"  - 74.9% chance HOD and LOD are on Opposite Sides of 12:00 ET.")
            if not london.empty:
                lh, ll = london['high'].max(), london['low'].min()
                print(f"\n📍 KEY NQSTATS LEVELS:")
                print(f"  - London High: {lh:.2f}")
                print(f"  - London Low:  {ll:.2f}")
                print(f"  - London Mid:  {(lh+ll)/2:.2f}")
            print("\n" + "="*42)

    if args.discord:
        from scripts.utils.discord_notify import get_webhook_url, send_message
        webhook_url = get_webhook_url(args.channel)
        if webhook_url:
            send_message(webhook_url, report_text)
        else:
            print(f"❌ Discord Error: Channel '{args.channel}' not found.")

if __name__ == "__main__":
    main()
