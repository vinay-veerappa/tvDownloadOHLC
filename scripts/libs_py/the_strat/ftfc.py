"""Full Time Frame Continuity (FTFC) Engine for The Strat.

Computes directional continuity across multiple timeframes by comparing
the current price to the open price of the active candle in each timeframe.

Supports:
  - Intraday timeframes: 5m, 15m, 30m, 1h, 4h
  - Daily: RTH (09:30 ET open) or Globex/ETH (18:00 ET prior day open)
  - Weekly: Sunday 18:00 ET Globex open
  - Monthly: 1st trading day of the month
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from enum import Enum
from typing import Any
import pandas as pd


class Direction(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"

    @property
    def short_code(self) -> str:
        if self == Direction.BULLISH:
            return "G"  # Green
        elif self == Direction.BEARISH:
            return "R"  # Red
        return "N"      # Neutral


@dataclass
class TimeframeState:
    timeframe: str
    open_price: float
    current_price: float
    direction: Direction
    diff_points: float
    diff_percent: float


@dataclass
class FTFCResult:
    timestamp: datetime
    current_price: float
    states: dict[str, TimeframeState] = field(default_factory=dict)
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    total_timeframes: int = 0
    score: int = 0  # Net score (bullish - bearish)
    full_continuity: Direction = Direction.NEUTRAL
    is_full_continuity: bool = False
    dominant_bias: Direction = Direction.NEUTRAL

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat() if hasattr(self.timestamp, "isoformat") else str(self.timestamp),
            "current_price": self.current_price,
            "states": {
                k: {
                    "open": v.open_price,
                    "current": v.current_price,
                    "direction": v.direction.value,
                    "code": v.direction.short_code,
                    "diff_points": round(v.diff_points, 2),
                    "diff_pct": round(v.diff_percent, 4),
                }
                for k, v in self.states.items()
            },
            "bullish_count": self.bullish_count,
            "bearish_count": self.bearish_count,
            "neutral_count": self.neutral_count,
            "score": self.score,
            "full_continuity": self.full_continuity.value,
            "is_full_continuity": self.is_full_continuity,
            "dominant_bias": self.dominant_bias.value,
            "summary": self.format_summary(),
        }

    def format_summary(self) -> str:
        codes = " | ".join(f"{tf}:{st.direction.short_code}" for tf, st in self.states.items())
        return f"FTFC [{self.dominant_bias.value}] ({self.bullish_count}G/{self.bearish_count}R) -> {codes}"


class FTFCEngine:
    """Engine for computing live or historical FTFC state."""

    DEFAULT_TIMEFRAMES = ["5m", "15m", "1h", "4h", "D", "W", "M"]

    @staticmethod
    def evaluate_direction(open_price: float, current_price: float, tolerance: float = 1e-4) -> tuple[Direction, float, float]:
        diff = current_price - open_price
        pct = (diff / open_price) * 100.0 if open_price > 0 else 0.0
        if abs(diff) <= tolerance:
            return Direction.NEUTRAL, diff, pct
        elif diff > 0:
            return Direction.BULLISH, diff, pct
        else:
            return Direction.BEARISH, diff, pct

    @classmethod
    def compute_from_candles(
        cls,
        current_price: float,
        opens_by_tf: dict[str, float],
        timestamp: datetime | None = None,
    ) -> FTFCResult:
        """Compute FTFC from a dictionary mapping timeframe name to current candle open price."""
        ts = timestamp or datetime.now(timezone.utc)
        states: dict[str, TimeframeState] = {}
        bull_count = 0
        bear_count = 0
        neut_count = 0

        for tf, o_price in opens_by_tf.items():
            if o_price is None or o_price <= 0:
                continue
            direction, diff, pct = cls.evaluate_direction(o_price, current_price)
            states[tf] = TimeframeState(
                timeframe=tf,
                open_price=o_price,
                current_price=current_price,
                direction=direction,
                diff_points=diff,
                diff_percent=pct,
            )
            if direction == Direction.BULLISH:
                bull_count += 1
            elif direction == Direction.BEARISH:
                bear_count += 1
            else:
                neut_count += 1

        total = len(states)
        score = bull_count - bear_count

        full_cont = Direction.NEUTRAL
        is_full = False
        if total > 0:
            if bull_count == total:
                full_cont = Direction.BULLISH
                is_full = True
            elif bear_count == total:
                full_cont = Direction.BEARISH
                is_full = True

        if score >= 2:
            dom_bias = Direction.BULLISH
        elif score <= -2:
            dom_bias = Direction.BEARISH
        else:
            dom_bias = Direction.NEUTRAL

        return FTFCResult(
            timestamp=ts,
            current_price=current_price,
            states=states,
            bullish_count=bull_count,
            bearish_count=bear_count,
            neutral_count=neut_count,
            total_timeframes=total,
            score=score,
            full_continuity=full_cont,
            is_full_continuity=is_full,
            dominant_bias=dom_bias,
        )

    @classmethod
    def compute_from_1m_df(
        cls,
        df_1m: pd.DataFrame,
        timestamp: datetime | None = None,
        use_rth_for_daily: bool = False,
    ) -> FTFCResult:
        """Compute FTFC dynamically from a 1-minute OHLC DataFrame (Eastern Time).

        Expects DateTimeIndex normalized to America/New_York and columns ['open', 'high', 'low', 'close'].
        """
        if df_1m.empty:
            return FTFCResult(timestamp=timestamp or datetime.now(timezone.utc), current_price=0.0)

        cols = {c.lower(): c for c in df_1m.columns}
        o_col = cols["open"]
        c_col = cols["close"]

        if timestamp is not None:
            df_slice = df_1m.loc[:timestamp]
            if df_slice.empty:
                return FTFCResult(timestamp=timestamp, current_price=0.0)
        else:
            df_slice = df_1m
            timestamp = df_slice.index[-1]

        current_price = float(df_slice[c_col].iloc[-1])
        opens: dict[str, float] = {}

        # 5m
        df_5m = df_slice[[o_col, c_col]].resample("5min", origin="start_day").agg({o_col: "first", c_col: "last"}).dropna()
        if not df_5m.empty:
            opens["5m"] = float(df_5m[o_col].iloc[-1])

        # 15m
        df_15m = df_slice[[o_col, c_col]].resample("15min", origin="start_day").agg({o_col: "first", c_col: "last"}).dropna()
        if not df_15m.empty:
            opens["15m"] = float(df_15m[o_col].iloc[-1])

        # 30m
        df_30m = df_slice[[o_col, c_col]].resample("30min", origin="start_day").agg({o_col: "first", c_col: "last"}).dropna()
        if not df_30m.empty:
            opens["30m"] = float(df_30m[o_col].iloc[-1])

        # 1h
        df_1h = df_slice[[o_col, c_col]].resample("1h", origin="start_day").agg({o_col: "first", c_col: "last"}).dropna()
        if not df_1h.empty:
            opens["1h"] = float(df_1h[o_col].iloc[-1])

        # 4h (clock-aligned: 02:00, 06:00, 10:00, 14:00, 18:00, 22:00)
        df_4h = df_slice[[o_col, c_col]].resample("4h", origin="start_day").agg({o_col: "first", c_col: "last"}).dropna()
        if not df_4h.empty:
            opens["4h"] = float(df_4h[o_col].iloc[-1])

        # Daily (Session Open: Globex 18:00 ET prior day or RTH 09:30 ET)
        # Find the open of the current session
        last_dt = df_slice.index[-1]
        if use_rth_for_daily:
            # 09:30 ET open
            rth_today = last_dt.replace(hour=9, minute=30, second=0, microsecond=0)
            if last_dt < rth_today:
                # Still in premarket, use prior day RTH open or premarket open
                df_d = df_slice.loc[df_slice.index >= (rth_today - pd.Timedelta(days=1))]
            else:
                df_d = df_slice.loc[df_slice.index >= rth_today]
        else:
            # Globex 18:00 ET open
            session_open_dt = last_dt.replace(hour=18, minute=0, second=0, microsecond=0)
            if last_dt.hour < 18:
                session_open_dt -= pd.Timedelta(days=1)
            df_d = df_slice.loc[df_slice.index >= session_open_dt]

        if not df_d.empty:
            opens["D"] = float(df_d[o_col].iloc[0])

        # Weekly (Sunday 18:00 ET open)
        # Find start of current week (most recent Sunday 18:00 ET)
        days_since_sunday = (last_dt.weekday() + 1) % 7
        sun_dt = (last_dt - pd.Timedelta(days=days_since_sunday)).replace(hour=18, minute=0, second=0, microsecond=0)
        if last_dt < sun_dt:
            sun_dt -= pd.Timedelta(days=7)
        df_w = df_slice.loc[df_slice.index >= sun_dt]
        if not df_w.empty:
            opens["W"] = float(df_w[o_col].iloc[0])

        # Monthly (1st of current month 18:00 ET or first trading bar of month)
        m_start = last_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        df_m = df_slice.loc[df_slice.index >= m_start]
        if not df_m.empty:
            opens["M"] = float(df_m[o_col].iloc[0])

        return cls.compute_from_candles(current_price, opens, timestamp=last_dt)
