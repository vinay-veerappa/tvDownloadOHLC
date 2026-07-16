# filepath: tests/test_trade_outcomes.py
"""Unit tests for get_trade_outcomes() and _format_trade_outcome_line().

Covers the four high-level outcome states:
  - FILLED + CLOSED  (STOPPED, TARGET, generic CLOSED)
  - FILLED + OPEN    (still in flight at EOD time)
  - NEVER FILLED     (PENDING, EXPIRED, CANCELLED)
  - UNKNOWN / edge cases (no entryDate, missing pnl, etc.)

The Prisma client is mocked (we never touch the real DB in unit tests).
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytz

# Import the module under test
import scripts.trader.daily_narrative as dn


# ── Helpers ────────────────────────────────────────────────────────
def _make_trade(
    *,
    ticker: str = "MNQ",
    direction: str = "LONG",
    status: str = "PENDING",
    entry_date: datetime | None = None,
    exit_date: datetime | None = None,
    entry_price: float = 17000.0,
    exit_price: float | None = None,
    stop_loss: float = 16950.0,
    take_profit: float = 17100.0,
    quantity: int = 1,
    pnl: float | None = None,
    mae: float | None = None,
    mfe: float | None = None,
) -> SimpleNamespace:
    """Build a SimpleNamespace that mimics a Prisma Trade row."""
    return SimpleNamespace(
        ticker=ticker,
        direction=direction,
        status=status,
        entryDate=entry_date,
        exitDate=exit_date,
        entryPrice=entry_price,
        exitPrice=exit_price,
        stopLoss=stop_loss,
        takeProfit=take_profit,
        quantity=quantity,
        pnl=pnl,
        mae=mae,
        mfe=mfe,
    )


def _et(year, month, day, hour, minute=0):
    """Build an ET (US/Eastern) datetime for fixture use."""
    eastern = pytz.timezone("US/Eastern")
    return eastern.localize(datetime(year, month, day, hour, minute))


# ── _format_trade_outcome_line: NEVER FILLED cases ──────────────────
def test_format_pending_long_never_filled_limit_not_hit() -> None:
    t = _make_trade(status="PENDING", entry_date=None, entry_price=17000.0)
    line = dn._format_trade_outcome_line(t, now=datetime.now(timezone.utc))
    assert "MNQ LONG qty=1" in line
    assert "PLANNED entry=17000.0 stop=16950.0 target=17100.0" in line
    assert "NEVER FILLED (limit not hit)" in line


def test_format_pending_short_never_filled_limit_not_hit() -> None:
    t = _make_trade(direction="SHORT", status="PENDING", entry_date=None,
                    entry_price=5000.0, stop_loss=5030.0, take_profit=4940.0)
    line = dn._format_trade_outcome_line(t, now=datetime.now(timezone.utc))
    assert "MES SHORT qty=1" not in line  # wrong ticker
    assert "MNQ SHORT qty=1" in line
    assert "PLANNED entry=5000.0 stop=5030.0 target=4940.0" in line
    assert "NEVER FILLED (limit not hit)" in line


def test_format_expired_status_never_filled_with_reason() -> None:
    t = _make_trade(status="EXPIRED", entry_date=None)
    line = dn._format_trade_outcome_line(t, now=datetime.now(timezone.utc))
    assert "NEVER FILLED (status=EXPIRED)" in line


def test_format_cancelled_status_never_filled_with_reason() -> None:
    t = _make_trade(status="CANCELLED", entry_date=None)
    line = dn._format_trade_outcome_line(t, now=datetime.now(timezone.utc))
    assert "NEVER FILLED (status=CANCELLED)" in line


# ── _format_trade_outcome_line: FILLED + CLOSED cases ──────────────
def test_format_stopped_long_with_pnl() -> None:
    """09:35 ET fill, 10:15 ET stop-out at 16950, -$100 loss."""
    fill = _et(2026, 7, 14, 9, 35)
    stop = _et(2026, 7, 14, 10, 15)
    t = _make_trade(status="STOPPED", entry_date=fill, exit_date=stop,
                    exit_price=16950.0, pnl=-100.0, mae=-50.0, mfe=20.0)
    line = dn._format_trade_outcome_line(t, now=datetime.now(timezone.utc))
    assert "FILLED 17000.0 @09:35" in line
    assert "STOPPED 16950.0 @10:15" in line
    assert "P&L=$-100" in line
    assert "MAE=-50" in line
    assert "MFE=20" in line


def test_format_loss_status_treated_as_stop() -> None:
    """A 'LOSS' status should produce the same STOPPED phrasing."""
    fill = _et(2026, 7, 14, 9, 35)
    stop = _et(2026, 7, 14, 10, 15)
    t = _make_trade(status="LOSS", entry_date=fill, exit_date=stop,
                    exit_price=5030.0, pnl=-150.0)
    line = dn._format_trade_outcome_line(t, now=datetime.now(timezone.utc))
    assert "STOPPED 5030.0" in line


def test_format_target_hit_long_with_pnl() -> None:
    fill = _et(2026, 7, 14, 11, 22)
    tgt = _et(2026, 7, 14, 13, 45)
    t = _make_trade(status="TARGET_HIT", entry_date=fill, exit_date=tgt,
                    exit_price=17100.0, pnl=200.0, mae=-20.0, mfe=100.0)
    line = dn._format_trade_outcome_line(t, now=datetime.now(timezone.utc))
    assert "FILLED 17000.0 @11:22" in line
    assert "TARGET 17100.0 @13:45" in line
    assert "P&L=$+200" in line


def test_format_win_status_treated_as_target() -> None:
    fill = _et(2026, 7, 14, 9, 35)
    tgt = _et(2026, 7, 14, 14, 0)
    t = _make_trade(status="WIN", entry_date=fill, exit_date=tgt,
                    exit_price=4940.0, pnl=300.0)
    line = dn._format_trade_outcome_line(t, now=datetime.now(timezone.utc))
    assert "TARGET 4940.0" in line


def test_format_closed_status_neutral_phrasing() -> None:
    """A generic 'CLOSED' status with both an entry and exit should
    produce a 'CLOSED' (not STOPPED/TARGET) outcome phrase."""
    fill = _et(2026, 7, 14, 9, 35)
    close = _et(2026, 7, 14, 12, 0)
    t = _make_trade(status="CLOSED", entry_date=fill, exit_date=close,
                    exit_price=17050.0, pnl=50.0)
    line = dn._format_trade_outcome_line(t, now=datetime.now(timezone.utc))
    assert "CLOSED 17050.0 @12:00" in line
    assert "P&L=$+50" in line


def test_format_closed_status_missing_pnl_gracefully() -> None:
    """Missing pnl should show 'P&L=unrecorded', not crash."""
    fill = _et(2026, 7, 14, 9, 35)
    close = _et(2026, 7, 14, 12, 0)
    t = _make_trade(status="CLOSED", entry_date=fill, exit_date=close,
                    exit_price=17050.0, pnl=None)
    line = dn._format_trade_outcome_line(t, now=datetime.now(timezone.utc))
    assert "P&L=unrecorded" in line


def test_format_closed_status_missing_exit_date_shows_question_mark() -> None:
    """Missing exitDate should render as '?' rather than crashing."""
    fill = _et(2026, 7, 14, 9, 35)
    t = _make_trade(status="CLOSED", entry_date=fill, exit_date=None,
                    exit_price=17050.0, pnl=50.0)
    line = dn._format_trade_outcome_line(t, now=datetime.now(timezone.utc))
    assert "@?" in line


# ── _format_trade_outcome_line: FILLED + OPEN cases ────────────────
def test_format_filled_still_open() -> None:
    fill = _et(2026, 7, 14, 9, 35)
    t = _make_trade(status="FILLED", entry_date=fill, mfe=80.0, mae=-10.0)
    line = dn._format_trade_outcome_line(t, now=datetime.now(timezone.utc))
    assert "FILLED 17000.0 @09:35" in line
    assert "STILL OPEN" in line
    assert "MFE=+80" in line
    assert "MAE=-10" in line


def test_format_open_status_treated_as_still_open() -> None:
    fill = _et(2026, 7, 14, 9, 35)
    t = _make_trade(status="OPEN", entry_date=fill, mfe=50.0, mae=-5.0)
    line = dn._format_trade_outcome_line(t, now=datetime.now(timezone.utc))
    assert "STILL OPEN" in line


def test_format_filled_status_missing_mfe_mae_defaults_to_zero() -> None:
    fill = _et(2026, 7, 14, 9, 35)
    t = _make_trade(status="FILLED", entry_date=fill, mfe=None, mae=None)
    line = dn._format_trade_outcome_line(t, now=datetime.now(timezone.utc))
    assert "STILL OPEN" in line
    assert "MFE=+0" in line
    assert "MAE=+0" in line


# ── Time conversion ────────────────────────────────────────────────
def test_utc_to_et_str_handles_aware_utc() -> None:
    """Aware UTC datetimes convert to ET."""
    utc = pytz.utc.localize(datetime(2026, 7, 14, 13, 35))  # 13:35 UTC = 09:35 ET
    result = dn._utc_to_et_str(utc)
    assert result == "09:35"


def test_utc_to_et_str_handles_naive_utc() -> None:
    """Naive datetimes are assumed UTC."""
    naive = datetime(2026, 7, 14, 13, 35)
    result = dn._utc_to_et_str(naive)
    assert result == "09:35"


def test_utc_to_et_str_returns_question_mark_for_none() -> None:
    assert dn._utc_to_et_str(None) == "?"


# ── get_trade_outcomes: end-to-end with mocked Prisma ──────────────
@pytest.mark.asyncio
async def test_get_trade_outcomes_no_account_returns_message(monkeypatch) -> None:
    """If the account row is missing, return a short explanatory message."""
    mock_db = MagicMock()
    mock_db.connect = AsyncMock()
    mock_db.disconnect = AsyncMock()
    mock_db.account.find_first = AsyncMock(return_value=None)

    # Patch Prisma class so `Prisma()` returns our mock
    monkeypatch.setattr(dn, "Prisma", lambda: mock_db)

    result = await dn.get_trade_outcomes()
    assert "unavailable" in result
    assert "not found" in result


@pytest.mark.asyncio
async def test_get_trade_outcomes_no_trades_returns_message(monkeypatch) -> None:
    """If no trades were created today, return a short message."""
    mock_acc = MagicMock()
    mock_acc.id = "acc-1"
    mock_db = MagicMock()
    mock_db.connect = AsyncMock()
    mock_db.disconnect = AsyncMock()
    mock_db.account.find_first = AsyncMock(return_value=mock_acc)
    mock_db.trade.find_many = AsyncMock(return_value=[])

    monkeypatch.setattr(dn, "Prisma", lambda: mock_db)

    result = await dn.get_trade_outcomes()
    assert "No trades" in result


@pytest.mark.asyncio
async def test_get_trade_outcomes_mixed_states(monkeypatch) -> None:
    """A mix of FILLED+STOPPED, FILLED+OPEN, and NEVER FILLED all
    appear in the output in chronological (createdAt-asc) order."""
    mock_acc = MagicMock()
    mock_acc.id = "acc-1"
    mock_db = MagicMock()
    mock_db.connect = AsyncMock()
    mock_db.disconnect = AsyncMock()
    mock_db.account.find_first = AsyncMock(return_value=mock_acc)

    # Three trades: stopped MNQ, open MES, never-filled MNQ
    trades = [
        _make_trade(ticker="MNQ", status="STOPPED",
                    entry_date=_et(2026, 7, 14, 9, 35),
                    exit_date=_et(2026, 7, 14, 10, 15),
                    exit_price=16950.0, pnl=-100.0),
        _make_trade(ticker="MES", status="FILLED",
                    entry_date=_et(2026, 7, 14, 11, 0), mfe=40.0, mae=-10.0,
                    entry_price=5000.0, stop_loss=4970.0, take_profit=5060.0),
        _make_trade(ticker="MNQ", status="PENDING", entry_date=None,
                    entry_price=17200.0, stop_loss=17150.0, take_profit=17300.0,
                    direction="SHORT"),
    ]
    mock_db.trade.find_many = AsyncMock(return_value=trades)

    monkeypatch.setattr(dn, "Prisma", lambda: mock_db)

    result = await dn.get_trade_outcomes()
    lines = result.split("\n")
    assert len(lines) == 3
    # MNQ STOPPED
    assert "MNQ LONG qty=1" in lines[0]
    assert "STOPPED 16950.0 @10:15" in lines[0]
    # MES STILL OPEN
    assert "MES LONG qty=1" in lines[1]
    assert "STILL OPEN" in lines[1]
    # MNQ NEVER FILLED
    assert "MNQ SHORT qty=1" in lines[2]
    assert "NEVER FILLED" in lines[2]


@pytest.mark.asyncio
async def test_get_trade_outcomes_ticker_filter_maps_to_micro(monkeypatch) -> None:
    """When narrative tickers [NQ1, ES1] are passed, the Prisma query
    should filter for [MNQ, MES] in the ticker field."""
    mock_acc = MagicMock()
    mock_acc.id = "acc-1"
    mock_db = MagicMock()
    mock_db.connect = AsyncMock()
    mock_db.disconnect = AsyncMock()
    mock_db.account.find_first = AsyncMock(return_value=mock_acc)
    mock_db.trade.find_many = AsyncMock(return_value=[])

    captured_kwargs = {}
    async def _capture_find_many(**kwargs):
        captured_kwargs.update(kwargs)
        return []

    mock_db.trade.find_many = _capture_find_many

    monkeypatch.setattr(dn, "Prisma", lambda: mock_db)

    await dn.get_trade_outcomes(tickers=["NQ1", "ES1"])

    # The where clause should include ticker filter with MNQ+MES
    where = captured_kwargs.get("where", {})
    ticker_filter = where.get("ticker", {})
    assert "in" in ticker_filter
    assert set(ticker_filter["in"]) == {"MNQ", "MES"}


@pytest.mark.asyncio
async def test_get_trade_outcomes_ticker_filter_none_returns_all(monkeypatch) -> None:
    """When tickers=None, no ticker filter is applied."""
    mock_acc = MagicMock()
    mock_acc.id = "acc-1"
    mock_db = MagicMock()
    mock_db.connect = AsyncMock()
    mock_db.disconnect = AsyncMock()
    mock_db.account.find_first = AsyncMock(return_value=mock_acc)
    mock_db.trade.find_many = AsyncMock(return_value=[])

    captured_kwargs = {}
    async def _capture_find_many(**kwargs):
        captured_kwargs.update(kwargs)
        return []

    mock_db.trade.find_many = _capture_find_many

    monkeypatch.setattr(dn, "Prisma", lambda: mock_db)

    await dn.get_trade_outcomes()  # no tickers arg

    where = captured_kwargs.get("where", {})
    assert "ticker" not in where


@pytest.mark.asyncio
async def test_get_trade_outcomes_creates_single_connection(monkeypatch) -> None:
    """The function should call connect() and disconnect() exactly once."""
    mock_acc = MagicMock()
    mock_acc.id = "acc-1"
    mock_db = MagicMock()
    mock_db.connect = AsyncMock()
    mock_db.disconnect = AsyncMock()
    mock_db.account.find_first = AsyncMock(return_value=mock_acc)
    mock_db.trade.find_many = AsyncMock(return_value=[])

    monkeypatch.setattr(dn, "Prisma", lambda: mock_db)

    await dn.get_trade_outcomes()

    mock_db.connect.assert_awaited_once()
    mock_db.disconnect.assert_awaited_once()
