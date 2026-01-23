import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import argparse
import subprocess
from datetime import datetime, timedelta

# Script Paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")

FETCH_SCRIPT = os.path.join(SCRIPTS_DIR, "market_data", "fetch_schwab_data.py")
PRECOMPUTE_SCRIPT = os.path.join(SCRIPTS_DIR, "derived", "precompute_daily_classification.py")
ICT_CONTEXT_SCRIPT = os.path.join(SCRIPTS_DIR, "trader", "retrieve_ict_context.py")
STATS_SCRIPT = os.path.join(SCRIPTS_DIR, "trader", "retrieve_daily_stats.py")
GAP_SCRIPT = os.path.join(SCRIPTS_DIR, "trader", "generate_ict_nwog_ndog.py")

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
    parser.add_argument("--newsletter", action="store_true", help="Generate a consolidated daily newsletter")
    parser.add_argument("--discord", action="store_true", help="Send the final newsletter and charts to Discord")
    parser.add_argument("--channel", default="test_channel", help="Discord channel for notifications")
    args = parser.parse_args()

    print("==========================================")
    print(f"🛡️  DAILY WARGAME PREP: {datetime.now().strftime('%Y-%m-%d %H:%M')}  🛡️")
    if args.next_day:
        print("   (MODE: NEXT TRADING DAY / TOMORROW)")
    print("==========================================\n")

    # --- DATA ACQUISITION & ANALYSIS ---
    newsletter_content = []

    # 1. News Prep (Global for all tickers)
    if args.newsletter:
        tmr = datetime.now().date()
        if args.next_day:
            tmr += timedelta(days=1)
            if tmr.weekday() == 5: tmr += timedelta(days=2)
            elif tmr.weekday() == 6: tmr += timedelta(days=1)
        target_date = tmr.strftime("%Y-%m-%d")

        import scripts.market_data.fetch_economic_events as econ_module
        news_events = econ_module.fetch_events(target_date, print_output=False, us_only=True)
        
        news_section = [
            f"🗞️ **DAILY NEWSLETTER | {target_date}**",
            "---",
            "## 📅 ECONOMIC CALENDAR (US ONLY)",
        ]
        if news_events:
            for ev in news_events:
                news_section.append(f"- {ev}")
            
            # ICT News Analysis
            news_section.append("\n**ICT News Guidance**:")
            
            # Detect High Impact Events
            has_cpi = any("CPI" in ev.upper() for ev in news_events)
            has_fomc = any("FOMC" in ev.upper() or "FED" in ev.upper() or "INTEREST RATE" in ev.upper() for ev in news_events)
            has_nfp = any("NON-FARM PAYROLL" in ev.upper() or "NFP" in ev.upper() for ev in news_events)
            has_high = any("HIGH" in ev for ev in news_events)
            
            is_wednesday = tmr.weekday() == 2
            
            if has_fomc and is_wednesday:
                news_section.append("> 🛑 **FOMC WEDNESDAY**: ICT Rule: **NO TRADES TODAY**. Expect consolidation pre-news and extreme manipulation during the release. Protect your capital.")
            elif has_cpi or has_nfp or has_fomc:
                news_section.append(f"> ⚠️ **MAJOR EVENT DETECTED ({'CPI' if has_cpi else 'NFP' if has_nfp else 'FOMC'}):** ICT Rule: Avoid intraday trading before the 08:30 AM release. Volatility is unpredictable and designed to run stops. Wait 15-60 minutes post-release for the 'Recovery Setup'.")
            elif has_high:
                news_section.append("> 🔸 **High Impact News detected.** Expect heightened volatility. Mark 08:30 Open as a key pivot. Avoid trading the 08:35-09:20 'Manipulation Window'.")
            else:
                news_section.append("> ✅ Standard volatility expected. Technical levels (PDH/PDL/MidOpen) are likely to hold without news-driven overrides.")
        else:
            news_section.append("- No major economic events scheduled.")
        
        newsletter_content.append("\n".join(news_section))

    for t in args.tickers:
        print(f"\n\n🔶 ANALYSIS FOR {t} 🔶")
        print("-----------------------------")
        
        tmr = datetime.now().date()
        if args.next_day:
            tmr += timedelta(days=1)
            if tmr.weekday() == 5: tmr += timedelta(days=2)
            elif tmr.weekday() == 6: tmr += timedelta(days=1)
        target_date = tmr.strftime("%Y-%m-%d")

        # 0. Generate ICT Gaps (NWOG/NDOG) & RTH Gaps
        run_command(["python", GAP_SCRIPT, "--tickers", t, "--lookback", "365"])
        
        # 0.1 RTH Gaps (Break Stats)
        RTH_GAP_SCRIPT = os.path.join(SCRIPTS_DIR, "derived", "generate_rth_gaps.py")
        run_command(["python", RTH_GAP_SCRIPT, "--tickers", t])

        # A. ICT Context (Levels & HTF)
        import scripts.trader.retrieve_ict_context as ict_module
        ict_result = ict_module.main(t, args.next_day)
        ict_ctx = ict_result['context']
        ict_htf = ict_result['htf']
        
        # B. NQStats
        import scripts.analysis.analyze_daily_nqstats as nqstats_module
        orig_argv = sys.argv[:]
        sys.argv = ["analyze_daily_nqstats.py", "--ticker", t, "--date", target_date]
        nqstats_report, nqstats_result_data = nqstats_module.main()
        sys.argv = orig_argv

        # C. Classification Bias
        import scripts.analysis.analyze_daily_classification_bias as class_module
        orig_argv = sys.argv[:]
        sys.argv = ["analyze_daily_classification_bias.py", "--ticker", t, "--date", target_date]
        class_report, class_result_data = class_module.main()
        sys.argv = orig_argv

        if args.newsletter:
            # ALN Expansion Lookup
            ALN_EXPANSIONS = {
                "LPEU": "London Partially Engulfs Up",
                "LPED": "London Partially Engulfs Down",
                "LEA": "London Engulfs Asia",
                "AEL": "Asia Engulfs London"
            }
            
            # Section 1: ALN Stats (NQStats)
            aln_data = nqstats_result_data
            news_section = [
                f"\n## 📈 MARKET ANALYSIS: {t}",
                "---",
                "### 1️⃣ ALN STATS ANALYSIS (NQStats)",
                f"**Pattern**: **{aln_data['aln']}** ({ALN_EXPANSIONS.get(aln_data['aln'], '')})",
                f"**Reasoning**: {aln_data['reasoning']}",
                "\n**Statistical Claims**:"
            ]
            news_section.extend(aln_data['claims'])

            # Section 2: Daily Profiler Analysis
            # Load Profiler Stats
            profiler_stats = {}
            stats_path = f"c:/Users/vinay/tvDownloadOHLC/data/{t}_ny_levels_stats.json"
            if os.path.exists(stats_path):
                import json
                with open(stats_path, 'r') as f: profiler_stats = json.load(f)
            
            news_section.extend([
                "\n### 2️⃣ DAILY PROFILER ANALYSIS",
                f"**Asia/London Behavior Today**:",
                f"- London High/Low: `{aln_data['levels']['lh']:.2f}` / `{aln_data['levels']['ll']:.2f}`",
                f"- Session Status: `{aln_data['status']}` (vs P12)",
                "\n**Expected NY Outcomes (Historical probability)**:",
                f"- Average NY Expansion (MFE): `~{profiler_stats.get('bull_mfe_dist', {}).get('50', 0):.2f}%` Bulls | `~{profiler_stats.get('bear_mfe_dist', {}).get('50', 0):.2f}%` Bears",
                f"- HOD/LOD Timing: Likely between `{profiler_stats.get('median_peak_time_bull', '09:30')}` and `{profiler_stats.get('median_peak_time_bear', '09:30')}` EST."
            ])

            # Section 3: Daily Classification Analysis
            class_data = class_result_data
            news_section.extend([
                "\n### 3️⃣ DAILY CLASSIFICATION ANALYSIS",
                f"**Prev Day Type**: `{class_data['prior_type']}`",
                f"**Overnight Key**: `{class_data['overnight_key']}`",
                f"\n**Probabilities**:",
                f"- Sequential: " + " | ".join([f"{k}: `{v}%`" for k,v in class_data['sequential_probs'].items()]),
                f"- Overnight:  " + " | ".join([f"{k}: `{v}%`" for k,v in class_data['overnight_probs'].items()]),
                f"**Most Likely Outcome**: `{class_data['most_likely']}`"
            ])

            # Section 4: ICT Based Analysis
            ict_analysis = ict_result.get('ict_analysis', {})
            news_section.extend([
                "\n### 4️⃣ ICT BASED ANALYSIS",
                f"**HTF Context**: `{ict_htf['pwh'] or 0:.2f} (PWH)` / `{ict_htf['pwl'] or 0:.2f} (PWL)`" if ict_htf['pwh'] else "**HTF Context**: N/A"
            ])
            
            # Method 1-3 Confirmations
            if ict_analysis:
                if ict_analysis.get('method_1_pvh') != "Neutral":
                    news_section.append(f"- **Method 1 (Prev Day)**: {ict_analysis['method_1_pvh']}")
                if ict_analysis.get('method_2_midnight_london') != "Neutral":
                    news_section.append(f"- **Method 2 (Md-Ldn Range)**: {ict_analysis['method_2_midnight_london']}")
                if ict_analysis.get('method_3_london_confirmation') != "Neutral":
                    news_section.append(f"- **Method 3 (Ldn Confirm)**: {ict_analysis['method_3_london_confirmation']}")
                if ict_analysis.get('sweeps'):
                    news_section.append(f"- **Detected Sweeps**: {', '.join(ict_analysis['sweeps'])}")
                    
            news_section.extend([
                f"**Draw on Liquidity (DOL)**: **{'PDH' if 'BULL' in nqstats_report else 'PDL'}**",
                f"- Midnight Open: `{ict_ctx['Midnight_Open']:.2f}`" if ict_ctx['Midnight_Open'] else "- Midnight Open: `N/A`",
                f"- PDH/PDL: `{ict_ctx['PDH']:.2f}` / `{ict_ctx['PDL']:.2f}`" if ict_ctx['PDH'] else "- PDH/PDL: `N/A`"
            ])

            # Section 5: Key Levels of Liquidity (Weighted Probabilities)
            l_mid = aln_data['levels']['mid']
            l_high = aln_data['levels']['lh']
            l_low = aln_data['levels']['ll']
            
            # Target Calculation: Baseline Target = Session Open * (1 + MFE_pct)
            # We use aln_data['levels']['lh'] or 'll' if specific session data exists
            bull_target = l_high * (1 + (profiler_stats.get('bull_mfe_dist', {}).get('80', 0.5) / 100)) if l_high else None
            bear_target = l_low * (1 - (profiler_stats.get('bear_mfe_dist', {}).get('80', 0.5) / 100)) if l_low else None

            news_section.extend([
                "\n### 5️⃣ KEY LEVELS OF LIQUIDITY (Weighted Probabilities)",
                f"- **London Mid**: `{l_mid:.2f}`" if l_mid else "- **London Mid**: `N/A`",
                f"- **Exp. Bull Target (80%)**: `{bull_target:.2f}`" if bull_target else "- **Exp. Bull Target**: `N/A` (80% confidence level)",
                f"- **Exp. Bear Target (80%)**: `{bear_target:.2f}`" if bear_target else "- **Exp. Bear Target**: `N/A` (80% confidence level)",
                f"- **HTF Range**: {ict_htf['pwh']:.2f} - {ict_htf['pwl']:.2f}" if ict_htf['pwh'] else "- **HTF Range**: `N/A`"
            ])

            # Final Unified Analysis
            is_r2 = class_data['most_likely'] == 'R2'
            confluence = "High Confluence" if (('BULL' in aln_data['bias'] and is_r2) or ('BEAR' in aln_data['bias'] and not is_r2)) else "Mixed Signals"
            
            news_section.extend([
                "\n### 🎯 FINAL UNIFIED ANALYSIS & GAME PLAN",
                f"**Final Bias**: `{aln_data['bias']}` | **Conviction**: `{aln_data['conviction']}`",
                f"**Confluence**: {confluence} (NQStats: `{aln_data['aln']}` | Class: `{class_data['most_likely']}`)",
                f"**Logic**: {aln_data['reasoning']}. Classification confirms `{class_data['most_likely']}` logic applies.",
                "**Action Plan**:",
                f"- [ ] **Bias**: {aln_data['action']}",
                "- [ ] **Open (09:30)**: Watch Opening Range relative to Midnight Open.",
                "- [ ] **Judas Sweep**: Wait for London High/Low sweep before entry.",
                "- [ ] **Macro (09:50-10:10)**: Look for MSS + FVG displacement.",
                "- [ ] **Targets**: Aim for Baseline MFE targets (Section 5).",
                "\n---"
            ])
            
            newsletter_content.append("\n".join(news_section))

        # D. Chart Generation (Still run these to have files ready)
        chart_script = os.path.join(SCRIPTS_DIR, "analysis", "generate_ict_chart.py")
        run_command(["python", chart_script, t, "--date", target_date])

    # --- FINAL OUTPUT ---
    if args.newsletter:
        final_newsletter = "\n\n".join(newsletter_content)
        print("\n" + "="*60)
        print("📜 FINAL NEWSLETTER PREVIEW")
        print("="*60 + "\n")
        print(final_newsletter)
        print("\n" + "="*60)

        if args.discord:
            from scripts.utils.discord_notify import get_webhook_url, send_message
            webhook_url = get_webhook_url(args.channel)
            if webhook_url:
                send_message(webhook_url, final_newsletter)
                
                # After newsletter, send charts
                for t in args.tickers:
                    chart_path = f"c:/Users/vinay/tvDownloadOHLC/data/analysis/charts/{t}_ict_context_{target_date}.png"
                    if os.path.exists(chart_path):
                        from scripts.utils.discord_notify import upload_file
                        upload_file(webhook_url, chart_path, f"📈 ICT Chart: {t}")
            else:
                print(f"❌ Discord Error: Channel '{args.channel}' not found.")

    print("\n==========================================")
    print("✅ PREP COMPLETE. GOOD LUCK.")
    print("==========================================")

if __name__ == "__main__":
    main()
