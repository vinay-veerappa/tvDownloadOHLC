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
            dow_int=('dow_int', 'first'),
            n_quarters=('q_int', 'nunique')
        ).reset_index()
        
        # Filter to only complete hours (all 4 quarters present)
        full_hours = h_agg[h_agg['n_quarters'] == 4].copy()
        partial_dropped = len(h_agg) - len(full_hours)
        print(f"Dropped {partial_dropped} partial-hour sessions ({partial_dropped/len(h_agg)*100:.2f}%)")
        
        full_hours['h_q_int'] = full_hours['h_high_idx'].dt.minute // 15
        full_hours['l_q_int'] = full_hours['h_low_idx'].dt.minute // 15
        
        # 4. Pivot Quarter Data for breakout analysis
        q_pivot = q_agg.pivot(index=['date_key', 'hour'], columns='q_int', values=['q_high', 'q_low', 'h_is_m0', 'l_is_m0'])
        q_pivot.columns = [f"{col[0]}_{q_map[col[1]]}" for col in q_pivot.columns]
        q_pivot = q_pivot.reset_index()
        
        # 5. Merge
        merged = full_hours.merge(q_pivot, on=['date_key', 'hour'], how='left')
        
        # 6. Breakouts (mutually exclusive: first quarter to break Q1)
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
            
            # DOW — Q1 influence stats
            dow_stats = {}
            for d_int, d_name in dow_names.items():
                d_df = h_df[h_df['dow_int'] == d_int]
                if d_df.empty: continue
                d_tot = len(d_df)
                d_inf = (d_df['h_q_int'] == 0) | (d_df['l_q_int'] == 0)
                dow_stats[d_name] = {'total': d_tot, 'Q1_either': int(d_inf.sum())}
                
            # Q1-Q4 Opposite Extreme Analysis (overall)
            q1_h_q4_l = int(((h_df['h_q_int'] == 0) & (h_df['l_q_int'] == 3)).sum())
            q1_l_q4_h = int(((h_df['l_q_int'] == 0) & (h_df['h_q_int'] == 3)).sum())
            
            # Q1-Q4 Opposite Extreme Analysis (by DOW)
            dow_q1q4 = {}
            for d_int, d_name in dow_names.items():
                d_df = h_df[h_df['dow_int'] == d_int]
                if d_df.empty: continue
                d_tot = len(d_df)
                d_q1h_q4l = int(((d_df['h_q_int'] == 0) & (d_df['l_q_int'] == 3)).sum())
                d_q1l_q4h = int(((d_df['l_q_int'] == 0) & (d_df['h_q_int'] == 3)).sum())
                dow_q1q4[d_name] = {
                    'total': d_tot,
                    'q1_high_q4_low': d_q1h_q4l,
                    'q1_low_q4_high': d_q1l_q4h,
                    'either_opp': d_q1h_q4l + d_q1l_q4h
                }
            
            # Full 4x4 Joint Distribution: High_Q x Low_Q
            joint_dist = {}
            for hq in range(4):
                for lq in range(4):
                    key = f'{q_map[hq]}_H_{q_map[lq]}_L'
                    joint_dist[key] = int(((h_df['h_q_int'] == hq) & (h_df['l_q_int'] == lq)).sum())
            
            stats_by_hour[h] = {
                'total_sessions': tot,
                'h_high_q': h_q_dist,
                'h_low_q': l_q_dist,
                'q1_exclusive': exclusive,
                'q1_q4_extremes': {
                    'q1_high_q4_low': q1_h_q4_l,
                    'q1_low_q4_high': q1_l_q4_h,
                    'either_opp': q1_h_q4_l + q1_l_q4_h,
                    'by_dow': dow_q1q4
                },
                'joint_dist': joint_dist,
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
        lines.append("- **Exclusion Criteria:** Partial sessions (hours with fewer than 4 quarters) and non-trading holidays excluded.")
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
        lines.append("### 5. Q1-Q4 Opposite Extremes Definition")
        lines.append("A **Q1-Q4 Trend Reversal** occurs when Q1 establishes one boundary and Q4 establishes the opposite:")
        lines.append("- **Q1 High / Q4 Low:** Price peaks early, declines through the hour (bearish trend).")
        lines.append("- **Q1 Low / Q4 High:** Price troughs early, rallies through the hour (bullish trend).")
        lines.append("These represent the cleanest directional hours with maximum trend duration.")
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

        # 7. Q1-Q4 Trend Reversal (Opposite Extremes) — Overall
        lines.append("### 7. Q1-Q4 Trend Reversal (Opposite Extremes)")
        lines.append("Probability that the hour's range is bookended by Q1 and Q4 (e.g., Q1 High and Q4 Low).")
        lines.append("| Hour | Total | Q1 High / Q4 Low | Q1 Low / Q4 High | **Total Joint Prob** |")
        lines.append("|---|---|---|---|---|")
        for h in display_order:
            if h not in self.report_data: continue
            s = self.report_data[h]
            tot = s['total_sessions']
            ex = s['q1_q4_extremes']
            
            p_h1_l4 = (ex['q1_high_q4_low'] / tot * 100) if tot else 0
            p_l1_h4 = (ex['q1_low_q4_high'] / tot * 100) if tot else 0
            p_total = (ex['either_opp'] / tot * 100) if tot else 0
            
            row = f"| {h:02d}:00 | {tot} | {ex['q1_high_q4_low']} (**{p_h1_l4:.1f}%**) | {ex['q1_low_q4_high']} (**{p_l1_h4:.1f}%**) | **{p_total:.1f}%** |"
            lines.append(row)
        lines.append("")

        # 8. Q1-Q4 Trend Reversal by Day of Week
        lines.append("### 8. Q1-Q4 Trend Reversal by Day of Week")
        lines.append("Total joint probability (Q1 High/Q4 Low + Q1 Low/Q4 High) by day of week.")
        lines.append("| Hour | Sun | Mon | Tue | Wed | Thu | Fri |")
        lines.append("|---|---|---|---|---|---|---|")
        for h in display_order:
            if h not in self.report_data: continue
            s = self.report_data[h]
            dow_data = s['q1_q4_extremes'].get('by_dow', {})
            row = f"| {h:02d}:00 |"
            for d in days:
                d_s = dow_data.get(d, {'total': 0, 'either_opp': 0})
                pct = (d_s['either_opp'] / d_s['total'] * 100) if d_s['total'] else 0
                row += f" {pct:.1f}% |"
            lines.append(row)
        lines.append("")

        # 8b. Detailed DOW breakdown (Q1H/Q4L vs Q1L/Q4H)
        lines.append("### 8b. Q1-Q4 Detailed DOW Breakdown")
        lines.append("Per-day split: Q1H/Q4L (bearish trend) vs Q1L/Q4H (bullish trend).")
        lines.append("| Hour | Day | N | Q1H/Q4L | Q1L/Q4H | Total |")
        lines.append("|---|---|---|---|---|---|")
        # Only show key RTH hours to keep report manageable
        key_hours = [9, 10, 11, 12, 13, 14, 15]
        for h in key_hours:
            if h not in self.report_data: continue
            s = self.report_data[h]
            dow_data = s['q1_q4_extremes'].get('by_dow', {})
            for d in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
                d_s = dow_data.get(d, {'total': 0, 'q1_high_q4_low': 0, 'q1_low_q4_high': 0, 'either_opp': 0})
                if d_s['total'] == 0: continue
                t = d_s['total']
                p_hl = d_s['q1_high_q4_low'] / t * 100
                p_lh = d_s['q1_low_q4_high'] / t * 100
                p_tot = d_s['either_opp'] / t * 100
                row = f"| {h:02d}:00 | {d[:3]} | {t} | {p_hl:.1f}% | {p_lh:.1f}% | **{p_tot:.1f}%** |"
                lines.append(row)
        lines.append("")

        # 9. Dominant Quarter per Hour
        lines.append("### 9. Dominant Quarter per Hour")
        lines.append("Which quarter most frequently sets the High and Low of each hour. **Bold** = dominant quarter.")
        lines.append("| Hour | High→Q | High% | Low→Q | Low% | Q2+Q3 High% | Q2+Q3 Low% |")
        lines.append("|---|---|---|---|---|---|---|")
        for h in display_order:
            if h not in self.report_data: continue
            s = self.report_data[h]
            tot = s['total_sessions']
            
            # Find dominant quarter for High
            hq = s['h_high_q']
            dom_hq = max(hq, key=hq.get)
            dom_hq_pct = hq[dom_hq] / tot * 100
            
            # Find dominant quarter for Low
            lq = s['h_low_q']
            dom_lq = max(lq, key=lq.get)
            dom_lq_pct = lq[dom_lq] / tot * 100
            
            # Q2+Q3 combined (middle quarters)
            q2q3_high = (hq.get('Q2', 0) + hq.get('Q3', 0)) / tot * 100
            q2q3_low = (lq.get('Q2', 0) + lq.get('Q3', 0)) / tot * 100
            
            row = f"| {h:02d}:00 | **{dom_hq}** | {dom_hq_pct:.1f}% | **{dom_lq}** | {dom_lq_pct:.1f}% | {q2q3_high:.1f}% | {q2q3_low:.1f}% |"
            lines.append(row)
        lines.append("")

        # 9b. Middle Quarter Analysis (sorted by hour)
        lines.append("### 9b. Middle Quarter (Q2/Q3) Analysis")
        lines.append("Breakdown of middle-quarter boundary formation by hour.")
        lines.append("| Hour | Q2 High% | Q3 High% | Q2 Low% | Q3 Low% | **Q2+Q3 Combined** | Interpretation |")
        lines.append("|---|---|---|---|---|---|---|")
        
        for h in display_order:
            if h not in self.report_data: continue
            s = self.report_data[h]
            tot = s['total_sessions']
            hq = s['h_high_q']
            lq = s['h_low_q']
            q2h = hq.get('Q2', 0) / tot * 100
            q3h = hq.get('Q3', 0) / tot * 100
            q2l = lq.get('Q2', 0) / tot * 100
            q3l = lq.get('Q3', 0) / tot * 100
            combined = q2h + q3h + q2l + q3l
            # Interpretation
            if combined > 80:
                interp = "Mid-Q dominant — Q1 unreliable"
            elif q3h > 25 or q3l > 25:
                interp = "Q3 elevated — :30 mark pivotal"
            elif q3h > q2h and q3l > q2l:
                interp = "Q3 > Q2 — late-hour reversal zone"
            elif q2h > q3h and q2l > q3l:
                interp = "Q2 > Q3 — early continuation"
            else:
                interp = "Balanced mid-quarters"
            row = f"| {h:02d}:00 | {q2h:.1f}% | {q3h:.1f}% | {q2l:.1f}% | {q3l:.1f}% | **{combined:.1f}%** | {interp} |"
            lines.append(row)
        lines.append("")

        # 10. Full Joint Distribution: High_Q x Low_Q
        lines.append("### 10. Joint Distribution: High Quarter x Low Quarter")
        lines.append("Full 4x4 matrix showing which quarter makes the High AND which makes the Low. All 16 cells sum to 100%.")
        lines.append("")
        
        for h in display_order:
            if h not in self.report_data: continue
            s = self.report_data[h]
            tot = s['total_sessions']
            jd = s['joint_dist']
            
            lines.append(f"**{h:02d}:00** (N={tot})")
            lines.append("")
            lines.append("| | Low=Q1 | Low=Q2 | Low=Q3 | Low=Q4 | **Row** |")
            lines.append("|---|---|---|---|---|---|")
            
            for hq in ['Q1', 'Q2', 'Q3', 'Q4']:
                cells = []
                row_sum = 0
                for lq in ['Q1', 'Q2', 'Q3', 'Q4']:
                    count = jd.get(f'{hq}_H_{lq}_L', 0)
                    pct = count / tot * 100
                    cells.append(f'{pct:.1f}%')
                    row_sum += pct
                row_label = f'**Hi={hq}**'
                lines.append(f"| {row_label} | {' | '.join(cells)} | **{row_sum:.1f}%** |")
            
            # Column totals
            col_cells = []
            for lq in ['Q1', 'Q2', 'Q3', 'Q4']:
                col_sum = sum(jd.get(f'{hq}_H_{lq}_L', 0) for hq in ['Q1', 'Q2', 'Q3', 'Q4']) / tot * 100
                col_cells.append(f'**{col_sum:.1f}%**')
            lines.append(f"| **Col** | {' | '.join(col_cells)} | **100%** |")
            lines.append("")
        
        # 11. Opposite Extreme Destination
        lines.append("### 11. Where Does the Opposite Extreme Land When Q1 Sets One Boundary?")
        lines.append("Given Q1 makes the High (or Low), which quarter makes the opposite boundary?")
        lines.append("| Hour | Q1 Hi Only | ...Q4 Low | ...Q2/Q3 Low | Q4 Share | Q1 Lo Only | ...Q4 High | ...Q2/Q3 High | Q4 Share |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        
        for h in display_order:
            if h not in self.report_data: continue
            s = self.report_data[h]
            tot = s['total_sessions']
            ex = s['q1_q4_extremes']
            q1_ho = s['q1_exclusive']['high_only']
            q1_lo = s['q1_exclusive']['low_only']
            
            q1h_q4l = ex['q1_high_q4_low']
            q1h_mid = q1_ho - q1h_q4l if q1_ho > 0 else 0
            q4_share_h = (q1h_q4l / q1_ho * 100) if q1_ho > 0 else 0
            
            q1l_q4h = ex['q1_low_q4_high']
            q1l_mid = q1_lo - q1l_q4h if q1_lo > 0 else 0
            q4_share_l = (q1l_q4h / q1_lo * 100) if q1_lo > 0 else 0
            
            row = (f"| {h:02d}:00 "
                   f"| {q1_ho/tot*100:.1f}% "
                   f"| {q1h_q4l/tot*100:.1f}% "
                   f"| {q1h_mid/tot*100:.1f}% "
                   f"| **{q4_share_h:.0f}%** "
                   f"| {q1_lo/tot*100:.1f}% "
                   f"| {q1l_q4h/tot*100:.1f}% "
                   f"| {q1l_mid/tot*100:.1f}% "
                   f"| **{q4_share_l:.0f}%** |")
            lines.append(row)
        lines.append("")
        
        lines.append("> **Reading this table:** When Q1 sets the High ('Q1 Hi Only'), the Low can land in Q2, Q3, or Q4. ")
        lines.append("> 'Q4 Share' shows what percentage of those Q1-High sessions have Q4 as the Low — the clean trend scenario. ")
        lines.append("> The remainder ('Q2/Q3 Low') represents mid-hour reversals where the opposite extreme is set before Q4.")
        lines.append("")

        # ========== III. Overall Analysis ==========
        lines.append("---")
        lines.append("")
        lines.append("## III. Overall Analysis & Tactical Implications")
        lines.append("")
        
        # Compute aggregate metrics across all hours
        all_hours = sorted(self.report_data.keys())
        
        # --- A. Cross-Hour Summary Table ---
        lines.append("### A. Cross-Hour Summary")
        lines.append("Sorted by Q1-Q4 opposite extreme probability (highest first).")
        lines.append("| Rank | Hour | N | Q1 Sets H or L | Q1H/Q4L | Q1L/Q4H | **Q1-Q4 Total** | Expansion |")
        lines.append("|---|---|---|---|---|---|---|---|")
        
        hour_summary = []
        for h in all_hours:
            s = self.report_data[h]
            tot = s['total_sessions']
            q1_inf = (1 - s['q1_exclusive']['neither'] / tot) * 100
            ex = s['q1_q4_extremes']
            p_hl = ex['q1_high_q4_low'] / tot * 100
            p_lh = ex['q1_low_q4_high'] / tot * 100
            p_total = ex['either_opp'] / tot * 100
            p_exp = s['q1_exclusive']['neither'] / tot * 100
            hour_summary.append((h, tot, q1_inf, p_hl, p_lh, p_total, p_exp))
        
        hour_summary.sort(key=lambda x: x[5], reverse=True)
        for rank, (h, tot, q1_inf, p_hl, p_lh, p_total, p_exp) in enumerate(hour_summary, 1):
            row = f"| {rank} | {h:02d}:00 | {tot} | {q1_inf:.1f}% | {p_hl:.1f}% | {p_lh:.1f}% | **{p_total:.1f}%** | {p_exp:.1f}% |"
            lines.append(row)
        lines.append("")
        
        # --- B. Session-Level Insights ---
        lines.append("### B. Session-Level Insights")
        lines.append("")
        
        # Group hours into trading sessions
        sessions = {
            'Globex Evening (18-20)': [18, 19, 20],
            'Asia (21-01)': [21, 22, 23, 0, 1],
            'London (02-07)': [2, 3, 4, 5, 6, 7],
            'Pre-Market (08)': [8],
            'NY Open (09)': [9],
            'NY AM (10-12)': [10, 11, 12],
            'NY PM/Lunch (13-14)': [13, 14],
            'Power Hour (15)': [15],
            'Close (16)': [16],
        }
        
        lines.append("| Session | Avg Q1-Q4 Opp% | Best Hour | Worst Hour | Avg Expansion% |")
        lines.append("|---|---|---|---|---|")
        
        for session_name, hours in sessions.items():
            session_stats = [(h, self.report_data[h]) for h in hours if h in self.report_data]
            if not session_stats: continue
            
            avg_opp = np.mean([s['q1_q4_extremes']['either_opp'] / s['total_sessions'] * 100 for _, s in session_stats])
            avg_exp = np.mean([s['q1_exclusive']['neither'] / s['total_sessions'] * 100 for _, s in session_stats])
            
            best_h, best_s = max(session_stats, key=lambda x: x[1]['q1_q4_extremes']['either_opp'] / x[1]['total_sessions'])
            worst_h, worst_s = min(session_stats, key=lambda x: x[1]['q1_q4_extremes']['either_opp'] / x[1]['total_sessions'])
            
            best_pct = best_s['q1_q4_extremes']['either_opp'] / best_s['total_sessions'] * 100
            worst_pct = worst_s['q1_q4_extremes']['either_opp'] / worst_s['total_sessions'] * 100
            
            row = f"| {session_name} | {avg_opp:.1f}% | {best_h:02d}:00 ({best_pct:.1f}%) | {worst_h:02d}:00 ({worst_pct:.1f}%) | {avg_exp:.1f}% |"
            lines.append(row)
        lines.append("")
        
        # --- C. Bullish vs Bearish Bias ---
        lines.append("### C. Bullish vs Bearish Trend Bias")
        lines.append("Ratio of Q1L/Q4H (bullish) to Q1H/Q4L (bearish). Ratio > 1.0 = bullish bias.")
        lines.append("| Hour | Q1L→Q4H (Bull) | Q1H→Q4L (Bear) | Bull/Bear Ratio | Bias |")
        lines.append("|---|---|---|---|---|")
        
        for h in display_order:
            if h not in self.report_data: continue
            s = self.report_data[h]
            tot = s['total_sessions']
            ex = s['q1_q4_extremes']
            p_bull = ex['q1_low_q4_high'] / tot * 100
            p_bear = ex['q1_high_q4_low'] / tot * 100
            ratio = p_bull / p_bear if p_bear > 0 else 0
            bias = "🐂 Bullish" if ratio > 1.1 else ("🐻 Bearish" if ratio < 0.9 else "⚖ Neutral")
            row = f"| {h:02d}:00 | {p_bull:.1f}% | {p_bear:.1f}% | {ratio:.2f} | {bias} |"
            lines.append(row)
        lines.append("")
        
        # --- D. Key Tactical Findings ---
        lines.append("### D. Key Findings")
        lines.append("")
        
        # Find top/bottom hours
        top3 = hour_summary[:3]
        bottom3 = hour_summary[-3:]
        
        lines.append("#### Highest Q1-Q4 Trend Reversal Hours (Best for Directional Plays)")
        for rank, (h, tot, q1_inf, p_hl, p_lh, p_total, p_exp) in enumerate(top3, 1):
            lines.append(f"{rank}. **{h:02d}:00** — {p_total:.1f}% of sessions see Q1 set one extreme, Q4 the opposite. "
                        f"Bearish trend {p_hl:.1f}% / Bullish trend {p_lh:.1f}%.")
        lines.append("")
        
        lines.append("#### Lowest Q1-Q4 Trend Reversal Hours (Choppy / Expansion)")
        for rank, (h, tot, q1_inf, p_hl, p_lh, p_total, p_exp) in enumerate(bottom3, 1):
            lines.append(f"{rank}. **{h:02d}:00** — Only {p_total:.1f}% Q1-Q4 bookends. "
                        f"Expansion (Neither) at {p_exp:.1f}%.")
        lines.append("")
        
        # Specific tactical callouts
        h16 = self.report_data.get(16, {})
        if h16:
            p1inf = (1 - h16['q1_exclusive']['neither'] / h16['total_sessions']) * 100
            lines.append(f"- **Session Open (16:00):** Q1 sets at least one boundary {p1inf:.1f}% of the time. "
                        f"This is the 'Judas' hour — the first 15 minutes sets the tone.")
        
        h09 = self.report_data.get(9, {})
        if h09:
            p09exp = (h09['q1_exclusive']['neither'] / h09['total_sessions']) * 100
            p09_opp = h09['q1_q4_extremes']['either_opp'] / h09['total_sessions'] * 100
            lines.append(f"- **NY Open (09:00):** Highest expansion at {p09exp:.1f}% — Q1 boundaries are broken in both "
                        f"directions. Only {p09_opp:.1f}% Q1-Q4 opposite extremes. Avoid fading Q1.")
        
        h15 = self.report_data.get(15, {})
        if h15:
            p15_opp = h15['q1_q4_extremes']['either_opp'] / h15['total_sessions'] * 100
            p15_bull = h15['q1_q4_extremes']['q1_low_q4_high'] / h15['total_sessions'] * 100
            p15_bear = h15['q1_q4_extremes']['q1_high_q4_low'] / h15['total_sessions'] * 100
            lines.append(f"- **Power Hour (15:00):** Highest Q1-Q4 opposite extreme at {p15_opp:.1f}%. "
                        f"Strong directional moves: Bull {p15_bull:.1f}% / Bear {p15_bear:.1f}%.")
        
        # DOW patterns for key hours
        lines.append("")
        lines.append("#### Day-of-Week Patterns (RTH Hours)")
        for h in [9, 10, 15]:
            if h not in self.report_data: continue
            s = self.report_data[h]
            dow_data = s['q1_q4_extremes'].get('by_dow', {})
            best_day = max(((d, v) for d, v in dow_data.items() if v['total'] > 0), 
                          key=lambda x: x[1]['either_opp'] / x[1]['total'], default=None)
            worst_day = min(((d, v) for d, v in dow_data.items() if v['total'] > 0), 
                           key=lambda x: x[1]['either_opp'] / x[1]['total'], default=None)
            if best_day and worst_day:
                b_pct = best_day[1]['either_opp'] / best_day[1]['total'] * 100
                w_pct = worst_day[1]['either_opp'] / worst_day[1]['total'] * 100
                lines.append(f"- **{h:02d}:00** — Best: {best_day[0]} ({b_pct:.1f}%), Worst: {worst_day[0]} ({w_pct:.1f}%)")
        
        # --- E. Quarter Dominance Analysis ---
        lines.append("")
        lines.append("### E. Quarter Dominance Analysis")
        lines.append("")
        lines.append("**Q1 dominates 21 of 23 hours** for both High and Low formation. The two exceptions reveal critical regime changes:")
        lines.append("")
        
        # Find Q4-dominant and high-mid-Q hours dynamically
        q4_dom_hours = []
        high_mid_hours = []
        for h in display_order:
            if h not in self.report_data: continue
            s = self.report_data[h]
            tot = s['total_sessions']
            hq = s['h_high_q']
            lq = s['h_low_q']
            dom_hq = max(hq, key=hq.get)
            dom_lq = max(lq, key=lq.get)
            q2q3_h = (hq.get('Q2', 0) + hq.get('Q3', 0)) / tot * 100
            q2q3_l = (lq.get('Q2', 0) + lq.get('Q3', 0)) / tot * 100
            combined_mid = q2q3_h + q2q3_l
            
            if dom_hq == 'Q4' or dom_lq == 'Q4':
                q4_dom_hours.append((h, dom_hq, hq[dom_hq]/tot*100, dom_lq, lq[dom_lq]/tot*100))
            if combined_mid > 80:
                high_mid_hours.append((h, combined_mid, hq.get('Q3',0)/tot*100, lq.get('Q3',0)/tot*100))
        
        lines.append("#### Q4-Dominant Hours")
        for h, dh, dh_pct, dl, dl_pct in q4_dom_hours:
            lines.append(f"- **{h:02d}:00** — High: {dh} ({dh_pct:.1f}%), Low: {dl} ({dl_pct:.1f}%). "
                        f"{'The hour trends from open to close. Q1 is the setup, Q4 is the destination.' if h == 15 else 'Maximum expansion hour — Q1 boundaries are noise, not signal.'}")
        lines.append("")
        
        lines.append("#### High Middle-Quarter Hours (Q2+Q3 Combined > 80%)")
        for h, combined, q3h, q3l in high_mid_hours:
            lines.append(f"- **{h:02d}:00** — Q2+Q3 combined: {combined:.1f}%. "
                        f"Q3 alone: High {q3h:.1f}% / Low {q3l:.1f}%. "
                        f"{'The :30 mark (8:30 news) is the true session pivot — ignore Q1.' if h == 8 else 'Q1 is essentially random. Wait for the :30 rotation to trade.'}")
        lines.append("")
        
        lines.append("#### Tactical Rules by Quarter Regime")
        lines.append("| Regime | Hours | Rule |")
        lines.append("|---|---|---|")
        lines.append("| Q1 Dominant (>35%) | Most Globex, London, NY AM | Fade Q1 extreme for mean-reversion, or use Q1 boundary as SL for continuation |")
        lines.append("| Q4 Dominant | 09:00, 15:00 | Do NOT fade Q1 — let the trend develop. Enter on Q2/Q3 pullbacks toward Q4 |")
        lines.append("| Mid-Q Dominant (>80%) | 08:00, 09:00 | Wait for :30 rotation. Q1 boundaries are unreliable. The real range sets after economic data |")
        lines.append("| Q1 Overwhelm (>60%) | 16:00, 18:00 | The 'Judas Candle' regime. Q1 IS the range. Fade breakout attempts from Q2-Q4 |")

        return "\n".join(lines)

    def save(self):
        # Save JSON
        out_path = Path("data/derived")
        out_path.mkdir(parents=True, exist_ok=True)
        with open(out_path / f"hourly_quarter_stats_{self.ticker}.json", "w") as f:
            json.dump(self.report_data, f, indent=2, cls=NumpyEncoder)
            
        # Save CSV Summary (one row per hour)
        csv_rows = []
        for h, s in self.report_data.items():
            tot = s['total_sessions']
            row = {
                'hour': h,
                'total_sessions': tot,
                'q1_high_prob': round(s['h_high_q'].get('Q1', 0) / tot, 4),
                'q2_high_prob': round(s['h_high_q'].get('Q2', 0) / tot, 4),
                'q3_high_prob': round(s['h_high_q'].get('Q3', 0) / tot, 4),
                'q4_high_prob': round(s['h_high_q'].get('Q4', 0) / tot, 4),
                'q1_low_prob': round(s['h_low_q'].get('Q1', 0) / tot, 4),
                'q2_low_prob': round(s['h_low_q'].get('Q2', 0) / tot, 4),
                'q3_low_prob': round(s['h_low_q'].get('Q3', 0) / tot, 4),
                'q4_low_prob': round(s['h_low_q'].get('Q4', 0) / tot, 4),
                'q1h_q4l_prob': round(s['q1_q4_extremes']['q1_high_q4_low'] / tot, 4),
                'q1l_q4h_prob': round(s['q1_q4_extremes']['q1_low_q4_high'] / tot, 4),
                'q1q4_opp_total_prob': round(s['q1_q4_extremes']['either_opp'] / tot, 4),
                'q1_exclusive_high_only': round(s['q1_exclusive']['high_only'] / tot, 4),
                'q1_exclusive_low_only': round(s['q1_exclusive']['low_only'] / tot, 4),
                'q1_exclusive_both': round(s['q1_exclusive']['both'] / tot, 4),
                'q1_exclusive_neither': round(s['q1_exclusive']['neither'] / tot, 4),
            }
            csv_rows.append(row)
        
        pd.DataFrame(csv_rows).to_csv(out_path / f"hourly_quarter_stats_{self.ticker}.csv", index=False)
        print(f"Saved CSV stats to {out_path / f'hourly_quarter_stats_{self.ticker}.csv'}")

        # Save DOW x Hour x Q1Q4 CSV (one row per hour x dow combination)
        dow_rows = []
        dow_names = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday', 4: 'Friday', 5: 'Saturday', 6: 'Sunday'}
        for h, s in self.report_data.items():
            dow_data = s['q1_q4_extremes'].get('by_dow', {})
            for d_name, d_s in dow_data.items():
                t = d_s['total']
                if t == 0: continue
                dow_rows.append({
                    'hour': h,
                    'day_of_week': d_name,
                    'total_sessions': t,
                    'q1h_q4l': d_s['q1_high_q4_low'],
                    'q1l_q4h': d_s['q1_low_q4_high'],
                    'q1q4_opp_total': d_s['either_opp'],
                    'q1h_q4l_prob': round(d_s['q1_high_q4_low'] / t, 4),
                    'q1l_q4h_prob': round(d_s['q1_low_q4_high'] / t, 4),
                    'q1q4_opp_total_prob': round(d_s['either_opp'] / t, 4),
                })
        
        pd.DataFrame(dow_rows).to_csv(out_path / f"hourly_quarter_dow_{self.ticker}.csv", index=False)
        print(f"Saved DOW CSV to {out_path / f'hourly_quarter_dow_{self.ticker}.csv'}")

        # Save Report
        rpt_path = Path("docs/nqstats/quarterly_dynamics") 
        rpt_path.mkdir(parents=True, exist_ok=True)
        report_content = self.generate_report()
        with open(rpt_path / f"{self.ticker}_QUARTER_ANALYSIS.md", "w", encoding="utf-8") as f:
            f.write(report_content)
            
        print(f"Saved report to {rpt_path}")

if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "NQ1"
    print(f"Analyzing {ticker}...")
    analyzer = HourlyQuarterAnalyzer(ticker)
    analyzer.compute_stats()
    analyzer.save()
