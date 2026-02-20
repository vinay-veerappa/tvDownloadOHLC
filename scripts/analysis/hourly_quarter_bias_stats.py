import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime

class HourlyQuarterContextAnalyzer:
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
        df['minute'] = df.index.minute
        df['date_key'] = df.index.date
        df['dow_int'] = df.index.dayofweek
        
        self.df = df
        print(f"Loaded {len(df)} rows ({self.start_year}-{self.end_year})")

    def compute_stats(self):
        """Compute stats including previous hour mid-point bias."""
        if self.df is None: self.load_data()
        df = self.df
        
        # 1. Hourly Aggregates (to get Prev Hour Mid)
        h_agg = df.groupby(['date_key', 'hour']).agg(
            h_open=('open', 'first'),
            h_high=('high', 'max'),
            h_low=('low', 'min'),
            h_close=('close', 'last'),
            dow_int=('dow_int', 'first')
        ).reset_index()
        
        # Calculate Mid for current
        h_agg['h_mid'] = (h_agg['h_high'] + h_agg['h_low']) / 2
        
        # Create a shifted version for "Previous Hour" same-day context
        # We need to be careful with session transitions, but for now simple shift within the sorted group
        h_agg = h_agg.sort_values(['date_key', 'hour'])
        h_agg['prev_mid'] = h_agg.groupby('date_key')['h_mid'].shift(1)
        h_agg['prev_high'] = h_agg.groupby('date_key')['h_high'].shift(1)
        h_agg['prev_low'] = h_agg.groupby('date_key')['h_low'].shift(1)
        
        # 2. Assign Quarters
        work_df = df[['hour', 'minute', 'date_key', 'high', 'low', 'open', 'close']].copy()
        work_df['q_int'] = work_df['minute'] // 15
        
        # Quarter boundaries
        q_agg = work_df.groupby(['date_key', 'hour', 'q_int']).agg(
            q_high=('high', 'max'),
            q_low=('low', 'min')
        ).reset_index()
        
        # Pivot quarters
        q_pivot = q_agg.pivot(index=['date_key', 'hour'], columns='q_int', values=['q_high', 'q_low'])
        q_pivot.columns = [f"{col[0]}_Q{col[1]+1}" for col in q_pivot.columns]
        q_pivot = q_pivot.reset_index()
        
        # 3. Final Join
        merged = h_agg.merge(q_pivot, on=['date_key', 'hour'], how='left')
        merged = merged[merged['prev_mid'].notna()].copy() # Only keep sessions with prev hour context
        
        # 4. Scenario logic
        
        # Scenario 1: Q1 High / Q4 Low (Clean Bearish Trend)
        # Conditioned on Bias: Prev Mid > Curr Open
        merged['is_q1h_q4l'] = (merged['q_high_Q1'] == merged['h_high']) & (merged['q_low_Q4'] == merged['h_low'])
        
        # Scenario 2: Q1 Low / Q4 High (Clean Bullish Trend)
        # Conditioned on Bias: Prev Mid < Curr Open
        merged['is_q1l_q4h'] = (merged['q_low_Q1'] == merged['h_low']) & (merged['q_high_Q4'] == merged['h_high'])
        
        # Scenario 3: Q2/Q3 sets High, but Close < Prev Mid
        # (This implies a rally that fails to recover the previous hour's midpoint)
        merged['q2_or_q3_high'] = (merged['q_high_Q2'] == merged['h_high']) | (merged['q_high_Q3'] == merged['h_high'])
        merged['q23h_fail_mid'] = merged['q2_or_q3_high'] & (merged['h_close'] < merged['prev_mid'])
        
        # Scenario 4: Q2/Q3 sets Low, but Close > Prev Mid
        # (Inverse: selloff that doesn't break prev mid trend)
        merged['q2_or_q3_low'] = (merged['q_low_Q2'] == merged['h_low']) | (merged['q_low_Q3'] == merged['h_low'])
        merged['q23l_fail_mid'] = merged['q2_or_q3_low'] & (merged['h_close'] > merged['prev_mid'])

        # Extended Analysis Metrics
        
        # A: Strong Continuation (Close Beyond Previous Hi/Lo)
        merged['close_above_prev_high'] = merged['h_close'] > merged['prev_high']
        merged['close_below_prev_low'] = merged['h_close'] < merged['prev_low']
        
        # B: Reversal Flag (Q1 sets the WRONG extreme relative to Prev Mid Context)
        # Bearish Context (Prev Mid > Open): Expect Q1 High. If Q1 sets Low, that implies Reversal.
        merged['q1_is_low'] = merged['q_low_Q1'] == merged['h_low']
        merged['reversal_risk_bear'] = merged['q1_is_low'] # For bearish context sessions
        
        # Bullish Context (Prev Mid < Open): Expect Q1 Low. If Q1 sets High, that implies Reversal.
        merged['q1_is_high'] = merged['q_high_Q1'] == merged['h_high']
        merged['reversal_risk_bull'] = merged['q1_is_high'] # For bullish context sessions

        # Bias Flag
        merged['bias_bearish'] = merged['h_open'] < merged['prev_mid'] # Mid is ABOVE open
        merged['bias_bullish'] = merged['h_open'] > merged['prev_mid'] # Mid is BELOW open
        
        print("Gathering cross-sectional statistics...")
        stats_by_hour = {}
        dow_names = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday', 4: 'Friday'}
        
        for h in range(24):
            h_df = merged[merged['hour'] == h]
            if h_df.empty: continue
            
            # 1. Bearish Bias Subset (Prev Mid > Open)
            bear_df = h_df[h_df['bias_bearish']]
            bear_tot = len(bear_df)
            
            # 2. Bullish Bias Subset (Prev Mid < Open)
            bull_df = h_df[h_df['bias_bullish']]
            bull_tot = len(bull_df)
            
            # Aggregates
            stats_by_hour[h] = {
                'total_with_context': len(h_df),
                'bearish_bias': {
                    'total': bear_tot,
                    'q1h_q4l': int(bear_df['is_q1h_q4l'].sum()),
                    'q23h_fail': int(bear_df['q23h_fail_mid'].sum()),
                    'strong_continuation': int(bear_df['close_below_prev_low'].sum()),
                    'reversal_risk': int(bear_df['reversal_risk_bear'].sum()),
                    'by_dow': {dow_names[d]: {
                        'total': int((bear_df['dow_int'] == d).sum()),
                        'q1h_q4l': int((bear_df[bear_df['dow_int'] == d]['is_q1h_q4l']).sum())
                    } for d in range(5)}
                },
                'bullish_bias': {
                    'total': bull_tot,
                    'q1l_q4h': int(bull_df['is_q1l_q4h'].sum()),
                    'q23l_fail': int(bull_df['q23l_fail_mid'].sum()),
                    'strong_continuation': int(bull_df['close_above_prev_high'].sum()),
                    'reversal_risk': int(bull_df['reversal_risk_bull'].sum()),
                    'by_dow': {dow_names[d]: {
                        'total': int((bull_df['dow_int'] == d).sum()),
                        'q1l_q4h': int((bull_df[bull_df['dow_int'] == d]['is_q1l_q4h']).sum())
                    } for d in range(5)}
                }
            }
            
        self.report_data = stats_by_hour
        return stats_by_hour

    def generate_report(self):
        lines = []
        lines.append(f"# Hourly Quarter Bias Analysis: {self.ticker}")
        lines.append("")
        lines.append("> **Analysis focus:** How the previous hour's midpoint (PrevMid) influences current hour's boundary formation.")
        lines.append("")
        
        # 1. Bearish Continuation
        lines.append("## I. Bearish Continuation Logic (Prev Mid Above Open)")
        lines.append("Here, context suggests weakness. We analyze probability of:")
        lines.append("- **Q1H/Q4L**: Clean trend down.")
        lines.append("- **Q2-Q3 High Fail**: High formed in Q2/Q3, but Close < Prev Mid.")
        lines.append("- **Strong Cont**: Does price close *below* the previous hour's LOW?")
        lines.append("- **Reversal Risk**: Does Q1 make the *LOW* instead of the High?")
        lines.append("")
        lines.append("| Hour | Sessions | Q1H / Q4L Trend | Q2-Q3 High Fail | Strong Continuation | Reversal Risk (Q1=Low) |")
        lines.append("|---|---|---|---|---|---|")
        
        display_order = [9, 10, 11, 12, 13, 14, 15, 16, 18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7, 8]
        
        for h in display_order:
            if h not in self.report_data: continue
            s = self.report_data[h]['bearish_bias']
            tot = s['total']
            if tot == 0: continue
            
            p_trend = (s['q1h_q4l'] / tot) * 100
            p_fail = (s['q23h_fail'] / tot) * 100
            p_cont = (s['strong_continuation'] / tot) * 100
            p_rev = (s['reversal_risk'] / tot) * 100
            
            lines.append(f"| {h:02d}:00 | {tot} | **{p_trend:.1f}%** | {p_fail:.1f}% | {p_cont:.1f}% | {p_rev:.1f}% |")
            
        lines.append("")

        # 2. Bullish Continuation
        lines.append("## II. Bullish Continuation Logic (Prev Mid Below Open)")
        lines.append("Context suggests strength. Analyzing probability of:")
        lines.append("- **Q1L/Q4H**: Clean trend up.")
        lines.append("- **Q2-Q3 Low Fail**: Low formed in Q2/Q3, but Close > Prev Mid.")
        lines.append("- **Strong Cont**: Does price close *above* the previous hour's HIGH?")
        lines.append("- **Reversal Risk**: Does Q1 make the *HIGH* instead of the Low?")
        lines.append("")
        lines.append("| Hour | Sessions | Q1L / Q4H Trend | Q2-Q3 Low Fail | Strong Continuation | Reversal Risk (Q1=High) |")
        lines.append("|---|---|---|---|---|---|")
        
        for h in display_order:
            if h not in self.report_data: continue
            s = self.report_data[h]['bullish_bias']
            tot = s['total']
            if tot == 0: continue
            
            p_trend = (s['q1l_q4h'] / tot) * 100
            p_fail = (s['q23l_fail'] / tot) * 0
            p_fail = (s['q23l_fail'] / tot) * 100
            p_cont = (s['strong_continuation'] / tot) * 100
            p_rev = (s['reversal_risk'] / tot) * 100
            
            lines.append(f"| {h:02d}:00 | {tot} | **{p_trend:.1f}%** | {p_fail:.1f}% | {p_cont:.1f}% | {p_rev:.1f}% |")
        
        lines.append("")
        
        # 3. DOW Breakdown
        lines.append("## III. Day of Week Persistence")
        lines.append("Probability of Q1 boundary setting the tone when context (Prev Mid) is aligned.")
        lines.append("")
        lines.append("| Hour | Mon | Tue | Wed | Thu | Fri |")
        lines.append("|---|---|---|---|---|---|")
        
        # Focus on RTH
        for h in [9, 10, 11, 12, 13, 14, 15]:
            if h not in self.report_data: continue
            bear = self.report_data[h]['bearish_bias']['by_dow']
            bull = self.report_data[h]['bullish_bias']['by_dow']
            
            row = f"| {h:02d}:00 |"
            for d in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
                # Average of bear trend and bull trend probability for that DOW
                b_s = bear[d]
                l_s = bull[d]
                
                b_p = (b_s['q1h_q4l'] / b_s['total']) if b_s['total'] > 0 else 0
                l_p = (l_s['q1l_q4h'] / l_s['total']) if l_s['total'] > 0 else 0
                
                combined = ((b_p + l_p) / 2) * 100 if (b_s['total'] + l_s['total']) > 0 else 0
                row += f" {combined:.1f}% |"
            lines.append(row)
        
        lines.append("")
        
        # 4. Extended Analysis / Interpretation
        lines.append("## IV. Extended Analysis & Tactical Findings")
        lines.append("")
        
        # Helper to find max/min
        def get_stat(h, bias, metric):
            if h not in self.report_data: return 0
            s = self.report_data[h][bias]
            if s['total'] == 0: return 0
            return (s[metric] / s['total']) * 100

        # Most Responsive Hours (highest Trend %)
        lines.append("### A. Most Responsive Hours")
        lines.append("Hours where the Prev High/Low + Midpoint bias leads to the cleanest Q1-Q4 trend continuation.")
        
        responsive_h = []
        for h in display_order:
            avg_trend = (get_stat(h, 'bearish_bias', 'q1h_q4l') + get_stat(h, 'bullish_bias', 'q1l_q4h')) / 2
            responsive_h.append((h, avg_trend))
        
        responsive_h.sort(key=lambda x: x[1], reverse=True)
        top3 = responsive_h[:3]
        lines.append(f"1. **{top3[0][0]:02d}:00** ({top3[0][1]:.1f}%)")
        lines.append(f"2. **{top3[1][0]:02d}:00** ({top3[1][1]:.1f}%)")
        lines.append(f"3. **{top3[2][0]:02d}:00** ({top3[2][1]:.1f}%)")
        lines.append("")
        
        # Highest Reversal Risk Hours
        lines.append("### B. Reversal Danger Zones")
        lines.append("Hours where Q1 frequently sets the *opposite* extreme, signaling a failure of the previous hour's bias.")
        
        reversal_h = []
        for h in display_order:
            avg_rev = (get_stat(h, 'bearish_bias', 'reversal_risk') + get_stat(h, 'bullish_bias', 'reversal_risk')) / 2
            reversal_h.append((h, avg_rev))
        
        reversal_h.sort(key=lambda x: x[1], reverse=True)
        top3_rev = reversal_h[:3]
        lines.append(f"1. **{top3_rev[0][0]:02d}:00** ({top3_rev[0][1]:.1f}%) - Frequent trend exhaustion.")
        lines.append(f"2. **{top3_rev[1][0]:02d}:00** ({top3_rev[1][1]:.1f}%)")
        lines.append(f"3. **{top3_rev[2][0]:02d}:00** ({top3_rev[2][1]:.1f}%)")
        lines.append("")
        
        # 16:00 Special Note
        h16_cont = (get_stat(16, 'bearish_bias', 'strong_continuation') + get_stat(16, 'bullish_bias', 'strong_continuation')) / 2
        lines.append(f"### C. The 16:00 Close Effect")
        lines.append(f"At 16:00, strong continuation (closing beyond the previous hour's extreme) occurs **{h16_cont:.1f}%** of the time.")
        lines.append("This confirms the strong persistence of trend into the close despite frequent Q4 volatility.")
        
        return "\n".join(lines)

    def save_report(self):
        report = self.generate_report()
        path = Path(f"docs/nqstats/quarterly_dynamics/{self.ticker}_BIAS_ANALYSIS.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(report)
        print(f"Report saved to {path}")

if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "NQ1"
    analyzer = HourlyQuarterContextAnalyzer(ticker)
    analyzer.compute_stats()
    analyzer.save_report()
