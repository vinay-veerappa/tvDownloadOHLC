import os
from pathlib import Path

# ==========================================
# Path Configuration (ADR-006, ADR-008)
# ==========================================
OHLCV_DATA_DIR = Path(r"C:\Users\vinay\tvDownloadOHLC\data")
DERIVED_DATA_DIR = OHLCV_DATA_DIR / "derived"
LIVE_DATA_DIR = OHLCV_DATA_DIR / "live"

# Research Data (Daily Scenarios)
ICT_RESEARCH_DIR = Path(r"C:\Users\vinay\tvDownloadOHLC\docs\research\ict\data")

# Output for the Pipeline
MACRO_RECORDS_PATH = DERIVED_DATA_DIR / "macro_records.parquet"
FVG_DETAIL_PATH = DERIVED_DATA_DIR / "fvg_detail.parquet"

# Databases
PRISMA_DB_PATH = Path(r"C:\Users\vinay\tvDownloadOHLC\web\prisma\dev.db")

# ==========================================
# Parameters (Phase 4)
# ==========================================
PIVOT_LENGTH = 13
VOL_AVG_LOOKBACK = 20      # Rolling average for volume_vs_avg

# ==========================================
# Macro Window Definitions
# ==========================================

# Standard Macros: 20-minute windows every hour boundary (XX:50 to XX+1:10)
# Returns list of (name, start_h, start_m, end_h, end_m)
EXCLUDED_STANDARD_MACRO_START_HOURS = {17}

STANDARD_MACROS = [
    (f"Macro_{h:02d}50", h, 50, (h + 1) % 24, 10)
    for h in range(24)
    if h not in EXCLUDED_STANDARD_MACRO_START_HOURS
]

# ICT Alias Mapping
ICT_ALIASES = {
    "Macro_1850": "Asia_1",
    "Macro_1950": "Asia_2",
    "Macro_2050": "Asia_3",
    "Macro_0250": "London_1",
    "Macro_0450": "London_2",
    "Macro_0950": "NY_AM_1",
    "Macro_1050": "NY_AM_2",
    "Macro_1150": "NY_Lunch",
    "Macro_1350": "NY_PM",
    "Macro_1550": "NY_Close",
}

# Hydra Macros: 20-minute windows (XX:20 to XX:40)
HYDRA_MACROS = [
    ("Hydra_1", 8, 20, 8, 40),
    ("Hydra_2", 9, 20, 9, 40),
    ("Hydra_3", 10, 20, 10, 40),
]

# ==========================================
# Instruments (ADR-001)
# ==========================================
INSTRUMENTS = {
    "ES1": "ES",
    "NQ1": "NQ",
    "YM1": "YM",
    "RTY1": "RTY",
    "CL1": "CL",
    "GC1": "GC",
}

def get_1m_path(instrument: str) -> Path:
    return OHLCV_DATA_DIR / f"{instrument}_1m.parquet"

def get_5m_path(instrument: str) -> Path:
    return OHLCV_DATA_DIR / f"{instrument}_5m.parquet"
