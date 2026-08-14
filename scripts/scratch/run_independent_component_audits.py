"""Run Independent Multi-LLM Audits for Each Component

Generates independent review prompts and calls Ollama bridge for:
1. Candle Science
2. HTF EMA Analysis
3. Line vs Apex 3-Hour Block Sequencing
4. P12 Directional & Handshake Vector
5. Multi-Ticker Position Sizer
"""
from pathlib import Path
import os
import sys

REPO = Path(__file__).parent.parent
SCRATCH = REPO / "scratch"
SCRATCH.mkdir(exist_ok=True)

components = {
    "candle_science": {
        "title": "Candle Science Engine & Blueprint",
        "files": [
            REPO / "docs" / "features" / "CandleScience" / "BLUEPRINT.md",
            REPO / "scripts" / "trader" / "signals" / "candle_science.py",
            REPO / "scripts" / "validation" / "v_02_candle_science_pa.py",
        ]
    },
    "htf_ema": {
        "title": "HTF Weekly EMA(5) Excursion Analysis",
        "files": [
            REPO / "docs" / "features" / "htf_ema_analysis" / "BLUEPRINT.md",
            REPO / "scripts" / "wargaming" / "htf_ema_analysis.py",
            REPO / "scripts" / "validation" / "v_03_htf_ema_pa.py",
        ]
    },
    "line_vs_apex": {
        "title": "3-Hour Line vs Apex & 0-5 Box Sequencing",
        "files": [
            REPO / "docs" / "profiler" / "line_vs_apex_blueprint.md",
            REPO / "scripts" / "validation" / "v_04_line_vs_apex_pa.py",
        ]
    },
    "p12_handshake": {
        "title": "P12 Directional Switch & NY Handshake Vector",
        "files": [
            REPO / "docs" / "profiler" / "p12_directional_blueprint.md",
            REPO / "scripts" / "validation" / "v_05_p12_pa.py",
        ]
    },
    "position_sizer": {
        "title": "Multi-Ticker Position Sizing Risk Engine",
        "files": [
            REPO / "scripts" / "config" / "ticker_registry.json",
            REPO / "scripts" / "risk" / "position_sizer.py",
        ]
    }
}

for key, item in components.items():
    prompt_file = SCRATCH / f"audit_prompt_{key}.txt"
    content_blocks = []
    for f in item["files"]:
        if f.exists():
            content_blocks.append(f"\n--- FILE: {f.name} ---\n" + f.read_text(encoding="utf-8"))
    
    full_code = "\n".join(content_blocks)
    prompt_text = f"""You are an expert quantitative trading auditor and senior python software engineer.

Conduct a strict, independent, unsparing review of the following component: **{item['title']}**.

Focus your audit on:
1. **Rule Fidelity & Domain Correctness**: Does the implementation accurately reflect Matt Mickey & Austin's master trading methodology?
2. **Edge Cases & Failure Modes**: What market conditions, data gaps, or holiday sessions could invalidate or break this component?
3. **Code Quality, Vectorization & Performance**: Are there non-vectorized pandas loops, memory leaks, or type errors?
4. **Concrete Actionable Enhancements**: What specific code or rule changes will improve accuracy and robustness?

--- COMPONENT SOURCE FILES ---
{full_code}
"""
    prompt_file.write_text(prompt_text, encoding="utf-8")
    print(f"Wrote audit prompt for [{key}] to {prompt_file}")

print("All 5 independent component audit prompts prepared.")
