"""
run_doc_review_dialogue.py
==========================
Multi-agent dialogue script between gemma4:31b-cloud (Maker) and kimi-k2.7-code:cloud (Checker)
to review NinjaTrader MCP documentation, suggest improvements, new features, and architectural fixes.
"""
import sys
from scripts.utils.ollama_bridge import query_ollama

sys.stdout.reconfigure(encoding='utf-8')

doc_context = """
# NinjaTrader MCP Architecture & Feature Overview
- 51 Tool MCP Schemas (nt_health, nt_orders, nt_place_order, nt_place_atm_order, nt_positions, nt_riskguard_state, nt_emergency_flatten, nt_copier_config, nt_deploy_strategy, nt_backtest, etc.)
- Components: McpBridgeAddOn.cs, RiskGuardAddOn.cs, TradeCopierEngine.cs, DynamicAtmManager.cs, PropFirmProtectionSuite.cs
- Version: v1.5.0
- Key Features: Multi-Account Trade Copier, Prop Firm Red-Folder News Shield, Intraday Peak Equity Lock (30% giveback cap), Reflection Strategy Discovery, WPF Base64 Chart Snapshot.
"""

# Step 1: Query Gemma for documentation improvements and new feature suggestions
prompt_gemma = f"""You are an expert algorithmic trading architect reviewing the NinjaTrader MCP documentation:
{doc_context}

Based on day trading best practices, prop firm requirements (Apex, Topstep, MyFundedFutures), and execution performance:
1. Review the current documentation and architectural capabilities.
2. Suggest 4-5 critical improvements to existing tools.
3. Propose 3 high-impact NEW features to add to the MCP tool suite.
4. Highlight subtle issues or vulnerabilities that need addressing.
"""

print("=== STEP 1: Querying gemma4:31b-cloud for MCP Improvements & New Features ===")
gemma_output = query_ollama(prompt_gemma, model="gemma4:31b-cloud")
print(gemma_output)

# Step 2: Pass Gemma's suggestions to Kimi for critical review and verification
prompt_kimi = f"""You are a senior NinjaTrader 8 & C# systems auditor. Review the following proposed MCP enhancements and feature proposals from Gemma:

--- GEMMA PROPOSALS ---
{gemma_output}

Perform a critical technical review:
1. Evaluate feasibility in NinjaTrader 8 API & WPF environment.
2. Identify any latency, thread safety, or API limitation flaws in the proposals.
3. Provide final refined recommendations ready for documentation and implementation.
"""

print("\n=== STEP 2: Passing Gemma's Proposals to kimi-k2.7-code:cloud for Verification ===")
kimi_output = query_ollama(prompt_kimi, model="kimi-k2.7-code:cloud")
print(kimi_output)
