"""
run_hedging_audit_dialogue.py
==============================
Asks gemma4:31b-cloud and kimi-k2.7-code:cloud to review the 3 trade safety requirements:
1. Prevent Hedging / Opposite-Side Market Order Skips.
2. Position Reconciler (verify follower direction matches leader).
3. Auto-close follower positions when leader reaches 0.
"""
import sys
from scripts.utils.ollama_bridge import query_ollama

sys.stdout.reconfigure(encoding='utf-8')

prompt_gemma = """
You are an expert algorithmic trading architect. Review these 3 specific Trade Copier execution rules for NinjaTrader 8:

1. Prevent Hedging: Skips opposite-side Market orders on flat followers and caps quantity at the follower's open position size — avoiding flipping into a reversed direction. Standalone Limit/Stop/Bracket entries remain unblocked.
2. Position Reconciler: After every follower fill event, verify that the follower position direction matches the leader's direction. If a mismatch is detected, automatically exit the follower position.
3. Auto-close Follower Positions: When the leader's net position reaches 0 (Flat), automatically flatten all follower positions and cancel open follower working orders for that instrument.

Design the C# logic and methods to implement these 3 rules in TradeCopierEngine.cs.
"""

print("=== STEP 1: Querying gemma4:31b-cloud for Hedging & Reconciliation Logic ===")
gemma_res = query_ollama(prompt_gemma, model="gemma4:31b-cloud")
print(gemma_res)

prompt_kimi = f"""
You are a senior NinjaTrader 8 C# auditor. Review the proposed design from Gemma for implementing Hedging Prevention, Position Reconciliation, and Auto-Close on Leader Flat:

--- GEMMA PROPOSALS ---
{gemma_res}

Verify:
1. Thread safety & NinjaTrader 8 API semantics (MarketPosition, OrderAction, ExecutionUpdate).
2. Edge cases (e.g. partial fills, scale-out orders, reverse flips).
3. Provide the final, production-hardened C# code implementation ready for TradeCopierEngine.cs.
"""

print("\n=== STEP 2: Querying kimi-k2.7-code:cloud for Final Audit & Code Validation ===")
kimi_res = query_ollama(prompt_kimi, model="kimi-k2.7-code:cloud")
print(kimi_res)
