"""
Institutional Levels Engine (1H+ and Key Session Anchors Only) - Vectorized & Ultra-Fast

Computes pure institutional reference levels:
1. Daily Levels: Prior Day High (PDH), Prior Day Low (PDL), Prior Day Close (PDC), Prior Day Open (PDO)
2. Overnight Session Levels (18:00 to 09:30 ET): Overnight High (ONH), Overnight Low (ONL), Overnight Mid (EQ)
3. Key Benchmark Opens: Midnight Open (00:00 ET), RTH Open (09:30 ET)
4. 1-Hour Rolling Fractal Swings: 1H BSL (Buy-Side Liquidity) and 1H SSL (Sell-Side Liquidity)
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np


class InstitutionalLevelEngine:
    """
    Computes and tracks exclusively 1H+ institutional reference points and session benchmark anchors.
    Rejects 5m and 15m noise levels completely.
    """

    def __init__(self, swing_lookback_1h: int = 2):
        self.swing_lookback_1h = swing_lookback_1h

    def compute_levels(self, df_5m: pd.DataFrame) -> pd.DataFrame:
        """
        Takes a 5-minute DatetimeIndex OHLCV DataFrame (ET timezone)
        and computes all 1H+ and session institutional levels via vectorized operations.
        """
        df = df_5m.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df["datetime"] = pd.to_datetime(df["datetime"])
            df.set_index("datetime", inplace=True)

        if df.index.tz is not None and str(df.index.tz) not in ("America/New_York", "US/Eastern"):
            raise ValueError(
                f"institutional_levels expects ET-naive or ET-aware index; got tz={df.index.tz}. "
                "UTC data will shift session windows by 4-5h. Convert with df.tz_convert('America/New_York').tz_localize(None)."
            )

        df = df.sort_index()

        # 1. 1-Hour Rolling Swings
        df_1h = df.resample("1h").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last"
        }).dropna()

        n_1h = len(df_1h)
        h_1h = df_1h["high"].values
        l_1h = df_1h["low"].values

        sw_h_1h = np.full(n_1h, np.nan)
        sw_l_1h = np.full(n_1h, np.nan)

        k = self.swing_lookback_1h
        for i in range(k, n_1h - k):
            if all(h_1h[i] > h_1h[i - j] for j in range(1, k + 1)) and all(h_1h[i] > h_1h[i + j] for j in range(1, k + 1)):
                sw_h_1h[i + k] = h_1h[i]
            if all(l_1h[i] < l_1h[i - j] for j in range(1, k + 1)) and all(l_1h[i] < l_1h[i + j] for j in range(1, k + 1)):
                sw_l_1h[i + k] = l_1h[i]

        df_1h["sw_h_1h"] = sw_h_1h
        df_1h["sw_l_1h"] = sw_l_1h

        df["htf_1h_bsl"] = df_1h["sw_h_1h"].shift(1).reindex(df.index, method="ffill")
        df["htf_1h_ssl"] = df_1h["sw_l_1h"].shift(1).reindex(df.index, method="ffill")

        # 2. Daily Prior Day Levels (PDH, PDL, PDC, PDO)
        daily = df.groupby(df.index.date).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last"
        })
        daily_shifted = daily.shift(1)

        pdh_map = daily_shifted["high"].to_dict()
        pdl_map = daily_shifted["low"].to_dict()
        pdc_map = daily_shifted["close"].to_dict()
        pdo_map = daily_shifted["open"].to_dict()

        bar_dates = df.index.date
        df["pdh"] = [pdh_map.get(d, np.nan) for d in bar_dates]
        df["pdl"] = [pdl_map.get(d, np.nan) for d in bar_dates]
        df["pdc"] = [pdc_map.get(d, np.nan) for d in bar_dates]
        df["pdo"] = [pdo_map.get(d, np.nan) for d in bar_dates]

        # 3. Vectorized Overnight & Session Anchors
        hours = df.index.hour.values
        dates = df.index.date
        next_dates = (df.index + pd.Timedelta(days=1)).date

        session_dates = np.where(hours >= 18, next_dates, dates)
        df["session_date"] = session_dates

        times_str = df.index.strftime("%H%M")
        is_overnight = (times_str >= "1800") | (times_str < "0930")

        # Fast group agg for ONH / ONL
        df_on = df[is_overnight]
        on_agg = df_on.groupby("session_date").agg(onh=("high", "max"), onl=("low", "min"))
        onh_map = on_agg["onh"].to_dict()
        onl_map = on_agg["onl"].to_dict()

        df["onh"] = [onh_map.get(sd, np.nan) for sd in session_dates]
        df["onl"] = [onl_map.get(sd, np.nan) for sd in session_dates]
        df["on_eq"] = (df["onh"] + df["onl"]) / 2.0

        # Midnight Open (00:00 ET)
        is_midnight = (times_str == "0000")
        df_mo = df[is_midnight]
        if len(df_mo) > 0:
            mo_map = df_mo.groupby("session_date")["open"].first().to_dict()
            df["midnight_open"] = [mo_map.get(sd, np.nan) for sd in session_dates]
            df["midnight_open"] = df["midnight_open"].ffill()
        else:
            df["midnight_open"] = np.nan

        # RTH Open (09:30 ET)
        is_rth = (times_str == "0930")
        df_rth = df[is_rth]
        if len(df_rth) > 0:
            rth_map = df_rth.groupby("session_date")["open"].first().to_dict()
            df["rth_open"] = [rth_map.get(sd, np.nan) for sd in session_dates]
            df["rth_open"] = df["rth_open"].ffill()
        else:
            df["rth_open"] = np.nan

        return df

    def detect_institutional_sweep(
        self,
        bar_high: float,
        bar_low: float,
        bar_close: float,
        bar_open: float,
        pdh: float,
        pdl: float,
        onh: float,
        onl: float,
        htf_1h_bsl_list: List[float],
        htf_1h_ssl_list: List[float],
    ) -> Tuple[bool, bool, str]:
        """
        Detects if current bar swept a genuine institutional level.
        Returns: (bsl_swept, ssl_swept, level_name)
        """
        # 1. Bearish Sweep of Buy-Side Liquidity
        if not np.isnan(pdh) and bar_high > pdh and (bar_close < pdh or bar_open < pdh):
            return True, False, "PDH"

        if not np.isnan(onh) and bar_high > onh and (bar_close < onh or bar_open < onh):
            return True, False, "ONH"

        for bsl_1h in htf_1h_bsl_list:
            if bar_high > bsl_1h and (bar_close < bsl_1h or bar_open < bsl_1h):
                return True, False, "1H_BSL"

        # 2. Bullish Sweep of Sell-Side Liquidity
        if not np.isnan(pdl) and bar_low < pdl and (bar_close > pdl or bar_open > pdl):
            return False, True, "PDL"

        if not np.isnan(onl) and bar_low < onl and (bar_close > onl or bar_open > onl):
            return False, True, "ONL"

        for ssl_1h in htf_1h_ssl_list:
            if bar_low < ssl_1h and (bar_close > ssl_1h or bar_open > ssl_1h):
                return False, True, "1H_SSL"

        return False, False, "NONE"
