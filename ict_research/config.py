from datetime import time
import pytz

# Timezone
TZ_NY = pytz.timezone('America/New_York')
TZ_UTC = pytz.timezone('UTC')

# Session Times (ET)
# format: (start_time, end_time)
# Note: Asia spans midnight, requires special handling in logic
SESSION_TIMES = {
    'ASIA': (time(19, 30), time(2, 30)),
    'LONDON': (time(2, 30), time(8, 0)),
    'PRE_MARKET': (time(8, 0), time(9, 30)),
    'NY_AM': (time(9, 30), time(12, 0)),
    'NY_LUNCH': (time(12, 0), time(13, 0)),
    'NY_PM': (time(13, 0), time(16, 0)),
    'GLOBEX_OPEN': time(18, 0),
    'NY_CLOSE': time(16, 0),
    'MIDNIGHT_OPEN': time(0, 0),
    'HOUR_7_8': (time(7, 0), time(8, 0)),
    'HOUR_2_3': (time(2, 0), time(3, 0)),

    # NEW sessions:
    'LUNCH': (time(12, 0), time(13, 30)),         # Lunch session (wider than NY_LUNCH)
    'NY_PM_ICT': (time(13, 30), time(16, 0)),     # ICT PM definition (after lunch)
    'CBDR_CLASSIC': (time(14, 0), time(20, 0)),   # Classic CBDR (crosses into next day)
    'CBDR_ASIA': (time(19, 30), time(0, 0)),      # Asia CBDR (first half before midnight)
    'FLOUT': (time(20, 0), time(0, 0)),           # Flout range (Asian Range used for flout)
    'P12': (time(18, 0), time(6, 0)),             # First 12 hours
    'RTH': (time(9, 30), time(16, 0)),            # Regular trading hours
    'NY_FULL': (time(8, 0), time(16, 0)),         # Full NY
    'OVERNIGHT': (time(18, 0), time(9, 30)),      # Full overnight

    # Time-based opens (single timestamps):
    'LONDON_OPEN': time(2, 30),
    'OPEN_0730': time(7, 30),
    'RTH_OPEN': time(9, 30),
    'PM_OPEN': time(13, 30),
}

# CBDR Standard Deviation multipliers
CBDR_SIGMA_LEVELS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]

# Range percentile lookback
RANGE_PERCENTILE_LOOKBACK = 50

# PD Array Detection Settings
RTH_GAP_THRESHOLD_PCT = 0.03  # 0.03% of price for FVG detection
SWING_LOOKBACK = 5            # Bars to look back/forward for swing points

# Reporting
OUTPUT_DIR = 'reports'
DATA_DIR = '../data'          # Default to parent data directory if not found in local
