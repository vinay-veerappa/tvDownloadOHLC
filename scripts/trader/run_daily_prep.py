import os
import sys
import argparse
import subprocess
from datetime import datetime, timedelta

# Script Paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")

FETCH_SCRIPT = os.path.join(SCRIPTS_DIR, "market_data", "fetch_schwab_data.py")
PRECOMPUTE_SCRIPT = os.path.join(SCRIPTS_DIR, "derived", "precompute_daily_classification.py")
ICT_CONTEXT_SCRIPT = os.path.join(SCRIPTS_DIR, "trader", "retrieve_ict_context.py")
STATS_SCRIPT = os.path.join(SCRIPTS_DIR, "trader", "retrieve_daily_stats.py")

def run_command(cmd):
    print(f"\n[EXEC] {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing {cmd[0]}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Daily Analysis Wargame")
    parser.add_argument("--tickers", nargs="+", default=["NQ1", "ES1"], help="Tickers to analyze")
    parser.add_argument("--force-fetch", action="store_true", help="Force fresh data download")
    parser.add_argument("--next-day", action="store_true", help="Prepare for next trading day (Tomorrow)")
    args = parser.parse_args()

    print("==========================================")
    print(f"🛡️  DAILY WARGAME PREP: {datetime.now().strftime('%Y-%m-%d %H:%M')}  🛡️")
    if args.next_day:
        print("   (MODE: NEXT TRADING DAY / TOMORROW)")
    print("==========================================\n")

    # 1. BRIDGE THE GAP (Data Acquisition)
    print("📡 STEP 1: BRIDGING DATA GAPS (Schwab API)...")
    for t in args.tickers:
        # Fetch 1m and 1h data
        if os.path.exists(FETCH_SCRIPT):
            run_command(["python", FETCH_SCRIPT, t, "--tf", "1m"])
            # 1h not supported by Schwab Minute API (max 30m)
        else:
            print(f"Warning: {FETCH_SCRIPT} not found. Skipping data fetch.")

    # 2. RUN CLASSIFICATION (HTF & Overnight)
    print("\n⚙️  STEP 2: UPDATING CLASSIFICATIONS...")
    if os.path.exists(PRECOMPUTE_SCRIPT):
         run_command(["python", PRECOMPUTE_SCRIPT, "--tickers"] + args.tickers)
    
    # 3. GENERATE ANALYSIS PER TICKER
    for t in args.tickers:
        print(f"\n\n🔶 ANALYSIS FOR {t} 🔶")
        print("-----------------------------")
        
        # A. ICT Context (Levels & HTF)
        print("\n🔎 ICT LEVELS (Liquidity & Validations):")
        ict_cmd = ["python", ICT_CONTEXT_SCRIPT, t]
        if args.next_day:
            ict_cmd.append("--next-day")
        run_command(ict_cmd)
        
        # B. Econ Calendar
        print("\n📅 ECONOMIC CALENDAR CHECK:")
        econ_script = os.path.join(SCRIPTS_DIR, "market_data", "fetch_economic_events.py")
        
        # Determine date for econ events
        # If args.next_day is set, we need to calculate tomorrow's date
        # But run_daily_prep doesn't calculate date itself easily without duplication logic.
        # However, fetch_economic_events defaults to TODAY.
        # Let's import datetime and calculate 'tomorrow' if needed.
        if args.next_day:
            tmr = datetime.now().date() + timedelta(days=1)
            # Skip weekend logic handled in ict context but here simple add is risky on Friday
            if tmr.weekday() == 5: tmr += timedelta(days=2)
            elif tmr.weekday() == 6: tmr += timedelta(days=1)
            target_date = tmr.strftime("%Y-%m-%d")
        else:
            target_date = datetime.now().strftime("%Y-%m-%d")
            
        run_command(["python", econ_script, "--date", target_date])
        
        # C. Profile Analysis (Weekly)
        print("\n📐 WEEKLY PROFILE CHECK:")
        prof_script = os.path.join(SCRIPTS_DIR, "analysis", "analyze_weekly_profile.py")
        run_command(["python", prof_script, t, "--date", target_date])
        
        # D. ICT Context Chart
        print("\n🎨 GENERATING ICT CHART:")
        chart_script = os.path.join(SCRIPTS_DIR, "analysis", "generate_ict_chart.py")
        chart_path = f"c:/Users/vinay/tvDownloadOHLC/data/analysis/charts/{t}_ict_context_{target_date}.png"
        run_command(["python", chart_script, t, "--date", target_date])
        
        # E. Upload Chart to Discord
        print("\n📤 UPLOADING TO DISCORD:")
        discord_script = os.path.join(SCRIPTS_DIR, "utils", "discord_notify.py")
        message = f"🛡️ Daily Bias Report: **{t}** | Target: {target_date}"
        run_command(["python", discord_script, "-c", "test_channel", "-m", message, "-f", chart_path])
        
        # F. Wargame Synthesis
        print("\n⚔️  WARGAME SCENARIO:")
        # We need Stats for this. Let's run retrieve_daily_stats blindly?
        # Ideally we parse the output of ICT Context to get "Overnight Context"
        # For now, we prompt the user or just show the Stats Tool usage.
        print("   To finalize your plan, determine the Overnight Sentiment (Bullish/Bearish) and run:")
        print(f"   > python scripts/trader/retrieve_daily_stats.py {t} --prev [YESTERDAY_TYPE] --overnight [SENTIMENT]")
        
    # 4. DATA INTEGRITY CHECK
    print("\n🔍 STEP 4: DATA INTEGRITY CHECK (Bootstrap Conflicts)...")
    conflict_script = os.path.join(SCRIPTS_DIR, "maintenance", "generate_conflict_report.py")
    if os.path.exists(conflict_script):
        run_command(["python", conflict_script, "--discord", "--channel", "data_gap_reports", "--clear"])
    else:
        print(f"Warning: {conflict_script} not found. Skipping integrity check.")

    # 5. NQSTATS ANALYSIS
    print("\n📈 STEP 5: NQSTATS STATISTICAL BIAS...")
    nqstats_script = os.path.join(SCRIPTS_DIR, "analysis", "analyze_daily_nqstats.py")
    if os.path.exists(nqstats_script):
        for t in args.tickers:
            print(f"\n[NQStats] Analyzing {t}...")
            # Run and notify Discord using the Data Gap reports channel
            run_command(["python", nqstats_script, "--ticker", t, "--discord", "--channel", "data_gap_reports"])
    else:
        print(f"Warning: {nqstats_script} not found. Skipping NQStats analysis.")

    print("\n==========================================")
    print("✅ PREP COMPLETE. GOOD LUCK.")
    print("==========================================")

if __name__ == "__main__":
    main()
