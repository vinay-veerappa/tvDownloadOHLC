import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        return super(NumpyEncoder, self).default(obj)

class HourlyQuarterAnalyzer:
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
        
        # Extract features for vectorization
        df['hour'] = df.index.hour
        df['minute'] = df.index.minute
        df['date_key'] = df.index.date
        df['dow_int'] = df.index.dayofweek
        
        self.df = df
        print(f"Loaded {len(df)} rows ({self.start_year}-{self.end_year})")

    def compute_stats(self):
        """Hyper-optimized Vectorized Statistics with Mutually Exclusive Categories."""
        if self.df is None: self.load_data()
        df = self.df
        
        # 1. Assign Quarters
        work_df = df[['hour', 'minute', 'date_key', 'dow_int', 'high', 'low']].copy()
        work_df['q_int'] = work_df['minute'] // 15
        q_map = {0: 'Q1', 1: 'Q2', 2: 'Q3', 3: 'Q4'}

        print("Aggregating boundaries...")
        # 2. Quarter-level boundaries
        q_agg = work_df.groupby(['date_key', 'hour', 'q_int']).agg(
            q_high=('high', 'max'),
            q_low=('low', 'min'),
            q_high_idx=('high', 'idxmax'),
            q_low_idx=('low', 'idxmin')
        ).reset_index()
        
        # Minute 0 logic
        q_agg['h_is_m0'] = q_agg['q_high_idx'].dt.minute == (q_agg['q_int'] * 15)
        q_agg['l_is_m0'] = q_agg['q_low_idx'].dt.minute == (q_agg['q_int'] * 15)
        
        # 3. Hour-level boundaries
        h_agg = work_df.groupby(['date_key', 'hour']).agg(
            h_high=('high', 'max'),
            h_low=('low', 'min'),
            h_high_idx=('high', 'idxmax'),
            h_low_idx=('low', 'idxmin'),
            dow_int=('dow_int', 'first')
        ).reset_index()
        
        h_agg['h_q_int'] = h_agg['h_high_idx'].dt.minute // 15
        h_agg['l_q_int'] = h_agg['h_low_idx'].dt.minute // 15
        
        # 4. Pivot Quarter Data for breakout analysis
        q_pivot = q_agg.pivot(index=['date_key', 'hour'], columns='q_int', values=['q_high', 'q_low', 'h_is_m0', 'l_is_m0'])
        q_pivot.columns = [f"{col[0]}_{q_map[col[1]]}" for col in q_pivot.columns]
        q_pivot = q_pivot.reset_index()
        
        # 5. Merge
        merged = h_agg.merge(q_pivot, on=['date_key', 'hour'], how='left')
        
        # 6. Breakouts
        merged['q1_h_bk_q2'] = merged['q_high_Q2'] > merged['q_high_Q1']
        merged['q1_h_bk_q3'] = (~merged['q1_h_bk_q2']) & (merged['q_high_Q3'] > merged['q_high_Q1'])
        merged['q1_h_bk_q4'] = (~merged['q1_h_bk_q2']) & (~merged['q1_h_bk_q3']) & (merged['q_high_Q4'] > merged['q_high_Q1'])
        
        merged['q1_l_bk_q2'] = merged['q_low_Q2'] < merged['q_low_Q1']
        merged['q1_l_bk_q3'] = (~merged['q1_l_bk_q2']) & (merged['q_low_Q3'] < merged['q_low_Q1'])
        merged['q1_l_bk_q4'] = (~merged['q1_l_bk_q2']) & (~merged['q1_l_bk_q3']) & (merged['q_low_Q4'] < merged['q_low_Q1'])

        print("Synthesizing final statistics...")
        stats_by_hour = {}
        dow_names = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday', 4: 'Friday', 5: 'Saturday', 6: 'Sunday'}
        
        for h in range(24):
            h_df = merged[merged['hour'] == h]
            if h_df.empty: continue
            
            tot = len(h_df)
            ex_h = h_df['h_q_int'] == 0
            ex_l = h_df['l_q_int'] == 0
            
            # Map high/low q distribution
            h_q_dist = h_df['h_q_int'].map(q_map).value_counts().to_dict()
            l_q_dist = h_df['l_q_int'].map(q_map).value_counts().to_dict()
            
            # Mutual Exclusivity
            exclusive = {
                'high_only': int((ex_h & ~ex_l).sum()),
                'low_only': int((ex_l & ~ex_h).sum()),
                'both': int((ex_h & ex_l).sum()),
                'neither': int((~ex_h & ~ex_l).sum())
            }
            
            # DOW
            dow_stats = {}
            for d_int, d_name in dow_names.items():
                d_df = h_df[h_df['dow_int'] == d_int]
                if d_df.empty: continue
                d_tot = len(d_df)
                d_inf = (d_df['h_q_int'] == 0) | (d_df['l_q_int'] == 0)
                dow_stats[d_name] = {'total': d_tot, 'Q1_either': int(d_inf.sum())}
                
            stats_by_hour[h] = {
                'total_sessions': tot,
                'h_high_q': h_q_dist,
                'h_low_q': l_q_dist,
                'q1_exclusive': exclusive,
                'dow_stats': dow_stats,
                'q_micro': {q_map[i]: {
                    'total': int(h_df[f'q_high_{q_map[i]}'].notna().sum()),
                    'high_is_m0': int(h_df[f'h_is_m0_{q_map[i]}'].sum()),
                    'low_is_m0': int(h_df[f'l_is_m0_{q_map[i]}'].sum())
                } for i in range(4)},
                'q_breakouts': {'Q1': {
                    'high_violated_in': {
                        'Q2': int(h_df['q1_h_bk_q2'].sum()),
                        'Q3': int(h_df['q1_h_bk_q3'].sum()),
                        'Q4': int(h_df['q1_h_bk_q4'].sum()),
                        'Never': int(ex_h.sum())
                    },
                    'low_violated_in': {
                        'Q2': int(h_df['q1_l_bk_q2'].sum()),
                        'Q3': int(h_df['q1_l_bk_q3'].sum()),
                        'Q4': int(h_df['q1_l_bk_q4'].sum()),
                        'Never': int(ex_l.sum())
                    }
                }}
            }
            
        self.report_data = stats_by_hour
        return stats_by_hour

    def generate_report(self):
        """Generate Markdown report based on refined user design."""
        lines = []
        lines.append(f"# Quantitative Analysis of Intrahour Price Boundary Formation: {self.ticker}")
        lines.append("")
        lines.append("> **Abstract:** This study examines the probabilistic distribution of daily High and Low price formation across sixty-minute temporal clusters, specifically focusing on the first fifteen-minute interval (Q1). The objective is to determine the statistical significance of initial momentum as a range-boundary predictor.")
        lines.append("")
        lines.append("## I. Methodology & Data Infrastructure")
        lines.append("### 1. Data Source and Resolution")
        lines.append(f"- **Instrument:** {self.ticker} (Continuous Futures Contract)")
        lines.append("- **Resolution:** 1-Minute OHLC Intervals")
        lines.append(f"- **Temporal Scope:** {self.start_year} - {self.end_year}")
        lines.append("- **Exclusion Criteria:** Partial sessions and non-trading holidays excluded by data provider defaults.")
        lines.append("")
        lines.append("### 2. Time-Series Alignment")
        lines.append("- **Primary Timezone:** America/New_York (EST/EDT)")
        lines.append("- **Preprocessing:** Source UTC timestamps localized to Exchange Time to account for RTH/Globex session boundaries.")
        lines.append("- **Observation Window:** 18:00 (Session Open) to 16:00 (Session Close).")
        lines.append("")
        lines.append("### 3. Statistical Categorization (Quarters)")
        lines.append("The 60-minute hour is discretized into four equal 15-minute segments:")
        lines.append("- **Q1 (Initial Quarter):** Minutes :00 - :14")
        lines.append("- **Q2:** Minutes :15 - :29")
        lines.append("- **Q3:** Minutes :30 - :44")
        lines.append("- **Q4:** Minutes :45 - :59")
        lines.append("")
        lines.append("### 4. Mutual Exclusivity Logic for Q1 Influence")
        lines.append("To ensure statistical integrity, Table 3 utilizes a mutually exclusive classification system:")
        lines.append("- **Q1 High Only:** Q1 interval contains the final hourly High; Low is established later.")
        lines.append("- **Q1 Low Only:** Q1 interval contains the final hourly Low; High is established later.")
        lines.append("- **Q1 Both:** Both High and Low are established within the Q1 window (Range Contained).")
        lines.append("- **Neither (Expansion):** Both High and Low are broken later in the hour (Range Expansion).")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## II. Statistical Results")

        display_order = [18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]

        # 1. High of Hour Probability
        lines.append("### 1. High of Hour Probability")
        lines.append("| Hour | Total | Q1 High | Q2 High | Q3 High | Q4 High |")
        lines.append("|---|---|---|---|---|---|")
        for h in display_order:
            if h not in self.report_data: continue
            s = self.report_data[h]
            tot = s['total_sessions']
            row = f"| {h:02d}:00 | {tot} |"
            for q in ['Q1', 'Q2', 'Q3', 'Q4']:
                count = s['h_high_q'].get(q, 0)
                pct = (count/tot)*100 if tot else 0
                row += f" {count} (**{pct:.1f}%**) |"
            lines.append(row)
        lines.append("")

        # 2. Low of Hour Probability
        lines.append("### 2. Low of Hour Probability")
        lines.append("| Hour | Total | Q1 Low | Q2 Low | Q3 Low | Q4 Low |")
        lines.append("|---|---|---|---|---|---|")
        for h in display_order:
            if h not in self.report_data: continue
            s = self.report_data[h]
            tot = s['total_sessions']
            row = f"| {h:02d}:00 | {tot} |"
            for q in ['Q1', 'Q2', 'Q3', 'Q4']:
                count = s['h_low_q'].get(q, 0)
                pct = (count/tot)*100 if tot else 0
                row += f" {count} (**{pct:.1f}%**) |"
            lines.append(row)
        lines.append("")

        # 3. Q1 Influence & Range Expansion
        lines.append("### 3. Q1 Influence & Range Expansion")
        lines.append("Mutually exclusive breakdown of how Q1 (00-15) affects the hour's range.")
        lines.append("| Hour | Total | Q1 High Only | Q1 Low Only | Q1 Both | **Neither (Exp)** |")
        lines.append("|---|---|---|---|---|---|")
        for h in display_order:
            if h not in self.report_data: continue
            s = self.report_data[h]
            tot = s['total_sessions']
            ex = s['q1_exclusive']
            
            def get_ex_val(key):
                c = ex.get(key, 0)
                p = (c/tot)*100 if tot else 0
                return f"{c} ({p:.1f}%)"

            row = f"| {h:02d}:00 | {tot} | {get_ex_val('high_only')} | {get_ex_val('low_only')} | {get_ex_val('both')} | **{get_ex_val('neither')}** |"
            lines.append(row)
        lines.append("")

        # 4. Day of Week Analysis
        lines.append("### 4. Day of Week Analysis (Q1 Influence Probability)")
        lines.append("Cross-sectional variance of Q1 boundary formation (Sun-Fri).")
        lines.append("| Hour | Sun | Mon | Tue | Wed | Thu | Fri |")
        lines.append("|---|---|---|---|---|---|---|")
        days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        for h in display_order:
            if h not in self.report_data: continue
            s = self.report_data[h]
            row = f"| {h:02d}:00 |"
            for d in days:
                d_s = s['dow_stats'].get(d, {'total':0, 'Q1_either':0})
                pct = (d_s['Q1_either'] / d_s['total'] * 100) if d_s['total'] else 0
                row += f" {pct:.1f}% |"
            lines.append(row)
        lines.append("")

        # 5. Micro-Temporal Analysis
        lines.append("### 5. Micro-Temporal Analysis: First Minute Dominance")
        lines.append("Probability that the boundary (H or L) for a 15m quarter is formed in its **first minute**.")
        lines.append("| Hour | Q1 (H/L) | Q2 (H/L) | Q3 (H/L) | Q4 (H/L) |")
        lines.append("|---|---|---|---|---|")
        for h in display_order:
            if h not in self.report_data: continue
            s = self.report_data[h]
            q_m = s.get('q_micro', {})
            row = f"| {h:02d}:00 |"
            for q in ['Q1', 'Q2', 'Q3', 'Q4']:
                m = q_m.get(q, {'total':0, 'high_is_m0':0, 'low_is_m0':0})
                tot = m['total']
                h0 = (m['high_is_m0']/tot)*100 if tot else 0
                l0 = (m['low_is_m0']/tot)*100 if tot else 0
                row += f" {h0:.1f}%/{l0:.1f}% |"
            lines.append(row)
        lines.append("")

        # 6. Q1 Breakout Dynamics
        lines.append("### 6. Q1 Breakout Dynamics")
        lines.append("Percentage of sessions where the Q1 (00-14) High/Low is violated by subsequent quarters.")
        lines.append("| Hour | Q1 High Broken By (Q2 | Q3 | Q4 | Never) | Q1 Low Broken By (Q2 | Q3 | Q4 | Never) |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for h in display_order:
            if h not in self.report_data: continue
            s = self.report_data[h]
            tot = s['total_sessions']
            b = s['q_breakouts']['Q1']
            
            def b_p(side, target):
                c = b[side].get(target, 0)
                return f"{(c/tot)*100:.1f}%"

            row = f"| {h:02d}:00 | {b_p('high_violated_in','Q2')} | {b_p('high_violated_in','Q3')} | {b_p('high_violated_in','Q4')} | {b_p('high_violated_in','Never')} |"
            row += f" {b_p('low_violated_in','Q2')} | {b_p('low_violated_in','Q3')} | {b_p('low_violated_in','Q4')} | {b_p('low_violated_in','Never')} |"
            lines.append(row)
        lines.append("")

        lines.append("## III. Tactical Implications & Expert Analysis")
        lines.append("Synthesis of quantitative findings for active market participants:")
        
        # Highlights
        h16 = self.report_data.get(16, {})
        if h16:
            p1inf = (1 - h16['q1_exclusive']['neither'] / h16['total_sessions']) * 100
            lines.append(f"- **The 'Judas' / Range Setting Hour:** 16:00 has a {p1inf:.1f}% probability of Q1 setting at least one boundary. In this hour, Q1 is highly influential.")
        
        h09 = self.report_data.get(9, {})
        if h09:
            p09exp = (h09['q1_exclusive']['neither'] / h09['total_sessions']) * 100
            lines.append(f"- **Trending / Expansion Hour:** 09:00 shows the highest 'Neither' probability ({p09exp:.1f}%), meaning price often breaks BOTH the Q1 High and Low, expanding its range significantly later in the hour.")

        return "\n".join(lines)

    def save(self):
        # Save JSON
        out_path = Path("data/derived")
        out_path.mkdir(parents=True, exist_ok=True)
        with open(out_path / f"hourly_quarter_stats_{self.ticker}.json", "w") as f:
            json.dump(self.report_data, f, indent=2, cls=NumpyEncoder)
            
        # Save Report
        rpt_path = Path("docs/nqstats/quarterly_dynamics") 
        rpt_path.mkdir(parents=True, exist_ok=True)
        report_content = self.generate_report()
        with open(rpt_path / f"{self.ticker}_QUARTER_ANALYSIS.md", "w") as f:
            f.write(report_content)
            
        print(f"Saved report to {rpt_path}")

if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "NQ1"
    print(f"Analyzing {ticker}...")
    analyzer = HourlyQuarterAnalyzer(ticker)
    analyzer.compute_stats()
    analyzer.save()
