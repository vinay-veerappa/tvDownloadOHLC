"""Benchmark the optimized fresh mode."""
import sys, time
sys.path.insert(0, r'C:\Users\vinay\tvDownloadOHLC')

import pandas as pd
from scripts.strategies.ict.strategies.ict_fvg_cisd_rejection import ICTFVGCISDRejectionStrategy

data = pd.read_parquet(r'C:\Users\vinay\tvDownloadOHLC\data\ES1_1m.parquet')
data = data[data.index >= '2025-06-01']
print(f'Data: {len(data):,} bars')

strategy = ICTFVGCISDRejectionStrategy(ticker='ES1')

# Test fresh mode speed
params = {
    'htf_tf': '15m', 'ltf_tf': '5m',
    'require_rejection_fvg': False,
    'cisd_impl': 'sweep_open',
    'entry_method': 'cisd_close',
    'sl_method': 'htf_fvg_boundary',
    'tp_rr': 2, 'require_mss': False,
    'fvg_freshness': 'fresh',
    'use_precomputed': True,
}
t0 = time.time()
sig = strategy.hunt(data, params=params)
print(f'fresh: {len(sig)} signals in {time.time()-t0:.2f}s')

# Compare with multi
params['fvg_freshness'] = 'multi'
t0 = time.time()
sig_m = strategy.hunt(data, params=params)
print(f'multi: {len(sig_m)} signals in {time.time()-t0:.2f}s')

# Test delivery_series
params['fvg_freshness'] = 'fresh'
params['cisd_impl'] = 'delivery_series'
params['require_rejection_fvg'] = True
params['entry_method'] = '1st_fvg'
params['sl_method'] = 'swing_extreme'
params['require_mss'] = True
t0 = time.time()
sig_ds = strategy.hunt(data, params=params)
print(f'delivery_series+fresh: {len(sig_ds)} signals in {time.time()-t0:.2f}s')