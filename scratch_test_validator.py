import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add project root to sys.path
sys.path.insert(0, str(Path("c:/Users/vinay/tvDownloadOHLC").resolve()))

from scripts.libs_py.features.options_regime_validator import OptionsRegimeValidator

def main():
    validator = OptionsRegimeValidator("web/prisma/dev.db")
    
    # Generate some dummy OHLC data that overlaps with recent dates
    # We'll just generate from 2026-01-01 to 2026-06-30
    dates = pd.date_range(start="2026-06-01", end="2026-06-30", freq='1min', tz="US/Eastern")
    df = pd.DataFrame(index=dates)
    df['open'] = np.random.uniform(5000, 5100, len(df))
    df['high'] = df['open'] + np.random.uniform(0, 10, len(df))
    df['low'] = df['open'] - np.random.uniform(0, 10, len(df))
    df['close'] = df['open'] + np.random.uniform(-5, 5, len(df))
    
    ticker = "SPX"
    
    # Run the feature vectorizer
    df_features = validator.vectorize_features(df, ticker)
    
    # Generate the report
    validator.generate_regime_report(df_features)

if __name__ == "__main__":
    main()
