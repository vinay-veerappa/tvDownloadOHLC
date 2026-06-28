import sqlite3
import logging
import pandas as pd
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)

def _safe_to_datetime(series: pd.Series) -> pd.Series:
    """Helper to robustly parse ISO8601 strings or epoch ms timestamps to DatetimeSeries."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_datetime(series, unit='ms', utc=True)
    else:
        try:
            numeric_series = pd.to_numeric(series)
            return pd.to_datetime(numeric_series, unit='ms', utc=True)
        except Exception:
            return pd.to_datetime(series, utc=True)

class OptionsRegimeValidator:
    """
    High-performance options feature extraction layer.
    Ingests historical records directly from Prisma SQLite and maps them as structural feature tags.
    """
    TICKER_MAP = {
        "NQ1": "QQQ",
        "NQ": "QQQ",
        "MNQ": "QQQ",
        "ES1": "SPX",
        "ES": "SPX",
        "MES": "SPX"
    }

    def __init__(self, db_path: str | Path = "web/prisma/dev.db"):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found at {self.db_path}")

    def _fetch_gex_snapshots(self, ticker: str) -> pd.DataFrame:
        mapped_ticker = self.TICKER_MAP.get(ticker, ticker)
        query = """
            SELECT timestamp, totalGex, totalGexDeltaAdj, regimeLabel, opening_gap_target, gammaMagnet
            FROM GexSnapshot
            WHERE ticker = ?
            ORDER BY timestamp ASC
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql(query, conn, params=(mapped_ticker,))
        except Exception:
            # Fallback wrapper if database schema hasn't run migrations for opening_gap_target yet
            query = """
                SELECT timestamp, totalGex, totalGexDeltaAdj, regimeLabel, gammaMagnet
                FROM GexSnapshot
                WHERE ticker = ?
                ORDER BY timestamp ASC
            """
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql(query, conn, params=(mapped_ticker,))
            df['opening_gap_target'] = np.nan
        
        if not df.empty:
            df['datetime'] = _safe_to_datetime(df['timestamp']).dt.tz_convert('US/Eastern')
            df.set_index('datetime', inplace=True)
            df.drop(columns=['timestamp'], inplace=True)
        return df

    def _fetch_macro_snapshots(self, ticker: str) -> pd.DataFrame:
        query_full = """
            SELECT tradingDate, zeroGamma, zero_gamma_delta_adj, spotPrice, volatility_risk_premium
            FROM MacroSnapshot
            WHERE ticker = ?
            ORDER BY tradingDate ASC
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql(query_full, conn, params=(ticker,))
        except Exception:
            # Fallback if zero_gamma_delta_adj is missing from the DB schema
            query_fallback = """
                SELECT tradingDate, zeroGamma, spotPrice, volatility_risk_premium
                FROM MacroSnapshot
                WHERE ticker = ?
                ORDER BY tradingDate ASC
            """
            try:
                with sqlite3.connect(self.db_path) as conn:
                    df = pd.read_sql(query_fallback, conn, params=(ticker,))
                df['zero_gamma_delta_adj'] = np.nan
            except Exception:
                # Absolute fallback if even volatility_risk_premium is missing (e.g. unmigrated DB)
                query_base = """
                    SELECT tradingDate, zeroGamma, spotPrice
                    FROM MacroSnapshot
                    WHERE ticker = ?
                    ORDER BY tradingDate ASC
                """
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        df = pd.read_sql(query_base, conn, params=(ticker,))
                    df['zero_gamma_delta_adj'] = np.nan
                    df['volatility_risk_premium'] = np.nan
                except Exception:
                    df = pd.DataFrame(columns=['tradingDate', 'zeroGamma', 'zero_gamma_delta_adj', 'spotPrice', 'volatility_risk_premium'])
        
        if not df.empty:
            df['tradingDate'] = _safe_to_datetime(df['tradingDate']).dt.tz_convert('US/Eastern').dt.normalize()
            df.set_index('tradingDate', inplace=True)
        return df

    def _fetch_expected_moves(self, ticker: str) -> pd.DataFrame:
        mapped_ticker = self.TICKER_MAP.get(ticker, ticker)
        query = """
            SELECT date, openPrice, emStraddle
            FROM RthExpectedMove
            WHERE ticker = ?
            ORDER BY date ASC
        """
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql(query, conn, params=(mapped_ticker,))
        
        if not df.empty:
            df['date'] = _safe_to_datetime(df['date']).dt.tz_convert('US/Eastern').dt.normalize()
            df.set_index('date', inplace=True)
        return df

    def vectorize_features(self, df_ohlc: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """
        Appends options regime feature tags to a 1-minute OHLC DataFrame.
        Assumes df_ohlc has a tz-aware 'US/Eastern' DatetimeIndex.
        """
        logger.info(f"Vectorizing options features for {ticker}...")
        df = df_ohlc[df_ohlc.index.notnull()].copy().sort_index()
        orig_index = df.index
        
        mapped_ticker = self.TICKER_MAP.get(ticker, ticker)
        gex_df = self._fetch_gex_snapshots(ticker)
        if not gex_df.empty:
            gex_df = gex_df[gex_df.index.notnull()].sort_index()
        
        macro_df = self._fetch_macro_snapshots(ticker)
        if macro_df.empty:
            macro_df = self._fetch_macro_snapshots(mapped_ticker)
            
        em_df = self._fetch_expected_moves(ticker)

        # Sort and deduplicate database frames by index to prevent duplicate rows on merge
        if not gex_df.empty:
            gex_df = gex_df[~gex_df.index.duplicated(keep='first')].sort_index()
        if not macro_df.empty:
            macro_df = macro_df[~macro_df.index.duplicated(keep='first')].sort_index()
        if not em_df.empty:
            em_df = em_df[~em_df.index.duplicated(keep='first')].sort_index()

        # Merge GexSnapshot data as-of minute (backward match to prevent lookahead)
        if not gex_df.empty:
            df = pd.merge_asof(
                df, 
                gex_df[['totalGex', 'totalGexDeltaAdj', 'regimeLabel', 'opening_gap_target', 'gammaMagnet']],
                left_index=True, 
                right_index=True, 
                direction='backward'
            )
        else:
            df['totalGex'] = np.nan
            df['totalGexDeltaAdj'] = np.nan
            df['regimeLabel'] = np.nan
            df['opening_gap_target'] = np.nan
            df['gammaMagnet'] = np.nan

        # Merge Macro (Daily) Data
        df['trading_date'] = df.index.normalize()
        if not macro_df.empty:
            cols_to_merge = [c for c in ['zeroGamma', 'zero_gamma_delta_adj', 'spotPrice', 'volatility_risk_premium'] if c in macro_df.columns]
            df = df.merge(macro_df[cols_to_merge], left_on='trading_date', right_index=True, how='left')
            # Dynamic scaling if macro spot is in a different price scale
            if 'open' in df.columns:
                daily_open = df.groupby('trading_date')['open'].transform('first')
                sample_ratio = (daily_open / df['spotPrice']).dropna()
                if not sample_ratio.empty and (sample_ratio.iloc[0] > 1.5 or sample_ratio.iloc[0] < 0.6):
                    scale_factor = daily_open / df['spotPrice'].replace(0, np.nan)
                    df['zeroGamma'] = df['zeroGamma'] * scale_factor
                    df['zero_gamma_delta_adj'] = df['zero_gamma_delta_adj'] * scale_factor
        else:
            df['zeroGamma'] = np.nan
            df['zero_gamma_delta_adj'] = np.nan
            df['volatility_risk_premium'] = np.nan

        # Merge Expected Move (Daily) Data
        if not em_df.empty:
            df = df.merge(em_df[['openPrice', 'emStraddle']], left_on='trading_date', right_index=True, how='left', suffixes=('', '_em'))
            # Dynamic scaling of Expected Move straddle based on relative open price difference
            if 'open' in df.columns and 'openPrice' in df.columns:
                daily_open = df.groupby('trading_date')['open'].transform('first')
                em_pct = df['emStraddle'] / df['openPrice'].replace(0, np.nan)
                df['emStraddle'] = em_pct * daily_open
                df['openPrice'] = daily_open
        else:
            df['openPrice'] = np.nan
            df['emStraddle'] = np.nan

        # Save index to prevent any pandas merge realignment issues
        df['orig_index'] = df.index

        # Stitch the Parquet Matrix (Market Friction Matrix)
        friction_path = Path("data/derived/market_friction_matrix.parquet")
        if friction_path.exists():
            try:
                friction_df = pd.read_parquet(friction_path)
                if not friction_df.empty:
                    friction_df['date_key'] = friction_df['date_key'].astype(str)
                    df['date_key'] = df['orig_index'].dt.strftime('%Y-%m-%d')
                    
                    ticker_filter = [ticker, mapped_ticker]
                    ticker_friction = friction_df[friction_df['ticker'].isin(ticker_filter)]
                    
                    if not ticker_friction.empty:
                        ticker_friction = ticker_friction.drop_duplicates(subset=['date_key'])
                        cols_to_join = [col for col in ticker_friction.columns if col != 'ticker']
                        df = df.merge(ticker_friction[cols_to_join], on='date_key', how='left')
                    else:
                        for col in ['dist_21_ema_pct', 'dist_200_sma_pct', 'vix_close', 'vvix_close']:
                            df[col] = np.nan
                else:
                    for col in ['dist_21_ema_pct', 'dist_200_sma_pct', 'vix_close', 'vvix_close']:
                        df[col] = np.nan
            except Exception as e:
                logger.error(f"Failed to stitch market friction matrix: {e}", exc_info=True)
                for col in ['dist_21_ema_pct', 'dist_200_sma_pct', 'vix_close', 'vvix_close']:
                    df[col] = np.nan
        else:
            for col in ['dist_21_ema_pct', 'dist_200_sma_pct', 'vix_close', 'vvix_close']:
                df[col] = np.nan

        # Restore index from the orig_index column
        if 'orig_index' in df.columns:
            df.set_index('orig_index', inplace=True)
            df.index.name = None

        # Restore original index to preserve time-series index structure
        df.index = orig_index

        # 1. total_dealer_gamma
        df['total_dealer_gamma'] = df['totalGexDeltaAdj']

        # 2. is_track_b_active
        df['is_track_b_active'] = (
            df['regimeLabel'].isin(['PINNED', 'BATTLE_ZONE']) & 
            (df['totalGex'] > 0)
        )

        # 3. Adaptive Invalidation Flip Check (Uses high-precision line with standard fallback)
        df['active_flip_line'] = df['zero_gamma_delta_adj'].fillna(df['zeroGamma'])
        df['is_under_flip_line'] = df['close'] < df['active_flip_line']

        # 4. [NEW] Opening Gap Target Real-Time Filled Engine
        df['ogt_is_filled'] = False
        if 'opening_gap_target' in df.columns:
            # Calculate intraday fill states per day without lookahead leaks
            for day, group in df.groupby('trading_date'):
                ogt = group['opening_gap_target'].iloc[0]
                if pd.notna(ogt) and ogt > 0:
                    # Find out exactly when price crossed the target line
                    condition = (group['low'] <= ogt) & (group['high'] >= ogt)
                    if condition.any():
                        fill_time = group[condition].index[0]
                        df.loc[(df['trading_date'] == day) & (df.index >= fill_time), 'ogt_is_filled'] = True

        logger.info("Options regime features appended successfully.")
        return df

    def generate_regime_report(self, df: pd.DataFrame):
        """
        Summarizes performance using professional quantitative daytrading criteria.
        """
        # Filter to the active options period to calculate meaningful scorecard metrics
        if 'total_dealer_gamma' in df.columns:
            df_active = df.dropna(subset=['total_dealer_gamma']).copy()
            if not df_active.empty:
                df = df_active

        # Strict RTH Filtering
        df = df.between_time('09:30', '16:00').copy()

        print("="*68)
        print("OPTIONS MARKET STRUCTURE QUANT SCORECARD")
        print("="*68)

        # 1. EM Hold Rate (Intraday Acceptance Definition)
        if 'openPrice' in df.columns and 'emStraddle' in df.columns:
            df['upper_bound'] = df['openPrice'] + df['emStraddle']
            df['lower_bound'] = df['openPrice'] - df['emStraddle']
            
            daily_metrics = []
            for day, group in df.groupby('trading_date'):
                group = group.dropna(subset=['upper_bound', 'lower_bound'])
                if group.empty: continue
                
                u_bound = group['upper_bound'].iloc[0]
                l_bound = group['lower_bound'].iloc[0]
                
                # Check if the boundaries were tested intraday
                tested_upper = (group['high'] >= u_bound).any()
                tested_lower = (group['low'] <= l_bound).any()
                
                if tested_upper or tested_lower:
                    # Intraday Acceptance check: Did a 5-minute chunk close past the boundary?
                    df_5m = group['close'].resample('5min').last()
                    accepted_outside = (df_5m > u_bound).any() or (df_5m < l_bound).any()
                    held = not accepted_outside
                    daily_metrics.append(held)

            if daily_metrics:
                tested_sessions = len(daily_metrics)
                held_sessions = sum(daily_metrics)
                hold_rate = (held_sessions / tested_sessions) * 100
                print(f"- Expected Move 1.0-sigma Rejection Hold Rate:  {hold_rate:.2f}% ({held_sessions}/{tested_sessions} tested session spikes held)")
            else:
                print("- Expected Move 1.0-sigma Rejection Hold Rate:  N/A")

        # 2. Flip Line Vol Expansion (Log Returns)
        if 'is_under_flip_line' in df.columns:
            # 1-minute log returns (groupby day to avoid overnight jumps)
            df['log_returns'] = np.log(df['close'] / df.groupby('trading_date')['close'].shift(1))
            
            std_above = df[df['is_under_flip_line'] == False]['log_returns'].std()
            std_below = df[df['is_under_flip_line'] == True]['log_returns'].std()
            
            if pd.notna(std_above) and std_above > 0 and pd.notna(std_below):
                vol_multiplier = std_below / std_above
                print(f"- Zero Gamma Volatility Expansion Factor:  {vol_multiplier:.2f}x (Speed below vs above)")
            else:
                print("- Zero Gamma Volatility Expansion Factor:  N/A")

        # 3. Forward-Looking OGT Benchmark
        if 'opening_gap_target' in df.columns and 'ogt_is_filled' in df.columns:
            total_gap_days = 0
            filled_gap_days = 0
            
            for day, group in df.groupby('trading_date'):
                ogt = group['opening_gap_target'].iloc[0]
                if pd.notna(ogt) and ogt > 0:
                    open_px = group['open'].iloc[0]
                    if abs(open_px - ogt) >= (open_px * 0.001):
                        total_gap_days += 1
                        if group['ogt_is_filled'].any():
                            filled_gap_days += 1
            
            if total_gap_days > 0:
                ogt_rate = (filled_gap_days / total_gap_days) * 100
                print(f"- Opening Gap Target (OGT) Resolve Rate:     {ogt_rate:.2f}% ({filled_gap_days}/{total_gap_days} gap mornings resolved)")
            else:
                print("- Opening Gap Target (OGT) Resolve Rate:     N/A (Accumulating data records)")

        # 4. Strategy Mode Optimization Matrix (Dynamic)
        track_a_pct = "N/A"
        if 'is_under_flip_line' in df.columns:
            df['rolling_close_5'] = df.groupby('trading_date')['close'].transform(lambda x: x.rolling(5).mean())
            df_under = df[df['is_under_flip_line'] == True]
            if not df_under.empty:
                count_under = len(df_under)
                count_persist = len(df_under[df_under['close'] < df_under['rolling_close_5']])
                track_a_pct = f"{(count_persist / count_under) * 100:.1f}%"

        track_b_pct = "N/A"
        if 'is_track_b_active' in df.columns and 'gammaMagnet' in df.columns:
            df['dist_to_magnet'] = (df['close'] - df['gammaMagnet']).abs()
            df['forward_dist_15'] = df.groupby('trading_date')['dist_to_magnet'].shift(-15)
            
            df_track_b = df[(df['is_track_b_active'] == True) & (df['gammaMagnet'].notna())]
            df_valid_fwd = df_track_b.dropna(subset=['forward_dist_15'])
            
            if not df_valid_fwd.empty:
                count_total = len(df_valid_fwd)
                count_decreased = len(df_valid_fwd[df_valid_fwd['forward_dist_15'] < df_valid_fwd['dist_to_magnet']])
                track_b_pct = f"{(count_decreased / count_total) * 100:.1f}%"

        print("\n[EXECUTION PATH ALPHA OPTIMIZATION MATRIX]")
        print("-" * 68)
        print(f"{'Trading Strategy Profile':<28} | {'Dynamic Signal Integrity':<24}")
        print("-" * 68)
        print(f"{'Expansion Continuity (Track A)':<28} | {track_a_pct:<24}")
        print(f"{'Premium/Discount Fade (Track B)':<28} | {track_b_pct:<24}")
        print("="*68)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Options Regime Validator initialized for pre-built workspace execution.")