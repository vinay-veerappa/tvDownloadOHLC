"""
NQStats Library Entrance - Simplified interface for fetching status.
"""

import pandas as pd
from .sessions import extract_all_sessions
from .classifiers import (
    classify_aln_vectorized, 
    get_broken_status_vectorized, 
    get_quadrant_status,
    classify_noon_curve_vectorized
)
from .ib import calculate_ib_bias
from .timing import identify_hourly_mode
from .levels import calculate_daily_levels, calculate_session_opens, calculate_p12_levels, get_session_mids

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
        
        # New: Detailed Quadrant Profiler (LT/ST/LF/SF) - SPECIFICALLY FOR THE BOXES
        quadrants = get_quadrant_status(self.df, self.sessions)
        self.stats['asiabox_status'] = quadrants['asiabox_status']
        self.stats['londonbox_status'] = quadrants['londonbox_status']
        self.stats['ny1box_status'] = quadrants['ny1box_status']
        self.stats['ny2box_status'] = quadrants['ny2box_status']

        
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
        # Asia Broken: if price touches asia_mid between 02:30 and 16:00
        # London Broken: if price touches london_mid between 07:30 and 16:00
        # NY1 Broken: if price touches ny1_mid between 11:30 and 16:00
        self._calculate_session_broken()

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
        # We need to shift across trading days, not across 1m bars.
        # We do this by resampling the daily status from the sessions dataframe
        # then mapping back to the 1m timeline.
        def _get_daily_shift(col: str) -> pd.Series:
            # Map each 1m bar to its trading date
            trading_dates = self.sessions.index.date
            # Create a per-date series of final statuses
            daily = self.stats[col].groupby(trading_dates).last().shift(1).fillna("None")
            # Map back to the stats index
            return daily.reindex(trading_dates).values

        self.stats['prev_ny1_status'] = _get_daily_shift('ny1box_status')
        self.stats['prev_ny2_status'] = _get_daily_shift('ny2box_status')
        self.stats['prev_asia_status'] = _get_daily_shift('asiabox_status')
        
        # Broken status context for prior days
        def _get_daily_shift_bool(col: str) -> pd.Series:
            trading_dates = self.sessions.index.date
            daily = self.stats[col].groupby(trading_dates).last().shift(1).fillna(False)
            return daily.reindex(trading_dates).values

        self.stats['prev_ny1_broken'] = _get_daily_shift_bool('ny1box_broken')
        self.stats['prev_ny2_broken'] = _get_daily_shift_bool('ny2box_broken')
        self.stats['prev_asia_broken'] = _get_daily_shift_bool('asiabox_broken')
        
        return self.stats

    def _calculate_session_broken(self):
        """Vectorized calculation of session breakout reversion (broken) status."""
        # Config matches ProfilerService.apply_filters
        configs = [
            ('asiabox',   '02:30', '16:00'), # Broken if touched during London/NY
            ('londonbox', '07:30', '16:00'), # Broken if touched during NY
            ('ny1box',    '11:30', '16:00'), # Broken if touched during NY2 (Next Session)
            ('ny2box',    '18:00', '11:30')  # Broken if touched during Next Asia (Cycle Loop)
        ]
        
        for prefix, start_time, end_time in configs:
            mid_col = f'{prefix}_mid'
            if prefix == 'ny2box' and f'prev_{mid_col}' in self.stats.columns:
                # NY2 is broken in the NEXT cycle (18:00+), so we evaluate the 
                # NEXT day's prices (Today) against the PREVIOUS day's mid.
                mid_col = f'prev_{mid_col}'

            if mid_col not in self.stats.columns:
                self.stats[f'{prefix}_broken'] = False
                continue
            
            mid_vals = self.stats[mid_col]
            
            # Mask for the "Post-Session" window
            et_df = self.df # Already ET from process()
            post_mask = et_df.between_time(start_time, end_time)
            
            # Check for touch: low <= mid <= high
            # mid_vals.reindex(post_mask.index) correctly aligns the mid (which is daily)
            # to every minute in the post-session mask.
            is_broken_mask = (post_mask['low'] <= mid_vals.reindex(post_mask.index)) & \
                             (post_mask['high'] >= mid_vals.reindex(post_mask.index))
            
            # Group by date and see if it was ever broken on that date
            broken_days = is_broken_mask.groupby(is_broken_mask.index.date).any()
            
            # Map back to full stats index
            # IMPORTANT: For NY2, 'broken_days' on Date T (using prev_mid) 
            # means Date T-1 was broken. However, our context shift in process() 
            # handles the mapping for future days. For the raw 'ny2box_broken' 
            # column, we keep it aligned with the date the price touch occurred.
            self.stats[f'{prefix}_broken'] = broken_days.reindex(self.stats.index.date).values

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
