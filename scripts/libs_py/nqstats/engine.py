"""
NQStats Library Entrance - Simplified interface for fetching status.
"""

import pandas as pd
# Silence Pandas warnings for downcasting
pd.set_option('future.no_silent_downcasting', True)

from .sessions import extract_all_sessions
from .classifiers import (
    classify_aln_vectorized, 
    get_broken_status_vectorized, 
    classify_noon_curve_vectorized
)
from .ib import calculate_ib_bias
from .timing import identify_hourly_mode
from .levels import calculate_daily_levels, calculate_session_opens, calculate_p12_levels, get_session_mids

# Profiler box status computation — delegated to the profiler library.
# This was previously inlined as get_quadrant_status() in classifiers.py
# and _calculate_session_broken() in this file.
from scripts.libs_py.profiler.session_box_status import (
    compute_box_status,
    compute_box_broken,
    compute_prev_day_shifts,
)

class NQStatsEngine:
    """Core Engine for calculating NQStats based on Unified Bias Algorithm."""
    
    def __init__(self, t1m_df: pd.DataFrame, ticker: str = "NQ1"):
        """
        Initialize with a 1-minute OHLC DataFrame.
        Expected index: DatetimeIndex (localized or UTC).
        """
        self.df = t1m_df
        self.ticker = ticker
        self._processed = False
        self.sessions = None
        self.stats = None
        
    def check_9am_reversion(self, df_1m: pd.DataFrame) -> pd.DataFrame:
        """
        Implements the 75.2% Reversion Rule for the 09:00 hour.
        If price breaks the 08:00 high or low, it must return to the 09:00 open.
        """
        # Ensure US/Eastern normalization
        et_df = df_1m.tz_convert('US/Eastern') if df_1m.index.tz else df_1m
        hours = et_df.index.hour

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
        # 0. NORMALIZE TO US/EASTERN DATA LAYER
        # All NQStats logic depends on Eastern Time (institutional standard)
        if self.df.index.tz:
            self.df = self.df.tz_convert('US/Eastern')
        else:
            # Assume UTC if no TZ info, then localize and convert
            self.df = self.df.tz_localize('UTC').tz_convert('US/Eastern')

        # 1. Extract session ranges
        # from .sessions import extract_all_sessions # This line is now redundant as it's defined above or imported
        self.sessions = extract_all_sessions(self.df)
        
        # 2. Extract Prior Close (P12)
        p12 = self._get_prior_close(self.df)
        
        # 3. Apply classifiers
        self.stats = pd.DataFrame(index=self.df.index)
        self.stats['aln'] = classify_aln_vectorized(self.sessions)
        
        broken_info = get_broken_status_vectorized(self.sessions)
        self.stats['broken'] = broken_info['broken_status']
        self.stats['l_vs_a'] = broken_info['london_vs_asia']
        self.stats['p_vs_l'] = broken_info['preny_vs_london']
        
        # Profiler box status (LT/LF/ST/SF) — delegated to profiler library
        box_status = compute_box_status(self.df, self.sessions)
        self.stats['asiabox_status'] = box_status['asiabox_status']
        self.stats['londonbox_status'] = box_status['londonbox_status']
        self.stats['ny1box_status'] = box_status['ny1box_status']
        self.stats['ny2box_status'] = box_status['ny2box_status']

        
        self.stats['noon_curve'] = classify_noon_curve_vectorized(self.df)
        
        # 4. Extract Institutional Levels
        lvl_daily = calculate_daily_levels(self.df)
        lvl_opens = calculate_session_opens(self.df)
        lvl_p12   = calculate_p12_levels(self.df)
        lvl_mids  = get_session_mids(self.sessions)
        
        # 5. Combine everything
        self.stats = pd.concat([
            self.stats,
            lvl_daily,
            lvl_opens,
            lvl_p12,
            lvl_mids
        ], axis=1)

        # 5b. Calculate PER-SESSION BROKEN (Reversion to Mid)
        # Delegated to profiler.session_box_status
        broken_df = compute_box_broken(self.df, self.stats)
        for col in broken_df.columns:
            self.stats[col] = broken_df[col]

        # 6. New Statistical Modules
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
            if col not in self.stats.columns:
                self.stats[col] = self.sessions[col]

        # 7. Transition Matrix Context (Shifted statuses)
        # Delegated to profiler.session_box_status
        prev_df = compute_prev_day_shifts(self.stats)
        for col in prev_df.columns:
            self.stats[col] = prev_df[col]
        
        return self.stats

    # _calculate_session_broken removed — now delegated to
    # scripts.libs_py.profiler.session_box_status.compute_box_broken()

    def get_latest_status(self):
        """Fetch the most recent complete status."""
        if not self._processed:
            self.process()
            
        return self.stats.iloc[-1].to_dict()

    def get_report(self):
        """Generates a human-friendly briefing of the current status."""
        latest = self.get_latest_status()
        
        # Ensure the timestamp is in US/Eastern for the report
        last_ts = self.df.index[-1]
        if last_ts.tzinfo is None:
            last_ts = last_ts.tz_localize('UTC').tz_convert('US/Eastern')
        else:
            last_ts = last_ts.tz_convert('US/Eastern')

        report = []
        report.append(f"📊 NQStats Briefing: {last_ts}")
        report.append(f"---")
        report.append(f"ALN Pattern: {latest['aln']}")
        report.append(f"Broken Status: {latest['broken']}")
        report.append(f"Profiler Boxes: Asia:{latest['asiabox_status']} | London:{latest['londonbox_status']} | NY1:{latest['ny1box_status']} | NY2:{latest['ny2box_status']}")
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
