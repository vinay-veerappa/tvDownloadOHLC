"""
agentic_review.py
==================
Agent-as-a-Judge panel in REVIEW mode — for design-doc review + open-question debate.

Distinct from agentic_panel.py (which drafts code). This panel:
1. Reads a design doc (or a compact brief extracted from one).
2. Runs 4 REVIEW judges in parallel (architecture, consistency, edge-cases, trading-rules).
3. Runs a DEBATE round on the doc's Open Questions — each judge proposes answers,
   a Moderator merges them into resolved recommendations.
4. Outputs a structured review report + resolved open questions.

Reuses ollama_bridge.query_ollama — no new HTTP code.

Usage:
    python -m scripts.utils.agentic_review --doc path/to/design.md
    python -m scripts.utils.agentic_review --doc path/to/design.md --report review.json
"""
from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from scripts.utils.ollama_bridge import query_ollama


# ---------------------------------------------------------------------------
# Model assignment — deeper models for review (judgment is harder than drafting)
# ---------------------------------------------------------------------------
REVIEW_JUDGES = {
    "architecture":  "glm-5.2:cloud",       # structural / OOP / reuse soundness
    "consistency":   "minimax-m3:cloud",    # cross-section contradictions, naming drift
    "edge_cases":    "kimi-k2.7-code:cloud",# failure modes, runtime crashes, concurrency
    "trading_rules": "qwen3.5:397b-cloud",  # ADR + SecondBrain compliance
}
MODERATOR_MODEL = "glm-5.2:cloud"  # merges debate answers


# ---------------------------------------------------------------------------
# Rubrics — each review judge has a distinct lens
# ---------------------------------------------------------------------------
REVIEW_RUBRICS: Dict[str, str] = {
    "architecture": """You are Judge A — ARCHITECTURE reviewer for a trading-strategy design doc.
Evaluate the *design*, not the prose. Focus on:
1. **Reuse contract soundness**: is the IntradayStrategyBase / IBStrategyBase split clean? Does anything IB-specific leak into the generic base? Does anything generic get duplicated in subclasses?
2. **Interface boundaries**: are the abstract methods (BuildRangeWindow / ComputeBias / CheckForEntry) the right cut? Are there concerns that *should* be pluggable interfaces (like IStopModel/ITargetModel) but are hardcoded?
3. **Cross-platform parity**: will the C# and Pine implementations actually produce identical signals given the described component split? Flag any platform-asymmetry that breaks parity.
4. **Future-strategy extensibility**: could a new ORB / sweep / key-level strategy inherit this base without contortions? Where would it strain?

Output STRICT JSON only:
{
  "score": <1-10>,
  "approved": <bool, true iff score >= 7 and no blocking architectural flaws>,
  "blocking_flaws": ["<flaw 1>", "..."],
  "suggestions": ["<non-blocking improvement 1>", "..."],
  "summary": "<2-3 sentence verdict>"
}
""",

    "consistency": """You are Judge B — INTERNAL CONSISTENCY reviewer.
Cross-check the doc against ITSELF. Look for:
1. **Naming drift**: does the same concept use different names across sections (e.g. ibHigh vs rangeHigh, predictedBreakDir vs predictedDir, RequireDirectionTrigger vs RequireDirectionBias)? List every drift pair with the section numbers.
2. **Parameter default mismatches**: does §2 (parameters) state a default that §3 (algorithm) or §4 (code) contradicts? (e.g. FlattenBy 15:50 vs 15:45, stop_r_mult 0.25 vs 0.5 for Play 3).
3. **Number mismatches**: any statistic cited in §2 findings that disagrees with §4.4-4.6 code (e.g. target_lvl 0.25 but code uses 0.5)?
4. **Section cross-references**: does any §X.Y reference point to a section that doesn't exist or was renumbered?

Output STRICT JSON only:
{
  "score": <1-10>,
  "approved": <bool, true iff no blocking inconsistencies>,
  "inconsistencies": [{"where":"§2.3 vs §4.6","issue":"...","fix":"..."}],
  "summary": "<verdict>"
}
""",

    "edge_cases": """You are Judge C — EDGE CASE / FAILURE MODE reviewer for a trading-strategy design.
Assume the strategy WILL be deployed live on real money. Find the failure modes:
1. **Range-window edge cases**: empty session (holiday), single-bar IB, IB with zero range (ibHigh==ibLow), session rollover at midnight, gap days.
2. **State machine bugs**: overshoot flag persistence across sessions (does it reset at session open?), firstBreakDir reset, rangeComplete stuck true across days.
3. **Order execution edge cases**: same-bar stop+target tie-break (Open Question #1), partial fills, order rejection, broker disconnect mid-position.
4. **Timezone / clock edge cases**: DST transition, the ibEnd arithmetic (IbStartHour*100 + IbDurationMin doesn't roll over hours correctly — e.g. 09:30 + 90 min = 1090 not 1100).
5. **Concurrency**: multiple strategies on the same account, copier replication race, RiskGuard flatten during copier submit.
6. **Data gaps**: missing bars in live_storage parquet, replay mode with incomplete day.

For each failure mode give a concrete reproduction and whether the current design handles it.

Output STRICT JSON only:
{
  "score": <1-10, harshly>,
  "approved": <bool, true only if no realistic unhandled failure>,
  "failure_modes": [{"scenario":"...","reproduction":"...","handled":false,"severity":"high|med|low"}],
  "summary": "<verdict>"
}
""",

    "trading_rules": """You are Judge D — TRADING-RULES COMPLIANCE reviewer.
Verify the design obeys repo guardrails. Cite each violation with the ADR id:
- ADR-001 Timezone (UTC storage, ET sessions)
- ADR-002 Statistical Normalization (metrics as %, not points)
- ADR-017 Zero-Loop (vectorized — but note: this is C#/Pine, not Python; the rule applies to any Python helpers)
- ADR-020 Prop Firm RTH Liquidation (exit by 16:00 ET)
- ADR-021 Unified Prop Firm Sim (only PropFirmSimulator for viability)
- ADR-018 Visual Compliance (if the design touches indicators)
- SecondBrain_Trading.md (ALN sessions, NQ hourly personalities, IB 96% rule)

Also check:
- Does the validation pipeline (§9.1) actually use PropFirmSimulator as source of truth (ADR-021)?
- Are MAE/MFE reported as price % (ADR-002) or raw points?
- Does the design respect the IB 96% rule (IB high/low holds 96% of session) in its stop placement?

Output STRICT JSON only:
{
  "score": <1-10>,
  "approved": <bool>,
  "violations": [{"adr":"ADR-0XX","issue":"...","fix":"..."}],
  "summary": "<verdict>"
}
""",
}


# ---------------------------------------------------------------------------
# Debate rubric — for resolving open questions
# ---------------------------------------------------------------------------
DEBATE_PROMPT_TEMPLATE = """You are a %(role)s debating the resolution of an OPEN QUESTION in a trading-strategy design.

### OPEN QUESTION #%(qid)d
%(question)s

### DESIGN CONTEXT (compact brief)
%(brief)s

### YOUR TASK
Propose a concrete resolution. State:
1. **Answer**: your recommended decision (1-3 sentences).
2. **Rationale**: why, grounded in the design or repo guardrails.
3. **Verification step**: a concrete test/script that would confirm the answer empirically.
4. **Confidence**: low | med | high.

Output STRICT JSON only:
{
  "qid": %(qid)d,
  "answer": "...",
  "rationale": "...",
  "verification": "...",
  "confidence": "low|med|high"
}
"""

MODERATOR_PROMPT = """You are the MODERATOR merging %(n)d judges' proposed resolutions for an open question.
Pick the resolution with the strongest verification step; if they disagree, synthesize a merged answer that
incorporates the strongest rationale and notes the dissent.

Output STRICT JSON only:
{
  "qid": %(qid)d,
  "resolved_answer": "...",
  "verification": "...",
  "dissent": "<short note if judges disagreed, else 'consensus'>",
  "confidence": "low|med|high"
}
"""


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------
@dataclass
class ReviewVerdict:
    judge: str
    model: str
    score: int
    approved: bool
    detail: Dict[str, Any] = field(default_factory=dict)
    raw: Optional[str] = None
    error: Optional[str] = None


@dataclass
class QuestionResolution:
    qid: int
    question: str
    proposals: List[Dict[str, Any]] = field(default_factory=list)
    moderated: Optional[Dict[str, Any]] = None


@dataclass
class ReviewReport:
    doc_path: str
    verdicts: List[ReviewVerdict] = field(default_factory=list)
    open_question_resolutions: List[QuestionResolution] = field(default_factory=list)
    overall_approved: bool = False
    overall_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_path": self.doc_path,
            "overall_approved": self.overall_approved,
            "overall_score": self.overall_score,
            "verdicts": [
                {"judge": v.judge, "model": v.model, "score": v.score,
                 "approved": v.approved, "detail": v.detail}
                for v in self.verdicts
            ],
            "open_questions": [
                {"qid": r.qid, "question": r.question,
                 "resolution": r.moderated}
                for r in self.open_question_resolutions
            ],
        }


# ---------------------------------------------------------------------------
# Doc extraction — pull design-critical sections so we don't blow context
# ---------------------------------------------------------------------------
def extract_review_brief(doc_path: str) -> str:
    """Extract §1, §3, §4.2-4.3, §7, §9 from the design doc (the reviewable core).
    Falls back to the whole doc if section markers aren't found."""
    with open(doc_path, "r", encoding="utf-8") as f:
        full = f.read()

    sections = []
    for marker in ["## 1. Architecture", "## 3. Algorithm Specification",
                   "### 4.2 IntradayStrategyBase", "### 4.3 IBStrategyBase",
                   "## 7. Open Questions", "## 9. Operational Concerns",
                   "## 10. Proposed Enhancements"]:
        idx = full.find(marker)
        if idx != -1:
            # take from this marker to the next ## or ### that starts a sibling section
            rest = full[idx:]
            # find the next top-level section end (## ) after the marker, generous 4000 chars
            end = rest.find("\n## ", 4000)
            sections.append(rest if end == -1 else rest[:end])

    brief = "\n\n...[truncated for review]...\n\n".join(sections) if sections else full
    # cap at ~16k chars to stay in model context windows
    if len(brief) > 16000:
        brief = brief[:16000] + "\n\n...[brief truncated at 16k chars]..."
    return brief


def extract_open_questions(doc_path: str) -> List[Tuple[int, str]]:
    """Parse '## 7. Open Questions' into a list of (qid, question) tuples."""
    with open(doc_path, "r", encoding="utf-8") as f:
        full = f.read()
    start = full.find("## 7. Open Questions")
    if start == -1:
        return []
    end = full.find("\n## ", start + 10)
    block = full[start:end] if end != -1 else full[start:]
    # questions are numbered "1. ", "2. ", ... until the next "---" or "## "
    questions = []
    for m in re.finditer(r"^\s*(\d+)\.\s+\*\*(.+?)\*\*", block, re.MULTILINE):
        qid = int(m.group(1))
        # capture the bold title + the following text until the next numbered item
        line_start = m.start()
        next_q = re.search(r"^\s*\d+\.\s+\*\*", block[m.end():], re.MULTILINE)
        line_end = (m.end() + next_q.start()) if next_q else block.find("\n---", m.end())
        if line_end == -1:
            line_end = len(block)
        questions.append((qid, block[line_start:line_end].strip()))
    return questions


# ---------------------------------------------------------------------------
# Helpers
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


# ---------------------------------------------------------------------------
# Review round
# ---------------------------------------------------------------------------
def _review_one(judge: str, model: str, system: str, brief: str) -> ReviewVerdict:
    user = f"### DESIGN DOC BRIEF TO REVIEW\n{brief}\n\nProduce your review JSON."
    raw = query_ollama(user, model=model, system_prompt=system, temperature=0.1)
    if raw is None:
        return ReviewVerdict(judge, model, 0, False, error="query_failed")
    parsed = _parse_json(raw)
    if not parsed:
        return ReviewVerdict(judge, model, 0, False,
                             detail={"raw": raw[:800]}, raw=raw, error="parse_failed")
    return ReviewVerdict(
        judge=judge, model=model,
        score=int(parsed.get("score", 0) or 0),
        approved=bool(parsed.get("approved", False)),
        detail=parsed, raw=raw,
    )


def run_review(brief: str) -> List[ReviewVerdict]:
    verdicts: List[ReviewVerdict] = []
    with ThreadPoolExecutor(max_workers=len(REVIEW_JUDGES)) as pool:
        futures = {
            pool.submit(_review_one, j, REVIEW_JUDGES[j], REVIEW_RUBRICS[j], brief): j
            for j in REVIEW_JUDGES
        }
        results: Dict[str, ReviewVerdict] = {}
        for fut in as_completed(futures):
            j = futures[fut]
            try:
                results[j] = fut.result()
            except Exception as exc:
                results[j] = ReviewVerdict(j, REVIEW_JUDGES[j], 0, False,
                                           error=f"crash: {exc}")
        for j in REVIEW_JUDGES:
            if j in results:
                verdicts.append(results[j])
    return verdicts


# ---------------------------------------------------------------------------
# Debate round — resolve open questions
# ---------------------------------------------------------------------------
def _debate_one(qid: int, question: str, role: str, brief: str) -> Dict[str, Any]:
    system = f"You are a {role} on a debate panel resolving a design open question."
    # Per-question brief is capped tighter (4k chars) to save tokens — the question + relevant
    # section is what matters, not the whole 16k design brief repeated 24× (6 questions × 4 judges).
    q_brief = brief[:4000]
    user = DEBATE_PROMPT_TEMPLATE % {"role": role, "qid": qid, "question": question, "brief": q_brief}
    model = REVIEW_JUDGES.get(role, "glm-5.2:cloud")
    raw = query_ollama(user, model=model, system_prompt=system, temperature=0.2)
    return _parse_json(raw) or {"qid": qid, "answer": raw or "no response",
                                "confidence": "low", "error": "parse_failed"}


def _moderate(qid: int, proposals: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Moderator only needs the proposals, not the design brief — saves context.
    user = MODERATOR_PROMPT % {"n": len(proposals), "qid": qid} + "\n\n### PROPOSALS\n" + json.dumps(proposals, indent=2)
    raw = query_ollama(user, model=MODERATOR_MODEL, temperature=0.1)
    parsed = _parse_json(raw)
    return parsed or {"qid": qid, "resolved_answer": "moderation failed",
                      "dissent": "parse error", "confidence": "low"}


def run_debate(questions: List[Tuple[int, str]], brief: str) -> List[QuestionResolution]:
    resolutions: List[QuestionResolution] = []
    roles = list(REVIEW_JUDGES.keys())
    for qid, question in questions:
        print(f"\n--- DEBATE OPEN QUESTION #{qid} ---")
        proposals: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=len(roles)) as pool:
            futures = {pool.submit(_debate_one, qid, question, r, brief): r for r in roles}
            for fut in as_completed(futures):
                try:
                    proposals.append(fut.result())
                except Exception as exc:
                    proposals.append({"qid": qid, "answer": f"crash: {exc}",
                                      "confidence": "low"})
        moderated = _moderate(qid, proposals)
        resolutions.append(QuestionResolution(qid, question, proposals, moderated))
        print(f"  Q#{qid} resolved: {moderated.get('resolved_answer','?')[:120]}")
    return resolutions


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------
def run_review_pipeline(doc_path: str, skip_debate: bool = False) -> ReviewReport:
    print("=" * 64)
    print("AGENT-AS-A-JUDGE REVIEW PANEL")
    print("=" * 64)
    print(f"Doc: {doc_path}")
    print(f"Judges: {REVIEW_JUDGES}")
    print(f"Moderator: {MODERATOR_MODEL}")
    print("=" * 64)

    print("\n[1/3] Extracting review brief...")
    brief = extract_review_brief(doc_path)
    print(f"      brief = {len(brief)} chars")

    print("\n[2/3] Running 4 review judges in parallel...")
    verdicts = run_review(brief)
    for v in verdicts:
        print(f"  [{v.judge:14s}] {v.model:24s} score={v.score}/10 approved={v.approved}")

    scores = [v.score for v in verdicts if v.error is None]
    overall = sum(scores) / len(scores) if scores else 0.0
    approved = all(v.approved for v in verdicts if v.error is None) and overall >= 7.0
    print(f"\n  => overall score={overall:.1f}  approved={approved}")

    resolutions: List[QuestionResolution] = []
    if not skip_debate:
        print("\n[3/3] Debating open questions...")
        questions = extract_open_questions(doc_path)
        print(f"      found {len(questions)} open questions")
        if questions:
            resolutions = run_debate(questions, brief)

    return ReviewReport(
        doc_path=doc_path, verdicts=verdicts,
        open_question_resolutions=resolutions,
        overall_approved=approved, overall_score=round(overall, 2),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent-as-a-Judge review panel for design docs.")
    parser.add_argument("--doc", type=str, required=True, help="Path to the design doc (.md).")
    parser.add_argument("--report", type=str, default=None, help="Write full review report JSON to this path.")
    parser.add_argument("--skip-debate", action="store_true", help="Skip the open-question debate round.")
    args = parser.parse_args()

    report = run_review_pipeline(args.doc, skip_debate=args.skip_debate)

    print("\n" + "=" * 64)
    print("REVIEW RESULT")
    print("=" * 64)
    print(f"Overall approved: {report.overall_approved}")
    print(f"Overall score   : {report.overall_score}/10")
    for v in report.verdicts:
        print(f"\n--- {v.judge} ({v.model}) score={v.score}/10 approved={v.approved} ---")
        if v.error:
            print(f"  ERROR: {v.error}")
        else:
            d = v.detail
            for key in ("blocking_flaws", "inconsistencies", "failure_modes", "violations", "suggestions"):
                if key in d and d[key]:
                    print(f"  {key}:")
                    for item in d[key]:
                        if isinstance(item, dict):
                            print(f"    - {item}")
                        else:
                            print(f"    - {item}")
            if "summary" in d:
                print(f"  summary: {d['summary']}")

    if report.open_question_resolutions:
        print("\n" + "=" * 64)
        print("OPEN QUESTION RESOLUTIONS")
        print("=" * 64)
        for r in report.open_question_resolutions:
            print(f"\nQ#{r.qid}: {r.question[:100]}...")
            if r.moderated:
                print(f"  Resolved: {r.moderated.get('resolved_answer','?')}")
                print(f"  Verification: {r.moderated.get('verification','?')}")
                print(f"  Dissent: {r.moderated.get('dissent','?')}")
                print(f"  Confidence: {r.moderated.get('confidence','?')}")

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"\nFull report written to: {args.report}")