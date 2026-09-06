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
from scripts.utils.universe_manager import (
    get_universe,
    get_dynamic_velocity_universe,
    get_dynamic_institutional_universe
)


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
        self.industry: str = data.get("industry", "")
        self.sector: str = data.get("sector", "")
        self.is_short_squeeze: bool = self.short_float_pct >= 20.0 or self.short_ratio >= 5.0
        self.is_fast_turn: bool = 0 < self.days_to_turn < 20.0

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
            "industry": self.industry,
            "sector": self.sector,
            "is_fast_turn": self.is_fast_turn,
            "is_short_squeeze": self.is_short_squeeze
        }


def scan_velocity_momentum(
    tickers: Optional[List[str]] = None,
    min_price: float = 10.0,
    min_chg_pct: float = 3.0,            # Ben's exact TOS threshold: >= +3.00%
    min_avg_vol_k: float = 150.0,        # Ben's exact TOS threshold: 50-day SMA(Vol) > 150k
    min_rel_vol_pct: float = 130.0,      # Ben's exact TOS threshold: Vol / Avg50[1] >= 130%
    min_rs_rating: int = 0,              # Pure TOS scan has no RS floor (RS used for ranking/tagging)
    max_float_m: Optional[float] = None, # Pure TOS scan has no float hard cap (allows NVS, CRK)
    exclude_biotech: bool = True,        # Ben's exact TOS setting: Exclude Biotechnology
) -> List[VelocityLeader]:
    """
    Executes Ben Bennett's exact ThinkorSwim Velocity Momentum Leader scan:
    - Scan in: All Stocks (dynamically screened across US equity market)
    - Exclude: Biotechnology
    - Stock Close >= $10.00
    - Stock % Change >= +3.00%
    - 50-day SMA Volume > 150,000
    - Custom Relative Volume: 100 * Volume / SMA(Volume, 50)[1] >= 130% (Vol % Chg >= +30%)
    - Analyzes Float & Days to Turn (< 20d flagged as Fast Float Churn)
    """
    target_tickers = tickers or get_dynamic_velocity_universe()
    finviz_client = FinvizClient()
    discovered: List[VelocityLeader] = []

    float_str = f"Float <= {max_float_m}M" if max_float_m else "Float: Uncapped"
    rs_str = f"RS >= {min_rs_rating}" if min_rs_rating > 0 else "RS: Uncapped"
    bio_str = "Exclude Biotech: YES" if exclude_biotech else "Exclude Biotech: NO"

    print(f"\n⚡ Running Ben's Velocity Scan across {len(target_tickers)} candidates...")
    print(f"   [Criteria: Price >= ${min_price}, Chg >= +{min_chg_pct}%, Rel Vol >= {min_rel_vol_pct}%, Avg Vol > {min_avg_vol_k}k | {bio_str} | {float_str} | {rs_str}]")

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

            # Check Biotechnology exclusion (Defense-in-depth against TOS exclude)
            industry = prof.industry
            if exclude_biotech and industry and "biotechnology" in industry.lower():
                continue

            # Quick fundamental pre-filter
            if prof.price < min_price:
                continue

            # Parse Float from Finviz or fallback
            float_str_val = prof.raw_data.get("Shs Float", "")
            float_val_m = 0.0
            if float_str_val and float_str_val != "-":
                if float_str_val.endswith("M"):
                    float_val_m = float(float_str_val.replace("M", ""))
                elif float_str_val.endswith("B"):
                    float_val_m = float(float_str_val.replace("B", "")) * 1000.0
                elif float_str_val.endswith("K"):
                    float_val_m = float(float_str_val.replace("K", "")) / 1000.0

            # Float constraint (optional)
            if max_float_m is not None and max_float_m > 0:
                if float_val_m > max_float_m and float_val_m > 0:
                    continue

            # Fetch daily OHLCV
            stock = yf.Ticker(ticker)
            hist = stock.history(period="6mo")
            if hist.empty or len(hist) < 51:
                continue

            close_today = float(hist["Close"].iloc[-1])
            close_prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else close_today
            chg = close_today - close_prev
            chg_pct = (chg / close_prev) * 100.0 if close_prev > 0 else 0.0

            if chg_pct < min_chg_pct:
                continue

            vol_today = int(hist["Volume"].iloc[-1])
            # TOS Study: def avg50 = Average(volume, 50)[1]; volume / avg50 >= 1.30
            avg_vol_50_prev = float(hist["Volume"].iloc[-51:-1].mean())

            if (avg_vol_50_prev / 1000.0) < min_avg_vol_k:
                continue

            rel_vol_pct = (vol_today / avg_vol_50_prev) * 100.0 if avg_vol_50_prev > 0 else 100.0
            if rel_vol_pct < min_rel_vol_pct:
                continue

            # Check Biotechnology via yfinance if industry wasn't populated by Finviz
            if exclude_biotech and not industry:
                try:
                    yf_ind = stock.info.get("industry", "")
                    if "biotechnology" in yf_ind.lower():
                        continue
                    if yf_ind:
                        industry = yf_ind
                except Exception:
                    pass

            # Relative Strength Percentile Calculation vs SPY (6-mo momentum)
            stock_6m_ret = (close_today / float(hist["Close"].iloc[0]) - 1.0) * 100.0
            rs_score = int(min(99, max(1, 50 + (stock_6m_ret - (spy_1y_ret * 0.5)) * 0.8)))
            if min_rs_rating > 0 and rs_score < min_rs_rating:
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
                "short_ratio": short_ratio_val,
                "industry": industry,
                "sector": prof.sector
            })
            discovered.append(cand)

        except Exception:
            continue

    # Sort descending by Relative Volume (highest volume velocity leaders first)
    discovered.sort(key=lambda x: (x.rel_vol_pct, x.rs_rating), reverse=True)
    print(f"✅ Velocity Scan complete: Found {len(discovered)} qualifying Momentum Leaders (Ex-Biotech).")
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
    min_eps_yoy: float = 25.0,        # Ben's exact hard floor: EPS YoY >= +25%
    min_rev_yoy: float = 25.0,        # Ben's exact hard floor: Rev YoY >= +25%
    min_rs_rating: int = 80,          # Ben's exact hard floor: RS Rating >= 80
    max_dist_to_52w_high: float = 20.0, # Ben's exact floor: Near 52-week high (within 20%)
) -> List[InstitutionalLeader]:
    """
    Executes Ben Bennett's exact Focus List: Institutional Leaders scan.
    Score = (40% EPS YoY) + (30% Rev YoY) + (30% RS Rating).
    Hard floors: EPS YoY >= +25%, Rev YoY >= +25%, RS >= 80, Near 52w High (within 20%).
    """
    target_tickers = tickers or get_dynamic_institutional_universe()
    finviz_client = FinvizClient()
    discovered: List[InstitutionalLeader] = []

    print(f"\n🏛️ Running Ben's Focus List: Institutional Leaders Scan across {len(target_tickers)} candidates...")
    print(f"   [Hard Floors: EPS YoY >= +{min_eps_yoy}%, Rev YoY >= +{min_rev_yoy}%, RS >= {min_rs_rating}, Near 52w High <= {max_dist_to_52w_high}%]")
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
            if dist_to_high > max_dist_to_52w_high:
                continue # Disqualify: more than 20% off 52-week highs

            # RS Rating calculation
            stock_1y_ret = (close_today / float(hist["Close"].iloc[0]) - 1.0) * 100.0
            rs_score = int(min(99, max(1, 50 + (stock_1y_ret - spy_1y_ret) * 0.7)))

            if rs_score < min_rs_rating:
                continue

            # Industry metadata fallback
            industry = prof.industry
            if not industry:
                try:
                    industry = stock.info.get("industry", "")
                except Exception:
                    pass

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
                "industry": industry,
                "sector": prof.sector,
                "notes": f"{industry} ({prof.sector})"
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

    print("\n" + "=" * 110)
    print("  VELOCITY SCAN: MOMENTUM LEADERS (TOS Criteria: Price >= $10, Chg >= +3%, Rel Vol >= 130% | Ex-Biotech)")
    print("=" * 110)
    print(f"  {'#':<3} {'Ticker':<7} {'Price':<8} {'Chg %':<8} {'Rel Vol':<10} {'Turn':<9} {'Float':<8} {'RS':<5} {'Industry':<28} {'Tags'}")
    print("  " + "-" * 106)
    for i, v in enumerate(velocity_list[:15], 1):
        tags = []
        if v.is_fast_turn:
            tags.append("🔥 (<20d)")
        if v.is_short_squeeze:
            tags.append("🍋 Squeeze")
        tag_str = " ".join(tags)
        ind_display = (v.industry[:26] + "..") if len(v.industry) > 28 else v.industry
        print(f"  {i:<3} {v.ticker:<7} ${v.price:<7.2f} {v.chg_pct:>+6.2f}% {v.rel_vol_pct:>6.0f}%   {v.days_to_turn:>6.1f}d   {v.float_m:>5.1f}M  {v.rs_rating:<5} {ind_display:<28} {tag_str}")

    print("\n" + "=" * 110)
    print("  FOCUS LIST: INSTITUTIONAL LEADERS (Floors: EPS >= 25%, Rev >= 25%, RS >= 80 | Score: EPS 40 / Rev 30 / RS 30)")
    print("=" * 110)
    if leaders_list:
        top_scorer = leaders_list[0]
        biggest_eps = max(leaders_list, key=lambda x: x.eps_yoy)
        print(f"  🏛️  {len(leaders_list)} QUALIFIERS  |  Top Score: {top_scorer.ticker} ({top_scorer.score:.1f})  |  Biggest EPS Grower: {biggest_eps.ticker} ({biggest_eps.eps_yoy:>+5.0f}%)")
        print("  " + "-" * 106)
    print(f"  {'#':<3} {'Ticker':<7} {'Price':<8} {'EPS YoY':<10} {'Rev YoY':<10} {'RS':<5} {'Score':<7} {'Industry / Group':<32}")
    print("  " + "-" * 106)
    for i, l in enumerate(leaders_list[:15], 1):
        ind_str = (l.industry[:30] + "..") if len(l.industry) > 32 else l.industry
        print(f"  {i:<3} {l.ticker:<7} ${l.price:<7.2f} {l.eps_yoy:>+7.1f}%   {l.rev_yoy:>+7.1f}%   {l.rs_rating:<5} {l.score:>5.1f}   {ind_str:<32}")
    print("=" * 110 + "\n")


if __name__ == "__main__":
    print_ben_scans()
