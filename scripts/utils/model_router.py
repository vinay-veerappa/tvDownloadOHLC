"""
model_router.py
===============
Intelligent Multi-Model Task Delegation Router.
Routes tasks automatically to the optimal model based on workload tier:

Tier 1: LOCAL_ZERO_COST (Ollama local: qwen2.5-coder:3b / gemma4:latest)
        Use: Syntax checks, code formatting, JSON/YAML parsing, simple unit test generation.
Tier 2: CHEAP_FAST (Subagent flash_lite / flash or Ollama deepseek-v4-flash:cloud)
        Use: Log file analysis, file search, routine feature additions, candidate screening.
Tier 3: DEEP_THINKING (Subagent pro or Ollama deepseek-v4-pro:cloud / qwen3.5:397b-cloud)
        Use: Complex trade logic audit, multi-file architectural refactoring, deep bug diagnosis.
"""
import os
import sys
import argparse
from typing import Dict, Any, Optional

from scripts.utils.ollama_bridge import query_ollama, list_ollama_models

TASK_ROUTING_TIERS = {
    "syntax_check": {"tier": "LOCAL_ZERO_COST", "ollama_model": "qwen2.5-coder:3b", "subagent_model": "flash_lite"},
    "code_formatting": {"tier": "LOCAL_ZERO_COST", "ollama_model": "codegemma:7b-instruct", "subagent_model": "flash_lite"},
    "log_analysis": {"tier": "CHEAP_FAST", "ollama_model": "deepseek-v4-flash:cloud", "subagent_model": "flash_lite"},
    "file_audit": {"tier": "CHEAP_FAST", "ollama_model": "gemma4:latest", "subagent_model": "flash"},
    "feature_coding": {"tier": "CHEAP_FAST", "ollama_model": "qwen3.6:latest", "subagent_model": "flash"},
    "deep_reasoning": {"tier": "DEEP_THINKING", "ollama_model": "deepseek-v4-pro:cloud", "subagent_model": "pro"},
    "architecture_plan": {"tier": "DEEP_THINKING", "ollama_model": "qwen3.5:397b-cloud", "subagent_model": "pro"},
}


def route_task(
    prompt: str,
    task_type: str = "feature_coding",
    use_ollama: bool = True,
    system_prompt: Optional[str] = None
) -> Dict[str, Any]:
    """
    Routes a task to the optimal model tier.
    If use_ollama=True, queries local/cloud Ollama model.
    Otherwise returns subagent invocation recommendations.
    """
    config = TASK_ROUTING_TIERS.get(task_type, TASK_ROUTING_TIERS["feature_coding"])
    tier = config["tier"]
    target_ollama = config["ollama_model"]
    target_subagent = config["subagent_model"]

    print(f"[model_router] Task: '{task_type}' | Tier: '{tier}' | Target Ollama: '{target_ollama}' | Target Subagent: '{target_subagent}'")

    if use_ollama:
        response = query_ollama(prompt, model=target_ollama, system_prompt=system_prompt)
        return {
            "success": response is not None,
            "response": response,
            "provider": "ollama",
            "model_used": target_ollama,
            "tier": tier
        }
    else:
        return {
            "success": True,
            "recommendation": {
                "subagent_model": target_subagent,
                "tier": tier
            }
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Model Task Delegation Router.")
    parser.add_argument("--prompt", type=str, required=True, help="Task prompt.")
    parser.add_argument("--type", type=str, default="feature_coding", choices=list(TASK_ROUTING_TIERS.keys()), help="Task workload type.")
    parser.add_argument("--recommend-only", action="store_true", help="Output subagent model recommendation without querying Ollama.")
    
    args = parser.parse_args()
    res = route_task(args.prompt, task_type=args.type, use_ollama=not args.recommend-only)
    
    if res.get("response"):
        print("\n--- MODEL RESPONSE ---")
        print(res["response"])
    else:
        print("\n--- DELEGATION RECOMMENDATION ---")
        print(json.dumps(res, indent=2))
