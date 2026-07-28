"""
run_parity_harness_loop.py
==========================
Agent loop to resolve the NT8 Strategy Analyzer vs Python validation discrepancy
for the ORB strategy family.

Roles:
  - Maker (Gemma): does the actual work — drafts the parity harness + Log() patch.
  - Reviewers (minimax, glm, qwen): review Gemma's drafts, debate the root cause,
    vote on the path forward.
  - kimi-k2.7-code:cloud was timing out → replaced with minimax-m3:cloud everywhere.

Outputs:
  - scripts/orb_generic/parity_check.py            (Maker draft, refined by reviewers)
  - scratch/nt8_diag_patch_ORB_AllDay_MultiTP.cs   (Log() diagnostics patch draft)
  - scratch/parity_loop_result.json                 (full agent-loop transcript)
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Repo root on sys.path so `scripts.utils.ollama_bridge` imports when run from scratch/
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from scripts.utils.ollama_bridge import query_ollama

sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# Model assignment — Gemma does the work; minimax + glm + qwen review/debate.
# kimi-k2.7-code:cloud removed (was timing out); minimax-m3:cloud takes its slot.
# ---------------------------------------------------------------------------
MAKER_MODEL = "gemma4:31b-cloud"        # does the actual drafting work
REFINER_MODEL = "gemma4:31b-cloud"       # Gemma also refines after review (user request)

REVIEW_JUDGES = {
    "architecture":  "glm-5.2:cloud",       # structural soundness of harness/patch
    "edge_cases":    "minimax-m3:cloud",     # replaces kimi — failure modes, runtime crashes
    "trading_rules": "qwen3.5:397b-cloud",  # ADR / SecondBrain compliance + parity correctness
}
MODERATOR_MODEL = "minimax-m3:cloud"        # merges debate answers (kimi's old slot)

# ---------------------------------------------------------------------------
# Discrepancy brief — shared context for every agent in the loop.
# ---------------------------------------------------------------------------
DISCREPANCY_BRIEF = """
### THE DISCREPANCY
NT8 Strategy Analyzer (SA) backtests of `ORB_AllDay_MultiTP.cs` on MNQ/MES disagree
with the Python validation framework in `scripts/orb_generic/strategy_validation/`
(scripts 01-06: OR breakout rates, excursion stats, prop sim).

### KNOWN ASSUMPTION GAPS (hypotheses, unconfirmed)
1. Entry timing: Python uses breakout-bar `close`; NT8 default fills at next bar `open`
   (or intra-bar if `Calculate != OnBarClose`). 1-bar slippage on every entry.
2. Stop/Target fill resolution: Python bar-level (conservative, worst-case intrabar);
   NT8 tick-level (aggressive, first-touch). Stops fire earlier in NT8 → edge shrinks.
3. Session filter: Python ET hour windows on 24h parquet; NT8 chart session template.
   A 1-min template mismatch shifts every OR window and the 16:00 liquidation fence.
4. Fees/commissions: Python `06_prop_sim.py` may assume $0; NT8 simulator defaults
   may include exchange fees. Even RT commission shifts small-edge strategies negative.
5. Data alignment: Python parquet (TradingView-sourced) vs NT8 historical feed.
   Different tick construction at bar boundaries → different OHLCV at the margins.

### TARGET STRATEGY
`ORB_AllDay_MultiTP.cs` (NT8) — all-day OR breakout with multi-TP exit.
Python equivalent: or_breakout / or_fade strategies in `signal_generators.py` +
`06_prop_sim.py` simulation.

### GOAL OF THIS LOOP
1. Build `scripts/orb_generic/parity_check.py` — runs Python sim for a single
   trade_date, queries NT8 SA via the nt-mcp-server `nt_backtest` tool for the
   same day, prints a side-by-side trade ledger (entry/exit time+price, fees, PnL).
2. Build a `Log()` diagnostics patch for `ORB_AllDay_MultiTP.cs` that emits
   per-bar gate decisions (in-window? rangeComplete? bias? close>rangeHigh?) so
   the SA log file gives ground truth for why a trade was/wasn't taken.
3. Have reviewers debate which of the 5 hypotheses is the most likely root cause
   and what the *first* 3-day parity tracer (trending / chop / gap day) should check.
"""

# ---------------------------------------------------------------------------
# Maker prompts
# ---------------------------------------------------------------------------
MAKER_HARNESS_PROMPT = """You are Gemma (Senior Developer). DO THE ACTUAL WORK: write a complete,
runnable Python script `parity_check.py` that resolves the NT8 SA vs Python validation
discrepancy for the ORB strategy family.

Requirements (ADR-compliant, vectorized where possible):
1. Load ONE trade_date of 1-min bars from `data/live/live_storage_-{ticker}.parquet`
   (live storage, NOT historical — per CLAUDE.md data architecture). Filter to RTH
   9:30-16:00 ET. Use `scripts/utils/fused_data_loader.py` only if live storage lacks
   the requested date.
2. Run the Python OR breakout simulation for that day inline (do NOT shell out to
   `06_prop_sim.py`). Replicate the or_breakout logic from
   `scripts/orb_generic/strategy_validation/scripts/signal_generators.py`:
   - OR window 9:30 + OR_DURATION minutes (default 30).
   - Long entry: first close > OR high, after OR window closes.
   - Short entry: first close < OR low.
   - Stop: opposite side of OR (OR low for long, OR high for short).
   - Target: configurable R-multiple of risk (default 2R).
   - Exit: stop, target, or 16:00 ET liquidation (ADR-020).
3. Query NT8 SA via the MCP bridge. Since this script runs outside the MCP,
   emit the exact `mcp_nt-mcp-server_nt_backtest` invocation the user should run
   (strategy="ORB_AllDay_MultiTP", symbol, from=to=trade_date, period=Minute,
   periodValue=1, maxTrades=50) and instructions to paste the JSON result into
   a `--nt8-json path/to/result.json` arg. Then parse that JSON side-by-side.
4. Print a trade-by-trade diff table:
   | metric | python | nt8 | delta | match |
   Entry time, entry price, stop, target, exit time, exit price, fees, pnl,
   pnl_pct (ADR-002: report as price %, not points).
5. CLI: `--ticker NQ1 --date 2026-03-15 --or-duration 30 --target-r 2.0
   --nt8-json path/to/sa_result.json`.
6. Vectorized entry/exit detection (NumPy, no for-loops in calc paths — ADR-017).
   A single bar-by-bar loop for trade *resolution* (stop/target tie-break) is
   acceptable and must be commented as the bounded loop exception.
7. Type hints, docstrings, snake_case, module docstring header (repo convention).

Output STRICT JSON only:
{
  "script_path": "scripts/orb_generic/parity_check.py",
  "code": "<full python file content>",
  "notes": "<2-3 sentence how to run it + what to compare>"
}
"""

MAKER_DIAG_PATCH_PROMPT = """You are Gemma (Senior Developer). DO THE ACTUAL WORK: write a
NinjaScript `Log()` diagnostics patch for the `OnBarUpdate` method of
`ORB_AllDay_MultiTP.cs` that emits per-bar gate decisions so the SA log file
(`Documents/NinjaTrader 8/log/log.YYYYMMDD.00000.txt`) gives ground truth for
why a trade was or wasn't taken on any given bar.

Use the memory note: SA backtest `Print()` goes to UI only (invisible to automation);
`Log(msg, LogLevel.Information)` goes to the log file. ALWAYS use `Log()`.

Requirements:
1. Gate-by-gate logging, every 100th bar when out-of-window, every 10th bar in-window,
   every bar on the bar where an entry/exit decision is made. (Per the verified debug playbook.)
2. Log these gates in order, with `[DIAG]` prefix:
   - bar index, ET time, close price
   - in_session_window (bool)
   - or_high, or_low, or_range, range_complete
   - predicted_dir, require_direction_bias (bool), bias_blocked (bool)
   - close_gt_rangeHigh / close_lt_rangeLow
   - gatekeeper_blocked (DailyMaxLoss, etc.) — bypassed if Account.Name contains
     "backtest" or "Playback" (per verified fix Bug 2)
   - ENTRY: long/short/skip with reason
   - EXIT: stop/target/liquidation/16:00 fence
3. Wrap each gate in `try/catch` so logging never crashes the strategy.
4. Add a `#if DEBUG` or a `VerboseDiag` bool property (default true in SA backtests,
   false in live) to disable per-bar spam in production.
5. Show ONLY the `OnBarUpdate` method body (the patch). Do NOT rewrite the whole file.
   Mark insertions with `// === DIAG PATCH START ===` / `// === DIAG PATCH END ===`.

Output STRICT JSON only:
{
  "patch_path": "scratch/nt8_diag_patch_ORB_AllDay_MultiTP.cs",
  "code": "<the OnBarUpdate method body with the DIAG patch>",
  "apply_instructions": "<1-2 sentence how to splice this into the existing .cs>"
}
"""

# ---------------------------------------------------------------------------
# Reviewer rubrics (concise; reuse agentic_review pattern)
# ---------------------------------------------------------------------------
REVIEW_RUBRIC = {
    "architecture": """You are Judge A — ARCHITECTURE reviewer for a parity-check harness +
NT8 Log() patch that must reconcile Python validation vs NT8 Strategy Analyzer.
Focus on:
1. Will the parity harness actually apples-to-apples compare? (entry timing, fees,
   session template, RTH window alignment).
2. Is the harness reusable across strategies or hard-coded to ORB?
3. Will the Log() patch survive compile in NT8 (.NET Framework 4.8 / NinjaScript
   constraints)? Flag any API misuse (BarsArray, GetCurrentBar, Account.Name access).
4. Does the patch leak into live trading (per-bar spam, perf impact)?
Output STRICT JSON: {"score":1-10,"approved":bool,"blocking_flaws":[...],"suggestions":[...],"summary":"..."}""",
    "edge_cases": """You are Judge B — EDGE CASE / FAILURE MODE reviewer (replacing kimi
which was timing out). Find the breaks:
1. Empty/holiday session, single-bar OR, OR with zero range (orHigh==orLow).
2. DST transition bar, midnight session rollover, missing bars in live_storage.
3. NT8 SA result JSON shape varies across NT8 versions — schema mismatch in parser.
4. Stop+target same-bar tie-break (the core discrepancy hypothesis #2).
5. Parquet datetime tz vs NT8 bar time (UTC vs ET vs exchange time).
6. Division-by-zero in pnl_pct when entry_price is 0.
For each: reproduction + does the design handle it?
Output STRICT JSON: {"score":1-10,"approved":bool,"failure_modes":[{"scenario":"","reproduction":"","handled":false,"severity":""}],"summary":""}""",
    "trading_rules": """You are Judge C — TRADING-RULES COMPLIANCE + PARITY CORRECTNESS reviewer.
Verify:
- ADR-002: pnl reported as price %, not points.
- ADR-020: 16:00 ET liquidation fence (close of 15:59 bar) — exact same fence in Python and NT8.
- ADR-021: PropFirmSimulator NOT required here (this is a *parity* check, not viability sim) —
  flag if the harness accidentally imports prop_firm_simulator.
- ADR-001: ET session windows; parquet tz handled.
- Live storage used (per CLAUDE.md), not historical-only loader.
- The 5 discrepancy hypotheses are all *testable* by the harness (entry timing, stop fill,
  session, fees, data alignment). List any hypothesis the harness CANNOT distinguish.
Output STRICT JSON: {"score":1-10,"approved":bool,"violations":[{"adr":"","issue":"","fix":""}],"summary":""}""",
}

# ---------------------------------------------------------------------------
# Debate prompt — resolve which hypothesis to chase first
# ---------------------------------------------------------------------------
DEBATE_PROMPT = """You are a %(role)s on a debate panel resolving the root cause of the
NT8 SA vs Python discrepancy. The 5 hypotheses are:
H1 entry-timing (close vs next-bar open)
H2 stop/target fill resolution (bar-level vs tick-level first-touch)
H3 session-filter / RTH template mismatch
H4 fees/commissions mismatch
H5 data alignment (parquet vs NT8 historical feed)

### PARITY HARNESS PLAN (from Maker)
%(harness_brief)s

### YOUR TASK
Pick the SINGLE most likely root cause for a small-edge ORB strategy showing edge
in Python but no edge (or negative edge) in NT8 SA. Justify with:
1. **answer**: the hypothesis ID + 1 sentence.
2. **rationale**: why this one dominates, grounded in ORB strategy mechanics.
3. **first_tracer**: which of these 3 days to test first and why — trending day,
   chop day, gap day.
4. **confidence**: low|med|high.

Output STRICT JSON: {"answer":"","rationale":"","first_tracer":"","confidence":"low|med|high"}
"""

MODERATOR_PROMPT = """You are the MODERATOR merging %(n)d judges' root-cause hypotheses.
Pick the resolution with the strongest rationale; if they disagree, synthesize and note dissent.
Output STRICT JSON: {"resolved_answer":"","first_tracer":"","dissent":"","confidence":"low|med|high"}
"""


# ---------------------------------------------------------------------------
# JSON helper
# ---------------------------------------------------------------------------
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
class MakerOutput:
    harness: Optional[Dict[str, Any]] = None
    diag_patch: Optional[Dict[str, Any]] = None


@dataclass
class ReviewVerdict:
    judge: str
    model: str
    score: int = 0
    approved: bool = False
    detail: Dict[str, Any] = field(default_factory=dict)
    raw: Optional[str] = None
    error: Optional[str] = None


@dataclass
class LoopResult:
    maker: MakerOutput = field(default_factory=MakerOutput)
    verdicts: List[ReviewVerdict] = field(default_factory=list)
    debate: List[Dict[str, Any]] = field(default_factory=list)
    moderated: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Maker pass — Gemma does the work
# ---------------------------------------------------------------------------
def run_maker() -> MakerOutput:
    print("=" * 72)
    print("STEP 1: MAKER PASS — Gemma drafts parity harness + Log() patch")
    print("=" * 72)
    out = MakerOutput()

    print("\n[1a] Gemma drafting parity_check.py ...")
    raw = query_ollama(MAKER_HARNESS_PROMPT, model=MAKER_MODEL, temperature=0.2, timeout=300)
    out.harness = _parse_json(raw) if raw else None
    if not out.harness:
        out.harness = {"error": "parse_failed", "raw": (raw or "")[:1000]}
        print("  !! harness parse failed; raw saved to transcript")
    else:
        print(f"  -> harness draft: {len(out.harness.get('code',''))} chars")

    print("\n[1b] Gemma drafting Log() diag patch for ORB_AllDay_MultiTP.cs ...")
    raw = query_ollama(MAKER_DIAG_PATCH_PROMPT, model=MAKER_MODEL, temperature=0.2, timeout=300)
    out.diag_patch = _parse_json(raw) if raw else None
    if not out.diag_patch:
        out.diag_patch = {"error": "parse_failed", "raw": (raw or "")[:1000]}
        print("  !! diag patch parse failed; raw saved to transcript")
    else:
        print(f"  -> diag patch draft: {len(out.diag_patch.get('code',''))} chars")

    return out


# ---------------------------------------------------------------------------
# Reviewer pass — minimax + glm + qwen critique (kimi replaced by minimax)
# ---------------------------------------------------------------------------
def _review_one(judge: str, model: str, system: str, brief: str) -> ReviewVerdict:
    user = f"### MAKER DRAFTS TO REVIEW\n{brief}\n\nProduce your review JSON."
    raw = query_ollama(user, model=model, system_prompt=system, temperature=0.1, timeout=240)
    if raw is None:
        return ReviewVerdict(judge, model, error="query_failed")
    parsed = _parse_json(raw)
    if not parsed:
        return ReviewVerdict(judge, model, detail={"raw": raw[:800]}, raw=raw, error="parse_failed")
    return ReviewVerdict(
        judge=judge, model=model,
        score=int(parsed.get("score", 0) or 0),
        approved=bool(parsed.get("approved", False)),
        detail=parsed, raw=raw,
    )


def run_reviewers(maker: MakerOutput) -> List[ReviewVerdict]:
    print("\n" + "=" * 72)
    print("STEP 2: REVIEWER PASS — minimax + glm + qwen critique (kimi replaced)")
    print("=" * 72)
    brief = json.dumps({
        "harness": maker.harness,
        "diag_patch": maker.diag_patch,
        "discrepancy_brief": DISCREPANCY_BRIEF.strip(),
    }, indent=2)[:12000]  # cap context
    verdicts: List[ReviewVerdict] = []
    with ThreadPoolExecutor(max_workers=len(REVIEW_JUDGES)) as pool:
        futures = {
            pool.submit(_review_one, j, REVIEW_JUDGES[j], REVIEW_RUBRIC[j], brief): j
            for j in REVIEW_JUDGES
        }
        for fut in as_completed(futures):
            j = futures[fut]
            try:
                verdicts.append(fut.result())
            except Exception as exc:
                verdicts.append(ReviewVerdict(j, REVIEW_JUDGES[j], error=f"crash: {exc}"))
    # stable order
    ordered = []
    for j in REVIEW_JUDGES:
        for v in verdicts:
            if v.judge == j:
                ordered.append(v)
    for v in ordered:
        print(f"  [{v.judge:14s}] {v.model:22s} score={v.score}/10 approved={v.approved} err={v.error}")
    return ordered


# ---------------------------------------------------------------------------
# Debate pass — resolve the root cause
# ---------------------------------------------------------------------------
def run_debate(maker: MakerOutput) -> tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    print("\n" + "=" * 72)
    print("STEP 3: DEBATE PASS — which discrepancy hypothesis to chase first")
    print("=" * 72)
    harness_brief = (maker.harness or {}).get("notes", "") + "\n" + DISCREPANCY_BRIEF
    proposals: List[Dict[str, Any]] = []
    roles = list(REVIEW_JUDGES.keys())
    with ThreadPoolExecutor(max_workers=len(roles)) as pool:
        futures = {}
        for r in roles:
            sys_prompt = f"You are a {r} on a debate panel."
            user = DEBATE_PROMPT % {"role": r, "harness_brief": harness_brief[:6000]}
            futures[pool.submit(
                query_ollama, user,
                model=REVIEW_JUDGES[r],
                system_prompt=sys_prompt,
                temperature=0.2,
                timeout=240,
            )] = r
        for fut in as_completed(futures):
            r = futures[fut]
            try:
                raw = fut.result()
                proposals.append(_parse_json(raw) or {"role": r, "raw": (raw or "")[:600], "confidence": "low"})
            except Exception as exc:
                proposals.append({"role": r, "error": f"crash: {exc}", "confidence": "low"})
    for p in proposals:
        print(f"  [{p.get('role','?'):14s}] answer={p.get('answer','?')[:80]} conf={p.get('confidence','?')}")

    # Moderate
    user = MODERATOR_PROMPT % {"n": len(proposals)} + "\n\n### PROPOSALS\n" + json.dumps(proposals, indent=2)
    raw = query_ollama(user, model=MODERATOR_MODEL, temperature=0.1, timeout=240)
    moderated = _parse_json(raw) or {"resolved_answer": "moderation_failed", "dissent": "parse error", "confidence": "low"}
    print(f"\n  => MODERATED: {moderated.get('resolved_answer','?')[:160]}")
    print(f"     first_tracer: {moderated.get('first_tracer','?')[:120]}")
    print(f"     dissent: {moderated.get('dissent','consensus')[:120]}")
    return proposals, moderated


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print("=" * 72)
    print("AGENT LOOP: NT8 SA vs Python ORB parity discrepancy")
    print(f"Maker: {MAKER_MODEL} | Reviewers: {REVIEW_JUDGES} | Moderator: {MODERATOR_MODEL}")
    print("NOTE: kimi-k2.7-code:cloud removed (timing out) — minimax-m3:cloud replaces it.")
    print("=" * 72)

    maker = run_maker()
    verdicts = run_reviewers(maker)
    proposals, moderated = run_debate(maker)

    # Persist Maker drafts to disk (best-effort)
    if maker.harness and "code" in maker.harness:
        try:
            p = "scripts/orb_generic/parity_check.py"
            with open(p, "w", encoding="utf-8") as f:
                f.write(maker.harness["code"])
            print(f"\n[saved] {p}")
        except Exception as e:
            print(f"[warn] could not save harness: {e}")
    if maker.diag_patch and "code" in maker.diag_patch:
        try:
            p = "scratch/nt8_diag_patch_ORB_AllDay_MultiTP.cs"
            with open(p, "w", encoding="utf-8") as f:
                f.write(maker.diag_patch["code"])
            print(f"[saved] {p}")
        except Exception as e:
            print(f"[warn] could not save diag patch: {e}")

    result = LoopResult(maker=maker, verdicts=verdicts, debate=proposals, moderated=moderated)
    transcript = {
        "maker": {"harness": maker.harness, "diag_patch": maker.diag_patch},
        "verdicts": [
            {"judge": v.judge, "model": v.model, "score": v.score,
             "approved": v.approved, "detail": v.detail, "error": v.error}
            for v in verdicts
        ],
        "debate": proposals,
        "moderated": moderated,
    }
    with open("scratch/parity_loop_result.json", "w", encoding="utf-8") as f:
        json.dump(transcript, f, indent=2, default=str)
    print("\n[saved] scratch/parity_loop_result.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())