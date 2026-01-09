import pandas as pd
import json
import glob
import os
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import argparse
import sys

def analyze():
    # 0. Parse Arguments
    parser = argparse.ArgumentParser(description='Analyze Retest Logic with Filters')
    parser.add_argument('--start', type=str, help='Start Date YYYY-MM-DD', default=None)
    parser.add_argument('--end', type=str, help='End Date YYYY-MM-DD', default=None)
    
    if sys.argv[0].endswith('analyze_retest_stats.py'):
        args = parser.parse_args()
    else:
        args = parser.parse_args([])

    # Configuration
    strategies_dir = "docs/strategies/9_30_breakout/0930_AllDay"
    reports_dir = f"{strategies_dir}/reports"
    os.makedirs(reports_dir, exist_ok=True)
    
    # 1. Load Data
    jsonl_files = glob.glob("data/derived/retests/or_retests_*.jsonl")
    
    summary_report = []
    summary_report.append("# OR Retest Strategy - Executive Summary")
    summary_report.append(f"**Generated**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
    
    range_str = "Full History"
    if args.start: range_str = f"From {args.start}"
    if args.end: range_str += f" To {args.end}"
    summary_report.append(f"**Date Range**: {range_str}")
    
    summary_report.append("")
    summary_report.append("| Ticker | Win Rate | Hourly Consistency | Top Time |")
    summary_report.append("| :--- | :--- | :--- | :--- |")

    for f in jsonl_files:
        try:
            # Parse Ticker
            base = os.path.basename(f)
            t_part = base.replace("or_retests_", "").replace(".jsonl", "")
            t = t_part.replace(".parquet", "") 
            
            print(f"Analyzing {t}...")
            
            # Load Data
            retests_list = []
            with open(f, 'r') as file:
                for line in file:
                    try:
                        row = json.loads(line)
                        if 'retests' not in row or not row['retests']: continue
                            
                        # Find First Valid Retest (Filter > 0.5 Disp)
                        first_valid = None
                        for rt in row['retests']:
                            if 'pre_retest_fam_norm' in rt:
                                if rt['pre_retest_fam_norm'] >= 0.5:
                                    first_valid = rt
                                    break
                            else:
                                first_valid = rt
                                break
                        
                        if not first_valid: continue
                            
                        # Extract Fields
                        r = first_valid
                        r['date'] = row['date']
                        r['start_time'] = r.get('retest_time', r.get('start_time', '00:00'))
                        r['breakout_dir'] = row.get('breakout_dir', '')
                        r['or_height'] = row.get('or_height', 1.0)
                        
                        # Backfill Metrics - Use PCT (Price Percentage)
                        if 'excursion_mfe_pct' not in r: r['excursion_mfe_pct'] = 0.0
                        if 'excursion_mae_pct' not in r: r['excursion_mae_pct'] = 0.0
                        
                        if 'is_failure' not in r:
                            # Failure if MAE exceeded entry significantly
                            mae_pct = r.get('excursion_mae_pct', 0.0)
                            r['is_failure'] = mae_pct >= 1.0  # 1% adverse move = stopped out
                         
                        retests_list.append(r)
                            
                    except Exception as e:
                        continue
            
            if not retests_list:
                print(f"Skipping {t} (No valid events)")
                continue
                
            rdf = pd.DataFrame(retests_list)
            
            # --- APPLY DATE FILTER ---
            if args.start: rdf = rdf[rdf['date'] >= args.start]
            if args.end: rdf = rdf[rdf['date'] <= args.end]
            
            if len(rdf) == 0:
                print(f"Skipping {t} (No events in date range)")
                continue

            # CLEAN DATA (Fix inf/nan)
            cols_to_clean = ['excursion_mae_pct', 'excursion_mfe_pct']
            rdf[cols_to_clean] = rdf[cols_to_clean].replace([np.inf, -np.inf], np.nan)
            rdf['excursion_mae_pct'] = rdf['excursion_mae_pct'].fillna(0.0)
            rdf['excursion_mfe_pct'] = rdf['excursion_mfe_pct'].fillna(0.0)

            # Time Extraction
            rdf['hour_val'] = rdf['start_time'].astype(str).apply(lambda x: int(x.split(':')[0]) if ':' in x else 0)
            rdf['minute_val'] = rdf['start_time'].astype(str).apply(lambda x: int(x.split(':')[1]) if ':' in x else 0)
            rdf['min_bucket'] = (rdf['minute_val'] // 5) * 5
            
            # --- GENERATE INDIVIDUAL REPORT ---
            repo = []
            repo.append(f"# {t} - Retest Forensics Report")
            repo.append(f"**Date Range**: {range_str}")
            repo.append(f"**Total Events Analyzed**: {len(rdf)}")
            repo.append(f"**Filter**: Pre-Retest Displacement > 0.5x OR Height (Chop Removed)")
            repo.append("")
            
            # Global Stats
            success_events = rdf[rdf['is_failure'] == False]
            win_rate = (len(success_events) / (len(rdf) if len(rdf)>0 else 1)) * 100
            
            avg_mfe = rdf['excursion_mfe_pct'].mean()
            avg_mae = rdf['excursion_mae_pct'].mean()

            repo.append("## Executive Summary")
            repo.append(f"- **Win Rate**: **{win_rate:.1f}%**")
            repo.append(f"- **Avg Reward (MFE)**: {avg_mfe:.2f}%")
            repo.append(f"- **Avg Risk (MAE)**: {avg_mae:.2f}%")
            repo.append("")

            # GLOBAL DISTRIBUTION CHARTS (Price %)
            # Bins for percentage: MAE 0-1% step 0.05, MFE 0-3% step 0.1
            mae_bins = np.arange(0, 1.55, 0.05)
            mfe_bins = np.arange(0, 3.1, 0.1)

            fig_g, (ax1_g, ax2_g) = plt.subplots(1, 2, figsize=(14, 5))
            
            # Global MAE (Price %)
            mae_vals = rdf['excursion_mae_pct'].abs()
            ax1_g.hist(mae_vals, bins=mae_bins, color='orange', alpha=0.7, edgecolor='black')
            ax1_g.set_title(f"Global Risk (MAE) - Price % Distribution")
            ax1_g.set_xlabel("Price % (Adverse Move)")
            ax1_g.set_ylabel("Frequency")
            ax1_g.axvline(mae_vals.median(), color='red', linestyle='--', label=f'Median {mae_vals.median():.2f}%')
            ax1_g.legend()
            
            # Global MFE (Price %)
            mfe_vals = rdf['excursion_mfe_pct']
            ax2_g.hist(mfe_vals, bins=mfe_bins, color='blue', alpha=0.7, edgecolor='black')
            ax2_g.set_title(f"Global Reward (MFE) - Price % Distribution")
            ax2_g.set_xlabel("Price % (Favorable Move)")
            ax2_g.axvline(mfe_vals.median(), color='green', linestyle='--', label=f'Median {mfe_vals.median():.2f}%')
            ax2_g.legend()

            global_dist_file = f"{t}_global_risk_reward.png"
            plt.tight_layout()
            plt.savefig(f"{reports_dir}/{global_dist_file}")
            plt.close()
            
            repo.append("## Global Risk/Reward Distribution (Price %)")
            repo.append(f"![Global Charts]({global_dist_file})")
            repo.append("")

            # --- HOURLY BREAKDOWN LOOP ---
            repo.append("## Hourly Breakdown")
            
            for h in range(9, 17):
                hour_df = rdf[rdf['hour_val'] == h].copy()
                
                if len(hour_df) == 0:
                    continue
                    
                repo.append(f"### Hour {h:02d}:00 - {h:02d}:59")
                
                # Stats for this hour
                h_wins = len(hour_df[hour_df['is_failure'] == False])
                h_wr = (h_wins / len(hour_df)) * 100
                repo.append(f"**Volume**: {len(hour_df)} | **Win Rate**: {h_wr:.1f}%")
                
                h_mfe = hour_df['excursion_mfe_pct']
                h_mae = hour_df['excursion_mae_pct'].abs()
                
                # Percentile Stats (Price %)
                repo.append("")
                repo.append("| Metric | Median | p75 | p90 | Max |")
                repo.append("| :--- | :--- | :--- | :--- | :--- |")
                repo.append(f"| **Reward (MFE)** | {h_mfe.median():.2f}% | {h_mfe.quantile(0.75):.2f}% | {h_mfe.quantile(0.90):.2f}% | {h_mfe.max():.2f}% |")
                repo.append(f"| **Risk (MAE)** | {h_mae.median():.2f}% | {h_mae.quantile(0.75):.2f}% | {h_mae.quantile(0.90):.2f}% | {h_mae.max():.2f}% |")
                repo.append("")

                # --- CHART 1: Time Scatter Plot (Price % vs Minute) ---
                plt.figure(figsize=(10, 5))
                plt.scatter(hour_df['minute_val'], h_mfe, color='green', alpha=0.5, s=20, label='Reward (MFE %)')
                plt.scatter(hour_df['minute_val'], -h_mae, color='red', alpha=0.5, s=20, label='Risk (-MAE %)')
                
                plt.axhline(0, color='black', linewidth=1)
                
                plt.title(f"{t} - {h:02d}:00 Risk/Reward vs Time (Price %)")
                plt.xlabel("Minute of Hour (0-59)")
                plt.ylabel("Price % Change")
                plt.legend()
                plt.grid(True, alpha=0.3)
                plt.xlim(-1, 60)
                plt.tight_layout()
                
                scatter_chart = f"{t}_{h:02d}00_scatter.png"
                plt.savefig(f"{reports_dir}/{scatter_chart}")
                plt.close()

                # --- CHART 2: Bidirectional Time Distribution (Wins vs Losses) ---
                chart_buckets = {}
                for m in range(0, 60):
                    chart_buckets[m] = {'success': 0, 'fail': 0}
                    
                for idx, row in hour_df.iterrows():
                    m = int(row['minute_val'])
                    if m in chart_buckets:
                        if row['is_failure']: chart_buckets[m]['fail'] += 1
                        else: chart_buckets[m]['success'] += 1
                        
                minutes = sorted(chart_buckets.keys())
                success_vals = [chart_buckets[m]['success'] for m in minutes]
                fail_vals = [-chart_buckets[m]['fail'] for m in minutes]
                
                plt.figure(figsize=(10, 3))
                plt.bar(minutes, success_vals, color='green', alpha=0.7, label='Wins')
                plt.bar(minutes, fail_vals, color='red', alpha=0.7, label='Losses')
                plt.axhline(0, color='black', linewidth=0.8)
                plt.xlabel("Minute (0-59)")
                plt.ylabel("Frequency")
                plt.title(f"{t} - {h:02d}:00 Win/Loss Distribution")
                plt.grid(axis='y', alpha=0.3, linestyle='--')
                plt.xlim(-1, 60)
                plt.legend(loc='upper right', fontsize='small')
                plt.tight_layout()
                
                time_chart = f"{t}_{h:02d}00_time.png"
                plt.savefig(f"{reports_dir}/{time_chart}")
                plt.close()

                # --- CHART 3: Granular Histograms (Price %) ---
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
                
                # MAE Hist (Risk %)
                ax1.hist(h_mae, bins=mae_bins, color='orange', alpha=0.7, edgecolor='black')
                ax1.set_title(f"Risk Profile (MAE %)")
                ax1.set_xlabel("Price % (Adverse)")
                ax1.axvline(h_mae.median(), color='red', linestyle='--', linewidth=1, label=f'Median: {h_mae.median():.2f}%')
                ax1.legend()
                ax1.grid(axis='y', alpha=0.3)
                
                # MFE Hist (Reward %)
                ax2.hist(h_mfe, bins=mfe_bins, color='blue', alpha=0.7, edgecolor='black')
                ax2.set_title(f"Reward Profile (MFE %)")
                ax2.set_xlabel("Price % (Favorable)")
                ax2.axvline(h_mfe.median(), color='green', linestyle='--', linewidth=1, label=f'Median: {h_mfe.median():.2f}%')
                ax2.legend()
                ax2.grid(axis='y', alpha=0.3)
                
                plt.tight_layout()
                hist_chart = f"{t}_{h:02d}00_hist.png"
                plt.savefig(f"{reports_dir}/{hist_chart}")
                plt.close()
                
                # Report Embed
                repo.append(f"![Time Scatter]({scatter_chart})")
                repo.append(f"![Win/Loss Dist]({time_chart})")
                repo.append(f"![Price % Hist]({hist_chart})")
                repo.append("")

                # BUCKET ANALYSIS
                bucket_groups = hour_df.groupby('min_bucket')
                b_stats = []
                for b, g in bucket_groups:
                    cnt = len(g)
                    if cnt < 3: continue 
                    wins = len(g[g['is_failure'] == False])
                    wr = (wins/cnt)*100
                    b_stats.append({'b': b, 'wr': wr, 'w': wins, 'l': cnt-wins})
                
                # BEST Windows
                repo.append("**Best 5-Min Windows (High WR)**")
                repo.append("| Minute Bucket | Win Rate | Wins | Losses |")
                repo.append("| :--- | :--- | :--- | :--- |")
                b_stats.sort(key=lambda x: x['wr'], reverse=True)
                for item in b_stats[:5]:
                    status = "💎" if item['wr'] >= 85 else ""
                    repo.append(f"| {h:02d}:{item['b']:02d} | **{item['wr']:.1f}%** {status} | {item['w']} | {item['l']} |")
                repo.append("")

                # WORST Windows
                repo.append("**Worst 5-Min Windows (Avoid)**")
                repo.append("| Minute Bucket | Win Rate | Wins | Losses |")
                repo.append("| :--- | :--- | :--- | :--- |")
                b_stats.sort(key=lambda x: x['wr'], reverse=False)
                for item in b_stats[:5]:
                    status = "⚠️" if item['wr'] <= 60 else ""
                    repo.append(f"| {h:02d}:{item['b']:02d} | **{item['wr']:.1f}%** {status} | {item['w']} | {item['l']} |")
                repo.append("")
                
                repo.append("---")
                repo.append("")
            
            with open(f"{reports_dir}/{t}_Retest_Forensics.md", "w", encoding='utf-8') as f_out:
                f_out.write("\n".join(repo))
                
            summary_report.append(f"| [{t}]({t}_Retest_Forensics.md) | {win_rate:.1f}% | See Report |")

        except Exception as e:
            print(f"Error analyzing {f}: {e}")
            continue

    with open(f"{reports_dir}/README_Summary.md", "w", encoding='utf-8') as f_sum:
        f_sum.write("\n".join(summary_report))

    print(f"Analysis Complete. Reports generated in {reports_dir}")

if __name__ == "__main__":
    analyze()
