"""
agentic_validator.py
====================
Programmatic Implementation of Maker-Checker & LLM-as-a-Judge Pipeline.

Workflow:
1. Maker (Fast/Cheap Model: qwen2.5-coder:3b / flash_lite) generates initial code draft.
2. Checker (Evaluator Model: deepseek-v4-pro:cloud / pro) critiques code for bugs, edge cases, and compliance.
3. If Maker draft fails verification, Self-Correction Refinement loop auto-fixes the code.
"""
import os
import sys
import json
import argparse
from typing import Dict, Any, Optional, Tuple

from scripts.utils.ollama_bridge import query_ollama


def maker_generate(prompt: str, maker_model: str = "qwen2.5-coder:3b") -> Optional[str]:
    """Maker Phase: Rapidly drafts code using fast/cheap model."""
    system_prompt = "You are an expert Python software engineer. Generate clean, minimal, production-ready code for the requested task. Output ONLY code without conversational fluff."
    print(f"[Maker] Drafting initial solution using '{maker_model}'...")
    return query_ollama(prompt, model=maker_model, system_prompt=system_prompt)


def checker_evaluate(code: str, requirements: str, checker_model: str = "deepseek-v4-pro:cloud") -> Tuple[bool, str, Optional[str]]:
    """
    Checker / LLM-as-a-Judge Phase: Evaluates Maker draft for bugs, edge cases, and quality.
    Returns (is_approved, critique_feedback, refined_code).
    """
    system_prompt = """You are a Senior Principal Software Architect acting as an LLM-as-a-Judge.
Evaluate the candidate Python code draft against the task requirements.

Check for:
1. Logic bugs or edge case crashes (nulls, empty dataframes, indexing errors).
2. Adherence to strict python standards & type safety.
3. Correctness against prompt requirements.

Output your evaluation in strict JSON format:
{
  "approved": true|false,
  "score": 1-10,
  "feedback": "Detailed explanation of findings or bugs",
  "refined_code": "Improved/corrected complete python code if revisions are required"
}
"""
    user_prompt = f"### TASK REQUIREMENTS:\n{requirements}\n\n### CODE DRAFT TO EVALUATE:\n```python\n{code}\n```"
    print(f"[Checker] LLM-as-a-Judge evaluating draft using '{checker_model}'...")
    raw_eval = query_ollama(user_prompt, model=checker_model, system_prompt=system_prompt, temperature=0.1)

    if not raw_eval:
        return False, "Checker query failed.", None

    try:
        # Extract JSON block
        start_idx = raw_eval.find("{")
        end_idx = raw_eval.rfind("}")
        if start_idx != -1 and end_idx != -1:
            eval_data = json.loads(raw_eval[start_idx:end_idx+1])
            approved = eval_data.get("approved", False)
            feedback = eval_data.get("feedback", "No feedback provided.")
            refined = eval_data.get("refined_code", None)
            return approved, feedback, refined
    except Exception as e:
        print(f"[Checker] Failed to parse evaluation JSON: {e}")

    return False, raw_eval, None


def run_maker_checker_pipeline(
    task_prompt: str,
    maker_model: str = "qwen2.5-coder:3b",
    checker_model: str = "deepseek-v4-pro:cloud",
    max_retries: int = 2
) -> Dict[str, Any]:
    """Executes full Maker-Checker + Self-Correction Loop."""
    print("=" * 60)
    print("STARTING MAKER-CHECKER AGENTIC PIPELINE")
    print("=" * 60)

    # Step 1: Maker Draft
    draft_code = maker_generate(task_prompt, maker_model=maker_model)
    if not draft_code:
        return {"success": False, "error": "Maker failed to generate code draft."}

    current_code = draft_code
    for attempt in range(1, max_retries + 2):
        print(f"\n--- EVALUATION CYCLE #{attempt} ---")
        approved, feedback, refined_code = checker_evaluate(current_code, task_prompt, checker_model=checker_model)

        if approved:
            print("✅ CHECKER APPROVED SOLUTION!")
            print(f"Feedback: {feedback}")
            return {
                "success": True,
                "approved": True,
                "final_code": current_code,
                "feedback": feedback,
                "attempts": attempt
            }
        else:
            print(f"❌ CHECKER REJECTED DRAFT (Attempt {attempt}/{max_retries + 1})")
            print(f"Feedback: {feedback}")

            if refined_code:
                print("[Self-Correction] Applying Checker's refined code version.")
                current_code = refined_code
            elif attempt <= max_retries:
                # Refinement loop prompt to Maker
                refine_prompt = f"Your previous code draft failed evaluation with feedback: {feedback}\n\nTask: {task_prompt}\nPrevious Code:\n{current_code}\n\nPlease generate a corrected version fixing all identified issues."
                current_code = maker_generate(refine_prompt, maker_model=maker_model) or current_code

    return {
        "success": False,
        "approved": False,
        "final_code": current_code,
        "feedback": feedback,
        "attempts": max_retries + 1
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Maker-Checker & LLM-as-a-Judge Verification Pipeline.")
    parser.add_argument("--prompt", type=str, required=True, help="Task prompt for code generation.")
    parser.add_argument("--maker", type=str, default="qwen2.5-coder:3b", help="Maker model name.")
    parser.add_argument("--checker", type=str, default="deepseek-v4-pro:cloud", help="Checker model name.")
    
    args = parser.parse_args()
    res = run_maker_checker_pipeline(args.prompt, maker_model=args.maker, checker_model=args.checker)
    
    print("\n" + "=" * 60)
    print("FINAL PIPELINE RESULT:")
    print("=" * 60)
    print(f"Success: {res.get('success')}")
    print(f"Approved: {res.get('approved')}")
    print(f"Feedback: {res.get('feedback')}")
    print("\nFINAL CODE:")
    print(res.get("final_code"))
