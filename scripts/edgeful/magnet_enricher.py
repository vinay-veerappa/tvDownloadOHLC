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

    def enrich(self, macro_df: pd.DataFrame, instrument: str):
        """
        Main enrichment logic for Sprint 2.
        - Adds HOD/LOD metrics (PDH, PDL)
        - Adds proximity to nearest NWOG/NDOG
        - Adds relative distance to multi-scale pivots
        """
        if macro_df.empty:
            return macro_df
            
        df = macro_df.copy()
        instrument_clean = instrument.replace("1", "") # ES1 -> ES
        
        # 1. HOD/LOD (Previous Day High/Low)
        hod_lod_data = self.load_hod_lod_levels(instrument)
        if hod_lod_data:
            sorted_dates = sorted(hod_lod_data.keys())
            
            def get_pdh_pdl(row):
                curr_date = str(row['trading_date'])[:10]
                # Find last date before current
                prior_dates = [d for d in sorted_dates if d < curr_date]
                if not prior_dates:
                    return None, None
                pd_data = hod_lod_data[prior_dates[-1]]
                return pd_data.get('daily_high'), pd_data.get('daily_low')

            levels = df.apply(get_pdh_pdl, axis=1)
            df['pdh'], df['pdl'] = zip(*levels)
            
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
                
                def get_nearest_gap(row):
                    curr_date = str(row['trading_date'])[:10]
                    # Only consider gaps formed BEFORE current session
                    valid_gaps = gap_df[gap_df['date'] < curr_date]
                    if valid_gaps.empty:
                        return None, None
                    
                    # Distance to each gap
                    dists = (valid_gaps['price'] - row['open']).abs()
                    idx = dists.idxmin()
                    return valid_gaps.loc[idx, 'price'], valid_gaps.loc[idx, 'type']
                
                gap_res = df.apply(get_nearest_gap, axis=1)
                df['nearest_gap_price'], df['nearest_gap_type'] = zip(*gap_res)
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
