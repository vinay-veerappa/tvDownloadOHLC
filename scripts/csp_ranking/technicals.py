"""
Technical Analysis & Relative Strength (RS) Module
Calculates RS line vs SPY benchmark (Stock / SPY ratio vs 21 SMA),
technical cushions, SMA levels, and swing lows.
"""

import time
import json
from datetime import date
from typing import Dict, Any, Optional
from pathlib import Path
import pandas as pd
import yfinance as yf

CACHE_DIR = Path("data/csp_ranking/cache")


class TechnicalMetrics:
    def __init__(
        self,
        ticker: str,
        current_price: float,
        sma20: float = 0.0,
        sma50: float = 0.0,
        sma200: float = 0.0,
        swing_low_20d: float = 0.0,
        rs_ratio: float = 0.0,
        rs_sma21: float = 0.0,
        is_rs_above_ma: bool = False,
        rs_slope_10d: float = 0.0,
    ):
        self.ticker = ticker.upper()
        self.current_price = current_price
        self.sma20 = sma20
        self.sma50 = sma50
        self.sma200 = sma200
        self.swing_low_20d = swing_low_20d
        self.rs_ratio = rs_ratio
        self.rs_sma21 = rs_sma21
        self.is_rs_above_ma = is_rs_above_ma
        self.rs_slope_10d = rs_slope_10d

    def evaluate_cushion(self, strike: float) -> Dict[str, Any]:
        """
        Evaluates technical buffer/cushion between current price/SMAs and the strike.
        """
        if self.current_price <= 0 or strike <= 0:
            return {
                "otm_cushion_pct": 0.0,
                "is_below_sma50": False,
                "is_below_sma200": False,
                "is_below_swing_low": False,
                "sma50_cushion_pct": 0.0,
                "sma200_cushion_pct": 0.0,
            }

        otm_cushion_pct = (self.current_price - strike) / self.current_price * 100.0
        is_below_sma50 = strike < self.sma50 if self.sma50 > 0 else False
        is_below_sma200 = strike < self.sma200 if self.sma200 > 0 else False
        is_below_swing_low = strike < self.swing_low_20d if self.swing_low_20d > 0 else False

        sma50_cushion_pct = ((self.sma50 - strike) / self.sma50 * 100.0) if self.sma50 > 0 else 0.0
        sma200_cushion_pct = ((self.sma200 - strike) / self.sma200 * 100.0) if self.sma200 > 0 else 0.0

        return {
            "otm_cushion_pct": round(otm_cushion_pct, 2),
            "is_below_sma50": is_below_sma50,
            "is_below_sma200": is_below_sma200,
            "is_below_swing_low": is_below_swing_low,
            "sma50_cushion_pct": round(sma50_cushion_pct, 2),
            "sma200_cushion_pct": round(sma200_cushion_pct, 2),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "current_price": round(self.current_price, 2),
            "sma20": round(self.sma20, 2),
            "sma50": round(self.sma50, 2),
            "sma200": round(self.sma200, 2),
            "swing_low_20d": round(self.swing_low_20d, 2),
            "rs_ratio": round(self.rs_ratio, 4),
            "rs_sma21": round(self.rs_sma21, 4),
            "is_rs_above_ma": self.is_rs_above_ma,
            "rs_slope_10d": round(self.rs_slope_10d, 4),
        }


class TechnicalAnalyzer:
    def __init__(self, benchmark_symbol: str = "SPY", cache_ttl_seconds: int = 14400):
        self.benchmark_symbol = benchmark_symbol
        self.cache_ttl = cache_ttl_seconds
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._benchmark_df: Optional[pd.DataFrame] = None

    def _get_benchmark_data(self) -> Optional[pd.DataFrame]:
        if self._benchmark_df is not None:
            return self._benchmark_df
        try:
            spy = yf.Ticker(self.benchmark_symbol)
            df = spy.history(period="1y")
            if not df.empty:
                self._benchmark_df = df
            return self._benchmark_df
        except Exception as e:
            print(f"[TechnicalAnalyzer] Error fetching benchmark {self.benchmark_symbol}: {e}")
            return None

    def analyze_ticker(self, ticker: str, fallback_price: float = 0.0) -> TechnicalMetrics:
        ticker = ticker.upper().strip()
        cache_file = CACHE_DIR / f"{ticker}_technicals.json"
        
        # Check cache
        if cache_file.exists():
            try:
                mtime = cache_file.stat().st_mtime
                if time.time() - mtime < self.cache_ttl:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        return TechnicalMetrics(**data)
            except Exception:
                pass

        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="1y")
            if df.empty or len(df) < 5:
                # Minimal fallback
                return TechnicalMetrics(ticker=ticker, current_price=fallback_price)

            close = df["Close"]
            current_price = float(close.iloc[-1])
            sma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else current_price
            sma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else current_price
            sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else current_price
            
            lows = df["Low"]
            swing_low_20d = float(lows.tail(20).min()) if len(lows) >= 20 else float(lows.min())

            # Relative Strength vs SPY
            bench_df = self._get_benchmark_data()
            is_rs_above_ma = False
            rs_ratio_val = 0.0
            rs_sma21_val = 0.0
            rs_slope = 0.0

            if bench_df is not None and not bench_df.empty:
                # Align dates
                combined = pd.DataFrame({
                    "stock": close,
                    "bench": bench_df["Close"]
                }).dropna()
                
                if len(combined) >= 25:
                    rs_series = combined["stock"] / combined["bench"]
                    rs_sma21 = rs_series.rolling(21).mean()
                    
                    rs_ratio_val = float(rs_series.iloc[-1])
                    rs_sma21_val = float(rs_sma21.iloc[-1])
                    is_rs_above_ma = rs_ratio_val > rs_sma21_val
                    
                    # 10-day slope
                    if len(rs_series) >= 10:
                        rs_slope = float((rs_series.iloc[-1] - rs_series.iloc[-10]) / rs_series.iloc[-10] * 100.0)

            metrics = TechnicalMetrics(
                ticker=ticker,
                current_price=current_price,
                sma20=sma20,
                sma50=sma50,
                sma200=sma200,
                swing_low_20d=swing_low_20d,
                rs_ratio=rs_ratio_val,
                rs_sma21=rs_sma21_val,
                is_rs_above_ma=is_rs_above_ma,
                rs_slope_10d=rs_slope,
            )

            # Save cache
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(metrics.to_dict(), f, indent=2)

            return metrics

        except Exception as e:
            print(f"[TechnicalAnalyzer] Error analyzing {ticker}: {e}")
            return TechnicalMetrics(ticker=ticker, current_price=fallback_price)
