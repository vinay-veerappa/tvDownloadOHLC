# filepath: tests/test_trade_plan_dedup.py
"""Tests for the `extract_and_save_trade_plan` duplicate-prevention logic.

These tests pin the behaviour added in audit issue §2.2:
the function tags every new Trade with an `originalSource` ("OPEN" or
"EOD_TOMORROW") and skips the insert if a PENDING trade with the
same (ticker, direction, entryPrice, accountId, originalSource)
already exists.

Coverage:
  1. First-time save: OPEN plan creates one trade per LLM proposal.
  2. Re-run with same plan_json: second save is a no-op (the
     duplicate is detected and the create is skipped).
  3. Cross-source pair: OPEN+OPEN dup is blocked, OPEN+EOD_TOMORROW
     pair is allowed (different commitments).
  4. Source validation: invalid source string is rejected (no DB
     write, no exception).
  5. Module-level constants: TRADE_SOURCE_OPEN and
     TRADE_SOURCE_EOD_TOMORROW are exposed.
  6. The `originalSource` field is written on the Trade record.
  7. Different entryPrice or direction is NOT considered a duplicate.
  8. Closed (non-PENDING) trade with the same signature does NOT
     block a new save.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.libs_py.risk import narrative as nv
from scripts.libs_py.risk.narrative import reset_cache

from scripts.trader import daily_narrative


# ── Module-level constants ─────────────────────────────────────────
def test_trade_source_open_constant():
    assert daily_narrative.TRADE_SOURCE_OPEN == "OPEN"


def test_trade_source_eod_tomorrow_constant():
    assert daily_narrative.TRADE_SOURCE_EOD_TOMORROW == "EOD_TOMORROW"


def test_trade_source_constants_are_distinct():
    """The two source tags must be distinct — that's the whole
    point of using them to distinguish OPEN from EOD_TOMORROW
    in the dedup query."""
    assert (
        daily_narrative.TRADE_SOURCE_OPEN
        != daily_narrative.TRADE_SOURCE_EOD_TOMORROW
    )


def test_trade_source_constants_have_no_whitespace():
    """Source tags are stored in the DB. Leading/trailing
    whitespace would silently break the dedup equality check."""
    for s in (
        daily_narrative.TRADE_SOURCE_OPEN,
        daily_narrative.TRADE_SOURCE_EOD_TOMORROW,
    ):
        assert s == s.strip()
        assert " " not in s
        assert "\t" not in s
        assert "\n" not in s


# ── Prisma mock with dedup support ────────────────────────────────
class _MockAccountClient:
    def __init__(self, account_id: str) -> None:
        self._account = SimpleNamespace(id=account_id)

    async def find_first(self, *, where: dict) -> Any:
        return self._account


class _MockTradeClient:
    def __init__(self, sink: list) -> None:
        self._sink = sink
        self._existing: list[SimpleNamespace] = []

    async def create(self, *, data: dict) -> Any:
        # Write to the sink (so tests can inspect what was saved)
        # AND add to the dedup index (so the next call's
        # find_first can find it). This mirrors the real Prisma
        # behaviour where a successful create makes the row
        # visible to subsequent queries.
        self._sink.append(data)
        new_id = f"trade-{len(self._sink)}"
        # Build a SimpleNamespace with all the data fields plus id
        # so `getattr(row, key, None)` works in find_first.
        record = SimpleNamespace(id=new_id, **data)
        self._existing.append(record)
        return record

    async def find_first(self, *, where: dict) -> Any:
        """Mimic Prisma's `find_first(where=...)` for the dedup
        check added in audit issue §2.2. Returns the first existing
        record that matches all the where-clause fields, or None
        if nothing matches."""
        for row in self._existing:
            if all(getattr(row, k, None) == v for k, v in where.items()):
                return row
        return None


class _MockTradePlanClient:
    def __init__(self, sink: list) -> None:
        self._sink = sink

    async def create(self, *, data: dict) -> Any:
        self._sink.append(data)
        return SimpleNamespace(id=f"plan-{len(self._sink)}")


class _MockPrisma:
    def __init__(self) -> None:
        self.trade_records: list[dict] = []
        self.tradeplan_records: list[dict] = []
        self._account_client = _MockAccountClient("acc-1")
        self._trade_client = _MockTradeClient(self.trade_records)
        self._tradeplan_client = _MockTradePlanClient(self.tradeplan_records)

    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None

    def __getattr__(self, name: str) -> Any:
        if name == "account":
            return self._account_client
        if name == "trade":
            return self._trade_client
        if name == "tradeplan":
            return self._tradeplan_client
        raise AttributeError(name)


@pytest.fixture
def mock_prisma(monkeypatch):
    """Patch the Prisma client so the function's local import picks
    up our stub. Pattern matches the existing test file."""
    import prisma as prisma_module

    mock = _MockPrisma()

    class _Factory:
        def __new__(cls) -> _MockPrisma:
            return mock

    monkeypatch.setattr(prisma_module, "Prisma", _Factory)
    from scripts.trader import daily_narrative as dn
    monkeypatch.setattr(dn, "Prisma", _Factory)

    reset_cache()
    yield mock
    reset_cache()


def _plan_block(trades: list[dict]) -> str:
    return f"<plan_json>\n{json.dumps({'logic': 'test logic', 'trades': trades})}\n</plan_json>"


def _mnq_long(entry: float = 17000.0, stop: float = 16950.0, target: float = 17100.0) -> dict:
    return {
        "asset": "MNQ",
        "direction": "LONG",
        "entryPrice": entry,
        "stopLoss": stop,
        "takeProfit": target,
        "contracts": 1,
        "logic": "breakout above the call wall",
    }


def _mes_long(entry: float = 5000.0, stop: float = 4970.0, target: float = 5060.0) -> dict:
    return {
        "asset": "MES",
        "direction": "LONG",
        "entryPrice": entry,
        "stopLoss": stop,
        "takeProfit": target,
        "contracts": 1,
        "logic": "trend follow above VWAP",
    }


# ── 1. First-time save: one trade per LLM proposal ────────────────
@pytest.mark.asyncio
async def test_first_open_save_creates_one_trade_per_proposal(mock_prisma):
    summary = _plan_block([_mnq_long(), _mes_long()])
    await daily_narrative.extract_and_save_trade_plan(
        summary, source=daily_narrative.TRADE_SOURCE_OPEN,
    )
    assert len(mock_prisma.trade_records) == 2
    assert len(mock_prisma.tradeplan_records) == 2


# ── 2. Re-run with same plan: second save is a no-op ───────────────
@pytest.mark.asyncio
async def test_second_open_save_with_same_plan_is_deduplicated(mock_prisma):
    summary = _plan_block([_mnq_long()])
    await daily_narrative.extract_and_save_trade_plan(
        summary, source=daily_narrative.TRADE_SOURCE_OPEN,
    )
    assert len(mock_prisma.trade_records) == 1

    # Re-run with the IDENTICAL plan_json (the EOD re-emit case).
    await daily_narrative.extract_and_save_trade_plan(
        summary, source=daily_narrative.TRADE_SOURCE_OPEN,
    )
    # Second call must not have created any additional trade.
    assert len(mock_prisma.trade_records) == 1


@pytest.mark.asyncio
async def test_three_runs_yield_one_trade(mock_prisma):
    """Triple-emit case: LLM retries and produces the same plan
    three times. Only the first insert should survive."""
    summary = _plan_block([_mnq_long()])
    for _ in range(3):
        await daily_narrative.extract_and_save_trade_plan(
            summary, source=daily_narrative.TRADE_SOURCE_OPEN,
        )
    assert len(mock_prisma.trade_records) == 1


# ── 3. Cross-source pair: OPEN+EOD_TOMORROW are NOT duplicates ────
@pytest.mark.asyncio
async def test_open_then_eod_tomorrow_with_same_plan_creates_two_trades(mock_prisma):
    """The morning OPEN plan and the EOD's EOD_TOMORROW plan are
    different commitments even if the LLM returns the same
    structure — the morning is for today's session, the EOD plan
    is for tomorrow's. They must both be saved."""
    summary = _plan_block([_mnq_long()])
    await daily_narrative.extract_and_save_trade_plan(
        summary, source=daily_narrative.TRADE_SOURCE_OPEN,
    )
    await daily_narrative.extract_and_save_trade_plan(
        summary, source=daily_narrative.TRADE_SOURCE_EOD_TOMORROW,
    )
    # Both rows survived because the dedup query is
    # originalSource-aware.
    assert len(mock_prisma.trade_records) == 2
    sources = sorted(
        r["originalSource"] for r in mock_prisma.trade_records
    )
    assert sources == sorted(
        [daily_narrative.TRADE_SOURCE_OPEN,
         daily_narrative.TRADE_SOURCE_EOD_TOMORROW]
    )


@pytest.mark.asyncio
async def test_eod_tomorrow_then_eod_tomorrow_with_same_plan_deduped(mock_prisma):
    """Running the EOD twice with the same plan_json must NOT
    create two EOD_TOMORROW rows. (The audit's §2.2 case.)"""
    summary = _plan_block([_mnq_long()])
    await daily_narrative.extract_and_save_trade_plan(
        summary, source=daily_narrative.TRADE_SOURCE_EOD_TOMORROW,
    )
    await daily_narrative.extract_and_save_trade_plan(
        summary, source=daily_narrative.TRADE_SOURCE_EOD_TOMORROW,
    )
    assert len(mock_prisma.trade_records) == 1
    assert (
        mock_prisma.trade_records[0]["originalSource"]
        == daily_narrative.TRADE_SOURCE_EOD_TOMORROW
    )


# ── 4. Source validation ─────────────────────────────────────────
@pytest.mark.asyncio
async def test_invalid_source_is_rejected_no_db_write(mock_prisma):
    summary = _plan_block([_mnq_long()])
    await daily_narrative.extract_and_save_trade_plan(
        summary, source="garbage",
    )
    # The function must short-circuit and write nothing.
    assert mock_prisma.trade_records == []
    assert mock_prisma.tradeplan_records == []


@pytest.mark.asyncio
async def test_lowercase_source_is_rejected(mock_prisma):
    """Lowercase 'open' must not pass the allow-list check (the
    constants are upper-case by convention; case-sensitivity
    protects against typos in the call site)."""
    summary = _plan_block([_mnq_long()])
    await daily_narrative.extract_and_save_trade_plan(
        summary, source="open",
    )
    assert mock_prisma.trade_records == []


# ── 5. originalSource is written on the Trade record ──────────────
@pytest.mark.asyncio
async def test_trade_record_has_original_source_field(mock_prisma):
    summary = _plan_block([_mnq_long()])
    await daily_narrative.extract_and_save_trade_plan(
        summary, source=daily_narrative.TRADE_SOURCE_OPEN,
    )
    record = mock_prisma.trade_records[0]
    assert record["originalSource"] == daily_narrative.TRADE_SOURCE_OPEN


@pytest.mark.asyncio
async def test_eod_tomorrow_trade_record_has_correct_source(mock_prisma):
    summary = _plan_block([_mnq_long()])
    await daily_narrative.extract_and_save_trade_plan(
        summary, source=daily_narrative.TRADE_SOURCE_EOD_TOMORROW,
    )
    record = mock_prisma.trade_records[0]
    assert record["originalSource"] == daily_narrative.TRADE_SOURCE_EOD_TOMORROW


# ── 6. Different entryPrice or direction is NOT a duplicate ────────
@pytest.mark.asyncio
async def test_different_entry_price_not_a_duplicate(mock_prisma):
    """A small change to entryPrice (e.g. LLM adjusts after seeing
    the morning's session) must NOT be considered a duplicate.
    Stop distance is kept small so the validator does not drop
    the second trade on cap-by-risk (the test is about dedup,
    not about contract sizing)."""
    # Trade 1: entry 17000, stop 16980 (20pt stop × $2/pt = $40 risk)
    await daily_narrative.extract_and_save_trade_plan(
        _plan_block([_mnq_long(entry=17000.0, stop=16980.0, target=17020.0)]),
        source=daily_narrative.TRADE_SOURCE_OPEN,
    )
    # Trade 2: entry 17005, stop 16985 (20pt stop, $40 risk).
    # Different entryPrice → must NOT be a duplicate.
    await daily_narrative.extract_and_save_trade_plan(
        _plan_block([_mnq_long(entry=17005.0, stop=16985.0, target=17025.0)]),
        source=daily_narrative.TRADE_SOURCE_OPEN,
    )
    # Two distinct trades — different entryPrice.
    assert len(mock_prisma.trade_records) == 2


@pytest.mark.asyncio
async def test_different_direction_not_a_duplicate(mock_prisma):
    """A flip from LONG to SHORT is a completely different plan."""
    await daily_narrative.extract_and_save_trade_plan(
        _plan_block([_mnq_long()]),
        source=daily_narrative.TRADE_SOURCE_OPEN,
    )
    short_mnq = _mnq_long()
    short_mnq["direction"] = "SHORT"
    short_mnq["stopLoss"] = 17050.0
    short_mnq["takeProfit"] = 16900.0
    await daily_narrative.extract_and_save_trade_plan(
        _plan_block([short_mnq]),
        source=daily_narrative.TRADE_SOURCE_OPEN,
    )
    assert len(mock_prisma.trade_records) == 2


@pytest.mark.asyncio
async def test_different_ticker_not_a_duplicate(mock_prisma):
    """MNQ and MES with the same numeric entry are different
    trades because the `ticker` field is part of the dedup key."""
    await daily_narrative.extract_and_save_trade_plan(
        _plan_block([_mnq_long(entry=17000.0)]),
        source=daily_narrative.TRADE_SOURCE_OPEN,
    )
    await daily_narrative.extract_and_save_trade_plan(
        _plan_block([_mes_long(entry=5000.0)]),
        source=daily_narrative.TRADE_SOURCE_OPEN,
    )
    assert len(mock_prisma.trade_records) == 2


# ── 7. Closed (non-PENDING) trade does NOT block a new save ───────
@pytest.mark.asyncio
async def test_closed_trade_does_not_block_new_save(mock_prisma):
    """The dedup query filters by status='PENDING'. A trade that
    was previously filled/closed/stopped should NOT prevent a
    new save even if the entryPrice / direction / ticker match.
    The test pre-seeds the mock with a CLOSED trade in the
    'existing' list and confirms the new save still happens."""
    # Pre-seed a CLOSED trade at the same (ticker, direction,
    # entryPrice). The mock's find_first returns it only if the
    # where-clause matches, but the dedup query in the function
    # includes status='PENDING', so the mock returns None for
    # this row.
    closed = SimpleNamespace(
        id="old-trade",
        ticker="MNQ",
        direction="LONG",
        entryPrice=17000.0,
        accountId="acc-1",
        status="CLOSED",
        originalSource=daily_narrative.TRADE_SOURCE_OPEN,
    )
    mock_prisma._trade_client._existing.append(closed)

    summary = _plan_block([_mnq_long()])
    await daily_narrative.extract_and_save_trade_plan(
        summary, source=daily_narrative.TRADE_SOURCE_OPEN,
    )
    # New trade was saved — the closed trade did not block it.
    assert len(mock_prisma.trade_records) == 1


# ── 8. Default source is OPEN (backward compat) ───────────────────
@pytest.mark.asyncio
async def test_default_source_is_open(mock_prisma):
    """If the caller does not pass `source=...`, the function
    defaults to OPEN. This preserves backward compatibility for
    any out-of-tree callers that did not opt in to the new arg."""
    summary = _plan_block([_mnq_long()])
    await daily_narrative.extract_and_save_trade_plan(summary)
    record = mock_prisma.trade_records[0]
    assert record["originalSource"] == daily_narrative.TRADE_SOURCE_OPEN
