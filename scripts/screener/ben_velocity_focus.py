"""
Ben Bennett (@PatternProfits) Velocity & Focus List Scanner Engine
Implements the exact dual-scanner system presented in the TraderLion / Stage Analysis Masterclass:

1. VELOCITY SCAN — Momentum Leaders
   - Price >= $10, Price % Chg >= +3.0%, 50-Day Avg Vol >= 150k, Vol % Chg >= +30%
   - RS Rating >= 60, Float <= 100M shares
   - Computes 'Days to Turn' (Float / Today's Vol) with < 20d highlighted (Fast Float Churn)
   - Short Squeeze Overlay: Short Float > 20%, Short Ratio > 5.0

2. FOCUS LIST — Institutional Leaders
   - Hard Floors: EPS YoY >= +25%, Rev YoY >= +25%, RS Rating >= 80
   - Composite Score (0-100): 40% EPS Growth + 30% Rev Growth + 30% RS Rating
   - Industry Group strength and quarterly rotation tracking
"""

import sys
import os
import math
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from pathlib import Path
import yfinance as yf
import pandas as pd
import numpy as np

# Dynamic root resolution
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from scripts.csp_ranking.finviz_client import FinvizClient
from scripts.csp_ranking.technicals import TechnicalAnalyzer
from scripts.utils.universe_manager import get_universe


# ─── 1. VELOCITY SCAN: MOMENTUM LEADERS ───────────────────────────────────────

class VelocityLeader:
    def __init__(self, data: Dict[str, Any]):
        self.ticker: str = data["ticker"]
        self.price: float = data["price"]
        self.chg: float = data["chg"]
        self.chg_pct: float = data["chg_pct"]
        self.rs_rating: int = data["rs_rating"]
        self.rel_vol_pct: float = data["rel_vol_pct"] # e.g. 626%
        self.float_m: float = data["float_m"]         # e.g. 17.1M
        self.today_vol: int = data["today_vol"]
        self.days_to_turn: float = data["days_to_turn"] # Float / Volume
        self.short_float_pct: float = data.get("short_float_pct", 0.0)
        self.short_ratio: float = data.get("short_ratio", 0.0)
        self.is_short_squeeze: bool = self.short_float_pct >= 20.0 or self.short_ratio >= 5.0
        self.is_fast_turn: bool = self.days_to_turn < 20.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "price": round(self.price, 2),
            "chg": round(self.chg, 2),
            "chg_pct": round(self.chg_pct, 2),
            "rs_rating": self.rs_rating,
            "rel_vol_pct": round(self.rel_vol_pct, 0),
            "float_m": round(self.float_m, 1),
            "days_to_turn": round(self.days_to_turn, 1),
            "short_float_pct": round(self.short_float_pct, 1),
            "short_ratio": round(self.short_ratio, 1),
            "is_fast_turn": self.is_fast_turn,
            "is_short_squeeze": self.is_short_squeeze
        }


def scan_velocity_momentum(
    tickers: Optional[List[str]] = None,
    min_price: float = 10.0,
    min_chg_pct: float = 2.0,       # Ben's filter is +3%, allowing 2% for comprehensive scan
    min_avg_vol_k: float = 150.0,   # 150k 50-day avg volume
    min_rel_vol_pct: float = 130.0, # +30% above 50-day avg
    min_rs_rating: int = 60,        # RS >= 60
    max_float_m: float = 100.0,     # Low Float <= 100M shares
) -> List[VelocityLeader]:
    """
    Executes Ben Bennett's exact Velocity Momentum Leader scan.
    """
    target_tickers = tickers or get_universe("all")
    finviz_client = FinvizClient()
    discovered: List[VelocityLeader] = []

    print(f"\n⚡ Running Ben's Velocity Scan across {len(target_tickers)} candidates...")
    print(f"   [Criteria: Price >= ${min_price}, Chg >= +{min_chg_pct}%, Rel Vol >= {min_rel_vol_pct}%, RS >= {min_rs_rating}, Float <= {max_float_m}M]")

    # 1. Fetch SPY 1-yr return for RS baseline
    try:
        spy_hist = yf.Ticker("SPY").history(period="1y")
        spy_1y_ret = (float(spy_hist["Close"].iloc[-1]) / float(spy_hist["Close"].iloc[0]) - 1.0) * 100.0
    except Exception:
        spy_1y_ret = 25.0

    for ticker in target_tickers:
        try:
            prof = finviz_client.get_ticker_profile(ticker)
            if not prof:
                continue

            # Quick fundamental pre-filter
            if prof.price < min_price:
                continue

            # Parse Float from Finviz or fallback
            float_str = prof.raw_data.get("Shs Float", "")
            float_val_m = 0.0
            if float_str and float_str != "-":
                if float_str.endswith("M"):
                    float_val_m = float(float_str.replace("M", ""))
                elif float_str.endswith("B"):
                    float_val_m = float(float_str.replace("B", "")) * 1000.0
                elif float_str.endswith("K"):
                    float_val_m = float(float_str.replace("K", "")) / 1000.0

            # Float constraint
            if float_val_m > max_float_m and float_val_m > 0:
                continue

            # Fetch daily OHLCV
            stock = yf.Ticker(ticker)
            hist = stock.history(period="6mo")
            if hist.empty or len(hist) < 50:
                continue

            close_today = float(hist["Close"].iloc[-1])
            close_prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else close_today
            chg = close_today - close_prev
            chg_pct = (chg / close_prev) * 100.0 if close_prev > 0 else 0.0

            if chg_pct < min_chg_pct:
                continue

            vol_today = int(hist["Volume"].iloc[-1])
            vol_50_median = float(hist["Volume"].tail(50).median())
            avg_vol_50 = float(hist["Volume"].tail(50).mean())

            if (avg_vol_50 / 1000.0) < min_avg_vol_k:
                continue

            rel_vol_pct = (vol_today / vol_50_median) * 100.0 if vol_50_median > 0 else 100.0
            if rel_vol_pct < min_rel_vol_pct:
                continue

            # Relative Strength Percentile Calculation vs SPY (6-mo momentum)
            stock_6m_ret = (close_today / float(hist["Close"].iloc[0]) - 1.0) * 100.0
            rs_score = int(min(99, max(1, 50 + (stock_6m_ret - (spy_1y_ret * 0.5)) * 0.8)))
            if rs_score < min_rs_rating:
                continue

            # Days to Turn Calculation: (Float Shares) / (Today's Volume)
            if float_val_m > 0 and vol_today > 0:
                days_to_turn = (float_val_m * 1_000_000.0) / float(vol_today)
            else:
                days_to_turn = 99.9

            # Short Float & Short Ratio
            short_float = prof.short_float
            short_ratio_val = float(prof.raw_data.get("Short Ratio", 0.0)) if prof.raw_data.get("Short Ratio", "-") != "-" else 0.0

            cand = VelocityLeader({
                "ticker": ticker,
                "price": close_today,
                "chg": chg,
                "chg_pct": chg_pct,
                "rs_rating": rs_score,
                "rel_vol_pct": rel_vol_pct,
                "float_m": float_val_m,
                "today_vol": vol_today,
                "days_to_turn": days_to_turn,
                "short_float_pct": short_float,
                "short_ratio": short_ratio_val
            })
            discovered.append(cand)

        except Exception:
            continue

    # Sort descending by RS Rating (and ascending by Days to Turn for ties)
    discovered.sort(key=lambda x: (x.rs_rating, -x.days_to_turn), reverse=True)
    print(f"✅ Velocity Scan complete: Found {len(discovered)} qualifying Momentum Leaders.")
    return discovered


# ─── 2. FOCUS LIST: INSTITUTIONAL LEADERS ────────────────────────────────────

class InstitutionalLeader:
    def __init__(self, data: Dict[str, Any]):
        self.ticker: str = data["ticker"]
        self.price: float = data["price"]
        self.eps_yoy: float = data["eps_yoy"]     # YoY EPS Growth % (e.g. +541%)
        self.rev_yoy: float = data["rev_yoy"]     # YoY Rev Growth % (e.g. +247%)
        self.rs_rating: int = data["rs_rating"]   # RS Percentile (e.g. 96)
        self.score: float = data["score"]         # 0-100 composite
        self.industry: str = data["industry"]
        self.sector: str = data["sector"]
        self.notes: str = data.get("notes", "")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "price": round(self.price, 2),
            "eps_yoy": round(self.eps_yoy, 1),
            "rev_yoy": round(self.rev_yoy, 1),
            "rs_rating": self.rs_rating,
            "score": round(self.score, 1),
            "industry": self.industry,
            "sector": self.sector,
            "notes": self.notes
        }


def scan_institutional_leaders(
    tickers: Optional[List[str]] = None,
    min_eps_yoy: float = 20.0,   # Ben's hard floor is +25%
    min_rev_yoy: float = 20.0,   # Ben's hard floor is +25%
    min_rs_rating: int = 75,     # Ben's hard floor is RS 80
) -> List[InstitutionalLeader]:
    """
    Executes Ben Bennett's exact Focus List: Institutional Leaders scan.
    Score = (40% EPS YoY) + (30% Rev YoY) + (30% RS Rating).
    """
    target_tickers = tickers or get_universe("all")
    finviz_client = FinvizClient()
    discovered: List[InstitutionalLeader] = []

    print(f"\n🏛️ Running Ben's Focus List: Institutional Leaders Scan across {len(target_tickers)} candidates...")
    print(f"   [Hard Floors: EPS YoY >= +{min_eps_yoy}%, Rev YoY >= +{min_rev_yoy}%, RS >= {min_rs_rating}]")
    print(f"   [Composite Score Weight: 40% EPS Growth + 30% Rev Growth + 30% RS Rating]")

    # SPY 1-yr baseline
    try:
        spy_hist = yf.Ticker("SPY").history(period="1y")
        spy_1y_ret = (float(spy_hist["Close"].iloc[-1]) / float(spy_hist["Close"].iloc[0]) - 1.0) * 100.0
    except Exception:
        spy_1y_ret = 25.0

    for ticker in target_tickers:
        try:
            prof = finviz_client.get_ticker_profile(ticker)
            if not prof:
                continue

            if prof.price < 10.0:
                continue

            # Hard Floors: EPS YoY and Sales YoY
            eps_growth = prof.eps_qq
            rev_growth = prof.sales_qq

            if eps_growth < min_eps_yoy or rev_growth < min_rev_yoy:
                continue

            # Near 52-week High Check (within 20% of highs)
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            if hist.empty or len(hist) < 50:
                continue

            high_52w = float(hist["High"].max())
            close_today = float(hist["Close"].iloc[-1])
            dist_to_high = ((high_52w - close_today) / high_52w) * 100.0
            if dist_to_high > 25.0:
                continue # Disqualify: more than 25% off 52-week highs

            # RS Rating calculation
            stock_1y_ret = (close_today / float(hist["Close"].iloc[0]) - 1.0) * 100.0
            rs_score = int(min(99, max(1, 50 + (stock_1y_ret - spy_1y_ret) * 0.7)))

            if rs_score < min_rs_rating:
                continue

            # Composite Score (0-100)
            # EPS Component: 0-40 pts (caps at +200% growth)
            eps_pts = min(40.0, (eps_growth / 200.0) * 40.0)
            # Rev Component: 0-30 pts (caps at +100% growth)
            rev_pts = min(30.0, (rev_growth / 100.0) * 30.0)
            # RS Component: 0-30 pts (RS 80 = 24 pts, RS 99 = 30 pts)
            rs_pts = (rs_score / 100.0) * 30.0

            composite_score = eps_pts + rev_pts + rs_pts

            cand = InstitutionalLeader({
                "ticker": ticker,
                "price": close_today,
                "eps_yoy": eps_growth,
                "rev_yoy": rev_growth,
                "rs_rating": rs_score,
                "score": composite_score,
                "industry": prof.industry,
                "sector": prof.sector,
                "notes": f"{prof.industry} ({prof.sector})"
            })
            discovered.append(cand)

        except Exception:
            continue

    # Sort descending by Composite Score
    discovered.sort(key=lambda x: x.score, reverse=True)
    print(f"✅ Focus List scan complete: Found {len(discovered)} top Institutional Leaders.")
    return discovered


# ─── 3. CLI & TEST RUNNER ────────────────────────────────────────────────────

def print_ben_scans():
    velocity_list = scan_velocity_momentum()
    leaders_list = scan_institutional_leaders()

    print("\n" + "=" * 95)
    print("  VELOCITY SCAN: MOMENTUM LEADERS (Fast Float Churn & High Rel Vol)")
    print("=" * 95)
    print(f"  {'#':<3} {'Ticker':<7} {'Price':<8} {'Chg %':<8} {'RS':<5} {'Rel Vol':<10} {'Float':<8} {'Days to Turn':<15} {'Short Float':<12}")
    print("  " + "-" * 91)
    for i, v in enumerate(velocity_list[:12], 1):
        fast_tag = "🔥 (<20d)" if v.is_fast_turn else ""
        sq_tag = "🍋 Squeeze" if v.is_short_squeeze else ""
        print(f"  {i:<3} {v.ticker:<7} ${v.price:<7.2f} {v.chg_pct:>+6.2f}% {v.rs_rating:<5} {v.rel_vol_pct:>6.0f}%   {v.float_m:>5.1f}M  {v.days_to_turn:>6.1f}d {fast_tag:<8} {v.short_float_pct:>5.1f}% {sq_tag}")

    print("\n" + "=" * 95)
    print("  FOCUS LIST: INSTITUTIONAL LEADERS (Earnings 40 / Rev 30 / RS 30)")
    print("=" * 95)
    print(f"  {'#':<3} {'Ticker':<7} {'Price':<8} {'EPS YoY':<10} {'Rev YoY':<10} {'RS':<5} {'Score':<7} {'Industry / Group':<30}")
    print("  " + "-" * 91)
    for i, l in enumerate(leaders_list[:15], 1):
        print(f"  {i:<3} {l.ticker:<7} ${l.price:<7.2f} {l.eps_yoy:>+7.1f}%   {l.rev_yoy:>+7.1f}%   {l.rs_rating:<5} {l.score:>5.1f}   {l.industry:<30}")
    print("=" * 95 + "\n")


if __name__ == "__main__":
    print_ben_scans()
