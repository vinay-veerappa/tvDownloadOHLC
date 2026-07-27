"""
run_order_verification_audit.py
================================
Queries kimi-k2.7-code:cloud to audit whether order placement, modification, and cancellation verification
is sufficiently handled across follower copy trades and flatten executions in NinjaTrader 8.
"""
import sys
from scripts.utils.ollama_bridge import query_ollama

sys.stdout.reconfigure(encoding='utf-8')

prompt = """
You are a senior NinjaTrader 8 C# execution auditor.
Audit our order verification logic for:
1. Trade Copier follower orders (verifying that follower orders actually transition to Filled / Working after submission).
2. Emergency Flatten orders (verifying that positions actually reach 0 and working orders reach 0 after calling acc.Flatten / acc.Cancel).

Analyze what is typically missing in NinjaTrader AddOn integrations when submitting orders, and recommend concrete hardening patterns (e.g. ExecutionUpdate watchdog timers, state reconciliation loops, fill verification callbacks, retry/escalation policies).
"""

print("Querying kimi-k2.7-code:cloud for Order Verification Audit...")
ans = query_ollama(prompt, model="kimi-k2.7-code:cloud")
print("\n--- KIMI ORDER VERIFICATION AUDIT RESPONSE ---")
print(ans)
