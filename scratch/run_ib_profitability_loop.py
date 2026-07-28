"""
run_ib_profitability_loop.py
============================
Agent loop to diagnose and fix the IB bot profitability gap between NT8 SA backtests
and the Python validation framework.

Context:
  NT8 baseline (Jan-Mar 2026, MNQ 03-26, no confluence filters, no bias):
    IBBreakoutBot: 944 trades, WR 44.6%, PF 0.986, net -1294.50, maxDD -7277
    IBFadeBot:      82 trades, WR 54.9%, PF 0.815, net -1206,    maxDD -1520.5
    IBRetestBot:    31 trades, WR 41.9%, PF 0.798, net -636,     maxDD -1646

  Python validation (NY AM IB, 5-year, 1308 sessions):
    Play 1 Breakout (0.25x target): E[R] +0.0798, PF 1.75, WR 71.0%
    Play 1 Breakout (0.5x target):  E[R] +0.0884, PF 1.30, WR 51.8%
    Play 3 Fade (0.25x target):     E[R] +0.0569, PF 1.13, WR 11.1%
    Play 2 Retest (0.25x target):   E[R] +0.0171, PF 0.82, WR 13.6%

  KEY GAPS:
    1. IBBreakoutBot uses TargetLvl=0.5 (WR 51.8% in Python) but NT8 shows 44.6% WR.
       Python 0.5x expects PF 1.30 (positive); NT8 shows PF 0.986 (negative).
    2. IBFadeBot uses TargetLvl=0.25 (WR 11.1% in Python) but NT8 shows 54.9% WR.
       The WR mismatch suggests different stop/target geometry or entry logic.
    3. All 3 bots are net negative in NT8 but Python shows positive E[R] for
       Play 1 (0.25x and 0.5x) and Play 3 (0.25x).

Roles:
  - Maker (Gemma): does the actual work — proposes parameter changes + code fixes.
  - Reviewers (minimax, glm, qwen): review, debate, vote on the fix path.
  - kimi replaced by minimax (was timing out).
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from scripts.utils.ollama_bridge import query_ollama

sys.stdout.reconfigure(encoding="utf-8")

MAKER_MODEL = "gemma4:31b-cloud"
REVIEW_JUDGES = {
    "architecture":  "glm-5.2:cloud",
    "edge_cases":     "minimax-m3:cloud",
    "trading_rules":  "qwen3.5:397b-cloud",
}
MODERATOR_MODEL = "minimax-m3:cloud"

# ---------------------------------------------------------------------------
BRIEF = """
### THE PROBLEM
All 3 IB bots (IBBreakoutBot, IBFadeBot, IBRetestBot) are NET NEGATIVE in NT8 Strategy
Analyzer backtests, despite the Python validation framework showing positive E[R]
for Play 1 (breakout) and Play 3 (fade) on NQ1 NY AM IB.

### NT8 BASELINE (Jan-Mar 2026, MNQ 03-26, no confluence filters, no direction bias)
IBBreakoutBot: 944 trades, WR 44.6%, PF 0.986, net -1294.50, maxDD -7277
  - TargetLvl=0.5, StopRMult=0.25, stop=entry-0.25*0.5*range, target=rangeHigh+0.5*range
IBFadeBot:      82 trades, WR 54.9%, PF 0.815, net -1206, maxDD -1520.5
  - TargetLvl=0.25, StopRMult=0.5, stop=boundary+0.5*range, target=rangeMid
IBRetestBot:    31 trades, WR 41.9%, PF 0.798, net -636, maxDD -1646
  - TargetLvl=0.5, StopRMult=0.25

### PYTHON VALIDATION (NY AM IB, 5-year, 1308 sessions, NQ1)
Play 1 Breakout (0.25x target): E[R] +0.0798, PF 1.75, WR 71.0%, N=41504
Play 1 Breakout (0.5x target):  E[R] +0.0884, PF 1.30, WR 51.8%, N=41504
Play 3 Fade (0.25x target):     E[R] +0.0569, PF 1.13, WR 11.1%, N=41504
Play 2 Retest (0.25x target):   E[R] +0.0171, PF 0.82, WR 13.6%, N=41504

### KEY DISCREPANCIES TO DIAGNOSE
1. IBBreakoutBot: NT8 WR=44.6% but Python 0.5x WR=51.8%. NT8 PF=0.986 but Python PF=1.30.
   The 7% WR gap and PF flip suggest the stop or target geometry differs.
   Python stop = opposite IB boundary (full range stop). NT8 stop = 0.25*0.5*range = 0.125*range (TINY).
   This is the likely root cause: the NT8 stop is 8x tighter than Python's, causing stop-outs.
2. IBFadeBot: NT8 WR=54.9% but Python 0.25x WR=11.1%. NT8 has 5x higher WR but is net negative.
   The WR inversion suggests the NT8 fade is hitting a very close target (rangeMid) but the
   stop (0.5*range beyond boundary) is much wider than the target, so losses swamp wins.
   Python's 11% WR with PF 1.13 means wins are ~10x larger than losses (target far, stop tight).
3. IBBreakoutBot has 944 trades in 3 months (~15/day) vs Python's 1 trade/session. The NT8
   bot is re-entering repeatedly on every bar beyond the IB boundary, not once per break.

### STRATEGY CODE REFERENCES
IBBreakoutBot.CheckForEntry(): close > rangeHigh -> EnterLong(entry=close, stop=entry-StopRMult*TargetLvl*range, target=rangeHigh+TargetLvl*range)
IBFadeBot.CheckForEntry(): overshoot + close back inside -> EnterShort(entry=rangeHigh, stop=rangeHigh+0.5*range, target=rangeMid)
Python play_detail: stop=opposite IB boundary, target=TargetLvl*range beyond break side

### GOAL
Diagnose the root causes and propose concrete parameter/code fixes to make the bots
profitable in NT8, matching the Python E[R] expectations.
"""

MAKER_PROMPT = """You are Gemma (Senior Developer). DO THE ACTUAL WORK: diagnose the IB bot
profitability gap and propose CONCRETE fixes.

Given the brief, for each of the 3 bots, identify:
1. ROOT CAUSE: why is NT8 net negative when Python shows positive E[R]?
2. FIX: the exact parameter change or code change needed.
3. EXPECTED: what the NT8 metrics should look like after the fix (WR, PF, net).

Focus especially on:
- Stop geometry mismatch (NT8 uses tiny 0.125*range stops vs Python's full-range stop)
- Entry frequency (NT8 re-enters every bar beyond IB; Python enters once per break)
- Target/stop R:R ratio (IBFadeBot target=rangeMid is close, stop=0.5*range is far)
- The EntriesPerDirection=1 setting in RiskManagerBase (should prevent re-entry, but
  EnterWithRangeStop uses raw EnterLong/Short, not the managed entry system)

Output STRICT JSON only:
{
  "diagnosis": [
    {
      "bot": "IBBreakoutBot",
      "root_cause": "...",
      "fix": "exact param change or code change",
      "expected_wr": "...",
      "expected_pf": "..."
    },
    {"bot": "IBFadeBot", ...},
    {"bot": "IBRetestBot", ...}
  ],
  "priority_order": ["first bot to fix", "second", "third"],
  "summary": "2-3 sentence overall strategy"
}
"""

REVIEW_RUBRIC = {
    "architecture": """You are Judge A — ARCHITECTURE reviewer. Evaluate whether the proposed
fixes correctly address the root causes without breaking the RiskManagerBase/IntradayStrategyBase
contract. Flag any fix that would bypass risk gates or break the inheritance chain.
Output STRICT JSON: {"score":1-10,"approved":bool,"blocking_flaws":[...],"suggestions":[...],"summary":"..."}""",
    "edge_cases": """You are Judge B — EDGE CASE reviewer (replacing kimi). For each proposed fix,
find the failure mode: will the fix cause over-trading, blown accounts, or silently miss the Python
parity target? Check: EntriesPerDirection, re-entry logic, stop-too-tight causing 99% stopout,
target-too-far causing 0% fill. Output STRICT JSON: {"score":1-10,"approved":bool,"failure_modes":[...],"summary":"..."}""",
    "trading_rules": """You are Judge C — TRADING-RULES + PARITY reviewer. Does the proposed fix
actually match the Python play_detail stop/target geometry? The Python stop for Play 1 is the
OPPOSITE IB BOUNDARY (full range), not 0.125*range. The Python target for Play 3 at 0.25x is
0.25*range from the FADE ENTRY POINT (rangeHigh), not rangeMid. Verify each fix against the
EDGE_VALIDATION_REPORT.md stats. Output STRICT JSON: {"score":1-10,"approved":bool,"violations":[...],"summary":"..."}""",
}

DEBATE_PROMPT = """You are a %(role)s on a debate panel. Given the Maker's diagnosis and fixes,
rank the 3 bots by "most likely to become profitable after the fix" and identify the SINGLE most
impactful change across all 3 bots. Output STRICT JSON:
{"ranked":["bot1","bot2","bot3"],"most_impactful_change":"...","rationale":"...","confidence":"low|med|high"}
"""

MODERATOR_PROMPT = """You are the MODERATOR. Merge the judges' rankings into a single action plan.
Output STRICT JSON: {"action_plan":"step-by-step fix order","most_impactful_change":"...","confidence":"low|med|high"}"""


def _parse_json(raw: str) -> Dict[str, Any]:
    if not raw:
        return {}
    s, e = raw.find("{"), raw.rfind("}")
    if s == -1 or e == -1 or e <= s:
        return {}
    try:
        return json.loads(raw[s : e + 1])
    except json.JSONDecodeError:
        return {}


@dataclass
class LoopResult:
    maker: Optional[Dict[str, Any]] = None
    verdicts: List[Dict[str, Any]] = field(default_factory=list)
    debate: List[Dict[str, Any]] = field(default_factory=list)
    moderated: Optional[Dict[str, Any]] = None


def main() -> int:
    print("=" * 72)
    print("AGENT LOOP: IB Bot Profitability Diagnosis")
    print(f"Maker: {MAKER_MODEL} | Reviewers: {REVIEW_JUDGES} | Moderator: {MODERATOR_MODEL}")
    print("=" * 72)

    # Step 1: Maker
    print("\n[STEP 1] Maker (Gemma) diagnosing profitability gap...")
    raw = query_ollama(MAKER_PROMPT, model=MAKER_MODEL, temperature=0.2, timeout=300)
    maker = _parse_json(raw) if raw else {"error": "parse_failed", "raw": (raw or "")[:2000]}
    if "diagnosis" in maker:
        print(f"  -> diagnosis for {len(maker['diagnosis'])} bots")
        for d in maker.get("diagnosis", []):
            print(f"     {d.get('bot','?')}: {d.get('root_cause','?')[:100]}")
    else:
        print(f"  !! parse failed; raw saved")
    print(f"  priority: {maker.get('priority_order','?')}")

    # Step 2: Reviewers (parallel)
    print("\n[STEP 2] Reviewers critiquing diagnosis...")
    brief = json.dumps({"maker": maker, "context": BRIEF.strip()}, indent=2)[:12000]
    verdicts: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=len(REVIEW_JUDGES)) as pool:
        futures = {}
        for j, model in REVIEW_JUDGES.items():
            futures[pool.submit(
                query_ollama,
                f"### MAKER DIAGNOSIS TO REVIEW\n{brief}\n\nProduce your review JSON.",
                model=model,
                system_prompt=REVIEW_RUBRIC[j],
                temperature=0.1,
                timeout=240,
            )] = j
        for fut in as_completed(futures):
            j = futures[fut]
            try:
                raw = fut.result()
                parsed = _parse_json(raw) or {"judge": j, "error": "parse_failed", "raw": (raw or "")[:800]}
                parsed["judge"] = j
                parsed["model"] = REVIEW_JUDGES[j]
                verdicts.append(parsed)
                print(f"  [{j:14s}] {REVIEW_JUDGES[j]:22s} score={parsed.get('score','?')} approved={parsed.get('approved','?')}")
            except Exception as exc:
                verdicts.append({"judge": j, "model": REVIEW_JUDGES[j], "error": f"crash: {exc}"})
                print(f"  [{j:14s}] CRASH: {exc}")

    # Step 3: Debate
    print("\n[STEP 3] Debate: ranking bots by fixability...")
    proposals: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=len(REVIEW_JUDGES)) as pool:
        futures = {}
        for j, model in REVIEW_JUDGES.items():
            user = DEBATE_PROMPT % {"role": j}
            futures[pool.submit(query_ollama, user, model=model, system_prompt=f"You are a {j}.", temperature=0.2, timeout=240)] = j
        for fut in as_completed(futures):
            j = futures[fut]
            try:
                raw = fut.result()
                p = _parse_json(raw) or {"role": j, "error": "parse_failed"}
                p["role"] = j
                proposals.append(p)
                print(f"  [{j:14s}] ranked={p.get('ranked','?')} change={p.get('most_impactful_change','?')[:80]}")
            except Exception as exc:
                proposals.append({"role": j, "error": f"crash: {exc}"})

    # Moderate
    user = MODERATOR_PROMPT + "\n\n### PROPOSALS\n" + json.dumps(proposals, indent=2)
    raw = query_ollama(user, model=MODERATOR_MODEL, temperature=0.1, timeout=240)
    moderated = _parse_json(raw) or {"action_plan": "moderation_failed", "confidence": "low"}
    print(f"\n  => ACTION PLAN: {moderated.get('action_plan','?')[:200]}")
    print(f"     MOST IMPACTFUL: {moderated.get('most_impactful_change','?')[:160]}")

    # Save
    result = LoopResult(maker=maker, verdicts=verdicts, debate=proposals, moderated=moderated)
    transcript = {
        "maker": maker,
        "verdicts": verdicts,
        "debate": proposals,
        "moderated": moderated,
    }
    with open("scratch/ib_profitability_loop.json", "w", encoding="utf-8") as f:
        json.dump(transcript, f, indent=2, default=str)
    print("\n[saved] scratch/ib_profitability_loop.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())