import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, date
import pytz
import pandas as pd

from scripts.libs_py.strategy_engine.services.regime_service import RegimeService
from scripts.libs_py.strategy_engine.services.em_service import ExpectedMoveService
from scripts.libs_py.strategy_engine.services.calendar_service import CalendarService, BlackoutWindow
from scripts.libs_py.strategy_engine.services.earnings_service import EarningsService, EarningsAnnouncement
from scripts.libs_py.strategy_engine.services.holding_service import HoldingService, HoldingRecord


# ==========================================
# RegimeService Tests
# ==========================================

@pytest.mark.asyncio
async def test_regime_service_get_gex_regime():
    mock_db = MagicMock()
    mock_db.gexsnapshot = MagicMock()
    
    # Return mock snapshot
    mock_snapshot = MagicMock()
    mock_snapshot.ticker = "SPY"
    mock_snapshot.timestamp = datetime(2026, 5, 18, 16, 0, tzinfo=pytz.utc)
    mock_snapshot.tradingDate = datetime(2026, 5, 18, 0, 0, tzinfo=pytz.utc)
    mock_snapshot.totalGex = 120000000.0
    mock_snapshot.gexRegime = "HIGH_GAMMA"
    mock_snapshot.regimeLabel = "High Gamma Regime"
    mock_snapshot.spotPrice = 5200.0
    mock_snapshot.gammaMagnet = 5220.0
    mock_snapshot.pinStrike = 5200.0
    
    mock_db.gexsnapshot.find_first = AsyncMock(return_value=mock_snapshot)
    
    service = RegimeService(mock_db)
    result = await service.get_gex_regime("SPY")
    
    assert result is not None
    assert result["gexRegime"] == "HIGH_GAMMA"
    assert result["regimeLabel"] == "High Gamma Regime"
    assert result["totalGex"] == 120000000.0
    assert result["spotPrice"] == 5200.0
    assert result["gammaMagnet"] == 5220.0
    assert result["pinStrike"] == 5200.0


@pytest.mark.asyncio
async def test_regime_service_get_gex_regime_empty():
    mock_db = MagicMock()
    mock_db.gexsnapshot = MagicMock()
    mock_db.gexsnapshot.find_first = AsyncMock(return_value=None)
    
    service = RegimeService(mock_db)
    result = await service.get_gex_regime("SPY")
    assert result is None


# ==========================================
# ExpectedMoveService Tests
# ==========================================

@pytest.mark.asyncio
async def test_expected_move_service_get_expected_move_bands():
    mock_db = MagicMock()
    mock_db.expectedmove = MagicMock()
    
    mock_em = MagicMock()
    mock_em.ticker = "SPX"
    mock_em.calculationDate = datetime(2026, 5, 18, 0, 0, tzinfo=pytz.utc)
    mock_em.expiryDate = datetime(2026, 5, 19, 0, 0, tzinfo=pytz.utc)
    mock_em.price = 5200.0
    mock_em.straddle = 45.0
    mock_em.em365 = 0.09
    mock_em.em252 = 0.08
    mock_em.adjEm = 49.0
    mock_em.manualEm = None
    
    mock_db.expectedmove.find_first = AsyncMock(return_value=mock_em)
    
    service = ExpectedMoveService(mock_db)
    result = await service.get_expected_move_bands("SPX", spot_price=5200.0, session_open=5210.0)
    
    assert result is not None
    assert result["em_value"] == 49.0
    assert result["basis_price"] == 5210.0
    assert result["upper_1sd"] == 5259.0
    assert result["lower_1sd"] == 5161.0
    assert result["source"] == "ExpectedMove"


# ==========================================
# CalendarService Tests
# ==========================================

@pytest.mark.asyncio
async def test_calendar_service_is_blackout_window():
    mock_db = MagicMock()
    mock_db.economicevent = MagicMock()
    
    # Event scheduled at 14:00
    mock_event = MagicMock()
    mock_event.name = "FOMC Press Conference"
    mock_event.impact = "High"
    mock_event.datetime = datetime(2026, 5, 18, 14, 0, tzinfo=pytz.utc)
    
    mock_db.economicevent.find_many = AsyncMock(return_value=[mock_event])
    
    service = CalendarService(mock_db)
    
    # High impact default pre buffer is 120 mins (starts at 12:00), post is 60 mins (ends at 15:00)
    # Test at 13:00 (inside window)
    assert await service.is_blackout_window(datetime(2026, 5, 18, 13, 0, tzinfo=pytz.utc)) is True
    
    # Test at 11:30 (before window)
    assert await service.is_blackout_window(datetime(2026, 5, 18, 11, 30, tzinfo=pytz.utc)) is False
    
    # Test at 15:30 (after window)
    assert await service.is_blackout_window(datetime(2026, 5, 18, 15, 30, tzinfo=pytz.utc)) is False


# ==========================================
# EarningsService Tests
# ==========================================

@pytest.mark.asyncio
async def test_earnings_service_days_to_earnings():
    mock_db = MagicMock()
    mock_db.earningscalendar = MagicMock()
    
    # Mock upcoming earnings date
    tz_et = pytz.timezone("US/Eastern")
    today_et = datetime.now(pytz.utc).astimezone(tz_et).date()
    earn_dt = tz_et.localize(datetime.combine(today_et + timedelta(days=5), datetime.min.time())).astimezone(pytz.utc)
    
    mock_earn = MagicMock()
    mock_earn.ticker = "AAPL"
    mock_earn.earningsDate = earn_dt
    mock_earn.beforeMarket = True
    mock_earn.confirmed = True
    
    mock_db.earningscalendar.find_first = AsyncMock(return_value=mock_earn)
    
    service = EarningsService(mock_db)
    days = await service.days_to_earnings("AAPL")
    
    assert days == 5
    assert await service.is_earnings_within("AAPL", 7) is True
    assert await service.is_earnings_within("AAPL", 3) is False


@pytest.mark.asyncio
@patch("yfinance.Ticker")
async def test_earnings_service_fetch_upcoming_all(mock_ticker_class):
    mock_db = MagicMock()
    mock_db.earningscalendar = MagicMock()
    mock_db.earningscalendar.upsert = AsyncMock()
    
    # Mock yfinance Ticker calendar DataFrame
    mock_ticker = MagicMock()
    mock_ticker_class.return_value = mock_ticker
    
    tz_et = pytz.timezone("US/Eastern")
    earn_date = datetime(2026, 7, 28, 16, 30) # AMC
    
    # Create pandas DataFrame similar to yfinance output
    calendar_df = pd.DataFrame(
        {"Value": [ [earn_date] ]},
        index=["Earnings Date"]
    )
    mock_ticker.calendar = calendar_df
    
    service = EarningsService(mock_db)
    count = await service.fetch_upcoming_all(["AAPL"])
    
    assert count == 1
    # Verify it attempted to upsert
    assert mock_db.earningscalendar.upsert.call_count == 1 or mock_db.earningscalendar.find_first.call_count == 1


# ==========================================
# HoldingService Tests
# ==========================================

@pytest.mark.asyncio
async def test_holding_service_add_holding_new():
    mock_db = MagicMock()
    mock_db.holding = MagicMock()
    
    mock_holding = MagicMock()
    mock_holding.ticker = "NVDA"
    mock_holding.shares = 100
    mock_holding.costBasis = 125.50
    mock_holding.acquiredAt = datetime(2026, 5, 18, 10, 0, tzinfo=pytz.utc)
    
    mock_db.holding.find_unique = AsyncMock(return_value=None)
    mock_db.holding.create = AsyncMock(return_value=mock_holding)
    
    service = HoldingService(mock_db)
    result = await service.add_holding("NVDA", 100, 125.50)
    
    assert result.ticker == "NVDA"
    assert result.shares == 100
    assert result.cost_basis == 125.50
    mock_db.holding.create.assert_called_once()


@pytest.mark.asyncio
async def test_holding_service_add_holding_increment():
    mock_db = MagicMock()
    mock_db.holding = MagicMock()
    
    # Existing holding: 100 shares @ $100
    existing_holding = MagicMock()
    existing_holding.ticker = "NVDA"
    existing_holding.shares = 100
    existing_holding.costBasis = 100.0
    existing_holding.acquiredAt = datetime(2026, 5, 18, 9, 30, tzinfo=pytz.utc)
    
    # Mock find_unique to return existing holding twice (once for initial check, once inside add_holding logic)
    mock_db.holding.find_unique = AsyncMock(return_value=existing_holding)
    
    # Updated holding: adding 100 shares @ $150 -> total 200 shares @ $125
    updated_holding = MagicMock()
    updated_holding.ticker = "NVDA"
    updated_holding.shares = 200
    updated_holding.costBasis = 125.0
    updated_holding.acquiredAt = datetime(2026, 5, 18, 9, 30, tzinfo=pytz.utc)
    
    mock_db.holding.update = AsyncMock(return_value=updated_holding)
    
    service = HoldingService(mock_db)
    result = await service.add_holding("NVDA", 100, 150.0)
    
    assert result.shares == 200
    assert result.cost_basis == 125.0
    mock_db.holding.update.assert_called_once()


@pytest.mark.asyncio
async def test_holding_service_remove_holding_partial():
    mock_db = MagicMock()
    mock_db.holding = MagicMock()
    
    existing_holding = MagicMock()
    existing_holding.ticker = "AAPL"
    existing_holding.shares = 150
    existing_holding.costBasis = 180.0
    existing_holding.acquiredAt = datetime(2026, 5, 18, 9, 30, tzinfo=pytz.utc)
    
    mock_db.holding.find_unique = AsyncMock(return_value=existing_holding)
    
    updated_holding = MagicMock()
    updated_holding.ticker = "AAPL"
    updated_holding.shares = 50
    updated_holding.costBasis = 180.0
    updated_holding.acquiredAt = datetime(2026, 5, 18, 9, 30, tzinfo=pytz.utc)
    
    mock_db.holding.update = AsyncMock(return_value=updated_holding)
    
    service = HoldingService(mock_db)
    result = await service.remove_holding("AAPL", 100)
    
    assert result is not None
    assert result.shares == 50
    mock_db.holding.update.assert_called_once()
    mock_db.holding.delete.assert_not_called()


@pytest.mark.asyncio
async def test_holding_service_remove_holding_full():
    mock_db = MagicMock()
    mock_db.holding = MagicMock()
    
    existing_holding = MagicMock()
    existing_holding.ticker = "AAPL"
    existing_holding.shares = 100
    existing_holding.costBasis = 180.0
    existing_holding.acquiredAt = datetime(2026, 5, 18, 9, 30, tzinfo=pytz.utc)
    
    mock_db.holding.find_unique = AsyncMock(return_value=existing_holding)
    mock_db.holding.delete = AsyncMock()
    
    service = HoldingService(mock_db)
    result = await service.remove_holding("AAPL", 100)
    
    assert result is None
    mock_db.holding.delete.assert_called_once()
    mock_db.holding.update.assert_not_called()
