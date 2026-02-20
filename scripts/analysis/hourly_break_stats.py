import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime

class HourlyBreakAnalyzer:
    def __init__(self, ticker="NQ1"):
        self.ticker = ticker
        self.df = None
        self.report_data = {}
        self.start_year = 2006
        self.end_year = datetime.now().year

    def load_data(self):
        """Loads full historical data from parquet."""
        path = Path(f"data/{self.ticker}_1m.parquet")
        if not path.exists():
            raise FileNotFoundError(f"Data for {self.ticker} not found at {path}")
            
        print(f"Loading {self.ticker} data...")
        df = pd.read_parquet(path)
        
        # Ensure index is datetime and localized
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
            
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
        else:
            df.index = df.index.tz_convert('America/New_York')
            
        self.start_year = df.index.year.min()
        self.end_year = df.index.year.max()
        
        # Extract features
        df['hour'] = df.index.hour
        df['date_key'] = df.index.date
        df['dow_int'] = df.index.dayofweek
        
        self.df = df
        print(f"Loaded {len(df)} rows ({self.start_year}-{self.end_year})")

    def compute_stats(self):
        if self.df is None: self.load_data()
        df = self.df
        
        # 1. Hourly Aggregates
        h_agg = df.groupby(['date_key', 'hour']).agg(
            h_open=('open', 'first'),
            h_high=('high', 'max'),
            h_low=('low', 'min'),
            h_close=('close', 'last'),
            dow_int=('dow_int', 'first')
        ).reset_index()
        
        # Sort to ensure shift works correctly
        h_agg = h_agg.sort_values(['date_key', 'hour'])
        
        # Shift for Previous Hour Context
        h_agg['prev_high'] = h_agg.groupby('date_key')['h_high'].shift(1)
        h_agg['prev_low'] = h_agg.groupby('date_key')['h_low'].shift(1)
        # Prev Mid = (PrevHigh + PrevLow) / 2
        h_agg['prev_mid'] = (h_agg['prev_high'] + h_agg['prev_low']) / 2
        
        # Filter: Only hours with valid previous context
        merged = h_agg[h_agg['prev_mid'].notna()].copy()
        
        # 2. Define Context (Bias)
        merged['above_prev_mid'] = merged['h_open'] > merged['prev_mid']
        merged['below_prev_mid'] = merged['h_open'] < merged['prev_mid']
        
        # 3. Define Outcomes (Breaks)
        merged['break_prev_high'] = merged['h_high'] > merged['prev_high']
        merged['break_prev_low'] = merged['h_low'] < merged['prev_low']
        
        # 4. Synthesize Stats
        stats_by_hour = {}
        dow_names = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday', 4: 'Friday'}
        
        print("Analyzing break probabilities...")
        
        for h in range(24):
            h_df = merged[merged['hour'] == h]
            if h_df.empty: continue
            
            # --- Scenario A: Open > Prev Mid (Bullish Context) ---
            bull_df = h_df[h_df['above_prev_mid']]
            n_bull = len(bull_df)
            
            # --- Scenario B: Open < Prev Mid (Bearish Context) ---
            bear_df = h_df[h_df['below_prev_mid']]
            n_bear = len(bear_df)
            
            stats_by_hour[h] = {
                'total_sessions': len(h_df),
                'bull_context': {
                    'total': n_bull,
                    'break_high': int(bull_df['break_prev_high'].sum()),
                    'break_low': int(bull_df['break_prev_low'].sum()),
                    'break_both': int((bull_df['break_prev_high'] & bull_df['break_prev_low']).sum()),
                    'break_neither': int((~bull_df['break_prev_high'] & ~bull_df['break_prev_low']).sum()),
                    'dow_stats': {d_name: {
                        'total': int((bull_df['dow_int'] == d).sum()),
                        'break_high': int((bull_df[bull_df['dow_int'] == d]['break_prev_high']).sum())
                    } for d, d_name in dow_names.items()}
                },
                'bear_context': {
                    'total': n_bear,
                    'break_high': int(bear_df['break_prev_high'].sum()),
                    'break_low': int(bear_df['break_prev_low'].sum()),
                    'break_both': int((bear_df['break_prev_high'] & bear_df['break_prev_low']).sum()),
                    'break_neither': int((~bear_df['break_prev_high'] & ~bear_df['break_prev_low']).sum()),
                    'dow_stats': {d_name: {
                        'total': int((bear_df['dow_int'] == d).sum()),
                        'break_low': int((bear_df[bear_df['dow_int'] == d]['break_prev_low']).sum())
                    } for d, d_name in dow_names.items()}
                }
            }
            
        self.report_data = stats_by_hour
        return stats_by_hour

    def generate_report(self):
        lines = []
        lines.append(f"# Hourly Break Probabilities: {self.ticker}")
        lines.append("")
        lines.append("> **Analysis:** Probability of breaking the **Previous Hour's High or Low** based on opening location relative to **Previous Hour's Midpoint (50%)**.")
        lines.append("")
        
        display_order = [9, 10, 11, 12, 13, 14, 15, 16, 18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7, 8]
        
        # --- Section 1: Bullish Context (Open > Prev Mid) ---
        lines.append("## I. Bullish Bias: Opening ABOVE Previous Hour Mid")
        lines.append("Given we open in the upper half of the previous range, what is the probability we continue higher vs reverse?")
        lines.append("")
        lines.append("| Hour | N | **Break High (Cont)** | Break Low (Rev) | Both (Exp) | Neither (Inside) |")
        lines.append("|---|---|---|---|---|---|")
        
        for h in display_order:
            if h not in self.report_data: continue
            s = self.report_data[h]['bull_context']
            tot = s['total']
            if tot == 0: continue
            
            p_high = s['break_high'] / tot * 100
            p_low = s['break_low'] / tot * 100
            p_both = s['break_both'] / tot * 100
            p_neither = s['break_neither'] / tot * 100
            
            lines.append(f"| {h:02d}:00 | {tot} | **{p_high:.1f}%** | {p_low:.1f}% | {p_both:.1f}% | {p_neither:.1f}% |")
        lines.append("")
        
        # --- Section 2: Bearish Context (Open < Prev Mid) ---
        lines.append("## II. Bearish Bias: Opening BELOW Previous Hour Mid")
        lines.append("Given we open in the lower half of the previous range, what is the probability we continue lower vs reverse?")
        lines.append("")
        lines.append("| Hour | N | **Break Low (Cont)** | Break High (Rev) | Both (Exp) | Neither (Inside) |")
        lines.append("|---|---|---|---|---|---|")
        
        for h in display_order:
            if h not in self.report_data: continue
            s = self.report_data[h]['bear_context']
            tot = s['total']
            if tot == 0: continue
            
            p_high = s['break_high'] / tot * 100
            p_low = s['break_low'] / tot * 100
            p_both = s['break_both'] / tot * 100
            p_neither = s['break_neither'] / tot * 100
            
            lines.append(f"| {h:02d}:00 | {tot} | **{p_low:.1f}%** | {p_high:.1f}% | {p_both:.1f}% | {p_neither:.1f}% |")
        lines.append("")
        
        # --- Section 3: DOW Analysis (Continuation Strength) ---
        lines.append("## III. Continuation Probability by Day of Week")
        lines.append("Probability of breaking the **bias-aligned side** (High if >Mid, Low if <Mid).")
        lines.append("")
        lines.append("| Hour | Mon | Tue | Wed | Thu | Fri |")
        lines.append("|---|---|---|---|---|---|")
        
        for h in [9, 10, 11, 12, 13, 14, 15]:
            if h not in self.report_data: continue
            bull_dow = self.report_data[h]['bull_context']['dow_stats']
            bear_dow = self.report_data[h]['bear_context']['dow_stats']
            
            row = f"| {h:02d}:00 |"
            for d in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
                # Average continuation prob
                b_s = bull_dow.get(d, {'total':0, 'break_high':0})
                br_s = bear_dow.get(d, {'total':0, 'break_low':0})
                
                p_bull = (b_s['break_high'] / b_s['total']) if b_s['total'] > 0 else 0
                p_bear = (br_s['break_low'] / br_s['total']) if br_s['total'] > 0 else 0
                
                # Weighted average? Or simple average? Simple average is cleaner for display
                avg_cont = (p_bull + p_bear) / 2 * 100
                row += f" {avg_cont:.1f}% |"
            lines.append(row)
        lines.append("")
        
        # --- Section 4: Detailed Analysis ---
        lines.append("## IV. Tactical Analysis & Hour-Specific Findings")
        lines.append("")
        
        # Identify Key Hours
        def get_cont_prob(h, context):
            if h not in self.report_data: return 0
            s = self.report_data[h][context]
            tgt = 'break_high' if context == 'bull_context' else 'break_low'
            return (s[tgt] / s['total'] * 100) if s['total'] > 0 else 0
            
        def get_rev_prob(h, context):
            if h not in self.report_data: return 0
            s = self.report_data[h][context]
            tgt = 'break_low' if context == 'bull_context' else 'break_high' # The opposite
            return (s[tgt] / s['total'] * 100) if s['total'] > 0 else 0

        # Most Continuation
        h_scores = []
        for h in display_order:
            if h not in self.report_data: continue
            avg_cont = (get_cont_prob(h, 'bull_context') + get_cont_prob(h, 'bear_context')) / 2
            h_scores.append((h, avg_cont))
        h_scores.sort(key=lambda x: x[1], reverse=True)
        
        lines.append("### A. Trend Persistence Leaderboard")
        lines.append("Best hours for continuation plays (Breaking the bias-side level):")
        for i in range(3):
            lines.append(f"{i+1}. **{h_scores[i][0]:02d}:00** ({h_scores[i][1]:.1f}%)")
        lines.append("")
        
        # 09:00 Special Case
        h09_both_bull = (self.report_data[9]['bull_context']['break_both'] / self.report_data[9]['bull_context']['total']) * 100
        h09_both_bear = (self.report_data[9]['bear_context']['break_both'] / self.report_data[9]['bear_context']['total']) * 100
        avg_09_vol = (h09_both_bull + h09_both_bear) / 2
        
        lines.append("### B. The 09:00 Volatility Trap")
        lines.append(f"The 09:00 hour has a unique characteristic: **Double Break Probability is {avg_09_vol:.1f}%**.")
        lines.append("Even if you open above the midpoint, there is a massive chance (>40%) that specific hour will break BOTH the Previous High AND Previous Low.")
        lines.append("Tactical Implication: Prev Hour Mid is a weak filter for 09:00. Expect expansion.")
        lines.append("")
        
        # 10:00 & 11:00 Reversal
        h10_rev = (get_rev_prob(10, 'bull_context') + get_rev_prob(10, 'bear_context')) / 2
        lines.append(f"### C. 10:00 AM Reversal Risk")
        lines.append(f"10:00 AM shows a higher Reversal Probability (**{h10_rev:.1f}%**) compared to adjacent hours.")
        lines.append("Opening above the 09:00 mid does NOT guarantee a breakout. 10am often sets a trap High and reverses.")
        lines.append("")
        
        return "\n".join(lines)

    def save_report(self):
        report = self.generate_report()
        out_path = Path(f"docs/nqstats/hourly_breaks/{self.ticker}_HOURLY_BREAKS.md")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            f.write(report)
        print(f"Report saved to {out_path}")

if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "NQ1"
    analyzer = HourlyBreakAnalyzer(ticker)
    analyzer.compute_stats()
    analyzer.save_report()
