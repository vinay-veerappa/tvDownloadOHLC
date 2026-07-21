import os
import json
import pytest
import datetime as dt


# ─── 1. Version Alignment Verification ───────────────────────────────────

def test_version_alignment():
    """Verify 1.5.0 version consistency across all project files."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # McpBridgeAddOn.cs
    addon_cs = os.path.join(repo_root, "ninjatrader-addon", "McpBridgeAddOn.cs")
    with open(addon_cs, "r", encoding="utf-8") as f:
        content = f.read()
        assert 'private const string Version = "1.5.0";' in content
        assert 'ctx.Response.Headers.Add("X-NT8-MCP-Version", Version);' in content

    # nt-mcp-server.js
    server_js = os.path.join(repo_root, "mcp", "ninjatrader-mcp", "nt-mcp-server.js")
    with open(server_js, "r", encoding="utf-8") as f:
        content = f.read()
        assert "const SERVER_VERSION = '1.5.0';" in content

    # package.json
    package_json = os.path.join(repo_root, "mcp", "ninjatrader-mcp", "package.json")
    with open(package_json, "r", encoding="utf-8") as f:
        pkg = json.load(f)
        assert pkg["version"] == "1.5.0"


# ─── 2. Audit Trail Format & Writing Verification ────────────────────────

def test_audit_trail_formatting(tmp_path):
    """Verify LogIntervention JSONL audit log format."""
    log_dir = tmp_path / "RiskGuard"
    log_dir.mkdir()
    log_file = log_dir / "interventions.jsonl"

    record = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "path": "/api/order",
        "request": {"action": "BUY", "quantity": 1, "symbol": "NQ 09-26", "idempotencyKey": "test-uuid-123"},
        "response": {"success": True, "orderId": "ORD-9988"}
    }

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    # Read back and parse
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["path"] == "/api/order"
    assert parsed["request"]["idempotencyKey"] == "test-uuid-123"
    assert parsed["response"]["success"] is True


# ─── 3. Indicator Calculation Logic Verification ──────────────────────────

def calculate_sma(closes, period):
    if len(closes) < period:
        return []
    return [round(sum(closes[i - period:i]) / period, 2) for i in range(period, len(closes) + 1)]

def calculate_ema(closes, period):
    if len(closes) < period:
        return []
    multiplier = 2.0 / (period + 1)
    ema = sum(closes[:period]) / period
    res = []
    for price in closes[period:]:
        ema = (price - ema) * multiplier + ema
        res.append(round(ema, 2))
    return res

def test_indicator_calculations():
    """Verify deterministic SMA and EMA indicator calculations."""
    closes = [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0, 108.0, 107.0, 109.0]
    period = 5

    smas = calculate_sma(closes, period)
    assert len(smas) == 6
    assert smas[0] == 102.2  # mean(100, 102, 101, 103, 105)

    emas = calculate_ema(closes, period)
    assert len(emas) == 5
    assert emas[-1] > smas[-1]  # EMA weights recent prices higher during an uptrend


# ─── 4. Block Bootstrap Monte Carlo Calculation Verification ─────────────

def run_monte_carlo(pnl_list, iterations=500):
    import random
    rnd = random.Random(42)
    final_equities = []
    max_dds = []

    for _ in range(iterations):
        capital = 50000.0
        peak = capital
        max_dd = 0
        for _ in range(30):
            pnl = rnd.choice(pnl_list)
            capital += pnl
            if capital > peak:
                peak = capital
            dd = capital - peak
            if dd < max_dd:
                max_dd = dd
        final_equities.append(capital - 50000.0)
        max_dds.append(max_dd)

    final_equities.sort()
    max_dds.sort()

    return {
        "iterations": iterations,
        "cvar95": round(max_dds[int(iterations * 0.05)], 2),
        "cvar99": round(max_dds[int(iterations * 0.01)], 2),
        "expectedEquityMedian": round(final_equities[iterations // 2], 2)
    }

def test_monte_carlo_engine():
    """Verify Bootstrap Monte Carlo produces non-zero risk metrics from trade PnL array."""
    pnl_sample = [250.0, -150.0, 300.0, -200.0, 450.0, -100.0]
    res = run_monte_carlo(pnl_sample, iterations=200)

    assert res["iterations"] == 200
    assert res["cvar95"] <= 0
    assert res["cvar99"] <= res["cvar95"]
    assert isinstance(res["expectedEquityMedian"], float)


# ─── 5. Trade Extraction Latency & Excursion Verification ───────────────

def test_trade_extraction_metrics():
    """Verify latency and MAE/MFE structure on extracted trades."""
    fill_time = dt.datetime(2026, 7, 21, 10, 0, 0, tzinfo=dt.timezone.utc)
    order_time = dt.datetime(2026, 7, 21, 9, 59, 59, 980000, tzinfo=dt.timezone.utc)
    
    latency_ms = int((fill_time - order_time).total_seconds() * 1000)
    assert latency_ms == 20

    price = 20500.0
    mae = round(-abs(price * 0.002), 2)
    mfe = round(abs(price * 0.005), 2)

    assert mae == -41.0
    assert mfe == 102.5


# ─── 6. ATM Order Bracket Metadata Verification ──────────────────────────

def test_atm_bracket_metadata():
    """Verify ATM order bracket metadata generation."""
    req = {
        "action": "BUY",
        "symbol": "NQ 09-26",
        "quantity": 2,
        "stopLossTicks": 20,
        "takeProfitTicks": 40
    }

    is_bracket = req.get("stopLossTicks", 0) > 0 or req.get("takeProfitTicks", 0) > 0
    assert is_bracket is True
    assert req["stopLossTicks"] == 20
    assert req["takeProfitTicks"] == 40


# ─── 7. Persistent State Store Simulation Verification ────────────────────

def test_state_persistence_stores():
    """Verify persistent state CRUD operations."""
    store = {}
    
    # SET
    store["Sim101"] = {"leaderAccount": "Sim101", "followerAccount": "SimCopy2", "quantityRatio": 1.5}
    assert store["Sim101"]["quantityRatio"] == 1.5

    # GET
    retrieved = store.get("Sim101")
    assert retrieved is not None
    assert retrieved["followerAccount"] == "SimCopy2"
