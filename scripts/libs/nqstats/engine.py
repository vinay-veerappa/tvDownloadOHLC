"""
NQStats Library Entrance - Simplified interface for fetching status.
"""

import pandas as pd
from .sessions import extract_all_nq_sessions
from .classifiers import (
    classify_aln_vectorized, 
    get_broken_status_vectorized, 
    get_quadrant_status,
    classify_noon_curve_vectorized
)
from .ib import calculate_ib_bias
from .timing import identify_hourly_mode

class NQStatsEngine:
    """Core Engine for calculating NQStats based on Unified Bias Algorithm."""
    
    def __init__(self, t1m_df: pd.DataFrame):
        """
        Initialize with a 1-minute OHLC DataFrame.
        Expected index: DatetimeIndex (localized or UTC).
        """
        self.df = t1m_df
        self._processed = False
        self.sessions = None
        self.stats = None
        
    def _get_prior_close(self, df: pd.DataFrame) -> pd.Series:
        """
        Extract P12 (Prior Close) for every day in the DataFrame.
        Standard NQ Close is 16:00 ET.
        """
        # Convert to US/Eastern for identification
        et_df = df.tz_convert('US/Eastern') if df.index.tz else df
        
        # 16:00 ET Close
        is_close = et_df.index.time == pd.Timestamp("16:00").time()
        close_prices = et_df['close'].where(is_close).ffill()
        
        # Shift so today's P12 is yesterday's 16:00 close
        # Using shift(1) after identifying the daily close
        # Since 'close_prices' is filled, we need to shift by 1 day equivalent
        # For simplicity in vectorized logic, we can just use the daily resampled close shift(1)
        daily_close = et_df['close'].resample('D').last().shift(1).ffill()
        
        # Map daily_close back to 1m timeframe
        return daily_close.reindex(et_df.index, method='ffill')

    def process(self):
        """Run all vectorized classifications."""
        # 1. Extract session ranges
        self.sessions = extract_all_nq_sessions(self.df)
        
        # 2. Extract Prior Close (P12)
        p12 = self._get_prior_close(self.df)
        
        # 3. Apply classifiers
        self.stats = pd.DataFrame(index=self.df.index)
        self.stats['aln'] = classify_aln_vectorized(self.sessions)
        
        broken_info = get_broken_status_vectorized(self.sessions)
        self.stats['broken'] = broken_info['broken_status']
        self.stats['l_vs_a'] = broken_info['london_vs_asia']
        self.stats['p_vs_l'] = broken_info['preny_vs_london']
        
        # New: Detailed Quadrant Profiler (LT/ST/LF/SF) - SPECIFICALLY FOR THE BOXES
        quadrants = get_quadrant_status(self.df, self.sessions)
        self.stats['asiabox_quadrant'] = quadrants['asiabox_status']
        self.stats['londonbox_quadrant'] = quadrants['londonbox_status']
        self.stats['ny1box_quadrant'] = quadrants['ny1box_status']

        
        self.stats['noon_curve'] = classify_noon_curve_vectorized(self.df)
        
        # 4. New Statistical Modules
        ib_info = calculate_ib_bias(self.sessions)
        self.stats['ib_bias'] = ib_info['ib_bias']
        self.stats['ib_conviction'] = ib_info['ib_conviction']
        
        timing_info = identify_hourly_mode(self.df)
        self.stats['hourly_mode'] = timing_info['hourly_mode']
        self.stats['expected_timing'] = timing_info['expected_extreme_timing']
        self.stats['orb_status'] = timing_info['orb_status']
        self.stats['base_orb_wr'] = timing_info['base_orb_wr']
        
        # 1H Continuation (09:00-10:00) Anchor
        # Green 9AM -> 70.6% Green close
        c_anchor = (self.sessions['ib_close'] > self.sessions['ib_open']).map({True: "BULLISH (70.6%)", False: "BEARISH"})
        self.stats['anchor'] = c_anchor
        
        self.stats['p12'] = p12
        
        # Add session highs/lows for reference
        for col in self.sessions.columns:
            self.stats[col] = self.sessions[col]
            
        self._processed = True
        return self.stats

    def get_latest_status(self):
        """Fetch the most recent complete status."""
        if not self._processed:
            self.process()
            
        return self.stats.iloc[-1].to_dict()

    def get_report(self):
        """Generates a human-friendly briefing of the current status."""
        latest = self.get_latest_status()
        
        report = []
        report.append(f"📊 NQStats Briefing: {self.df.index[-1]}")
        report.append(f"---")
        report.append(f"ALN Pattern: {latest['aln']}")
        report.append(f"Broken Status: {latest['broken']}")
        report.append(f"Profiler Boxes: Asia:{latest['asia_quadrant']} | London:{latest['london_quadrant']} | NY1:{latest['ny1_quadrant']}")
        report.append(f"Noon Curve: {latest['noon_curve']}")
        report.append(f"IB Bias: {latest['ib_bias']} ({latest['ib_conviction']*100:.1f}%)")
        report.append(f"Anchor (9AM): {latest['anchor']}")
        report.append(f"Hourly Mode: {latest['hourly_mode']} ({latest['base_orb_wr']*100:.1f}% WR)")
        report.append(f"ORB Prediction: {latest['orb_status']} (Expect {latest['expected_timing']})")
        report.append(f"\n📍 Key Levels:")
        report.append(f"- London High: {latest['london_high']:.2f} | Low: {latest['london_low']:.2f}")
        report.append(f"- IB High: {latest['ib_high']:.2f} | Low: {latest['ib_low']:.2f} | Mid: {latest['ib_mid']:.2f}")

        report.append(f"- Prior Close (P12): {latest['p12']:.2f}")
        
        return "\n".join(report)
