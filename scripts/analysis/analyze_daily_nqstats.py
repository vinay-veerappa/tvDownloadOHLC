import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
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
    
    if lh > ah and ll < al: return "LEA"   # London Engulfs Asia
    if lh > ah and ll >= al: return "LPEU" # London Partially Engulfs Up
    if ll < al and lh <= ah: return "LPED" # London Partially Engulfs Down
    return "AEL" # Asia Engulfs London

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
    parser.add_argument("--channel", default="test_channel", help="Discord channel name")
    args = parser.parse_args()
    
    target_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else datetime.now().date()
    
    # 1. Load Data
    df = load_fused_data(args.ticker, timeframe="1m", require_historical=True)
    if df.empty:
        print("❌ Error: No data available for analysis.")
        return

    # 3. Get Engine Status
    from scripts.libs_py.nqstats.engine import NQStatsEngine
    
    engine = NQStatsEngine(df, ticker=args.ticker)
    # Filter for target date
    day_df = df[df.index.date == target_date]
    if day_df.empty:
        print(f"❌ Error: No data for {target_date}")
        return
        
    # We run the engine on the full DF to get correct P12/prior context, 
    # then extract the last status for the target date.
    stats_df = engine.process()
    target_stats = stats_df[stats_df.index.date == target_date]
    if target_stats.empty:
        print(f"❌ Error: No stats generated for {target_date}")
        return
        
    latest = target_stats.iloc[-1]
    
    # Map back to report variables for compatibility
    aln = latest['aln']
    broken = latest['broken']
    # status in report was Asia/London LT/ST style, which matches the quadrants
    status = f"{latest['asia_quadrant']}/{latest['london_quadrant']}"
    prior_close = latest['p12']
    
    combo_key = f"{aln} | {broken} | {status}"
    
    # 5. Determine Bias (Refined Logic)
    bias = "NEUTRAL / WAIT"
    conviction = "LOW"
    action = latest.get('action', "Wait for NY Open (9:30) to establish direction.")
    logic_reasoning = f"NQStats Logic: {aln} + {broken} + {status}"
    
    # Handle specific ALN models (DRY: this logic is now partly in the engine, but we'll present it)
    if aln == "LPEU" and (broken == "Held/Held" or broken == "Broken/Held") and latest['asia_quadrant'] == "LT":
        bias = "STRONG BULLISH"
        conviction = "HIGH"
        action = "Look for Longs on pullbacks to London Mid."
        logic_reasoning = "LPEU (78% Continuation) + Strong Alignment + Clean Structure (Held)."
    elif aln == "LPEU" and broken == "Broken/Held" and latest['london_quadrant'] == "ST":
        bias = "STRONG BEARISH (REVERSAL)"
        conviction = "HIGH"
        action = "Look for Shorts on rallies to London Mid."
        logic_reasoning = "LPEU (63% Reversal) + Broken Asia + London Reversal."
    elif broken == "Broken/Broken":
        bias = "NEUTRAL / CHOP"
        conviction = "LOW"
        action = "Expect chop. Reduce size or wait."
        logic_reasoning = "Market structure is broken on both sides. High noise risk."

    # 6. Report
    report_lines = []
    
    report_lines.append(f"### 📊 NQSTATS: {args.ticker} | {target_date}")
    report_lines.append(f"---")
    report_lines.append(f"**Final Bias**: `{bias}` | **Conviction**: `{conviction}`")
    report_lines.append(f"**Action**: {action}")
    report_lines.append(f"\n**Classification**:")
    report_lines.append(f"- ALN: `{aln}`")
    report_lines.append(f"- Broken: `{broken}`")
    report_lines.append(f"- Status: `{status}`")
    report_lines.append(f"\n**Reasoning**: {logic_reasoning}")
    
    # 7. Add NQStats Claims
    report_lines.append(f"\n**📈 NQStats Claims for {aln}:**")
    if aln == "LPEU":
        report_lines.append("- NY breaks London High (Continuation): **~78%**")
        report_lines.append("- NY breaks London Low (Reversal): **~63%**")
        report_lines.append("- NY breaks Asia Low (Full Reversal): **~54%**")
    elif aln == "LPED":
        report_lines.append("- NY breaks London Low (Continuation): **~82%**")
        report_lines.append("- NY breaks London High (Reversal): **~58%**")
    elif aln == "LEA":
        report_lines.append("- NY breaks London High OR Low: **~80%**")
        report_lines.append("- NY breaks BOTH High AND Low: **~64%**")
    elif aln == "AEL":
        report_lines.append("- NY breaks Asia High: **~74%**")
        report_lines.append("- NY breaks Asia Low: **~63%**")
        report_lines.append("- NY breaks BOTH High AND Low: **~42%**")
    
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
            print(f"  - Prior Close (P12): {prior_close:.2f}" if prior_close else "  - Prior Close (P12): N/A")
            print(f"  - Combo Key: {combo_key}")
            print(f"\n📢 FINAL BIAS: {bias}")
            print(f"🎯 CONVICTION: {conviction}")
            print(f"📝 ACTION: {action}")
            if not london.empty:
                lh, ll = london['high'].max(), london['low'].min()
                print(f"\n📍 KEY NQSTATS LEVELS:")
                print(f"  - London High: {lh:.2f}")
                print(f"  - London Low:  {ll:.2f}")
                print(f"  - London Mid:  {(lh+ll)/2:.2f}")
            print("\n" + "="*42)

    # 8. Prepare Result Data
    result_data = {
        'aln': aln,
        'broken': broken,
        'status': status,
        'bias': bias,
        'conviction': conviction,
        'action': action,
        'reasoning': logic_reasoning,
        'claims': [l for l in report_lines if l.startswith("- NY breaks")],
        'levels': {
            'lh': lh if not london.empty else None,
            'll': ll if not london.empty else None,
            'mid': (lh+ll)/2 if not london.empty else None
        }
    }

    if args.discord:
        from scripts.utils.discord_notify import get_webhook_url, send_message
        webhook_url = get_webhook_url(args.channel)
        if webhook_url:
            send_message(webhook_url, report_text)
        else:
            print(f"❌ Discord Error: Channel '{args.channel}' not found.")
            
    return report_text, result_data

if __name__ == "__main__":
    report, data = main()
