"""Test geometric filtering of FVGs and OBs."""
import pandas as pd
from scripts.trader.signals.ict_data_loader import (
    load_imbalances, load_orderblocks, load_liquidity,
    load_imbalances_filtered, load_orderblocks_filtered, load_liquidity_filtered,
)
from datetime import date

session_date = date(2026, 8, 4)
current_price = 7792.0

# Test FVGs
fvg_all = load_imbalances("ES1", timeframe="5m", session_date=session_date)
fvg_filtered = load_imbalances_filtered("ES1", current_price, timeframe="5m", session_date=session_date)
print(f"FVGs: {len(fvg_all)} total -> {len(fvg_filtered)} filtered")

# Test OBs
ob_all = load_orderblocks("ES1", timeframe="5m", session_date=session_date)
ob_filtered = load_orderblocks_filtered("ES1", current_price, timeframe="5m", session_date=session_date)
print(f"OBs: {len(ob_all)} total -> {len(ob_filtered)} filtered")

# Test liquidity
liq_all = load_liquidity("ES1", timeframe="5m", session_date=session_date)
liq_filtered = load_liquidity_filtered("ES1", current_price, timeframe="5m", session_date=session_date)
print(f"Liquidity: {len(liq_all)} total -> {len(liq_filtered)} filtered")