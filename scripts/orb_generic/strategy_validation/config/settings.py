# strategy_validation/config/settings.py
"""
Master configuration for all validation scripts.
Ticker-agnostic. All times in ET (US/Eastern).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import json


@dataclass
class DataConfig:
    """Paths and file settings."""
    # Input: directory containing parquet files named like ES_1min.parquet, NQ_1min.parquet
    input_dir: str = "./data/raw"
    # Output: derived data cached here as CSV/JSON so we never re-read parquet unnecessarily
    derived_dir: str = "./data/derived"
    # Results: study outputs
    results_dir: str = "./results"

    # Parquet column mapping — adjust if your files use different names
    # Script will auto-detect common variations, but explicit mapping takes priority
    col_datetime: str = "datetime"   # or "timestamp", "date", "time", "Date"
    col_open: str = "open"
    col_high: str = "high"
    col_low: str = "low"
    col_close: str = "close"
    col_volume: str = "volume"

    # Timezone of raw data — set to None if already in US/Eastern
    # Common values: "UTC", "US/Central", "US/Eastern", None
    raw_timezone: Optional[str] = "US/Eastern"
    target_timezone: str = "US/Eastern"

    # Output format for derived data
    derived_format: str = "csv"  # "csv" or "json"

    def ensure_dirs(self):
        for d in [self.input_dir, self.derived_dir, self.results_dir]:
            Path(d).mkdir(parents=True, exist_ok=True)


@dataclass
class SessionConfig:
    """Session time definitions (hours in ET, 24h format).
    Each session is defined as (start_hour, start_min, end_hour, end_min).
    Sessions that cross midnight are handled automatically.
    """
    # RTH (Regular Trading Hours)
    rth_start: tuple = (9, 30)
    rth_end: tuple = (16, 0)

    # ETH (Electronic Trading Hours) — full session
    eth_start: tuple = (18, 0)   # prior day
    eth_end: tuple = (17, 0)     # current day

    # Overnight: from prior day ETH open to current day RTH open
    overnight_start: tuple = (18, 0)   # prior day
    overnight_end: tuple = (9, 29)     # current day

    # Asia session
    asia_start: tuple = (20, 0)   # prior day
    asia_end: tuple = (0, 0)      # midnight

    # London session
    london_start: tuple = (2, 0)
    london_end: tuple = (5, 0)

    # London open (first hour)
    london_open_start: tuple = (2, 0)
    london_open_end: tuple = (3, 0)

    # Pre-market
    pre_market_start: tuple = (8, 0)
    pre_market_end: tuple = (9, 29)

    # ICT Macro time windows (x:50 to x+1:10)
    macro_windows: list = field(default_factory=lambda: [
        ((9, 50), (10, 10)),
        ((10, 50), (11, 10)),
        ((13, 50), (14, 10)),
        ((14, 50), (15, 10)),
    ])

    # ICT Kill Zones
    london_killzone: tuple = ((2, 0), (5, 0))
    ny_killzone: tuple = ((9, 30), (12, 0))
    ny_afternoon_killzone: tuple = ((13, 30), (16, 0))


@dataclass
class OpeningRangeConfig:
    """Configurable opening range durations.
    All durations in minutes from RTH open (9:30 ET).
    """
    # Which OR durations to analyze — fully configurable
    or_durations_minutes: list = field(default_factory=lambda: [5, 15, 30, 45, 60])

    # OR reference time (RTH open)
    or_start: tuple = (9, 30)

    def get_or_end_times(self) -> dict:
        """Return {duration_min: (hour, minute)} for each OR window."""
        results = {}
        base_h, base_m = self.or_start
        for dur in self.or_durations_minutes:
            total_min = base_m + dur
            end_h = base_h + total_min // 60
            end_m = total_min % 60
            results[dur] = (end_h, end_m)
        return results


@dataclass
class StrategyConfig:
    """Parameters for strategy simulation."""
    # Prop firm constraints
    max_drawdown: float = 2000.0
    daily_loss_limit: float = 300.0
    max_trades_per_day: int = 3
    trailing_drawdown: bool = True

    # Execution assumptions
    slippage_ticks: int = 1
    commission_per_side: float = 0.62  # typical futures commission

    # Contract specs — loaded per instrument, not hardcoded
    # See InstrumentConfig below


@dataclass
class InstrumentConfig:
    """Per-instrument specifications. Loaded from JSON so new instruments
    can be added without code changes."""
    symbol: str
    tick_size: float
    tick_value: float
    point_value: float
    margin_day: float
    margin_overnight: float

    @property
    def ticks_per_point(self) -> float:
        return 1.0 / self.tick_size


# Default instrument specs — override via instruments.json
DEFAULT_INSTRUMENTS = {
    "MNQ": InstrumentConfig("MNQ", 0.25, 0.50, 2.00, 500, 1000),
    "MES": InstrumentConfig("MES", 0.25, 0.3125, 1.25, 500, 1000),
    "NQ":  InstrumentConfig("NQ",  0.25, 5.00, 20.00, 2000, 8000),
    "ES":  InstrumentConfig("ES",  0.25, 3.125, 12.50, 1000, 6000),
    "RTY": InstrumentConfig("RTY", 0.10, 5.00, 50.00, 1500, 6000),
    "YM":  InstrumentConfig("YM",  1.00, 5.00, 5.00, 1000, 5000),
    "GC":  InstrumentConfig("GC",  0.10, 10.00, 100.00, 2000, 8000),
    "CL":  InstrumentConfig("CL",  0.01, 10.00, 1000.00, 2000, 5000),
}


def load_instruments(path: Optional[str] = None) -> dict:
    """Load instrument configs from JSON file, falling back to defaults."""
    if path and Path(path).exists():
        with open(path) as f:
            data = json.load(f)
        return {k: InstrumentConfig(**v) for k, v in data.items()}
    return DEFAULT_INSTRUMENTS


@dataclass
class ValidationConfig:
    """Statistical thresholds for declaring an edge valid."""
    min_sample_size: int = 100           # minimum occurrences for any pattern
    min_profit_factor: float = 1.5       # on out-of-sample
    min_win_rate: float = 0.50           # for prop firm viability
    max_sim_drawdown: float = 1500.0     # leaves $500 buffer
    min_eval_pass_rate: float = 0.60     # Monte Carlo: 60% must pass
    consistency_max_day_pct: float = 0.30  # no single day > 30% of total profit


def get_config():
    """Return all config objects. Override by editing this function
    or loading from a master JSON/YAML file."""
    return {
        "data": DataConfig(),
        "sessions": SessionConfig(),
        "opening_range": OpeningRangeConfig(),
        "strategy": StrategyConfig(),
        "validation": ValidationConfig(),
        "instruments": load_instruments(),
    }
