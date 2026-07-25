import json
import time
import urllib.request

BASE_URL = "http://localhost:7890"

def post(endpoint, data):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return {"error": str(e)}

def get(endpoint):
    url = f"{BASE_URL}{endpoint}"
    try:
        with urllib.request.urlopen(url) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return {"error": str(e)}

def get_qty(positions, account):
    if not isinstance(positions, list): return 0
    for p in positions:
        if p.get("account", "").lower() == account.lower():
            return p.get("quantity", 0)
    return 0

print("=== STARTING COMPREHENSIVE EDGE CASE & STRESS TEST SUITE ===")

# Helper: Unlock & Flatten open positions accurately by opposite market order
def flatten_all():
    post("/api/lockout", {"action": "unlock", "account": "Sim101"})
    post("/api/lockout", {"action": "unlock", "account": "Sim-ORB"})
    time.sleep(0.5)

    positions = get("/api/positions")
    if isinstance(positions, list):
        for p in positions:
            acct = p.get("account")
            raw_symbol = p.get("symbol", "")
            qty = p.get("quantity", 0)
            market_pos = p.get("marketPosition")
            if qty > 0 and raw_symbol and acct:
                opposite_action = "Sell" if market_pos == "Long" else "Buy"
                symbol = "MNQ 09-26" if "MNQ" in raw_symbol else ("NQ 09-26" if "NQ" in raw_symbol else raw_symbol)
                post("/api/order", {"account": acct, "action": opposite_action, "order_type": "Market", "quantity": qty, "symbol": symbol})
    time.sleep(1.5)

flatten_all()

# --- EDGE CASE 1: Arming Gate Disarmed Safeguard ---
print("\n--- [EDGE CASE 1] Arming Gate Disarmed Safeguard ---")
post("/api/copier/config", {"action": "clear", "leaderAccount": "Sim101"})
resp1 = post("/api/copier/config", {
    "action": "set",
    "leaderAccount": "Sim101",
    "followerAccount": "RealAccountTest",
    "armedForLive": True,
    "confirmLive": False # Disarmed because confirmLive is False
})
print("Config Response (confirmLive=false):", json.dumps(resp1, indent=2))
assert resp1.get("enforcing") == False, "FAIL: Enforcing should be False when confirmLive=false"
assert resp1.get("config", {}).get("ArmedForLive") == False, "FAIL: ArmedForLive should be False"
print("[PASS] Arming gate correctly disarms ArmedForLive when confirmLive=false")

# --- EDGE CASE 2: Position-Level MaxPositionSize Clamping ---
print("\n--- [EDGE CASE 2] Position-Level MaxPositionSize Clamping ---")
post("/api/copier/config", {"action": "clear", "leaderAccount": "Sim101"})
flatten_all()
time.sleep(1.0)

# Configure Sim101 -> Sim-ORB with MaxPositionSize = 15
resp2 = post("/api/copier/config", {
    "action": "set",
    "leaderAccount": "Sim101",
    "followerAccount": "Sim-ORB",
    "armedForLive": True,
    "confirmLive": True,
    "autoSymbolConversion": False,
    "maxPositionSize": 15
})
print("Config Response (MaxPositionSize=15):", json.dumps(resp2, indent=2))

# Order 1: 1 MNQ (Follower Position = 1 MNQ)
order1 = post("/api/order", {"account": "Sim101", "action": "Buy", "order_type": "Market", "quantity": 1, "symbol": "MNQ 09-26"})
time.sleep(1.0)
pos1 = get("/api/positions")
print("Sim-ORB Position after Order 1 (1 MNQ):", get_qty(pos1, "Sim-ORB"))

# Order 2: 10 MNQ (Follower Position = 11 MNQ)
order2 = post("/api/order", {"account": "Sim101", "action": "Buy", "order_type": "Market", "quantity": 10, "symbol": "MNQ 09-26"})
time.sleep(1.0)
pos2 = get("/api/positions")
print("Sim-ORB Position after Order 2 (11 MNQ):", get_qty(pos2, "Sim-ORB"))

# Order 3: 10 MNQ -> capacity is 15 - 11 = 4 MNQ (Follower Position clamped to 15 MNQ)
order3 = post("/api/order", {"account": "Sim101", "action": "Buy", "order_type": "Market", "quantity": 10, "symbol": "MNQ 09-26"})
time.sleep(1.0)
pos3 = get("/api/positions")
follower_qty = get_qty(pos3, "Sim-ORB")
leader_qty = get_qty(pos3, "Sim101")
print(f"Leader Net Position: {leader_qty} MNQ")
print(f"Follower Net Position: {follower_qty} MNQ (Expected Max: 15)")
assert follower_qty == 15, f"FAIL: Expected follower net position 15, got {follower_qty}"
print("[PASS] Position-level clamping capped follower net position at exactly MaxPositionSize 15")

flatten_all()

# --- EDGE CASE 3: Recursion Loop Guard (Follower Set Exclusion) ---
print("\n--- [EDGE CASE 3] Recursion Loop Guard (Follower Set Exclusion) ---")
post("/api/copier/config", {"action": "clear", "leaderAccount": "Sim-ORB"})

# Try to configure Sim-ORB as a leader to copy back to Sim101
resp3 = post("/api/copier/config", {
    "action": "set",
    "leaderAccount": "Sim-ORB",
    "followerAccount": "Sim101",
    "armedForLive": True,
    "confirmLive": True
})
order_rec = post("/api/order", {"account": "Sim-ORB", "action": "Buy", "order_type": "Market", "quantity": 1, "symbol": "MNQ 09-26"})
time.sleep(1.0)
pos_rec = get("/api/positions")
sim101_qty = get_qty(pos_rec, "Sim101")
print("Sim101 position after order on Sim-ORB (Recursion Guard):", sim101_qty)
assert sim101_qty == 0, f"FAIL: Follower account Sim-ORB should not copy back to Sim101, got {sim101_qty}"
print("[PASS] Recursion guard 1 blocked follower account from acting as a leader")

flatten_all()

# --- STRESS CASE 4: Rapid High-Frequency Order Burst ---
print("\n--- [STRESS CASE 4] Rapid High-Frequency Order Burst ---")
post("/api/copier/config", {"action": "clear", "leaderAccount": "Sim101"})

# Reset config with MaxPositionSize = 100
post("/api/copier/config", {
    "action": "set",
    "leaderAccount": "Sim101",
    "followerAccount": "Sim-ORB",
    "armedForLive": True,
    "confirmLive": True,
    "maxPositionSize": 100
})

burst_count = 5
print(f"Firing {burst_count} rapid market buy orders in 100ms intervals...")
for i in range(burst_count):
    post("/api/order", {"account": "Sim101", "action": "Buy", "order_type": "Market", "quantity": 1, "symbol": "MNQ 09-26"})
    time.sleep(0.1)

time.sleep(2.5) # Allow execution processing
all_positions = get("/api/positions")
l_qty = get_qty(all_positions, "Sim101")
f_qty = get_qty(all_positions, "Sim-ORB")

print(f"Leader Position after burst: {l_qty} MNQ")
print(f"Follower Position after burst: {f_qty} MNQ")

assert l_qty == burst_count, f"Expected leader qty {burst_count}, got {l_qty}"
assert f_qty == burst_count, f"Expected follower qty {burst_count}, got {f_qty}"
print(f"[PASS] All {burst_count} high-frequency orders copied 1-for-1 without drops or duplicates!")

flatten_all()

print("\n====================================================")
print("ALL EDGE CASE AND STRESS TEST SCENARIOS PASSED LIVE!")
print("====================================================")
