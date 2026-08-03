"""
agentic_panel.py
================
Agent-as-a-Judge pattern with a panel of independent LLM judges.

Architecture:
    Maker (cheap, high token usage)  ──draft──►  4 Judges (parallel, distinct rubrics)
                                                      │
                                                    Aggregator (weighted vote + critique merge)
                                                      │
                                        ┌─────────────┴─────────────┐
                                   approved                       rejected
                                        │                             │
                                   Final code            Refiner (cheap cloud model)
                                                              │
                                                         re-draft ──► back to judges

Design choices (per repo conventions):
- Reuses `ollama_bridge.query_ollama` — no new HTTP code.
- Maker & Refiner are the two cheapest models (gemma4:31b-cloud, deepseek-v4-flash:cloud)
  because those roles consume the most tokens (drafting + redrafting).
- Judges are the deeper/stronger models; they run in parallel via ThreadPoolExecutor.
- Trading-rules judge is grounded in CLAUDE.md / SecondBrain / ADRs via its system prompt.
- ADR-017 (zero-loop vectorization) and ADR-002 (statistical normalization) are
  explicitly named in the rubrics so the judges enforce repo guardrails.

Usage:
    python -m scripts.utils.agentic_panel --prompt "Build a vectorized function that ..."
    python -m scripts.utils.agentic_panel --prompt "..." --max-retries 3 --threshold 7.5
    python -m scripts.utils.agentic_panel --prompt "Build a NinjaScript indicator..." --language csharp
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Ensure UTF-8 stdout on Windows (cp1252 chokes on box-drawing chars in LLM output)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from scripts.utils.ollama_bridge import query_ollama


# ---------------------------------------------------------------------------
# Model assignment — cheap models do the high-token work, judges do the thinking
# ---------------------------------------------------------------------------
MAKER_MODEL = "gemma4:31b-cloud"        # cheap cloud — drafts (local gemma4 is too slow)
REFINER_MODEL = "deepseek-v4-flash:cloud"  # cheap cloud — redrafts from feedback

JUDGE_MODELS = {
    "correctness":   "glm-5.2:cloud",
    "trading_rules":  "minimax-m3:cloud",
    "adversarial":    "kimi-k2.7-code:cloud",
    "style":          "qwen3.5:397b-cloud",
}

# Weighted vote — must sum to 1.0
JUDGE_WEIGHTS = {
    "correctness":   0.35,
    "trading_rules":  0.30,
    "adversarial":    0.25,
    "style":          0.10,
}

# A judge scoring below this is a hard veto even if weighted average passes.
HARD_VETO_FLOOR = 4
DEFAULT_APPROVAL_THRESHOLD = 7.0


# ---------------------------------------------------------------------------
# Language presets — python (default) and csharp (NinjaScript)
# Each preset provides: maker_system, refiner_system, code_fence_lang, rubrics
# ---------------------------------------------------------------------------
LANGUAGE_PRESETS: Dict[str, Dict[str, Any]] = {
    "python": {
        "code_fence_lang": "python",
        "maker_system": (
            "You are an expert Python engineer drafting code in the tvDownloadOHLC repo. "
            "Generate clean, minimal, production-ready code. Follow ADR-017 (vectorized NumPy/Pandas, "
            "no for-loops in calculation paths) and ADR-002 (stats as price-percentage). "
            "Output ONLY code in a single ```python block, no conversational text."
        ),
        "refiner_system": (
            "You are an expert Python refiner. You receive a draft plus merged judge feedback. "
            "Produce a single corrected ```python block that fixes every issue the judges raised. "
            "Do not re-introduce previously-fixed issues. Output ONLY the code block."
        ),
        "rubrics": {
            "correctness": """You are Judge A — CORRECTNESS evaluator on a 3-LLM agent-as-a-judge panel.
Evaluate the candidate Python code STRICTLY for:
1. Logic bugs, off-by-one errors, indexing mistakes, null/NaN/empty-DataFrame crashes.
2. Vectorization compliance (ADR-017): no Python for-loops in calculation paths over data arrays; use NumPy/Pandas vectorized ops or Numba @njit.
3. Type safety and correct exception handling.
4. Correctness against the task requirements.

Output STRICT JSON only:
{
  "score": <1-10 integer>,
  "approved": <bool, true iff score >= 7 and no blocking bugs>,
  "feedback": "<concise list of issues found, or 'No blocking issues.'>",
  "refined_code": "<full corrected code, or null if no changes needed>"
}
""",
            "trading_rules": """You are Judge B — TRADING-RULES COMPLIANCE evaluator.
The code must obey these repo guardrails (cite violations explicitly):
- ADR-001 Timezone: charts take UTC naive inputs; calculations use ET (New York) session windows; storage uses UTC Unix Epoch.
- ADR-002 Statistical Normalization: performance/stat metrics reported as price percentage gains/excursions, not absolute points.
- ADR-017 Zero-Loop: fully vectorized NumPy/Pandas models, no for-loops in calculation paths.
- ADR-020 Prop Firm RTH Liquidation: intraday positions exit by 16:00 ET (close of 15:59 bar).
- ADR-021 Unified Prop Firm Sim: only scripts/trading_framework/ml/prop_firm_simulator.py (PropFirmSimulator) is used for prop firm viability.
- ADR-018 Visual Compliance: indicators bind to shared templates in VISUAL_SYSTEM.md.
- Data Architecture: live analysis uses data/live/live_storage_-{ticker}.parquet, not historical-only loaders.
- SecondBrain_Trading.md: ALN sessions, NQ hourly personalities, IB 96% rule must be respected where applicable.

If the task is NOT trading-domain code, score 10 and approve (this judge only fires on trading logic).

Output STRICT JSON only:
{
  "score": <1-10>,
  "approved": <bool>,
  "feedback": "<list each ADR/SecondBrain violation with the ADR id, or 'No trading-rule violations.'>",
  "refined_code": <full corrected code if fixes are required, else null>
}
""",
            "adversarial": """You are Judge C — ADVERSARIAL / RED-TEAM evaluator.
Your job is to BREAK the candidate code. Assume it is broken; find the failure modes.
Probe specifically for:
- Empty DataFrame / single-row DataFrame edge cases.
- Gap days, missing trading days, timezone boundary errors (UTC↔ET).
- Index misalignment after merges (a known repo gotcha — index resets lose datetime).
- Extreme inputs: zero division, inf, NaN propagation, very large arrays.
- Race conditions or non-determinism in any file I/O.
- Any silent failure (returns wrong shape, writes nothing, logs to stderr but exits 0).

For each failure mode you find, give a concrete minimal reproducing scenario.

Output STRICT JSON only:
{
  "score": <1-10, harshly>,
  "approved": <bool, true only if no realistic break found>,
  "feedback": "<numbered list of break scenarios with reproduction steps>",
  "refined_code": <full corrected code fixing the breaks, or null>
}
""",
            "style": """You are Judge D — STYLE & READABILITY evaluator.
Enforce repo conventions:
- Idiomatic pandas/NumPy; no deprecated patterns.
- Functions have type hints and docstrings.
- No dead code, no commented-out blocks.
- Module/class docstrings follow the repo's triple-quoted header convention.
- Naming: snake_case functions, UPPER_CASE constants, PascalCase classes.
- Lines under ~110 chars where reasonable.

This judge is the lowest weight; do not block on minor cosmetic issues.

Output STRICT JSON only:
{
  "score": <1-10>,
  "approved": <bool>,
  "feedback": "<bulleted style notes, or 'Style acceptable.'>",
  "refined_code": <full restyled code if needed, or null>
}
""",
        },
    },

    "csharp": {
        "code_fence_lang": "csharp",
        "maker_system": (
            "You are an expert C# NinjaScript engineer drafting code for NinjaTrader 8 indicators "
            "in the tvDownloadOHLC repo. The code targets namespace NinjaTrader.NinjaScript.Indicators.Vinay. "
            "Follow NT8 framework conventions: OnStateChange lifecycle (SetDefaults/Configure/DataLoaded/Terminated), "
            "OnBarUpdate, OnRender with SharpDX, NinjaScript property attributes ([Display], [Range]). "
            "Pure data-model classes must be NT8-free (no NinjaTrader.* usings) for reuse across indicators. "
            "Follow ADR-001 (timezone: ET session windows, UTC storage) and ADR-018 (visual compliance). "
            "Output ONLY code in a single ```csharp block, no conversational text."
        ),
        "refiner_system": (
            "You are an expert C# NinjaScript refiner. You receive a draft plus merged judge feedback. "
            "Produce a single corrected ```csharp block that fixes every issue the judges raised. "
            "Do not re-introduce previously-fixed issues. Output ONLY the code block."
        ),
        "rubrics": {
            "correctness": """You are Judge A — CORRECTNESS evaluator for C# NinjaScript code.
Evaluate STRICTLY for:
1. Logic bugs, off-by-one errors, null reference exceptions, empty-list access, indexing mistakes.
2. NT8 framework compliance: correct lifecycle method signatures (protected override void OnBarUpdate, OnStateChange, OnRender), 
   correct use of BarsArray, CurrentBar, Time[], High[], Low[], Close[] series access.
3. Type safety: nullable types (bool?, double?), DateTime handling, dictionary key-existence checks before access.
4. SharpDX resource disposal: brushes, text formats, text layouts must be Dispose()'d after use in OnRender to avoid GDI leaks.
5. Correctness against the task requirements.

Output STRICT JSON only:
{
  "score": <1-10 integer>,
  "approved": <bool, true iff score >= 7 and no blocking bugs>,
  "feedback": "<concise list of issues found, or 'No blocking issues.'>",
  "refined_code": "<full corrected code, or null if no changes needed>"
}
""",
            "trading_rules": """You are Judge B — TRADING-RULES COMPLIANCE evaluator for C# NinjaScript code.
The code must obey these repo guardrails (cite violations explicitly):
- ADR-001 Timezone: charts take UTC naive inputs; calculations use ET (New York) session windows; storage uses UTC Unix Epoch.
  In NT8: use TimeZoneInfo.ConvertTimeFromUtc(utc, etZone) for UTC→ET conversion. ET = "Eastern Standard Time" zone (covers DST automatically).
- ADR-018 Visual Compliance: indicators bind to shared visual templates; SharpDX rendering must follow the repo's visual system conventions.
- Fence-post convention (per LIQUIDITY_LEVELS_INDICATOR_DESIGN.md §J.1): window start = barMins > startMin; window end (inclusive) = barMins <= endMin.
- ADR-020 Prop Firm RTH Liquidation: intraday positions exit by 16:00 ET (close of 15:59 bar) — applies to strategies, not indicators.
- Data Architecture: NT8 indicators recompute from loaded chart bars (no file persistence needed for deterministic stats).
- SecondBrain_Trading.md: ALN sessions, NQ personalities, session windows (Asia/London/NY) must be respected where applicable.
- Pure model/library classes must have NO NinjaTrader.* usings — they must be reusable across indicators.

If the task is NOT trading-domain code, score 10 and approve (this judge only fires on trading logic).

Output STRICT JSON only:
{
  "score": <1-10>,
  "approved": <bool>,
  "feedback": "<list each ADR/SecondBrain violation with the ADR id, or 'No trading-rule violations.'>",
  "refined_code": <full corrected code if fixes are required, else null>
}
""",
            "adversarial": """You are Judge C — ADVERSARIAL / RED-TEAM evaluator for C# NinjaScript code.
Your job is to BREAK the candidate code. Assume it is broken; find the failure modes.
Probe specifically for:
- Empty BarsArray / single-bar charts / Charts with insufficient history for lookback.
- Gap days, weekends, holidays, timezone boundary errors (UTC↔ET conversion).
- Dictionary key-not-found exceptions (KeyNotFoundException) — always use TryGetValue or ContainsKey.
- SharpDX resource leaks: undisposed brushes/layouts/text formats in OnRender cause GDI handle exhaustion.
- NaN/Infinity propagation in price calculations (e.g., division by zero, double.MaxValue defaults).
- Index out of bounds when accessing BarsArray[i] with i beyond Count.
- Race conditions or reentrancy in OnBarUpdate (e.g., modifying collections during enumeration).
- NullReferenceException: _priorDayOHLC or _currentDayOHL could be null if sub-indicator not yet loaded.
- Any silent failure (catch block swallows exception, returns wrong type, writes nothing).

For each failure mode you find, give a concrete minimal reproducing scenario.

Output STRICT JSON only:
{
  "score": <1-10, harshly>,
  "approved": <bool, true only if no realistic break found>,
  "feedback": "<numbered list of break scenarios with reproduction steps>",
  "refined_code": <full corrected code fixing the breaks, or null>
}
""",
            "style": """You are Judge D — STYLE & READABILITY evaluator for C# NinjaScript code.
Enforce repo conventions:
- C# naming: PascalCase for public properties/methods/classes, camelCase for private fields and locals.
- [Display] attribute properties with GroupName, Order, Name, Description for all user-configurable NinjaScript properties.
- Region blocks (#region / #endregion) for organizing large indicator classes.
- File header docstring comment (═══ boxed style matching existing indicators).
- No dead code, no commented-out blocks.
- Lines under ~120 chars where reasonable.
- XML doc comments (///) on public API methods.

This judge is the lowest weight; do not block on minor cosmetic issues.

Output STRICT JSON only:
{
  "score": <1-10>,
  "approved": <bool>,
  "feedback": "<bulleted style notes, or 'Style acceptable.'>",
  "refined_code": <full restyled code if needed, or null>
}
""",
        },
    },
}


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------
@dataclass
class JudgeVerdict:
    judge: str
    model: str
    score: int
    approved: bool
    feedback: str
    refined_code: Optional[str] = None
    raw: Optional[str] = None
    error: Optional[str] = None


@dataclass
class PanelReport:
    approved: bool
    weighted_score: float
    verdicts: List[JudgeVerdict] = field(default_factory=list)
    merged_feedback: str = ""
    final_code: str = ""
    attempts: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "weighted_score": self.weighted_score,
            "verdicts": [
                {"judge": v.judge, "model": v.model, "score": v.score,
                 "approved": v.approved, "feedback": v.feedback}
                for v in self.verdicts
            ],
            "merged_feedback": self.merged_feedback,
            "final_code": self.final_code,
            "attempts": self.attempts,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_language_preset(language: str = "python") -> Dict[str, Any]:
    """Return the language preset dict (maker_system, refiner_system, code_fence_lang, rubrics)."""
    preset = LANGUAGE_PRESETS.get(language)
    if not preset:
        raise ValueError(f"Unknown language '{language}'. Supported: {list(LANGUAGE_PRESETS.keys())}")
    return preset


def _strip_code_fence(raw: Optional[str], fence_lang: str = "python") -> Optional[str]:
    """Extract code from a ```lang ... ``` fence if present, else return as-is."""
    if raw is None:
        return None
    raw = raw.strip()
    if raw.startswith("```"):
        # remove first fence line (```lang or ```)
        first_newline = raw.find("\n")
        if first_newline != -1:
            raw = raw[first_newline + 1 :]
        if raw.rstrip().endswith("```"):
            raw = raw.rstrip()[:-3]
    return raw.strip()


def _pick_best_refined(verdicts: List[JudgeVerdict]) -> Optional[str]:
    """If any judge supplied refined_code, pick the one from the highest-scoring judge."""
    candidates = [v for v in verdicts if v.refined_code]
    if not candidates:
        return None
    candidates.sort(key=lambda v: v.score, reverse=True)
    return candidates[0].refined_code


# ---------------------------------------------------------------------------
# Maker / Refiner
# ---------------------------------------------------------------------------
def maker_generate(prompt: str, model: str = MAKER_MODEL, language: str = "python") -> Optional[str]:
    """Maker phase: cheap high-token role — drafts the initial solution."""
    preset = get_language_preset(language)
    fence_lang = preset["code_fence_lang"]
    print(f"[Maker] drafting with '{model}' (language={language})...")
    raw = query_ollama(prompt, model=model, system_prompt=preset["maker_system"], temperature=0.3, timeout=600)
    return _strip_code_fence(raw, fence_lang)


def refiner_redraft(prompt: str, draft: str, feedback: str, model: str = REFINER_MODEL,
                    language: str = "python") -> Optional[str]:
    """Refiner phase: cheap cloud model — redrafts from merged judge feedback."""
    preset = get_language_preset(language)
    fence_lang = preset["code_fence_lang"]
    user = (
        f"### ORIGINAL TASK\n{prompt}\n\n"
        f"### CURRENT DRAFT\n```{fence_lang}\n{draft}\n```\n\n"
        f"### MERGED JUDGE FEEDBACK (address every item)\n{feedback}\n\n"
        f"Produce the corrected full code."
    )
    print(f"[Refiner] redrafting with '{model}' (language={language})...")
    raw = query_ollama(user, model=model, system_prompt=preset["refiner_system"], temperature=0.2, timeout=600)
    return _strip_code_fence(raw, fence_lang)


# ---------------------------------------------------------------------------
# Judges — run in parallel
# ---------------------------------------------------------------------------
def _parse_verdict_json(raw: str) -> Dict[str, Any]:
    """Tolerant JSON extraction: find first { ... last } and parse."""
    if not raw:
        return {}
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return {}


def _judge_one(judge_name: str, model: str, system_prompt: str, task: str, code: str,
               fence_lang: str = "python") -> JudgeVerdict:
    """Single judge call. Returns a JudgeVerdict (with .error set on failure)."""
    user = f"### TASK REQUIREMENTS\n{task}\n\n### CODE DRAFT TO EVALUATE\n```{fence_lang}\n{code}\n```"
    raw = query_ollama(user, model=model, system_prompt=system_prompt, temperature=0.1, timeout=300)
    if raw is None:
        return JudgeVerdict(judge_name, model, score=0, approved=False,
                            feedback="Judge query failed.", error="query_failed")
    parsed = _parse_verdict_json(raw)
    if not parsed:
        # Judge didn't return parseable JSON — treat as soft fail, keep raw for debugging.
        return JudgeVerdict(judge_name, model, score=0, approved=False,
                            feedback=f"Judge returned non-JSON output:\n{raw[:500]}",
                            raw=raw, error="parse_failed")
    return JudgeVerdict(
        judge=judge_name,
        model=model,
        score=int(parsed.get("score", 0) or 0),
        approved=bool(parsed.get("approved", False)),
        feedback=str(parsed.get("feedback", "")),
        refined_code=parsed.get("refined_code"),
        raw=raw,
    )


def panel_evaluate(task: str, code: str, language: str = "python") -> List[JudgeVerdict]:
    """Run all 4 judges in parallel. Returns verdicts in fixed judge order."""
    preset = get_language_preset(language)
    rubrics = preset["rubrics"]
    fence_lang = preset["code_fence_lang"]
    verdicts: List[JudgeVerdict] = []
    with ThreadPoolExecutor(max_workers=len(rubrics)) as pool:
        futures = {
            pool.submit(_judge_one, name, JUDGE_MODELS[name], rubrics[name], task, code, fence_lang): name
            for name in rubrics
        }
        results: Dict[str, JudgeVerdict] = {}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                results[name] = fut.result()
            except Exception as exc:  # defensive: judge crash must not kill the panel
                results[name] = JudgeVerdict(name, JUDGE_MODELS[name], score=0,
                                             approved=False, feedback=f"Judge crashed: {exc}",
                                             error="crash")
        for name in rubrics:  # preserve canonical order
            if name in results:
                verdicts.append(results[name])
    return verdicts


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------
def aggregate_verdicts(
    verdicts: List[JudgeVerdict],
    threshold: float = DEFAULT_APPROVAL_THRESHOLD,
    hard_veto_floor: int = HARD_VETO_FLOOR,
) -> Tuple[bool, float, str]:
    """Weighted vote. Returns (approved, weighted_score, merged_feedback).
    Judges that errored (timeout/crash/parse-fail) are EXCLUDED — a timeout
    is a judge failure, not a code failure, and must not veto or drag the score."""
    weighted_sum = 0.0
    weight_total = 0.0
    vetoed_by: List[str] = []
    feedback_lines: List[str] = []
    errored: List[str] = []

    for v in verdicts:
        if v.error:  # timeout / crash / parse-fail → exclude, don't score 0
            errored.append(f"{v.judge} ({v.error})")
            continue
        w = JUDGE_WEIGHTS.get(v.judge, 0.0)
        weighted_sum += v.score * w
        weight_total += w
        if v.score < hard_veto_floor:
            vetoed_by.append(f"{v.judge} (score={v.score})")
        if v.feedback and v.feedback.strip().lower() not in {"no blocking issues.", "no trading-rule violations.", "style acceptable.", ""}:
            feedback_lines.append(f"[{v.judge} @ {v.model}, score={v.score}/10]\n{v.feedback}")

    weighted_score = (weighted_sum / weight_total) if weight_total else 0.0
    approved = weighted_score >= threshold and not vetoed_by

    merged = "\n\n".join(feedback_lines) if feedback_lines else "All judges reported no issues."
    if vetoed_by:
        merged = f"HARD VETO from: {', '.join(vetoed_by)}\n\n" + merged
    if errored:
        merged = f"EXCLUDED (errored, not scored): {', '.join(errored)}\n\n" + merged

    return approved, round(weighted_score, 2), merged


# ---------------------------------------------------------------------------
# Top-level pipeline
# ---------------------------------------------------------------------------
def run_panel_pipeline(
    task_prompt: str,
    max_retries: int = 2,
    threshold: float = DEFAULT_APPROVAL_THRESHOLD,
    maker_model: str = MAKER_MODEL,
    refiner_model: str = REFINER_MODEL,
    judge_overrides: Optional[Dict[str, str]] = None,
    language: str = "python",
) -> PanelReport:
    """Execute the full Agent-as-a-Judge panel with self-correction loop."""
    preset = get_language_preset(language)
    print("=" * 64)
    print(f"AGENT-AS-A-JUDGE PANEL  (Maker + 4 Judges + Refiner)  [language={language}]")
    print("=" * 64)
    print(f"Maker   : {maker_model}")
    print(f"Refiner : {refiner_model}")
    print(f"Judges  : {JUDGE_MODELS}")
    print(f"Threshold: {threshold}  Max retries: {max_retries}")
    print("=" * 64)

    # Effective judge models (allow per-call override)
    effective_judges = dict(JUDGE_MODELS)
    if judge_overrides:
        effective_judges.update(judge_overrides)

    # Step 1: Maker draft
    current_code = maker_generate(task_prompt, model=maker_model, language=language)
    if not current_code:
        return PanelReport(approved=False, weighted_score=0.0,
                           merged_feedback="Maker failed to produce a draft.")

    last_feedback = ""
    for attempt in range(1, max_retries + 2):
        print(f"\n--- PANEL EVALUATION CYCLE #{attempt} ---")
        verdicts = panel_evaluate(task_prompt, current_code, language=language)
        for v in verdicts:
            print(f"  [{v.judge:14s}] {v.model:24s} score={v.score}/10 approved={v.approved}")

        approved, weighted_score, merged_feedback = aggregate_verdicts(verdicts, threshold=threshold)
        print(f"  => weighted_score={weighted_score}  approved={approved}")

        if approved:
            print("[OK] PANEL APPROVED")
            return PanelReport(
                approved=True,
                weighted_score=weighted_score,
                verdicts=verdicts,
                merged_feedback=merged_feedback,
                final_code=current_code,
                attempts=attempt,
            )

        # Rejected — try judge-supplied refined code first, else refiner redraft
        last_feedback = merged_feedback
        judge_refined = _pick_best_refined(verdicts)
        if judge_refined:
            print("[Self-Correction] using highest-scoring judge's refined_code as next draft.")
            current_code = judge_refined
        else:
            print("[Self-Correction] no judge supplied refined code — calling Refiner.")
            redraft = refiner_redraft(task_prompt, current_code, merged_feedback, model=refiner_model, language=language)
            if redraft:
                current_code = redraft

    print("[FAIL] PANEL EXHAUSTED RETRIES — returning best draft with feedback.")
    return PanelReport(
        approved=False,
        weighted_score=weighted_score,
        verdicts=verdicts,
        merged_feedback=last_feedback,
        final_code=current_code,
        attempts=max_retries + 1,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent-as-a-Judge panel (Maker + 4 Judges + Refiner).")
    parser.add_argument("--prompt", type=str, required=True, help="Task prompt for code generation.")
    parser.add_argument("--maker", type=str, default=MAKER_MODEL, help="Maker model (high-token role).")
    parser.add_argument("--refiner", type=str, default=REFINER_MODEL, help="Refiner model (high-token role).")
    parser.add_argument("--max-retries", type=int, default=2, help="Self-correction retries on top of the first cycle.")
    parser.add_argument("--threshold", type=float, default=DEFAULT_APPROVAL_THRESHOLD,
                        help="Weighted score required for approval (default 7.0).")
    parser.add_argument("--language", type=str, default="python", choices=list(LANGUAGE_PRESETS.keys()),
                        help="Target language: python (default) or csharp (NinjaScript).")
    parser.add_argument("--out", type=str, default=None, help="Write final code to this file path.")
    parser.add_argument("--report", type=str, default=None, help="Write full panel report JSON to this path.")
    args = parser.parse_args()

    report = run_panel_pipeline(
        args.prompt,
        max_retries=args.max_retries,
        threshold=args.threshold,
        maker_model=args.maker,
        refiner_model=args.refiner,
        language=args.language,
    )

    print("\n" + "=" * 64)
    print("FINAL PANEL RESULT")
    print("=" * 64)
    print(f"Approved        : {report.approved}")
    print(f"Weighted score  : {report.weighted_score}")
    print(f"Cycles          : {report.attempts}")
    print(f"Merged feedback :\n{report.merged_feedback}")

    if args.out and report.final_code:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report.final_code)
        print(f"\nFinal code written to: {args.out}")
    elif report.final_code:
        print("\n--- FINAL CODE ---")
        print(report.final_code)

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"\nFull report written to: {args.report}")