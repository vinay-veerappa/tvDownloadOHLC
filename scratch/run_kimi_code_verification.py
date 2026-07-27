"""
run_kimi_code_verification.py
==============================
Asks kimi-k2.7-code:cloud to verify the roadmap and architectural proposals directly
against the existing C# files (McpBridgeAddOn.cs, RiskGuardAddOn.cs, TradeCopierEngine.cs, DynamicAtmManager.cs).
"""
import sys
from scripts.utils.ollama_bridge import query_ollama

sys.stdout.reconfigure(encoding='utf-8')

verification_prompt = """
You are a senior C# & NinjaTrader 8 codebase auditor.
Verify the proposed architectural fixes and documentation additions against the actual NinjaTrader C# files in the codebase (McpBridgeAddOn.cs, RiskGuardAddOn.cs, TradeCopierEngine.cs, DynamicAtmManager.cs).

Check the following:
1. Emergency Flatten Sequence: Confirm whether disabling managing strategies before calling Account.CancelAllOrders and Position.Close correctly prevents race conditions in NinjaTrader 8.
2. RiskGuard Persistence: Verify how state is currently recorded in RiskGuardAddOn.cs vs the proposed JSON recovery model.
3. Trade Copier Scaling & Main Thread Dispatching: Confirm that TradeCopierEngine.cs correctly marshals calls to Core.Globals.Dispatcher and uses AwayFromZero rounding.

Provide your final code verification comments and confirm if VERSION.md can be updated.
"""

print("Querying kimi-k2.7-code:cloud for codebase verification...")
ans = query_ollama(verification_prompt, model="kimi-k2.7-code:cloud")
print("\n--- KIMI CODEBASE VERIFICATION RESPONSE ---")
print(ans)
