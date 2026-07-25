"""Profile inside hunt() to find what's slow."""
import time, pandas as pd, numpy as np
from scripts.trading_framework.config.config_loader import load_config
from scripts.libs_py.data.loader import DataLoader
from scripts.utils.vectorized_indicators import VectorizedIndicators

config = load_config("scripts/trading_framework/config/sessions.yaml")
loader = DataLoader(config)
t0 = time.time()
df = loader.load_enriched("NQ1")
print(f"load: {time.time()-t0:.1f}s, shape: {df.shape}")

# Time df.copy()
t3 = time.time()
d = df.copy()
print(f"df.copy(): {time.time()-t3:.1f}s")

# Time FVG computation
t1 = time.time()
fvg = VectorizedIndicators.find_fvgs(df)
print(f"find_fvgs: {time.time()-t1:.1f}s, cols: {fvg.shape}")

# Time groupby operations
t2 = time.time()
d["trading_date"] = d.index.normalize()
ib_mask = (d.index.time >= pd.Timestamp("09:30").time()) & (d.index.time <= pd.Timestamp("10:15").time())
ib_data = d[ib_mask]
daily_ib_high = ib_data.groupby("trading_date")["high"].max()
daily_ib_low = ib_data.groupby("trading_date")["low"].min()
print(f"groupby IB: {time.time()-t2:.1f}s")

# Time mapping back
t4 = time.time()
d["ib_high"] = d["trading_date"].map(daily_ib_high)
d["ib_low"] = d["trading_date"].map(daily_ib_low)
print(f"map IB: {time.time()-t4:.1f}s")

# Time cummax operations
t5 = time.time()
d["has_broken_high"] = (d["high"] > d["ib_high"]).groupby(d["trading_date"]).cummax()
d["has_broken_low"] = (d["low"] < d["ib_low"]).groupby(d["trading_date"]).cummax()
print(f"cummax: {time.time()-t5:.1f}s")

# Time concat with FVG
t6 = time.time()
d2 = pd.concat([d, fvg], axis=1)
print(f"concat fvg: {time.time()-t6:.1f}s")