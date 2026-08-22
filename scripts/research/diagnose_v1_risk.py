"""Check how many V1 candidates pass the bps risk filter."""
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

config = load_config("scripts/trading_framework/config/sessions.yaml")
loader = DataLoader(config)
df = loader.load_enriched("NQ1")
df = df[(df.index >= "2025-06-01") & (df.index < "2026-04-01")].copy()
htf = resample_ohlcv(df, freq="5min")

cisd = compute_cisd(htf.copy())
fvg = compute_fvg(htf.copy())
bpr = compute_bpr(htf.copy(), align_to_base=False)
htf_full = htf.copy()
for col in fvg.columns:
    if col not in htf_full.columns:
        htf_full[col] = fvg[col]
ifvg = compute_ifvg(htf_full)

cisd_event_arr = cisd["cisd_event"].values.astype(np.int8)
fvg_event_arr = fvg["fvg_event"].values.astype(np.int8)
ifvg_event_arr = ifvg["ifvg_event"].values.astype(np.int8)
bpr_event_arr = bpr["bpr_event"].values.astype(np.int8)
bull_cisd_lvl = cisd["active_bull_cisd_level"].values.astype(np.float64)
bear_cisd_lvl = cisd["active_bear_cisd_level"].values.astype(np.float64)
htf_open = htf["open"].values
htf_high = htf["high"].values
htf_low = htf["low"].values
htf_close = htf["close"].values
htf_index = htf.index

regime = 0
leg_has_bpr = False
leg_has_ifvg = False
bull_fvg_count = 0
bear_fvg_count = 0
prior_bear_fvg = 0
prior_bull_fvg = 0
v2_triggered = False
leg_origin_low = np.nan
leg_origin_high = np.nan
leg_cisd_level = np.nan

tick_size = 0.25
min_risk_bps = 2.0
max_risk_bps = 15.0

v1_details = []
v2_details = []

for i in range(len(htf)):
    ce = cisd_event_arr[i]
    fe = fvg_event_arr[i]
    ie = ifvg_event_arr[i]
    be = bpr_event_arr[i]
    o = htf_open[i]; h = htf_high[i]; l = htf_low[i]; c = htf_close[i]

    if ce == 1:
        crossed = bear_cisd_lvl[i-1] if i > 0 and not np.isnan(bear_cisd_lvl[i-1]) else np.nan
        prior_bear_fvg = bear_fvg_count
        regime = 1
        leg_origin_low = crossed
        leg_origin_high = np.nan
        # new armed level = bull_cisd_lvl[i]
        leg_cisd_level = bull_cisd_lvl[i] if not np.isnan(bull_cisd_lvl[i]) else o
        leg_has_bpr = False
        leg_has_ifvg = False
        bull_fvg_count = 0
        v2_triggered = False

        # V1 check
        if leg_has_bpr or (leg_has_ifvg and bull_fvg_count >= 1):
            entry = leg_cisd_level
            raw_stop = leg_origin_low - 2*tick_size if not np.isnan(leg_origin_low) else l - 2*tick_size
            if raw_stop >= entry:
                raw_stop = l - 2*tick_size
            risk = abs(entry - raw_stop)
            price_ref = c
            min_r = price_ref * min_risk_bps / 10000.0
            max_r = price_ref * max_risk_bps / 10000.0
            v1_details.append({
                "time": htf_index[i],
                "dir": "LONG",
                "entry": entry,
                "stop": raw_stop,
                "risk_pts": risk,
                "min_risk": min_r,
                "max_risk": max_r,
                "passed": min_r <= risk <= max_r,
                "reason": f"{'BPR' if leg_has_bpr else ''}{'+' if leg_has_bpr and leg_has_ifvg else ''}{'IFVG+FVG' if leg_has_ifvg else ''}",
                "crossed": crossed,
                "bull_fvg": bull_fvg_count,
            })

        # V2 check
        if prior_bear_fvg >= 2:
            entry = leg_cisd_level
            raw_stop = leg_origin_low - 2*tick_size if not np.isnan(leg_origin_low) else l - 2*tick_size
            if raw_stop >= entry:
                raw_stop = l - 2*tick_size
            risk = abs(entry - raw_stop)
            price_ref = c
            min_r = price_ref * min_risk_bps / 10000.0
            max_r = price_ref * max_risk_bps / 10000.0
            v2_details.append({
                "time": htf_index[i],
                "dir": "LONG",
                "entry": entry,
                "stop": raw_stop,
                "risk_pts": risk,
                "min_risk": min_r,
                "max_risk": max_r,
                "passed": min_r <= risk <= max_r,
                "prior_bear_fvg": prior_bear_fvg,
                "crossed": crossed,
            })

    elif ce == -1:
        crossed = bull_cisd_lvl[i-1] if i > 0 and not np.isnan(bull_cisd_lvl[i-1]) else np.nan
        prior_bull_fvg = bull_fvg_count
        regime = -1
        leg_origin_low = np.nan
        leg_origin_high = crossed
        leg_cisd_level = bear_cisd_lvl[i] if not np.isnan(bear_cisd_lvl[i]) else o
        leg_has_bpr = False
        leg_has_ifvg = False
        bear_fvg_count = 0
        v2_triggered = False

        # V1 check
        if leg_has_bpr or (leg_has_ifvg and bear_fvg_count >= 1):
            entry = leg_cisd_level
            raw_stop = leg_origin_high + 2*tick_size if not np.isnan(leg_origin_high) else h + 2*tick_size
            if raw_stop <= entry:
                raw_stop = h + 2*tick_size
            risk = abs(raw_stop - entry)
            price_ref = c
            min_r = price_ref * min_risk_bps / 10000.0
            max_r = price_ref * max_risk_bps / 10000.0
            v1_details.append({
                "time": htf_index[i],
                "dir": "SHORT",
                "entry": entry,
                "stop": raw_stop,
                "risk_pts": risk,
                "min_risk": min_r,
                "max_risk": max_r,
                "passed": min_r <= risk <= max_r,
                "crossed": crossed,
                "bear_fvg": bear_fvg_count,
            })

        # V2 check
        if prior_bull_fvg >= 2:
            entry = leg_cisd_level
            raw_stop = leg_origin_high + 2*tick_size if not np.isnan(leg_origin_high) else h + 2*tick_size
            if raw_stop <= entry:
                raw_stop = h + 2*tick_size
            risk = abs(raw_stop - entry)
            price_ref = c
            min_r = price_ref * min_risk_bps / 10000.0
            max_r = price_ref * max_risk_bps / 10000.0
            v2_details.append({
                "time": htf_index[i],
                "dir": "SHORT",
                "entry": entry,
                "stop": raw_stop,
                "risk_pts": risk,
                "min_risk": min_r,
                "max_risk": max_r,
                "passed": min_r <= risk <= max_r,
                "prior_bull_fvg": prior_bull_fvg,
                "crossed": crossed,
            })
    else:
        regime = cisd_event_arr[i]  # actually cisd_state

    if regime != 0:
        if fe == 1: bull_fvg_count += 1
        elif fe == -1: bear_fvg_count += 1
        if ie == 1 and regime == 1: leg_has_ifvg = True
        if ie == -1 and regime == -1: leg_has_ifvg = True
        if be != 0: leg_has_bpr = True

v1df = pd.DataFrame(v1_details)
v2df = pd.DataFrame(v2_details)

print(f"V1 candidates: {len(v1df)}")
print(f"  Passed risk filter: {v1df['passed'].sum() if len(v1df)>0 else 0}")
print(f"  Failed risk filter: {(~v1df['passed']).sum() if len(v1df)>0 else 0}")
if len(v1df) > 0:
    failed = v1df[~v1df["passed"]]
    print(f"  Failed reason breakdown:")
    too_big = (failed["risk_pts"] > failed["max_risk"]).sum()
    too_small = (failed["risk_pts"] < failed["min_risk"]).sum()
    print(f"    Risk > max_risk (15bps): {too_big}")
    print(f"    Risk < min_risk (2bps): {too_small}")
    print(f"  Risk distribution:")
    print(f"    min={v1df['risk_pts'].min():.1f} max={v1df['risk_pts'].max():.1f} mean={v1df['risk_pts'].mean():.1f}")
    print(f"    > max_risk: {(v1df['risk_pts'] > v1df['max_risk']).sum()}")
    print(f"  First 10 V1 candidates:")
    for _, r in v1df.head(10).iterrows():
        status = "PASS" if r["passed"] else f"FAIL(risk={r['risk_pts']:.1f} > {r['max_risk']:.1f})"
        print(f"    {r['time']}  {r['dir']}  entry={r['entry']:.2f} stop={r['stop']:.2f} risk={r['risk_pts']:.1f}  crossed={r['crossed']:.2f}  {status}")

print()
print(f"V2 candidates: {len(v2df)}")
print(f"  Passed risk filter: {v2df['passed'].sum() if len(v2df)>0 else 0}")
print(f"  Failed risk filter: {(~v2df['passed']).sum() if len(v2df)>0 else 0}")
if len(v2df) > 0:
    failed = v2df[~v2df["passed"]]
    print(f"  Failed reason breakdown:")
    too_big = (failed["risk_pts"] > failed["max_risk"]).sum()
    too_small = (failed["risk_pts"] < failed["min_risk"]).sum()
    print(f"    Risk > max_risk (15bps): {too_big}")
    print(f"    Risk < min_risk (2bps): {too_small}")
    print(f"  Risk distribution:")
    print(f"    min={v2df['risk_pts'].min():.1f} max={v2df['risk_pts'].max():.1f} mean={v2df['risk_pts'].mean():.1f}")
    print(f"    > max_risk: {(v2df['risk_pts'] > v2df['max_risk']).sum()}")