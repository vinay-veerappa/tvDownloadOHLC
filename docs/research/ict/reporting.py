import pandas as pd
import os
import sys

# Ensure we can import from local analysis
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analysis.pattern_distribution import analyze_pattern_distribution
from analysis.manipulation_reversal import analyze_reversal_structure
from analysis.hit_first_stats import analyze_hit_first_stats
from analysis.gap_confluence import analyze_gap_confluence
from analysis.level_hit_rates import analyze_level_hit_rates
from analysis.pda_performance import analyze_pda_performance
from analysis.simulated_trades import simulate_trades

# NEW Analysis Modules
from analysis.pm_manipulation import analyze_pm_manipulation
from analysis.cbdr_sigma_analysis import analyze_cbdr_sigma
from analysis.asia_prediction import analyze_asia_prediction
from analysis.pm_bias import analyze_pm_bias
from analysis.range_effects import analyze_range_effects
from analysis.timing_analysis import analyze_timing
from analysis.sweep_order_analysis import analyze_sweep_order
from analysis.dow_analysis import analyze_day_of_week
from analysis.comprehensive_levels import analyze_all_levels
from analysis.decision_tree import analyze_decision_tree
from analysis.first_strike import analyze_first_strike

def generate_report(ticker='NQ', data_dir='ict_research/data'):
    # Adjust path if running from root
    if not os.path.exists(data_dir):
        if os.path.exists(os.path.join('ict_research', 'data')):
            data_dir = os.path.join('ict_research', 'data')
            
    days_file = os.path.join(data_dir, f'trading_days_enhanced_{ticker}.csv')
    if not os.path.exists(days_file):
        print(f"Enhanced data not found, checking standard data...")
        days_file = os.path.join(data_dir, f'trading_days_{ticker}.csv')
    arrays_file = os.path.join(data_dir, f'pd_arrays_{ticker}.csv')
    
    if not os.path.exists(days_file):
        print(f"Data file not found at {days_file}. Run pipeline first.")
        return
        
    print(f"Loading data from {days_file}...")
    df_days = pd.read_csv(days_file, low_memory=False)
    df_arrays = pd.read_csv(arrays_file, low_memory=False) if os.path.exists(arrays_file) else pd.DataFrame()
    
    # Clean up boolean columns that might be objects
    bool_keywords = ['hit_', 'gap_fill_', 'reversed', 'first']
    for col in df_days.columns:
        # Exclude time columns from boolean conversion
        if any(k in col for k in bool_keywords) and \
           not col.endswith('_time') and not col.endswith('_at') and \
           df_days[col].dtype == 'object':
            # Handle potential string 'True'/'False'
            df_days[col] = df_days[col].astype(str).map({'True': True, 'False': False, 'nan': None, 'None': None})
            # Convert to numeric (float) for mean calculation, keeping NaNs
            # Although for analysis logic true/false is needed.
            # Some analysis needs bool, some needs mean.
            # mean() on bool works in pandas (True=1, False=0).
            # But None/NaN forces float (1.0/0.0).
            pass

    print("\n" + "="*50)
    print("ICT SESSION MODEL RESEARCH REPORT")
    print("="*50 + "\n")
    
    # Run Analyses (Existing)
    analyze_pattern_distribution(df_days)
    analyze_reversal_structure(df_days)
    analyze_hit_first_stats(df_days)
    analyze_gap_confluence(df_days)
    analyze_level_hit_rates(df_days)
    analyze_pda_performance(df_arrays)
    # simulate_trades(df_days, df_arrays)
    
    # Run Analyses (New)
    try:
        analyze_pm_manipulation(df_days)
        analyze_cbdr_sigma(df_days)
        analyze_asia_prediction(df_days)
        analyze_pm_bias(df_days)
        analyze_range_effects(df_days)
        analyze_timing(df_days)
        analyze_sweep_order(df_days)
        analyze_day_of_week(df_days)
        analyze_all_levels(df_days)
        analyze_decision_tree(df_days)
        analyze_first_strike(df_days)
    except Exception as e:
        print(f"\nError running new analysis modules: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*50)
    print("End of Report")
    print("="*50)

class Tee(object):
    def __init__(self, name, mode):
        self.file = open(name, mode)
        self.stdout = sys.stdout
        sys.stdout = self
        
    def __del__(self):
        sys.stdout = self.stdout
        self.file.close()
        
    def write(self, data):
        self.file.write(data)
        self.stdout.write(data)
        
    def flush(self):
        self.file.flush()
        self.stdout.flush()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Generate ICT research report.')
    parser.add_argument('--ticker', type=str, default='NQ', help='Ticker symbol (e.g. NQ, ES, CL)')
    
    args = parser.parse_args()
    
    # Setup report path
    report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports')
    if not os.path.exists(report_dir):
        os.makedirs(report_dir)
        
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(report_dir, f"report_{args.ticker}_{timestamp}.md")
    
    print(f"Generating report for {args.ticker}...")
    print(f"Saving to: {report_file}")
    
    # Capture output
    tee = Tee(report_file, 'w')
    
    # Write Markdown header to file only
    tee.file.write(f"# ICT Research Report: {args.ticker}\n")
    tee.file.write(f"Generated: {timestamp}\n\n")
    tee.file.write("```text\n")
    
    try:
        generate_report(ticker=args.ticker)
    finally:
        # Close Markdown block in file only
        tee.file.write("\n```\n")
        del tee # Restore stdout
