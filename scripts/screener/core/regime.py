"""
regime.py
=========
Global Market Regime Gatekeeper.
Evaluates index trend (SPY/QQQ MAs) and macro event risk (dev.db EconomicEvent)
to determine if the market environment supports explosive breakouts (BULL_EXPLOSIVE),
requires position sizing reductions (BULL_CHOPIER), or mandates standing down (BEAR_PROTECTIVE).
"""
from dataclasses import dataclass
import logging
import sqlite3
from pathlib import Path
from datetime import date, datetime
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    yf = None

log = logging.getLogger("screener_regime")

REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = REPO_ROOT / "web" / "prisma" / "dev.db"


@dataclass
class MarketRegimeState:
    status: str                  # "BULL_EXPLOSIVE", "BULL_CHOPIER", "BEAR_PROTECTIVE"
    spy_close: float
    spy_above_21ema: bool
    spy_above_50sma: bool
    is_macro_high_risk: bool     # True if FOMC / CPI / NFP today
    evaluated_at: str


def _check_macro_event_today() -> bool:
    """Checks dev.db EconomicEvent for high impact events today."""
    if not DB_PATH.exists():
        return False
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        today_str = date.today().strftime("%Y-%m-%d")
        cursor.execute(
            "SELECT count(*) FROM EconomicEvent WHERE datetime LIKE ? AND (impact = 'HIGH' OR name LIKE '%FOMC%' OR name LIKE '%CPI%' OR name LIKE '%NFP%')",
            (f"{today_str}%",)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception as e:
        log.warning(f"Failed to query macro events: {e}")
        return False


def get_market_regime(spy_df: pd.DataFrame = None) -> MarketRegimeState:
    """
    Evaluates global market regime.
    If spy_df is not provided, attempts to fetch SPY daily history via yfinance.
    """
    spy_close = 500.0
    spy_above_21ema = True
    spy_above_50sma = True
    status = "BULL_EXPLOSIVE"
    
    if spy_df is None and yf is not None:
        try:
            spy_df = yf.Ticker("SPY").history(period="6mo")
        except Exception as e:
            log.warning(f"Failed to fetch SPY for regime evaluation: {e}")
            spy_df = None

    if spy_df is not None and len(spy_df) >= 50:
        close = spy_df["Close"]
        spy_close = float(close.iloc[-1])
        ema21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
        sma50 = float(close.rolling(window=50).mean().iloc[-1])

        spy_above_21ema = spy_close >= ema21
        spy_above_50sma = spy_close >= sma50

        if spy_above_21ema and spy_above_50sma:
            status = "BULL_EXPLOSIVE"
        elif spy_above_50sma:
            status = "BULL_CHOPIER"
        else:
            status = "BEAR_PROTECTIVE"

    is_macro_risk = _check_macro_event_today()

    return MarketRegimeState(
        status=status,
        spy_close=round(spy_close, 2),
        spy_above_21ema=spy_above_21ema,
        spy_above_50sma=spy_above_50sma,
        is_macro_high_risk=is_macro_risk,
        evaluated_at=datetime.now().isoformat()
    )
