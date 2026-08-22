"""Diagnose why variant1 gets so few trades and variant counts don't match NT8."""
import sys
from pathlib import Path
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)
import numpy as np
import pandas as pd
from scripts.libs_py.data.loader import DataLoader
from scripts.trading_framework.config.config_loader import load_config
from scripts.libs_py.data.resampler import resample_ohlcv
from scripts.libs_py.cisd import compute_cisd
from scripts.libs_py.fvg import compute_fvg
from scripts.libs_py.ifvg import compute_ifvg
from scripts.libs_py.bpr import compute_bpr
from scripts.strategies.ifvg_cisd.core.ifvg_cisd_strategy import IFVGCISDStrategy

config = load_config("scripts/trading_framework/config/sessions.yaml")
loader = DataLoader(config)
df = loader.load_enriched("NQ1")
df = df[(df.index >= "2025-06-01") & (df.index < "2026-04-01")].copy()
htf = resample_ohlcv(df, freq="5min")

# Compute all engines
cisd = compute_cisd(htf.copy())
fvg = compute_fvg(htf.copy())
bpr = compute_bpr(htf.copy(), align_to_base=False)
htf_full = htf.copy()
for col in fvg.columns:
    if col not in htf_full.columns:
        htf_full[col] = fvg[col]
ifvg = compute_ifvg(htf_full)

print(f"HTF bars: {len(htf)}")
print()

# Raw event counts
cisd_events = cisd[cisd["cisd_event"] != 0]
bull_cisd = (cisd["cisd_event"] == 1).sum()
bear_cisd = (cisd["cisd_event"] == -1).sum()
print(f"CISD events: {len(cisd_events)} (bull: {bull_cisd}, bear: {bear_cisd})")
print(f"FVG events: bull={(fvg['fvg_event']==1).sum()}, bear={(fvg['fvg_event']==-1).sum()}")
print(f"IFVG events: bull={(ifvg['ifvg_event']==1).sum()}, bear={(ifvg['ifvg_event']==-1).sum()}")
print(f"BPR events: {(bpr['bpr_event']!=0).sum()}")
print()

# Now trace the variant logic manually
# We need to track: leg state, FVG counts per leg, BPR/IFVG flags
cisd_event_arr = cisd["cisd_event"].values.astype(np.int8)
cisd_state_arr = cisd["cisd_state"].values.astype(np.int8)
fvg_event_arr = fvg["fvg_event"].values.astype(np.int8)
ifvg_event_arr = ifvg["ifvg_event"].values.astype(np.int8)
bpr_event_arr = bpr["bpr_event"].values.astype(np.int8)
bull_cisd_lvl = cisd["active_bull_cisd_level"].values.astype(np.float64)
bear_cisd_lvl = cisd["active_bear_cisd_level"].values.astype(np.float64)
htf_open = htf["open"].values
htf_high = htf["high"].values
htf_low = htf["low"].values
htf_close = htf["close"].values

regime = 0
leg_has_bpr = False
leg_has_ifvg = False
bull_fvg_count = 0
bear_fvg_count = 0
prior_bear_fvg = 0
prior_bull_fvg = 0
v2_triggered = False

# Count how many CISD flips have >=2 opposing FVGs
v1_candidates = 0
v2_candidates = 0
v1_bpr_candidates = 0
v1_ifvg_fvg_candidates = 0

# Track FVG counts at each CISD flip
flip_fvg_counts = []

for i in range(len(htf)):
    ce = cisd_event_arr[i]
    fe = fvg_event_arr[i]
    ie = ifvg_event_arr[i]
    be = bpr_event_arr[i]

    if ce == 1:
        crossed = bear_cisd_lvl[i-1] if i > 0 and not np.isnan(bear_cisd_lvl[i-1]) else np.nan
        prior_bear_fvg = bear_fvg_count
        flip_fvg_counts.append(("BULL", prior_bear_fvg, "bear_fvg"))
        regime = 1
        leg_has_bpr = False
        leg_has_ifvg = False
        bull_fvg_count = 0
        v2_triggered = False

        # Check v2 candidate
        if prior_bear_fvg >= 2:
            v2_candidates += 1
    elif ce == -1:
        prior_bull_fvg = bull_fvg_count
        flip_fvg_counts.append(("BEAR", prior_bull_fvg, "bull_fvg"))
        regime = -1
        leg_has_bpr = False
        leg_has_ifvg = False
        bear_fvg_count = 0
        v2_triggered = False

        if prior_bull_fvg >= 2:
            v2_candidates += 1
    else:
        regime = cisd_state_arr[i]

    if regime != 0:
        if fe == 1:
            bull_fvg_count += 1
        elif fe == -1:
            bear_fvg_count += 1
        if ie == 1 and regime == 1:
            leg_has_ifvg = True
        if ie == -1 and regime == -1:
            leg_has_ifvg = True
        if be != 0:
            leg_has_bpr = True

    # Check v1 candidates (at CISD trigger)
    if ce == 1 and (leg_has_bpr or (leg_has_ifvg and bull_fvg_count >= 1)):
        v1_candidates += 1
        if leg_has_bpr:
            v1_bpr_candidates += 1
        if leg_has_ifvg and bull_fvg_count >= 1:
            v1_ifvg_fvg_candidates += 1
    elif ce == -1 and (leg_has_bpr or (leg_has_ifvg and bear_fvg_count >= 1)):
        v1_candidates += 1
        if leg_has_bpr:
            v1_bpr_candidates += 1
        if leg_has_ifvg and bear_fvg_count >= 1:
            v1_ifvg_fvg_candidates += 1

print(f"V1 candidates (pre-risk-filter): {v1_candidates}")
print(f"  via BPR: {v1_bpr_candidates}")
print(f"  via IFVG+FVG: {v1_ifvg_fvg_candidates}")
print()
print(f"V2 candidates (pre-risk-filter): {v2_candidates}")
print()

# Show distribution of opposing FVG counts at each flip
print("FVG counts at CISD flips (opposing run):")
fc = [x[1] for x in flip_fvg_counts]
print(f"  Total flips: {len(fc)}")
print(f"  0 FVGs: {sum(1 for f in fc if f == 0)}")
print(f"  1 FVG:  {sum(1 for f in fc if f == 1)}")
print(f"  2 FVGs: {sum(1 for f in fc if f == 2)}")
print(f"  3+ FVGs: {sum(1 for f in fc if f >= 3)}")
print(f"  >=2 (v2 eligible): {sum(1 for f in fc if f >= 2)}")
print()

# Now run the actual strategy and check
s = IFVGCISDStrategy(ticker="NQ1")
for v in ["baseline", "variant1", "variant2"]:
    params = {"resample_tf": "5min", "filter_lunch": True, "max_trades_per_day": 2,
              "r_mult_tp1": 1.0, "r_mult_tp2": 2.5, "variant": v}
    if v == "baseline":
        params["strict_ifvg_only"] = True
    sig = s.hunt(df, params)
    longs = len(sig[sig.direction == "LONG"]) if len(sig) > 0 else 0
    shorts = len(sig[sig.direction == "SHORT"]) if len(sig) > 0 else 0
    print(f"{v}: {len(sig)} signals (LONG: {longs}, SHORT: {shorts})")
    if len(sig) > 0:
        print(f"  Risk: min={sig.risk_pts.min():.1f} max={sig.risk_pts.max():.1f} mean={sig.risk_pts.mean():.1f}")
        # Show how many were filtered by RTH
        st = pd.to_datetime(sig.signal_time)
        in_rth = st.dt.hour.between(9, 15)
        print(f"  In RTH (09-15): {in_rth.sum()}, Out: {(~in_rth).sum()}")