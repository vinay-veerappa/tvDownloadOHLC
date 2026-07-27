"""
run_ui_critical_audit.py
========================
Queries gemma4:31b-cloud and kimi-k2.7-code:cloud to perform a critical UI audit of both
RiskGuard and TradeCopier WPF controls in NinjaTrader 8.
"""
import sys
from scripts.utils.ollama_bridge import query_ollama

sys.stdout.reconfigure(encoding='utf-8')

prompt_gemma = """
You are a lead UI/UX engineer and prop firm trader auditing the NinjaTrader 8 WPF user interfaces for:
1. RiskGuard Manager (Daily loss limit, trailing drawdown, lockout timer, instrument limits, red-folder news shield).
2. Trade Copier Manager (Leader-follower relationships, group copier, symbol translations, ratio overrides, account quarantine, audit streams).

Be VERY CRITICAL. Identify:
- Missing UI configurations (e.g. inability to edit quarantine status from UI, lack of visual latency indicators, missing dark/light theme toggles, missing real-time account PnL badges).
- Missing safety controls (e.g. no confirmation dialog on Panic/Flatten All button, lack of explicit 'Armed for Live' visual badges).
- Missing execution metrics (e.g. no in-memory execution fill counter or average slippage display per follower).
- UX bottlenecks (e.g. manual refresh vs real-time WPF binding, hardcoded ratio text fields).

List 5-6 critical UI/UX improvements and new controls needed.
"""

print("=== STEP 1: Querying gemma4:31b-cloud for Critical UI/UX Audit ===")
gemma_res = query_ollama(prompt_gemma, model="gemma4:31b-cloud")
print(gemma_res)

prompt_kimi = f"""
You are a senior NinjaTrader 8 WPF C# developer. Perform a technical WPF audit of Gemma's proposed UI/UX enhancements for RiskGuard and TradeCopier:

--- GEMMA UI AUDIT ---
{gemma_res}

Critique WPF technical feasibility:
1. Dispatcher thread safety when binding real-time PnL/fills to WPF controls.
2. Confirm how to add confirmation modal dialogs (`MessageBox.Show` vs custom WPF overlay) for Panic/Flatten All.
3. Recommend exact C# WPF code extensions to add to TradeCopierWindow.cs / RiskGuard UI controls.
"""

print("\n=== STEP 2: Querying kimi-k2.7-code:cloud for WPF Technical Review ===")
kimi_res = query_ollama(prompt_kimi, model="kimi-k2.7-code:cloud")
print(kimi_res)
