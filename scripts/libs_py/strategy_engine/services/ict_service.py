from dataclasses import dataclass, field
from datetime import datetime, time
import os
import json
import logging
from typing import Optional, List, Dict, Any, Tuple
import pandas as pd
import numpy as np
import pytz

# Setup logger
logger = logging.getLogger(__name__)

# Standard ticker mappings for NWOG/NDOG lookup
TICKER_MAPPINGS = {
    "QQQ": "NQ1",
    "QQQ!": "NQ1",
    "NQ": "NQ1",
    "NQ1": "NQ1",
    "NQ1!": "NQ1",
    "SPY": "ES1",
    "SPY!": "ES1",
    "SPX": "ES1",
    "ES": "ES1",
    "ES1": "ES1",
    "ES1!": "ES1",
}


@dataclass
class FairValueGap:
    """A fair value gap detected in price action."""
    direction: str                  # "BULLISH" | "BEARISH"
    top: float
    bottom: float
    created_at: datetime
    is_mitigated: bool
    distance_from_spot_pct: float   # signed: + if above spot, - if below


@dataclass
class OrderBlock:
    """An order block."""
    direction: str                  # "BULLISH" | "BEARISH"
    top: float
    bottom: float
    created_at: datetime
    is_mitigated: bool


@dataclass
class LiquiditySweep:
    """A liquidity sweep event."""
    direction: str                  # "BUYSIDE" (swept highs) | "SELLSIDE" (swept lows)
    level: float                    # the swept level
    occurred_at: datetime
    minutes_ago: int


@dataclass
class SessionContext:
    """Current trading session tags."""
    asia: bool
    london: bool
    ny_am: bool
    ny_pm: bool
    rth: bool


@dataclass
class IctContext:
    """Snapshot of ICT-relevant state for a ticker at a timeframe."""
    ticker: str
    timeframe: str                  # "1m" | "5m" | "15m" | "1h"
    computed_at: datetime
    spot: float

    bullish_fvgs: List[FairValueGap] = field(default_factory=list)
    bearish_fvgs: List[FairValueGap] = field(default_factory=list)
    recent_bullish_obs: List[OrderBlock] = field(default_factory=list)
    recent_bearish_obs: List[OrderBlock] = field(default_factory=list)
    recent_sweeps: List[LiquiditySweep] = field(default_factory=list)
    session: SessionContext = field(default_factory=lambda: SessionContext(False, False, False, False, False))

    # Higher-timeframe references
    nwog_high: Optional[float] = None
    nwog_low: Optional[float] = None
    ndog_high: Optional[float] = None
    ndog_low: Optional[float] = None

    # Derived flags
    htf_bias: Optional[str] = "NEUTRAL"  # "BULLISH" | "BEARISH" | "NEUTRAL"

    def has_bullish_fvg_near(self, spot: float, tolerance_pct: float = 0.5) -> bool:
        """Convenience: any unmitigated bullish FVG within tolerance_pct of spot."""
        for fvg in self.bullish_fvgs:
            if not fvg.is_mitigated:
                # FVG mid or closest boundary
                fvg_mid = (fvg.top + fvg.bottom) / 2.0
                dist_pct = abs(fvg_mid - spot) / spot * 100.0
                if dist_pct <= tolerance_pct:
                    return True
        return False

    def has_bearish_fvg_near(self, spot: float, tolerance_pct: float = 0.5) -> bool:
        """Convenience: any unmitigated bearish FVG within tolerance_pct of spot."""
        for fvg in self.bearish_fvgs:
            if not fvg.is_mitigated:
                fvg_mid = (fvg.top + fvg.bottom) / 2.0
                dist_pct = abs(fvg_mid - spot) / spot * 100.0
                if dist_pct <= tolerance_pct:
                    return True
        return False

    def to_dict(self) -> dict:
        """Serialize for storage in Trade.metadata JSON."""
        return {
            "ticker": self.ticker,
            "timeframe": self.timeframe,
            "computed_at": self.computed_at.isoformat() if self.computed_at else None,
            "spot": self.spot,
            "bullish_fvgs": [
                {
                    "direction": f.direction,
                    "top": f.top,
                    "bottom": f.bottom,
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                    "is_mitigated": f.is_mitigated,
                    "distance_from_spot_pct": f.distance_from_spot_pct
                } for f in self.bullish_fvgs
            ],
            "bearish_fvgs": [
                {
                    "direction": f.direction,
                    "top": f.top,
                    "bottom": f.bottom,
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                    "is_mitigated": f.is_mitigated,
                    "distance_from_spot_pct": f.distance_from_spot_pct
                } for f in self.bearish_fvgs
            ],
            "recent_bullish_obs": [
                {
                    "direction": ob.direction,
                    "top": ob.top,
                    "bottom": ob.bottom,
                    "created_at": ob.created_at.isoformat() if ob.created_at else None,
                    "is_mitigated": ob.is_mitigated
                } for ob in self.recent_bullish_obs
            ],
            "recent_bearish_obs": [
                {
                    "direction": ob.direction,
                    "top": ob.top,
                    "bottom": ob.bottom,
                    "created_at": ob.created_at.isoformat() if ob.created_at else None,
                    "is_mitigated": ob.is_mitigated
                } for ob in self.recent_bearish_obs
            ],
            "recent_sweeps": [
                {
                    "direction": sw.direction,
                    "level": sw.level,
                    "occurred_at": sw.occurred_at.isoformat() if sw.occurred_at else None,
                    "minutes_ago": sw.minutes_ago
                } for sw in self.recent_sweeps
            ],
            "session": {
                "asia": self.session.asia,
                "london": self.session.london,
                "ny_am": self.session.ny_am,
                "ny_pm": self.session.ny_pm,
                "rth": self.session.rth
            },
            "nwog_high": self.nwog_high,
            "nwog_low": self.nwog_low,
            "ndog_high": self.ndog_high,
            "ndog_low": self.ndog_low,
            "htf_bias": self.htf_bias
        }


class IctService:
    """On-demand ICT context. Computes from parquet via existing pa.py.

    Caches in-process for 60 sec per (ticker, timeframe).
    No persistent storage of ICT state.
    """

    def __init__(self, parquet_loader=None, pa_module=None, sessions_module=None, nwog_ndog_module=None):
        """
        Args:
            parquet_loader: existing loader.py module
            pa_module: existing libs_py/ict_engine/core/pa.py
            sessions_module: existing libs_py/nqstats/sessions.py
            nwog_ndog_module: existing trader/generate_ict_nwog_ndog.py
        """
        # Set up modules with dynamic imports as fallback
        if parquet_loader is None:
            try:
                from api.features.shared import data_loader
                self.parquet_loader = data_loader
            except ImportError:
                logger.error("Could not import api.features.shared.data_loader fallback")
                self.parquet_loader = None
        else:
            self.parquet_loader = parquet_loader

        if pa_module is None:
            try:
                from scripts.libs_py.ict_engine.core import pa
                self.pa = pa
            except ImportError:
                logger.error("Could not import scripts.libs_py.ict_engine.core.pa fallback")
                self.pa = None
        else:
            self.pa = pa_module

        # Load structure module for swing detection
        try:
            from scripts.libs_py.ict_engine.core import structure
            self.structure = structure
        except ImportError:
            logger.error("Could not import scripts.libs_py.ict_engine.core.structure")
            self.structure = None

        if sessions_module is None:
            try:
                from scripts.libs_py.nqstats import sessions
                self.sessions_module = sessions
            except ImportError:
                logger.error("Could not import scripts.libs_py.nqstats.sessions fallback")
                self.sessions_module = None
        else:
            self.sessions_module = sessions_module

        self.nwog_ndog_module = nwog_ndog_module

        # Internal 60-second TTL cache mapping (ticker, timeframe) -> (IctContext, timestamp)
        self._cache: Dict[Tuple[str, str], Tuple[IctContext, float]] = {}

    def get_context(
        self,
        ticker: str,
        timeframe: str = "5m",
        lookback_bars: int = 200,
    ) -> Optional[IctContext]:
        """Current ICT context for ticker at timeframe.

        Reads last `lookback_bars` from the corresponding parquet file,
        runs vectorized pa.py to detect FVGs/OBs/sweeps, attaches session tags
        and NWOG/NDOG references.

        Cached in-process for 60s per (ticker, timeframe).
        Returns None if parquet file is unavailable or too short.
        """
        import time as time_lib

        now_sec = time_lib.time()
        cache_key = (ticker, timeframe)

        # Check Cache
        if cache_key in self._cache:
            cached_ctx, cached_time = self._cache[cache_key]
            if now_sec - cached_time < 60.0:
                logger.debug(f"Cache hit for ICT context: {cache_key}")
                return cached_ctx

        # Load Parquet Data (Load slightly more than lookback to ensure stable swing detection at start)
        if not self.parquet_loader:
            logger.error("Parquet loader is not initialized")
            return None

        # Fetch using load_parquet
        df = self.parquet_loader.load_parquet(ticker, timeframe)
        if df is None or df.empty or len(df) < 20:
            logger.warning(f"No parquet data found or not enough bars for {ticker} {timeframe}")
            return None

        # Sort and ensure we have sufficient lookback
        df = df.sort_values("time").reset_index(drop=True)
        total_needed = lookback_bars + 50  # Extra buffer for swing fractals
        if len(df) > total_needed:
            df_slice = df.iloc[-total_needed:].copy()
        else:
            df_slice = df.copy()

        # Reconstruct DatetimeIndex with US/Eastern (like in profiler/loader.py)
        # Check if 'time' is Unix timestamp (seconds)
        try:
            df_slice["datetime"] = pd.to_datetime(df_slice["time"], unit="s", utc=True)
            df_slice.set_index("datetime", inplace=True)
            df_slice.index = df_slice.index.tz_convert("US/Eastern")
        except Exception as e:
            logger.warning(f"Error converting time to DatetimeIndex: {e}. Trying raw localize.")
            try:
                df_slice.index = pd.to_datetime(df_slice["time"]).dt.tz_localize("UTC").dt.tz_convert("US/Eastern")
            except Exception as ex:
                logger.error(f"Failed to set index: {ex}")
                return None

        # Call detect_swings and vectorized indicators
        if not self.structure:
            logger.error("Structure module is not initialized")
            return None

        # 1. Swings Detection
        try:
            swings_df = self.structure.detect_swings(df_slice, swing_length=5)
        except Exception as e:
            logger.error(f"Error executing detect_swings: {e}")
            return None

        # 2. FVG Detection & Mitigation
        if not self.pa:
            logger.error("PA module is not initialized")
            return None

        try:
            fvg_df = self.pa.detect_fvg(df_slice, join_consecutive=False)
            mitigation_series = self.pa.check_fvg_mitigation(df_slice, fvg_df)
        except Exception as e:
            logger.error(f"Error executing FVG detection: {e}")
            return None

        # 3. OrderBlock Detection
        try:
            ob_df = self.pa.detect_orderblock(df_slice, swings_df)
        except Exception as e:
            logger.error(f"Error executing OB detection: {e}")
            ob_df = pd.DataFrame({"ob": 0, "top": np.nan, "bottom": np.nan}, index=df_slice.index)

        # 4. Breaker Detection (Optional, but useful context)
        try:
            breaker_df = self.pa.detect_breaker(df_slice, swings_df)
        except Exception as e:
            breaker_df = pd.DataFrame({"breaker": 0, "top": np.nan, "bottom": np.nan}, index=df_slice.index)

        # Spot is the close of the last candle
        last_row = df_slice.iloc[-1]
        spot = float(last_row["close"])
        last_time_et = df_slice.index[-1].to_pydatetime()

        # Filter FVGs / OBs / Sweeps in the last `lookback_bars` candles
        eval_slice = df_slice.iloc[-lookback_bars:]
        eval_indices = eval_slice.index

        bullish_fvgs: List[FairValueGap] = []
        bearish_fvgs: List[FairValueGap] = []
        recent_bullish_obs: List[OrderBlock] = []
        recent_bearish_obs: List[OrderBlock] = []
        recent_sweeps: List[LiquiditySweep] = []

        # Extract FVGs
        for idx in eval_indices:
            row_fvg = fvg_df.loc[idx]
            fvg_val = row_fvg["fvg"]
            if pd.isna(fvg_val) or fvg_val == 0:
                continue

            top_val = float(row_fvg["top"])
            bot_val = float(row_fvg["bottom"])
            fvg_mid = (top_val + bot_val) / 2.0
            dist_pct = (fvg_mid - spot) / spot * 100.0

            mit_val = mitigation_series.loc[idx]
            is_mit = not pd.isna(mit_val)

            # Check if mitigation occurred after the evaluation period (or already occurred)
            # is_mitigated is True if there's any mitigation index recorded
            fvg_obj = FairValueGap(
                direction="BULLISH" if fvg_val == 1 else "BEARISH",
                top=top_val,
                bottom=bot_val,
                created_at=idx.to_pydatetime(),
                is_mitigated=is_mit,
                distance_from_spot_pct=dist_pct
            )
            if fvg_val == 1:
                bullish_fvgs.append(fvg_obj)
            else:
                bearish_fvgs.append(fvg_obj)

        # Extract OBs and compute their mitigation on-the-fly
        for idx in eval_indices:
            row_ob = ob_df.loc[idx]
            ob_val = row_ob["ob"]
            if pd.isna(ob_val) or ob_val == 0:
                continue

            top_val = float(row_ob["top"])
            bot_val = float(row_ob["bottom"])

            # Check if OB is mitigated: did price go below/above the OB after creation?
            is_ob_mitigated = False
            post_idx = df_slice.index[df_slice.index > idx]
            if not post_idx.empty:
                post_lows = df_slice.loc[post_idx, "low"].values
                post_highs = df_slice.loc[post_idx, "high"].values
                if ob_val == 1:  # Bullish OB
                    # Mitigated if low goes below OB top
                    if np.any(post_lows <= top_val):
                        is_ob_mitigated = True
                else:  # Bearish OB
                    # Mitigated if high goes above OB bottom
                    if np.any(post_highs >= bot_val):
                        is_ob_mitigated = True

            ob_obj = OrderBlock(
                direction="BULLISH" if ob_val == 1 else "BEARISH",
                top=top_val,
                bottom=bot_val,
                created_at=idx.to_pydatetime(),
                is_mitigated=is_ob_mitigated
            )
            if ob_val == 1:
                recent_bullish_obs.append(ob_obj)
            else:
                recent_bearish_obs.append(ob_obj)

        # Extract Sweeps in the lookback period
        # BSL sweep: high > last_sh & close <= last_sh
        # SSL sweep: low < last_sl & close >= last_sl
        for idx in eval_indices:
            # We can calculate sweeps dynamically
            row_swing = swings_df.loc[idx]
            row_price = df_slice.loc[idx]
            
            # Find swings prior to this candle to avoid forward-looking sweeps
            prior_swings = swings_df.loc[swings_df.index < idx]
            if prior_swings.empty:
                continue
                
            sh_levels = prior_swings["level"].where(prior_swings["shl"] == 1).ffill()
            sl_levels = prior_swings["level"].where(prior_swings["shl"] == -1).ffill()
            
            if sh_levels.empty or sl_levels.empty:
                continue
                
            last_sh = sh_levels.iloc[-1]
            last_sl = sl_levels.iloc[-1]
            
            if pd.isna(last_sh) or pd.isna(last_sl):
                continue

            high_val = float(row_price["high"])
            low_val = float(row_price["low"])
            close_val = float(row_price["close"])

            is_bsl_sweep = (high_val > last_sh) and (close_val <= last_sh)
            is_ssl_sweep = (low_val < last_sl) and (close_val >= last_sl)

            if is_bsl_sweep or is_ssl_sweep:
                min_ago = int((last_time_et - idx.to_pydatetime()).total_seconds() / 60.0)
                sweep_obj = LiquiditySweep(
                    direction="BUYSIDE" if is_bsl_sweep else "SELLSIDE",
                    level=last_sh if is_bsl_sweep else last_sl,
                    occurred_at=idx.to_pydatetime(),
                    minutes_ago=max(0, min_ago)
                )
                recent_sweeps.append(sweep_obj)

        # Clean Sweeps: Keep sorted by time (descending)
        recent_sweeps.sort(key=lambda x: x.occurred_at, reverse=True)

        # Create SessionContext for the last bar
        session_tags = self._get_session_tags(last_time_et)

        # Load NWOG/NDOG Gaps
        nwog_h, nwog_l, ndog_h, ndog_l = self._get_nwog_ndog_levels(ticker)

        # Higher Timeframe Bias logic:
        # A simple HTF Bias: if spot is above the midpoint of the latest FVG, or based on unmitigated FVG dominance
        unmit_bull = sum(1 for f in bullish_fvgs if not f.is_mitigated)
        unmit_bear = sum(1 for f in bearish_fvgs if not f.is_mitigated)
        if unmit_bull > unmit_bear:
            htf_bias = "BULLISH"
        elif unmit_bear > unmit_bull:
            htf_bias = "BEARISH"
        else:
            htf_bias = "NEUTRAL"

        context = IctContext(
            ticker=ticker,
            timeframe=timeframe,
            computed_at=last_time_et,
            spot=spot,
            bullish_fvgs=bullish_fvgs,
            bearish_fvgs=bearish_fvgs,
            recent_bullish_obs=recent_bullish_obs,
            recent_bearish_obs=recent_bearish_obs,
            recent_sweeps=recent_sweeps,
            session=session_tags,
            nwog_high=nwog_h,
            nwog_low=nwog_l,
            ndog_high=ndog_h,
            ndog_low=ndog_l,
            htf_bias=htf_bias
        )

        # Save to Cache
        self._cache[cache_key] = (context, now_sec)

        return context

    def invalidate_cache(self, ticker: Optional[str] = None) -> None:
        """Force re-computation on next call. Used for testing."""
        if ticker:
            keys_to_del = [k for k in self._cache.keys() if k[0] == ticker]
            for k in keys_to_del:
                del self._cache[k]
        else:
            self._cache.clear()

    def _get_session_tags(self, dt: datetime) -> SessionContext:
        """Compute SessionContext for given datetime in New York time."""
        # Ensure timezone localized to US/Eastern
        tz = pytz.timezone("US/Eastern")
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt).astimezone(tz)
        else:
            dt = dt.astimezone(tz)

        t = dt.time()

        # asia: 18:00 to 02:00 ET
        is_asia = (t >= time(18, 0)) or (t < time(2, 0))
        # london: 02:00 to 08:00 ET
        is_london = (t >= time(2, 0)) and (t < time(8, 0))
        # ny_am: 08:00 to 12:00 ET
        is_ny_am = (t >= time(8, 0)) and (t < time(12, 0))
        # ny_pm: 12:00 to 17:00 ET
        is_ny_pm = (t >= time(12, 0)) and (t < time(17, 0))
        # rth: 09:30 to 16:00 ET (only on weekdays)
        is_rth = (t >= time(9, 30)) and (t < time(16, 0)) and (dt.weekday() < 5)

        return SessionContext(
            asia=is_asia,
            london=is_london,
            ny_am=is_ny_am,
            ny_pm=is_ny_pm,
            rth=is_rth
        )

    def _get_nwog_ndog_levels(self, ticker: str) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """Load standard NWOG/NDOG levels from ict_nwog_ndog.json database."""
        # Find the correct continuous contract name
        mapped_ticker = TICKER_MAPPINGS.get(ticker, ticker.replace("!", ""))

        # Check where GAP_FILE is located (derived directory)
        # Relative to strategy engine services: tvDownloadOHLC/data/derived/ict_nwog_ndog.json
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
        gap_file_path = os.path.join(project_root, "data", "derived", "ict_nwog_ndog.json")

        if not os.path.exists(gap_file_path):
            logger.debug(f"NWOG/NDOG JSON database not found at {gap_file_path}")
            return None, None, None, None

        try:
            with open(gap_file_path, "r") as f:
                db = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load NWOG/NDOG JSON: {e}")
            return None, None, None, None

        ticker_data = db.get(mapped_ticker)
        if not ticker_data:
            logger.debug(f"No NWOG/NDOG data for mapped ticker {mapped_ticker} in database")
            return None, None, None, None

        nwogs = ticker_data.get("NWOG", [])
        ndogs = ticker_data.get("NDOG", [])

        nwog_h = None
        nwog_l = None
        ndog_h = None
        ndog_l = None

        if nwogs:
            # First item is newest
            newest_nwog = nwogs[0]
            nwog_h = float(newest_nwog["high"])
            nwog_l = float(newest_nwog["low"])

        if ndogs:
            newest_ndog = ndogs[0]
            ndog_h = float(newest_ndog["high"])
            ndog_l = float(newest_ndog["low"])

        return nwog_h, nwog_l, ndog_h, ndog_l
