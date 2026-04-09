import pandas as pd
import json
import logging
from pathlib import Path
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MagnetEnricher:
    def __init__(self, data_root: str = "data"):
        self.data_root = Path(data_root)
        self.derived_root = self.data_root / "derived"
        self._gaps_cache = None
        self._hod_lod_cache = {}

    def load_gaps(self):
        """Loads NWOG/NDOG gaps from ict_nwog_ndog.json."""
        if self._gaps_cache is not None:
            return self._gaps_cache
            
        path = self.derived_root / "ict_nwog_ndog.json"
        if not path.exists():
            logger.warning(f"Gap file not found at {path}")
            return {}
        with open(path, 'r') as f:
            self._gaps_cache = json.load(f)
        return self._gaps_cache

    def load_hod_lod_levels(self, instrument: str):
        """Loads HTF PDH/PDL from {instrument}_daily_hod_lod.json."""
        if instrument in self._hod_lod_cache:
            return self._hod_lod_cache[instrument]
            
        path = self.data_root / f"{instrument}_daily_hod_lod.json"
        if not path.exists():
            # Try to find in derived if not in root
            path = self.derived_root / f"{instrument}_daily_hod_lod.json"
            
        if not path.exists():
            logger.warning(f"HOD/LOD file not found for {instrument} at {path}")
            return {}
            
        with open(path, 'r') as f:
            data = json.load(f)
            self._hod_lod_cache[instrument] = data
        return data

    def enrich(self, macro_df: pd.DataFrame, bars_in: pd.DataFrame = None, instrument: str = None):
        """
        Main enrichment logic for Sprint 2.
        - Adds HOD/LOD metrics (PDH, PDL)
        - Adds proximity to nearest NWOG/NDOG
        - Adds relative distance to multi-scale pivots
        """
        if macro_df.empty:
            return macro_df
            
        df = macro_df.copy()
        inst = instrument if instrument else (df['instrument'].iloc[0] if 'instrument' in df.columns else None)
        if not inst: return df
        
        # 1. HOD/LOD (Previous Day High/Low)
        hod_lod_data = self.load_hod_lod_levels(inst)
        if hod_lod_data:
            # Vectorized Lookup: Map to trading_date
            levels_df = pd.DataFrame.from_dict(hod_lod_data, orient='index').reset_index()
            levels_df = levels_df.rename(columns={'index': 'trading_date'})
            levels_df['trading_date'] = pd.to_datetime(levels_df['trading_date']).astype('datetime64[ns]')
            
            # We need the PREVIOUS day's levels
            levels_df = levels_df.sort_values('trading_date')
            levels_df['pdh'] = levels_df['daily_high'].shift(1)
            levels_df['pdl'] = levels_df['daily_low'].shift(1)
            
            df = df.merge(levels_df[['trading_date', 'pdh', 'pdl']], on='trading_date', how='left')
            
            # Distances
            df['dist_to_pdh_pct'] = (df['pdh'] - df['open']) / df['open'] * 100
            df['dist_to_pdl_pct'] = (df['open'] - df['pdl']) / df['open'] * 100

        # 2. NWOG/NDOG Gaps
        gap_data = self.load_gaps().get(instrument, {})
        if gap_data:
            # Flatten gaps into a list for proximity search
            # We care about 'close_price' as the gap-fill target
            all_gaps = []
            for gtype in ['NWOG', 'NDOG']:
                for g in gap_data.get(gtype, []):
                    all_gaps.append({
                        'price': g['close_price'],
                        'date': g['session_date'],
                        'type': gtype
                    })
            
            if all_gaps:
                gap_df = pd.DataFrame(all_gaps)
                gap_df['date'] = pd.to_datetime(gap_df['date']).astype('datetime64[ns]')
                
                # Vectorized Proximity: 
                # For each macro, we need the nearest gap formed BEFORE the trading_date.
                # Since gap_df is small (hundreds), we can use a clever broadcast.
                macro_dates = df['trading_date'].unique()
                
                # Precompute nearest gap for each unique date
                date_to_gap = {}
                for d in macro_dates:
                    valid_gaps = gap_df[gap_df['date'] < d]
                    if not valid_gaps.empty:
                        # We need to find nearest to SOME price. Since 'open' varies, 
                        # we'll do the final distance calc per row, but we've narrowed the gap pool.
                        date_to_gap[d] = valid_gaps
                
                # Final Vectorized Calc
                # To keep it O(N), we'll use the fact that gap_df is small.
                # If gap_df was large, we'd use a KD-Tree or BallTree.
                # For ~200 gaps, a broadcasted subtraction is fine.
                def fast_gap_lookup(group):
                    d = group.name
                    valid = date_to_gap.get(d)
                    if valid is None:
                        group['nearest_gap_price'] = np.nan
                        group['nearest_gap_type'] = None
                        return group
                        
                    # Prices as 1D arrays
                    macro_opens = group['open'].values[:, np.newaxis]
                    gap_prices = valid['price'].values
                    
                    # Distances (MacroRows x GapRows)
                    dists = np.abs(macro_opens - gap_prices)
                    nearest_idx = np.argmin(dists, axis=1)
                    
                    group['nearest_gap_price'] = gap_prices[nearest_idx]
                    group['nearest_gap_type'] = valid['type'].values[nearest_idx]
                    return group

                df = df.groupby('trading_date', group_keys=False).apply(fast_gap_lookup)
                df['dist_to_gap_pct'] = (df['nearest_gap_price'] - df['open']) / df['open'] * 100

        # 3. Structural Distances (Pivots)
        # We already have ph_5, ph_13, ph_21 columns from extract_macros
        for length in [5, 13, 21]:
            ph_col = f'ph_{length}'
            pl_col = f'pl_{length}'
            if ph_col in df.columns:
                df[f'dist_to_ph{length}_pct'] = (df[ph_col] - df['open']) / df['open'] * 100
            if pl_col in df.columns:
                df[f'dist_to_pl{length}_pct'] = (df[pl_col] - df['open']) / df['open'] * 100

        # 4. Global Position (Optional HOD/LOD of current day)
        # This requires knowing HOD/LOD SO FAR. 
        # For simplicity in Sprint 2, we skip developing HOD/LOD 
        # but keep PDH/PDL as the primary anchors.

        return df

if __name__ == "__main__":
    # Test stub
    enricher = MagnetEnricher()
    print("MagnetEnricher initialized.")
