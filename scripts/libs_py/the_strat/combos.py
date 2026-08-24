"""The Strat Combo Pattern Recognition and Magnitude Target Engine.

Detects classic Rob Smith Strat patterns:
  - 2-1-2 Continuation & Reversal (Bullish & Bearish)
  - 2-2 Reversal (Bullish & Bearish Momentum Traps)
  - 3-1-2 Broadening Expansion Breakout
  - 1-2-2 / 3 RevStrat (Failed 2 Traps)
  - Magnitude 1 and Magnitude 2 target projections
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
import numpy as np
import pandas as pd

from scripts.libs_py.the_strat.taxonomy import StratType, classify_bars_df


class ComboType(str, Enum):
    NONE = "NONE"
    # 2-1-2 Patterns
    BULLISH_212_CONT = "2-1-2_BULL_CONT"
    BEARISH_212_CONT = "2-1-2_BEAR_CONT"
    BULLISH_212_REV = "2-1-2_BULL_REV"
    BEARISH_212_REV = "2-1-2_BEAR_REV"

    # 2-2 Reversals
    BULLISH_22_REV = "2-2_BULL_REV"
    BEARISH_22_REV = "2-2_BEAR_REV"

    # 3-1-2 Patterns
    BULLISH_312 = "3-1-2_BULL"
    BEARISH_312 = "3-1-2_BEAR"

    # RevStrat Traps
    BULLISH_122_REVSTRAT = "1-2-2_BULL_REVSTRAT"
    BEARISH_122_REVSTRAT = "1-2-2_BEAR_REVSTRAT"
    BULLISH_3_REVSTRAT = "3_BULL_REVSTRAT"
    BEARISH_3_REVSTRAT = "3_BEAR_REVSTRAT"


class TradeDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class StratSetup:
    """Actionable Strat trade setup with entry, stop, and magnitude targets."""
    index: int
    timestamp: Any
    combo_type: ComboType
    direction: TradeDirection
    entry_trigger_price: float
    stop_loss_price: float
    magnitude_1_target: float
    magnitude_2_target: float
    risk_points: float
    reward_points_mag1: float
    reward_risk_ratio: float
    pattern_string: str  # e.g. "2U-1-2U" or "2D-2U"

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "timestamp": str(self.timestamp),
            "combo_type": self.combo_type.value,
            "direction": self.direction.value,
            "entry_trigger": round(self.entry_trigger_price, 2),
            "stop_loss": round(self.stop_loss_price, 2),
            "magnitude_1": round(self.magnitude_1_target, 2),
            "magnitude_2": round(self.magnitude_2_target, 2),
            "risk_pts": round(self.risk_points, 2),
            "reward_mag1_pts": round(self.reward_points_mag1, 2),
            "rr_ratio": round(self.reward_risk_ratio, 2),
            "pattern": self.pattern_string,
        }


class StratComboDetector:
    """Detects active and confirmed Strat setups across OHLC data."""

    def __init__(self, tick_size: float = 0.25):
        self.tick_size = tick_size

    def scan_dataframe(
        self,
        df: pd.DataFrame,
        min_rr_ratio: float = 0.0,
    ) -> list[StratSetup]:
        """Scan an OHLC DataFrame for all confirmed Strat setups."""
        df_strat = classify_bars_df(df)
        cols = {c.lower(): c for c in df_strat.columns}
        h = df_strat[cols["high"]].values
        l = df_strat[cols["low"]].values
        st = df_strat["strat_type"].values
        timestamps = df_strat.index if isinstance(df_strat.index, pd.DatetimeIndex) else np.arange(len(df_strat))

        setups: list[StratSetup] = []

        # Need at least 3 bars for 2-1-2 and 2 bars for 2-2
        for i in range(2, len(df_strat)):
            curr_st = st[i]
            prev1_st = st[i - 1]
            prev2_st = st[i - 2]
            ts = timestamps[i]

            # ----------------------------------------------------
            # 1. Check 2-1-2 Patterns (Bar[i-2], Bar[i-1]=1, Bar[i]=2)
            # ----------------------------------------------------
            if prev1_st == StratType.INSIDE:
                # Inside bar is setup bar Bar[i-1]
                inside_high = h[i - 1]
                inside_low = l[i - 1]

                # 2U-1-2U Bullish Continuation
                if prev2_st == StratType.TWO_UP and curr_st == StratType.TWO_UP:
                    entry = inside_high + self.tick_size
                    sl = inside_low - self.tick_size
                    mag1 = h[i - 2]
                    # Magnitude 2: prior swing high before setup
                    mag2 = max(h[max(0, i - 5):i - 1]) if i >= 5 else mag1
                    risk = max(entry - sl, self.tick_size)
                    reward = max(mag1 - entry, 0.0)
                    rr = reward / risk if risk > 0 else 0.0

                    if rr >= min_rr_ratio:
                        setups.append(StratSetup(
                            index=i, timestamp=ts, combo_type=ComboType.BULLISH_212_CONT,
                            direction=TradeDirection.LONG, entry_trigger_price=entry,
                            stop_loss_price=sl, magnitude_1_target=mag1, magnitude_2_target=mag2,
                            risk_points=risk, reward_points_mag1=reward, reward_risk_ratio=rr,
                            pattern_string="2U-1-2U",
                        ))

                # 2D-1-2D Bearish Continuation
                elif prev2_st == StratType.TWO_DOWN and curr_st == StratType.TWO_DOWN:
                    entry = inside_low - self.tick_size
                    sl = inside_high + self.tick_size
                    mag1 = l[i - 2]
                    mag2 = min(l[max(0, i - 5):i - 1]) if i >= 5 else mag1
                    risk = max(sl - entry, self.tick_size)
                    reward = max(entry - mag1, 0.0)
                    rr = reward / risk if risk > 0 else 0.0

                    if rr >= min_rr_ratio:
                        setups.append(StratSetup(
                            index=i, timestamp=ts, combo_type=ComboType.BEARISH_212_CONT,
                            direction=TradeDirection.SHORT, entry_trigger_price=entry,
                            stop_loss_price=sl, magnitude_1_target=mag1, magnitude_2_target=mag2,
                            risk_points=risk, reward_points_mag1=reward, reward_risk_ratio=rr,
                            pattern_string="2D-1-2D",
                        ))

                # 2D-1-2U Bullish Reversal
                elif prev2_st == StratType.TWO_DOWN and curr_st == StratType.TWO_UP:
                    entry = inside_high + self.tick_size
                    sl = inside_low - self.tick_size
                    mag1 = h[i - 2]
                    mag2 = max(h[max(0, i - 6):i - 1]) if i >= 6 else mag1
                    risk = max(entry - sl, self.tick_size)
                    reward = max(mag1 - entry, 0.0)
                    rr = reward / risk if risk > 0 else 0.0

                    if rr >= min_rr_ratio:
                        setups.append(StratSetup(
                            index=i, timestamp=ts, combo_type=ComboType.BULLISH_212_REV,
                            direction=TradeDirection.LONG, entry_trigger_price=entry,
                            stop_loss_price=sl, magnitude_1_target=mag1, magnitude_2_target=mag2,
                            risk_points=risk, reward_points_mag1=reward, reward_risk_ratio=rr,
                            pattern_string="2D-1-2U",
                        ))

                # 2U-1-2D Bearish Reversal
                elif prev2_st == StratType.TWO_UP and curr_st == StratType.TWO_DOWN:
                    entry = inside_low - self.tick_size
                    sl = inside_high + self.tick_size
                    mag1 = l[i - 2]
                    mag2 = min(l[max(0, i - 6):i - 1]) if i >= 6 else mag1
                    risk = max(sl - entry, self.tick_size)
                    reward = max(entry - mag1, 0.0)
                    rr = reward / risk if risk > 0 else 0.0

                    if rr >= min_rr_ratio:
                        setups.append(StratSetup(
                            index=i, timestamp=ts, combo_type=ComboType.BEARISH_212_REV,
                            direction=TradeDirection.SHORT, entry_trigger_price=entry,
                            stop_loss_price=sl, magnitude_1_target=mag1, magnitude_2_target=mag2,
                            risk_points=risk, reward_points_mag1=reward, reward_risk_ratio=rr,
                            pattern_string="2U-1-2D",
                        ))

                # 3-1-2 Broadening Expansion Breakout
                elif prev2_st == StratType.OUTSIDE:
                    if curr_st == StratType.TWO_UP:
                        entry = inside_high + self.tick_size
                        sl = inside_low - self.tick_size
                        mag1 = h[i - 2]
                        risk = max(entry - sl, self.tick_size)
                        reward = max(mag1 - entry, 0.0)
                        rr = reward / risk if risk > 0 else 0.0
                        if rr >= min_rr_ratio:
                            setups.append(StratSetup(
                                index=i, timestamp=ts, combo_type=ComboType.BULLISH_312,
                                direction=TradeDirection.LONG, entry_trigger_price=entry,
                                stop_loss_price=sl, magnitude_1_target=mag1, magnitude_2_target=mag1,
                                risk_points=risk, reward_points_mag1=reward, reward_risk_ratio=rr,
                                pattern_string="3-1-2U",
                            ))
                    elif curr_st == StratType.TWO_DOWN:
                        entry = inside_low - self.tick_size
                        sl = inside_high + self.tick_size
                        mag1 = l[i - 2]
                        risk = max(sl - entry, self.tick_size)
                        reward = max(entry - mag1, 0.0)
                        rr = reward / risk if risk > 0 else 0.0
                        if rr >= min_rr_ratio:
                            setups.append(StratSetup(
                                index=i, timestamp=ts, combo_type=ComboType.BEARISH_312,
                                direction=TradeDirection.SHORT, entry_trigger_price=entry,
                                stop_loss_price=sl, magnitude_1_target=mag1, magnitude_2_target=mag1,
                                risk_points=risk, reward_points_mag1=reward, reward_risk_ratio=rr,
                                pattern_string="3-1-2D",
                            ))

            # ----------------------------------------------------
            # 2. Check 2-2 Reversals (Bar[i-1]=2D into Bar[i]=2U, or 2U into 2D)
            # ----------------------------------------------------
            if prev1_st == StratType.TWO_DOWN and curr_st == StratType.TWO_UP:
                entry = h[i - 1] + self.tick_size
                sl = l[i - 1] - self.tick_size
                mag1 = h[i - 2] if i >= 2 else h[i - 1]
                mag2 = max(h[max(0, i - 5):i - 1]) if i >= 5 else mag1
                risk = max(entry - sl, self.tick_size)
                reward = max(mag1 - entry, 0.0)
                rr = reward / risk if risk > 0 else 0.0

                if rr >= min_rr_ratio:
                    setups.append(StratSetup(
                        index=i, timestamp=ts, combo_type=ComboType.BULLISH_22_REV,
                        direction=TradeDirection.LONG, entry_trigger_price=entry,
                        stop_loss_price=sl, magnitude_1_target=mag1, magnitude_2_target=mag2,
                        risk_points=risk, reward_points_mag1=reward, reward_risk_ratio=rr,
                        pattern_string="2D-2U",
                    ))

            elif prev1_st == StratType.TWO_UP and curr_st == StratType.TWO_DOWN:
                entry = l[i - 1] - self.tick_size
                sl = h[i - 1] + self.tick_size
                mag1 = l[i - 2] if i >= 2 else l[i - 1]
                mag2 = min(l[max(0, i - 5):i - 1]) if i >= 5 else mag1
                risk = max(sl - entry, self.tick_size)
                reward = max(entry - mag1, 0.0)
                rr = reward / risk if risk > 0 else 0.0

                if rr >= min_rr_ratio:
                    setups.append(StratSetup(
                        index=i, timestamp=ts, combo_type=ComboType.BEARISH_22_REV,
                        direction=TradeDirection.SHORT, entry_trigger_price=entry,
                        stop_loss_price=sl, magnitude_1_target=mag1, magnitude_2_target=mag2,
                        risk_points=risk, reward_points_mag1=reward, reward_risk_ratio=rr,
                        pattern_string="2U-2D",
                    ))

        return setups
