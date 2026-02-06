"""
Candle Science Service - Analyzes 3-candle patterns from OHLC data
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from api.services.data_loader import load_parquet

class CandleScienceService:
    @staticmethod
    def calculate_stats(
        ticker: str,
        timeframe: str,
        filters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Calculate candle science statistics for a given ticker and timeframe.
        Filter-then-Compute Methodology:
        1. Load all data
        2. Filter triplets based on ALL criteria
        3. Compute stats on the filtered subset
        """
        df = load_parquet(ticker, timeframe)
        if df is None or df.empty:
            return {"error": f"No data found for {ticker} {timeframe}"}

        df['datetime'] = pd.to_datetime(df['time'], unit='s')
        
        # 1. Build Triplets (C1, C2, C3)
        # Shift to align C1, C2 to current C3 row
        df['c1_open'] = df['open'].shift(2)
        df['c1_high'] = df['high'].shift(2)
        df['c1_low'] = df['low'].shift(2)
        df['c1_close'] = df['close'].shift(2)
        df['c1_time'] = df['datetime'].shift(2)
        
        df['c2_open'] = df['open'].shift(1)
        df['c2_high'] = df['high'].shift(1)
        df['c2_low'] = df['low'].shift(1)
        df['c2_close'] = df['close'].shift(1)
        
        df['c3_open'] = df['open']
        df['c3_high'] = df['high']
        df['c3_low'] = df['low']
        df['c3_close'] = df['close']

        # Drop invalid rows (first 2 rows)
        df = df.dropna(subset=['c1_open', 'c1_high', 'c1_low', 'c1_close'])

        # 2. Apply Filters (Reference & Time)
        if filters:
            # Time Filters
            if filters.get('years'):
                df = df[df['c1_time'].dt.year.isin([int(y) for y in filters['years']])]
            if filters.get('months'):
                df = df[df['c1_time'].dt.month.isin([int(m) for m in filters['months']])]
            if filters.get('daysOfWeek'):
                df = df[df['c1_time'].dt.dayofweek.isin([int(d) for d in filters['daysOfWeek']])]
            if filters.get('c1OpenHours'):
                df = df[df['c1_time'].dt.hour.isin([int(h) for h in filters['c1OpenHours']])]

            # Reference Filters (C1, C2, C3 relationships)
            # C1 Direction
            if filters.get('c1Direction') and filters['c1Direction'] != 'all':
                is_bull = df['c1_close'] >= df['c1_open']
                df = df[is_bull] if filters['c1Direction'] == 'bull' else df[~is_bull]
            
            # C2 Direction
            if filters.get('c2Direction') and filters['c2Direction'] != 'all':
                is_bull = df['c2_close'] >= df['c2_open']
                df = df[is_bull] if filters['c2Direction'] == 'bull' else df[~is_bull]

            # C2 vs C1
            if filters.get('c2HighVsC1High') and filters['c2HighVsC1High'] != 'all':
                mask = df['c2_high'] > df['c1_high']
                df = df[mask] if filters['c2HighVsC1High'] == 'above' else df[~mask]
            
            if filters.get('c2HighVsC1Low') and filters['c2HighVsC1Low'] != 'all':
                mask = df['c2_high'] > df['c1_low']
                df = df[mask] if filters['c2HighVsC1Low'] == 'above' else df[~mask]

            if filters.get('c2LowVsC1Low') and filters['c2LowVsC1Low'] != 'all':
                mask = df['c2_low'] > df['c1_low']
                df = df[mask] if filters['c2LowVsC1Low'] == 'above' else df[~mask]
            
            if filters.get('c2LowVsC1High') and filters['c2LowVsC1High'] != 'all':
                mask = df['c2_low'] > df['c1_high']
                df = df[mask] if filters['c2LowVsC1High'] == 'above' else df[~mask]

            if filters.get('c2CloseVsC1High') and filters['c2CloseVsC1High'] != 'all':
                mask = df['c2_close'] > df['c1_high']
                df = df[mask] if filters['c2CloseVsC1High'] == 'above' else df[~mask]
            
            if filters.get('c2CloseVsC1Low') and filters['c2CloseVsC1Low'] != 'all':
                mask = df['c2_close'] > df['c1_low']
                df = df[mask] if filters['c2CloseVsC1Low'] == 'above' else df[~mask]
            
            if filters.get('c2CloseVsC1Close') and filters['c2CloseVsC1Close'] != 'all':
                mask = df['c2_close'] > df['c1_close']
                df = df[mask] if filters['c2CloseVsC1Close'] == 'above' else df[~mask]

            if filters.get('c2CloseVsC1Open') and filters['c2CloseVsC1Open'] != 'all':
                mask = df['c2_close'] > df['c1_open']
                df = df[mask] if filters['c2CloseVsC1Open'] == 'above' else df[~mask]

            if filters.get('c2OpenVsC1Close') and filters['c2OpenVsC1Close'] != 'all':
                mask = df['c2_open'] > df['c1_close']
                df = df[mask] if filters['c2OpenVsC1Close'] == 'above' else df[~mask]

            if filters.get('c2OpenVsC1Open') and filters['c2OpenVsC1Open'] != 'all':
                mask = df['c2_open'] > df['c1_open']
                df = df[mask] if filters['c2OpenVsC1Open'] == 'above' else df[~mask]

            # C3 Open Filters
            if filters.get('c3OpenVsC2High') and filters['c3OpenVsC2High'] != 'all':
                mask = df['c3_open'] > df['c2_high']
                df = df[mask] if filters['c3OpenVsC2High'] == 'above' else df[~mask]

            if filters.get('c3OpenVsC2Low') and filters['c3OpenVsC2Low'] != 'all':
                mask = df['c3_open'] > df['c2_low']
                df = df[mask] if filters['c3OpenVsC2Low'] == 'above' else df[~mask]

            if filters.get('c3OpenVsC2Close') and filters['c3OpenVsC2Close'] != 'all':
                mask = df['c3_open'] > df['c2_close']
                df = df[mask] if filters['c3OpenVsC2Close'] == 'above' else df[~mask]

            if filters.get('c3OpenVsC2Open') and filters['c3OpenVsC2Open'] != 'all':
                mask = df['c3_open'] > df['c2_open']
                df = df[mask] if filters['c3OpenVsC2Open'] == 'above' else df[~mask]

        n = len(df)
        if n == 0:
            return {"sample_count": 0, "message": "No data matches the selected filters.", "error": "No matching patterns found"}

        # 3. Compute Stats
        def get_prob(condition):
            if n == 0: return 0
            return round((condition.sum() / n) * 100, 1)

        def get_comparison_stats(values, refs, prices):
            """
            Calculate detailed MFE/MAE style stats separating Above/Below outcomes.
            """
            diff = values - refs
            safe_prices = prices.replace(0, np.nan)
            pct_diff = (diff / safe_prices) * 100
            
            # Mask for Above and Below
            mask_above = values > refs
            mask_below = ~mask_above
            
            # Percentages
            above_pct = get_prob(mask_above)
            below_pct = get_prob(mask_below)
            
            # Detailed Stats for Above
            dist_above = pct_diff[mask_above]
            above_stats = {
                "count": int(len(dist_above)),
                "mean": round(float(dist_above.mean()), 4) if len(dist_above) > 0 else 0,
                "p30": round(float(dist_above.quantile(0.3)), 4) if len(dist_above) > 0 else 0,
                "median": round(float(dist_above.median()), 4) if len(dist_above) > 0 else 0,
                "p70": round(float(dist_above.quantile(0.7)), 4) if len(dist_above) > 0 else 0,
                "p90": round(float(dist_above.quantile(0.9)), 4) if len(dist_above) > 0 else 0
            }
            
            # Detailed Stats for Below
            dist_below = pct_diff[mask_below]
            below_stats = {
                "count": int(len(dist_below)),
                "mean": round(float(dist_below.mean()), 4) if len(dist_below) > 0 else 0,
                "p30": round(float(dist_below.quantile(0.3)), 4) if len(dist_below) > 0 else 0,
                "median": round(float(dist_below.median()), 4) if len(dist_below) > 0 else 0,
                "p70": round(float(dist_below.quantile(0.7)), 4) if len(dist_below) > 0 else 0,
                "p90": round(float(dist_below.quantile(0.9)), 4) if len(dist_below) > 0 else 0
            }

            return {
                "above": above_pct,
                "below": below_pct,
                "aboveStats": above_stats,
                "belowStats": below_stats
            }
        
        # Helper to get raw distribution for scatter plot
        def get_dist(series, reference_series, price_series):
            safe_prices = price_series.replace(0, np.nan)
            dist = ((series - reference_series) / safe_prices) * 100
            return dist.dropna().tolist()

        # Build Response Object
        stats = {
            "sample_count": n,
            "ticker": ticker,
            "timeframe": timeframe,
            "direction": {
                "c1": {"bull": get_prob(df['c1_close'] >= df['c1_open']), "bear": get_prob(df['c1_close'] < df['c1_open'])},
                "c2": {"bull": get_prob(df['c2_close'] >= df['c2_open']), "bear": get_prob(df['c2_close'] < df['c2_open'])},
                "c3": {"bull": get_prob(df['c3_close'] >= df['c3_open']), "bear": get_prob(df['c3_close'] < df['c3_open'])},
            },
            "high_wicks": {
                "c2_vs_c1": {
                    "high_vs_high": get_comparison_stats(df['c2_high'], df['c1_high'], df['c1_close']),
                    "high_vs_open": get_comparison_stats(df['c2_high'], df['c1_open'], df['c1_close']),
                },
                "c3_vs_c2": {
                    "high_vs_high": get_comparison_stats(df['c3_high'], df['c2_high'], df['c2_close']),
                    "high_vs_open": get_comparison_stats(df['c3_high'], df['c2_open'], df['c2_close']),
                }
            },
            "low_wicks": {
                "c2_vs_c1": {
                    "low_vs_low": get_comparison_stats(df['c2_low'], df['c1_low'], df['c1_close']),
                    "low_vs_open": get_comparison_stats(df['c2_low'], df['c1_open'], df['c1_close']),
                },
                "c3_vs_c2": {
                    "low_vs_low": get_comparison_stats(df['c3_low'], df['c2_low'], df['c2_close']),
                    "low_vs_open": get_comparison_stats(df['c3_low'], df['c2_open'], df['c2_close']),
                }
            },
            "body": {
                "c2_vs_c1": {
                    "close_vs_high": get_comparison_stats(df['c2_close'], df['c1_high'], df['c1_close']),
                    "close_vs_low": get_comparison_stats(df['c2_close'], df['c1_low'], df['c1_close']),
                    "close_vs_close": get_comparison_stats(df['c2_close'], df['c1_close'], df['c1_close']),
                    "close_vs_open": get_comparison_stats(df['c2_close'], df['c1_open'], df['c1_close']),
                },
                "c3_vs_c2": {
                    "close_vs_high": get_comparison_stats(df['c3_close'], df['c2_high'], df['c2_close']),
                    "close_vs_low": get_comparison_stats(df['c3_close'], df['c2_low'], df['c2_close']),
                    "close_vs_close": get_comparison_stats(df['c3_close'], df['c2_close'], df['c2_close']),
                    "close_vs_open": get_comparison_stats(df['c3_close'], df['c2_open'], df['c2_close']),
                }
            },
            "gaps": {
                "c2_vs_c1": {
                    "open_vs_close": get_comparison_stats(df['c2_open'], df['c1_close'], df['c1_close']),
                    "open_vs_open": get_comparison_stats(df['c2_open'], df['c1_open'], df['c1_close']),
                },
                "c3_vs_c2": {
                    "open_vs_close": get_comparison_stats(df['c3_open'], df['c2_close'], df['c2_close']),
                    "open_vs_open": get_comparison_stats(df['c3_open'], df['c2_open'], df['c2_close']),
                }
            },
            "distributions": {
                "c3_high_vs_c2_high": get_dist(df['c3_high'], df['c2_high'], df['c2_close']),
                "c3_high_vs_c2_open": get_dist(df['c3_high'], df['c2_open'], df['c2_close']),
                "c3_low_vs_c2_low": get_dist(df['c3_low'], df['c2_low'], df['c2_close']),
                "c3_low_vs_c2_open": get_dist(df['c3_low'], df['c2_open'], df['c2_close']),
                "c3_close_vs_c2_high": get_dist(df['c3_close'], df['c2_high'], df['c2_close']),
                "c3_close_vs_c2_low": get_dist(df['c3_close'], df['c2_low'], df['c2_close']),
                "c3_close_vs_c2_close": get_dist(df['c3_close'], df['c2_close'], df['c2_close']),
                "c3_close_vs_c2_open": get_dist(df['c3_close'], df['c2_open'], df['c2_close']),
            }
        }
        return stats

    @staticmethod
    def get_filter_options(ticker: str, timeframe: str) -> Dict[str, Any]:
        """Get available filter values for a specific ticker/timeframe."""
        df = load_parquet(ticker, timeframe)
        if df is None or df.empty:
            return {}

        df['datetime'] = pd.to_datetime(df['time'], unit='s')
        
        years = sorted(df['datetime'].dt.year.unique().tolist())
        months = sorted(df['datetime'].dt.month.unique().tolist())
        days_of_week = sorted(df['datetime'].dt.dayofweek.unique().tolist())
        hours = sorted(df['datetime'].dt.hour.unique().tolist())

        return {
            "years": [str(y) for y in years],
            "months": months,
            "daysOfWeek": days_of_week,
            "c1OpenHours": hours
        }
