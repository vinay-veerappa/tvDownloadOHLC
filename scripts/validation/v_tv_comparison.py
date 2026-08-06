"""TradingView Live Comparison Script (Ground-Truth Verification)

Compares TradingView chart labels against python profiler calculations from fused parquet data.
"""
from pathlib import Path
import sys
import pandas as pd
import pytz
from datetime import datetime, time

REPO = Path(__file__).parent.parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.utils.fused_data_loader import load_fused_data

ET = pytz.timezone("America/New_York")

tv_values = {
    "PDH": 30074.00,
    "PDL": 29530.75,
    "PDM": 29802.50,
    "Globex_Open": 29569.50,
    "ASN_High": 29679.50,
    "ASN_Low": 29454.25,
    "ASN_OR_H": 29679.50,
    "ASN_OR_L": 29563.50,
    "ASN_OU": 29621.50,
    "Settlement": 29615.00,
}

print("\n==========================================================================")
print("   TRADINGVIEW MCP LIVE CHART LEVEL MATCHING & GROUND-TRUTH VERIFICATION")
print("==========================================================================")

df_1d = pd.read_parquet(REPO / "data" / "NQ1_1d.parquet")
if df_1d.index.tz is not None:
    df_1d.index = df_1d.index.tz_convert("US/Eastern")
else:
    df_1d.index = df_1d.index.tz_localize("UTC").tz_convert("US/Eastern")

match_days = df_1d[(df_1d["high"] == tv_values["PDH"]) | (df_1d["low"] == tv_values["PDL"])]
if not match_days.empty:
    target_date = match_days.index[0].date()
    print(f"Matched TradingView Previous Day (PDH={tv_values['PDH']}, PDL={tv_values['PDL']}) -> {target_date}")
    
    pdh_py = float(match_days.iloc[0]["high"])
    pdl_py = float(match_days.iloc[0]["low"])
    pdm_py = float((pdh_py + pdl_py) / 2.0)
    
    print(f"  - PDH Match:  TV = {tv_values['PDH']:.2f} | PY = {pdh_py:.2f} | Diff = {abs(tv_values['PDH'] - pdh_py):.2f}")
    print(f"  - PDL Match:  TV = {tv_values['PDL']:.2f} | PY = {pdl_py:.2f} | Diff = {abs(tv_values['PDL'] - pdl_py):.2f}")
    print(f"  - PDM Match:  TV = {tv_values['PDM']:.2f} | PY = {pdm_py:.2f} | Diff = {abs(tv_values['PDM'] - pdm_py):.2f}")

    # Search for Globex Open 29569.50 in 1m data
    df_1m = load_fused_data("NQ1", "1m")
    if df_1m.index.tz is not None:
        df_1m.index = df_1m.index.tz_convert("US/Eastern")
    else:
        df_1m.index = df_1m.index.tz_localize("UTC").tz_convert("US/Eastern")

    g_open_bars = df_1m[df_1m["open"] == tv_values["Globex_Open"]]
    if not g_open_bars.empty:
        print(f"\nFound Globex Open {tv_values['Globex_Open']} at timestamp: {g_open_bars.index[0]}")
        session_dt = g_open_bars.index[0].date()
        p12_start = pd.Timestamp(datetime.combine(session_dt, time(18, 0))).tz_localize(ET, ambiguous="NaT", nonexistent="NaT")
        p12_end = pd.Timestamp(datetime.combine(session_dt + pd.Timedelta(days=1), time(6, 0))).tz_localize(ET, ambiguous="NaT", nonexistent="NaT")

        p12_bars = df_1m[(df_1m.index >= p12_start) & (df_1m.index < p12_end)]
        if not p12_bars.empty:
            py_high = float(p12_bars["high"].max())
            py_low = float(p12_bars["low"].min())
            print(f"  - Session P12 Range: High={py_high:.2f} | Low={py_low:.2f}")
            print(f"  - TV Asia High Match: TV = {tv_values['ASN_High']:.2f} | PY = {py_high:.2f} | Diff = {abs(tv_values['ASN_High'] - py_high):.2f}")
            print(f"  - TV Asia Low Match:  TV = {tv_values['ASN_Low']:.2f} | PY = {py_low:.2f} | Diff = {abs(tv_values['ASN_Low'] - py_low):.2f}")

print("==========================================================================\n")
