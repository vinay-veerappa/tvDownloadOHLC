import os
import sys
import argparse
import subprocess
from datetime import datetime

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
    args = parser.parse_args()

    print("==========================================")
    print(f"🛡️  DAILY WARGAME PREP: {datetime.now().strftime('%Y-%m-%d %H:%M')}  🛡️")
    print("==========================================\n")

    # 1. BRIDGE THE GAP (Data Acquisition)
    print("📡 STEP 1: BRIDGING DATA GAPS (Schwab API)...")
    for t in args.tickers:
        # Fetch 1m and 1h data
        # Check if fetch script exists (it should, we just made it)
        if os.path.exists(FETCH_SCRIPT):
            run_command(["python", FETCH_SCRIPT, t, "--tf", "1m"])
            run_command(["python", FETCH_SCRIPT, t, "--tf", "1h"])
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
        
        # A. ICT Context (Levels)
        print("\n🔎 ICT LEVELS (Liquidity & Validations):")
        run_command(["python", ICT_CONTEXT_SCRIPT, t])
        
        # B. Econ Calendar (Placeholder)
        print("\n📅 ECONOMIC CALENDAR CHECK:")
        print("   [TODO: Integrate external calendar source]")
        print("   - Check: High Impact News at 08:30 / 10:00 / 14:00?")
        
        # C. Profile Analysis (Placeholder)
        print("\n📐 PROFILE CHECK (Weekly/Daily):")
        print("   [TODO: Implement analyze_profiles.py]")
        weekday = datetime.now().strftime('%A')
        print(f"   - Current Day: {weekday}")
        print("   - Weekly Profile Idea: 'Classic Tuesday Low of Week'?")
        
        # D. Wargame Synthesis
        print("\n⚔️  WARGAME SCENARIO:")
        # We need Stats for this. Let's run retrieve_daily_stats blindly?
        # Ideally we parse the output of ICT Context to get "Overnight Context"
        # For now, we prompt the user or just show the Stats Tool usage.
        print("   To finalize your plan, determine the Overnight Sentiment (Bullish/Bearish) and run:")
        print(f"   > python scripts/trader/retrieve_daily_stats.py {t} --prev [YESTERDAY_TYPE] --overnight [SENTIMENT]")
        
    print("\n==========================================")
    print("✅ PREP COMPLETE. GOOD LUCK.")
    print("==========================================")

if __name__ == "__main__":
    main()
