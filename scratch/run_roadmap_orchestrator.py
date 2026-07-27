"""
run_roadmap_orchestrator.py
===========================
Orchestrates Kimi-k2.7-code (Manager/Architect) and Gemma-4:31b (Senior Developer)
to design, implement, and verify the v1.7.0 UI/UX Roadmap features:
1. HoldToConfirmButton (1.5s hold-to-confirm for emergency flatten)
2. Execution Latency & Average Slippage tracking in CopierRelationship
3. Red-Folder News Shield UI Banner & Break-Glass Overlay
"""
import sys
from scripts.utils.ollama_bridge import query_ollama

sys.stdout.reconfigure(encoding='utf-8')

prompt_kimi_arch = """
You are Kimi (Senior Technical Architect & Manager).
Review the v1.7.0 UI/UX Roadmap requirements:
1. HoldToConfirmButton in TradeCopierWindow.cs (replaces single-click panic button with 1.5s press-and-hold).
2. LatencyMs and AvgSlippageTicks properties in CopierRelationship + UI grid/card display.
3. Red-Folder News Shield UI status banner + Break-Glass override dialog control.

Specify the exact C# code architecture and class modifications required for Gemma (Senior Developer) to write into TradeCopierWindow.cs and TradeCopierEngine.cs.
Keep it clean, non-breaking, and fully compatible with .NET Framework 4.8 / NinjaTrader 8.
"""

print("=== STEP 1: Querying Kimi (Senior Architect) for Feature Specifications ===")
architect_spec = query_ollama(prompt_kimi_arch, model="kimi-k2.7-code:cloud")
print(architect_spec)

prompt_gemma_impl = f"""
You are Gemma (Senior Developer). Based on Architect Kimi's specification:
{architect_spec}

Generate the exact C# code snippets for:
1. `HoldToConfirmButton` WPF class definition.
2. `LatencyMs` and `AvgSlippageTicks` tracking in `CopierRelationship`.
3. `NewsShieldBanner` UI element.

Provide clear, compilable C# code snippets.
"""

print("\n=== STEP 2: Querying Gemma (Senior Developer) for C# Implementation ===")
dev_impl = query_ollama(prompt_gemma_impl, model="gemma4:31b-cloud")
print(dev_impl)
