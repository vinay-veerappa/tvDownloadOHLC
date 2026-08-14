---
name: agentic-maker-checker-protocol
description: Standard operating architecture for AI development in Antigravity. Enforces Maker-Checker, LLM-as-a-Judge, Multi-Agent Debate, and Self-Correction reflection loops.
applyTo: "**"
---

# Agentic Maker-Checker & Evaluation Protocol

This protocol establishes the mandatory standard operating procedure for code generation, strategy development, and analysis in Antigravity.

---

## When to use

Use when implementing any feature using the maker-checker protocol — two agents (maker + checker) collaborate on implementation with verification gates.

## 🏛️ The 4 Core Architectural Patterns

```
                                  ┌────────────────────────┐
                                  │      USER REQUEST      │
                                  └───────────┬────────────┘
                                              │
                                              ▼
                                 ┌──────────────────────────┐
                                 │   MAKER (Generator)      │
                                 │ (flash_lite / local LLM) │
                                 └────────────┬─────────────┘
                                              │
                                       Draft Output
                                              │
                                              ▼
                                 ┌──────────────────────────┐
                                 │   CHECKER (Evaluator)    │
                                 │  (pro / deepseek-v4-pro) │
                                 └────────────┬─────────────┘
                                              │
                              ┌───────────────┴───────────────┐
                              ▼                               ▼
                      [Pass / Approved]              [Reject / Revisions]
                              │                               │
                              ▼                               ▼
                      Save & Execute                  Refine Loop (Maker)
```

---

### 1. Maker-Checker (Generator-Validator) Pattern
- **The Maker (Generator)**: Uses fast, low-cost models (`flash_lite`, `flash`, or local `qwen2.5-coder:3b`) to rapidly draft code, data parsers, unit tests, or indicator logic.
- **The Checker (Validator)**: Uses high-capability models (`pro` subagent or `deepseek-v4-pro:cloud`) or automated validation tools (`code_guardian`, `pytest`) to strictly check constraints, types, edge cases, and trading rules.

### 2. LLM-as-a-Judge / Evaluator
- Before writing generated code to disk or merging strategy changes, a supervisor evaluator evaluates the draft against 4 mandatory criteria:
  1. **Correctness**: Zero syntax or import errors.
  2. **Edge Cases**: Handles nulls, missing bars, and boundary conditions.
  3. **Trading Rules**: Adheres to `SecondBrain_Trading.md` and statistical normalization (ADR-002).
  4. **Code Quality**: Concise, clean, no over-engineering.

### 3. Multi-Agent Debate / Peer Review
- For complex strategy logic or feature design, spawn 2 concurrent subagents:
  - Subagent A (Proposer): Generates feature proposal / logic draft.
  - Subagent B (Critic): Audits proposal for edge cases and logic gaps.
- The subagents reconcile differences to reach consensus before final implementation.

### 4. Self-Correction / Reflection Loops (Agentic Verification)
- Automated verification loop:
  `Maker Draft` ➔ `Checker Critique` ➔ `Self-Correction Refinement` ➔ `Automated Verification (Pytest / Lint)` ➔ `Final Output`
- Never save unverified draft code directly without passing through the Checker loop.
