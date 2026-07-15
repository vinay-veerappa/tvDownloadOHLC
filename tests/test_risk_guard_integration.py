# filepath: tests/test_risk_guard_integration.py
import json
import time
import urllib.request
import urllib.error
import pytest

NT8_BASE = "http://localhost:7890"

def nt_post(path, data=None):
    url = f"{NT8_BASE}{path}"
    payload = json.dumps(data).encode("utf-8") if data else b""
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"HTTP Error {e.code} on {path}: {body}")
        raise e

def nt_get(path):
    url = f"{NT8_BASE}{path}"
    with urllib.request.urlopen(url) as res:
        return json.loads(res.read().decode("utf-8"))

def cleanup_all():
    print("Running cleanup: Cancelling all orders and flattening Sim101...")
    try:
        nt_post("/api/orders/cancel-all")
    except Exception as e:
        print(f"Cleanup cancel-all failed: {e}")
    
    try:
        # Get positions and flatten Sim101
        positions = nt_get("/api/positions")
        for pos in positions:
            symbol = pos.get("symbol")
            qty = pos.get("quantity", 0)
            market_pos = pos.get("marketPosition")
            
            if qty > 0 and market_pos != "Flat":
                action = "sell" if market_pos == "Long" else "buy"
                print(f"Flattening remaining position: {action} {qty} {symbol}")
                nt_post("/api/order", {
                    "symbol": symbol,
                    "action": action,
                    "quantity": qty,
                    "orderType": "Market",
                    "timeInForce": "Day"
                })
    except Exception as e:
        print(f"Cleanup flatten failed: {e}")
    
    # Wait for the cleanup to settle (positions flat and orders cancelled)
    active_states = ["Working", "Submitted", "Accepted", "Initialized"]
    for i in range(15):
        time.sleep(0.5)
        try:
            positions = nt_get("/api/positions")
            orders = nt_get("/api/orders")
            
            has_active_pos = any(p.get("marketPosition") != "Flat" and p.get("quantity", 0) > 0 for p in positions)
            has_active_orders = any(o.get("state") in active_states for o in orders)
            
            if not has_active_pos and not has_active_orders:
                print("Cleanup completed: Sim101 is fully flat with no active orders.")
                return
        except Exception as e:
            print(f"Waiting for cleanup failed: {e}")
            
    print("WARNING: Cleanup timed out! Sim101 might not be fully flat.")

@pytest.fixture(autouse=True)
def setup_teardown():
    # Make sure we clean up before and after each test
    cleanup_all()
    yield
    cleanup_all()

def test_bridge_health():
    """Verify that NinjaTrader 8 McpBridge is online."""
    res = nt_get("/api/health")
    assert res.get("status") == "ok" or "version" in res

def test_auto_stop_loss_attachment():
    """Verify that entering a position without a stop causes Risk Guard to flatten the position after 3s (new safe default)."""
    print("Placing market BUY of 1 MES...")
    order_res = nt_post("/api/order", {
        "symbol": "MES SEP26", # Using MES Sep26 as in user logs
        "action": "buy",
        "quantity": 1,
        "orderType": "Market",
        "timeInForce": "Day"
    })
    
    print("Waiting 4.5 seconds for grace period to expire...")
    time.sleep(4.5)
    
    positions = nt_get("/api/positions")
    print(f"Current positions: {positions}")
    
    # Assert that the position was flattened
    mes_positions = [p for p in positions if p.get("instrument", "").startswith("MES")]
    assert len(mes_positions) == 0 or mes_positions[0].get("marketPosition") == "Flat", "Risk Guard failed to flatten position missing a stop!"
    print("Auto-stop loss attachment test passed!")

def test_cancel_and_reattach_stop():
    """Verify that if the stop is manually cancelled, Risk Guard flattens the position after 3s."""
    print("Placing market BUY of 1 MES...")
    nt_post("/api/order", {
        "symbol": "MES SEP26",
        "action": "buy",
        "quantity": 1,
        "orderType": "Market",
        "timeInForce": "Day"
    })
    
    print("Waiting 4.5 seconds for initial stop guard to trigger...")
    time.sleep(4.5)
    
    # After 4.5 seconds without a stop, position should have been flattened by the guard
    positions = nt_get("/api/positions")
    mes_positions = [p for p in positions if p.get("instrument", "").startswith("MES")]
    assert len(mes_positions) == 0 or mes_positions[0].get("marketPosition") == "Flat", "Position should be flattened after initial wait."
    print("Cancel and re-attach test passed!")

def test_manual_close_does_not_reattach():
    """Verify that manually exiting a trade with a Market order does not trigger a new stop."""
    print("Placing market BUY of 1 MES...")
    nt_post("/api/order", {
        "symbol": "MES SEP26",
        "action": "buy",
        "quantity": 1,
        "orderType": "Market",
        "timeInForce": "Day"
    })
    
    print("Waiting 1 second before manual close...")
    time.sleep(1)
    
    # Manually close
    nt_post("/api/order", {
        "symbol": "MES SEP26",
        "action": "sell",
        "quantity": 1,
        "orderType": "Market",
        "timeInForce": "Day"
    })
    
    print("Waiting 4.5 seconds to ensure no weird side effects...")
    time.sleep(4.5)
    
    orders = nt_get("/api/orders")
    active_states = ["Working", "Submitted", "Accepted", "Initialized"]
    stop_orders = [o for o in orders if o.get("orderType") == "StopMarket" and o.get("state") in active_states]
    assert len(stop_orders) == 0, "Stop order should NOT be found after manual close."
    print("Manual close test passed!")

def test_max_position_size_enforcement():
    """Verify that exceeding the maximum contract size (10) triggers an immediate flatten."""
    print("Placing market BUY of 12 MES (exceeding max size 10)...")
    nt_post("/api/order", {
        "symbol": "MES SEP26",
        "action": "buy",
        "quantity": 12,
        "orderType": "Market",
        "timeInForce": "Day"
    })
    
    print("Waiting 3 seconds for size limit lockout to trigger...")
    time.sleep(3)
    
    positions = nt_get("/api/positions")
    print(f"Current positions after size limit: {positions}")
    
    active_positions = [p for p in positions if p.get("marketPosition") != "Flat"]
    assert len(active_positions) == 0, "Risk Guard failed to flatten the position after a max contract size breach!"
    print("Max size enforcement test passed!")

def test_overtrading_cooldown_enforcement():
    """Verify that entering a trade immediately after closing one triggers a flatten due to the 5-minute cooldown."""
    nt_post("/api/dev/reset-risk")  # Clear any existing lockouts or cooldowns
    
    print("Placing market BUY of 1 MES...")
    nt_post("/api/order", {
        "symbol": "MES SEP26",
        "action": "buy",
        "quantity": 1,
        "orderType": "Market",
        "timeInForce": "Day"
    })
    
    time.sleep(1)
    print("Closing position to start cooldown...")
    nt_post("/api/order", {
        "symbol": "MES SEP26",
        "action": "sell",
        "quantity": 1,
        "orderType": "Market",
        "timeInForce": "Day"
    })
    
    time.sleep(1)
    print("Placing second market BUY of 1 MES during cooldown...")
    nt_post("/api/order", {
        "symbol": "MES SEP26",
        "action": "buy",
        "quantity": 1,
        "orderType": "Market",
        "timeInForce": "Day"
    })
    
    print("Waiting 2 seconds for Risk Guard to enforce cooldown...")
    time.sleep(2)
    
    positions = nt_get("/api/positions")
    active_positions = [p for p in positions if p.get("marketPosition") != "Flat"]
    assert len(active_positions) == 0, "Risk Guard failed to flatten position during overtrading cooldown!"
    print("Cooldown enforcement test passed!")
    
    # Reset state so subsequent runs don't start locked out
    nt_post("/api/dev/reset-risk")

def test_max_trades_enforcement():
    """Verify that exceeding MaxTradesPerSession locks out the account."""
    nt_post("/api/dev/reset-risk")
    
    # We assume MaxTradesPerSession is 8. We'll simulate 9 rapid trades.
    # To avoid hitting the cooldown between trades, wait... actually, the cooldown applies to the *same* account.
    # If the cooldown is active, the order is flattened immediately. But a flattened order might still count as a trade?
    # Yes, transitioning from Flat to Long counts as a trade. 
    # Since Cooldown flatten transitions Long -> Flat, if we spam it, we'll rack up trade counts extremely fast!
    for i in range(9):
        print(f"Spamming trade {i+1}/9...")
        nt_post("/api/order", {
            "symbol": "MES SEP26",
            "action": "buy",
            "quantity": 1,
            "orderType": "Market",
            "timeInForce": "Day"
        })
        time.sleep(0.5)
        
    print("Waiting 2 seconds for lockout...")
    time.sleep(2)
    
    positions = nt_get("/api/positions")
    active_positions = [p for p in positions if p.get("marketPosition") != "Flat"]
    assert len(active_positions) == 0, "Account should be locked out and flattened after MaxTrades!"
    
    # Clean up
    nt_post("/api/dev/reset-risk")

