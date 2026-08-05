# Chart Agent — Plan & Decisions

**Status:** living doc. Updated: 2026-08-04.
**Owner:** Vinay. This is the master plan for building an AI agent that analyzes charts the way you do.

---

## 1. Goal

An AI agent (Python scripts + LLM) that analyzes charts the way you do — generating a **verifiable verdict** you can act on, where **vision is the verifier, not the generator**. The primary agent is a feature-and-reasoner; vision models (cloud or local) confirm whether the verdict matches the real chart.

**North star ("like me"):** on held-out charts, the reasoner matches your `{bias, primary_pd_array, readiness}` at a target accuracy you set, with a vision check agreeing the verdict matches the chart. The target threshold is an open question (you set it).

---

## 2. Locked architecture decisions

| # | Decision | Rationale |
|---|---|---|
| A | **Reasoner = primary; vision = critic.** | Your edge is in selection/framework, not in the visual look itself. Vision is how you *verify* a generated analysis, not how you generate it. |
| B | **Single knowledge root:** `data/knowledge/` (this repo), raw inputs external (`C:\ICT_Videos\`), one merged LanceDB, controlled by `KB_DATA_DIR`. | You chose "inside this repo", "raw stays external", "one merged DB". Fixes the existing inconsistency (HANDOVER §22–23 put DB in ICT_Videos; KB_BRIDGE §8 moved produced data here — this makes KB_ROOT canonical). |
| C | **Verdict Schema Registry:** one schema per analytical perspective; each becomes a unit `kind` in the merged DB. | You use multiple perspectives (bias, entries, etc.) that need different fields. A registry keeps them composable. |
| D | **Three feedback modes:** correction (field diff), counter-example (full re-author when verdict is fundamentally wrong), vision-assisted diff (VLM proposes the diff, you confirm). | You said "if annotations are completely wrong then I need to provide an example of what I actually mean" — that's the counter-example. |
| E | **Corrections flow immediate + offline:** in-context self-correction within a session AND accumulation in KB/eval for long-term learning. | You chose "Both". |
| F | **No vision fine-tuning at 50–100 samples.** That volume is eval/grading data, not fine-tune data. | Vision fine-tuning wants thousands; 100 image+commentary pairs would lose to good prompting. |
| G | **De-risk first:** thin vertical slice before any consolidation infra. | Don't build KB-root migration before validating the schema and reasoner against real charts. |
| H | **Reuse, don't rebuild:** `chart_extract`, `kb_context.py`, `/ask`, `confluence_engine.py`, backtest engine, `generate_ict_chart*.py`. | These already do most of the job; reinventing would duplicate. |
| I | **NotebookLM = one-time knowledge export** to seed `STYLE.md`, not a runtime dependency. | It's a Google silo; only its text output matters. |
| J | **Reconcile produced LanceDB** from `C:\ICT_Videos\Testing\unified_knowledge.lancedb` → `data/knowledge/`. ICT_Videos reverts to *raw staging only*. | Makes the single root real. |
| K | **Cloud vision + Antigravity/Gemini** are valid model options. The 8GB local GPU is not a constraint on the critical path — cloud models (already used: `glm-5.2:cloud`, `gemma4:31b-cloud`) and Gemini (via Antigravity CLI, strong multimodal) are available. | Removes hardware as a risk; the reasoner is text/feature-driven (runs on any LLM); vision verifier can be cloud Gemini or local. |
| L | **Python scripts do the grunt work.** The reasoner, correction loop, rendering, and ingestion are all scripts. You only do eyeball-verify + corrections. | This is the plan — manual grunt work is eliminated; you add value at the judgment layer. |

---

## 3. Execution plan (value-first, approved)

| Phase | Goal | Gate to proceed |
|---|---|---|
| **0a — Schema refine + thin slice** | Refine `daily_bias_mtf` against ~10–20 real ES/NQ charts. Build a minimal reasoner (features + KB `/ask` + schema) that emits one verdict. You eyeball-verify: does it match your read? If not, is the gap features or reasoning? | Verdict matches your read on enough charts that the schema is validated. |
| **0b — Verdict + correction loop** | Productize verdict emission. Add inline-markdown correction form + counter-example authoring + vision-assisted diff. Annotations flow as `live_read` / `correction` units. | Loop feels natural in Obsidian. |
| **1 — KB root consolidation** (parallel, off critical path) | Migrate produced DB → `data/knowledge/`. Add unit kinds (`daily_bias_mtf`, `live_read`, `correction`, `journal`). Wire `merge_knowledge_base.py`. | One queryable store. |
| **2 — Copilot + autonomous analyst** | Reasoner as interactive copilot + scheduled analyst. Reuse `confluence_engine` + narrative scheduling. Integrate vision verifier (cloud Gemini / local VLM). | Daily briefs you trust enough to read. |
| **3 — Probabilities + validation** | Add `probability` field to schemas (replaces the removed `confidence`). Score daily verdicts through backtest / MFE-MAE for the decision-maker step. | Measured edge on logged verdicts. |
| **Later — Entry / trade schemas** | Separate schema family for trade entries (after `daily_bias_mtf` is locked). | — |

**Sequencing principle:** refine `daily_bias_mtf` on real charts *first*. No infra until the schema and the reasoner's verdict are validated against your actual reads.

---

## 4. Model options (defer choice to Phase 0a testing)

| Role | Local option | Cloud option | Notes |
|---|---|---|---|
| Reasoner (text + features) | Ollama (`gemma4`, `glm-5.2`) | `glm-5.2:cloud`, `gemma4:31b-cloud` | Reasoner is text-driven; any LLM works. Already used in narrative engine. |
| Vision verifier | Ollama vision model (8GB-constrained) | **Gemini via Antigravity CLI** (strong multimodal, large context) | Gemini is the leading candidate for chart verification — large context + strong image reasoning. Antigravity CLI provides access. |
| Fine-tune (if ever needed) | QLoRA on 8GB (3–7B class) | Cloud training | Deferred to a distant Phase 4+; off the table at 50–100 samples. |

---

## 5. Verdict Schema Registry

Each schema entry defines: `verdict_fields`, `verification_criteria`, `correction_format`, `action_mapping`, `open questions`, `iteration history`.

### 5.1 `daily_bias_mtf` v0.4 (LOCKED — pending real-chart refinement)

**Purpose:** verdict for "what is today's directional bias and why", derived from HTF narrative via PD-array confluence. This schema frames *which side to trade and where to seek liquidity* — it is NOT an entry schema.

```yaml
# Context — declared per verdict, never assumed
horizon:              <session | swing | positional>      # dynamic; NOT fixed by instrument
timeframes_used:      [Q, M, W, D, 1H, 15m, 5m]           # configurable; chosen because arrays are in play

# Per-TF reads (HTF -> LTF order) — each TF contributes the arrays it reveals
per_tf:
  - tf: Q
    target_pd_array:     <array name + level price is seeking on this TF>
    array_state:         <unmitigated | mitigated | swept | fresh>
    draw_on_liquidity:   <above X | below Y | none>
    market_structure:    <bullish | bearish | range>
    premium_discount:    <premium | discount | equilibrium>   # within this TF's dealing range
    key_levels:          [50% body, OB, FVG, swing...]
    notes:               <free text>

# CONFLUENCE MAP — the lead structure; multiple arrays held in play simultaneously
pd_arrays:
  - tf: Q
    array: "Quarterly OB"
    level: <price>
    state: <unmitigated | mitigated | swept | fresh>
    alignment: <supportive | pending | neutral>           # "pending" = price not ready yet, NOT a disagreement
    role:    <htf_target | ltf_entry_array | context>

# Primary array is DERIVED — emerges as price approaches; not declared up front
primary_pd_array:        <derived: the array price is currently seeking>
primary_array_tf:        <derived: which TF revealed it>

htf_story:               <the dominant HTF narrative / DOL — "what">
readiness:               <ready | not_ready | forming>
readiness_reason:        <e.g. "LTF hasn't retraced into discount" | "no fractal at the array">

bias:                    <bullish | bearish | neutral | range>
dealing_range:          {high, low, equilibrium}
premium_discount_position: <premium | discount | equilibrium>
liquidity_pools:
  buy_side:              [SSL targets above]
  sell_side:             [BSL targets below]
invalidation:            <level OR condition>             # a real HTF break, not LTF noise
rationale:               <narrative tying arrays together — incl. why pending arrays are timing, not wrong>
```

**Design principles encoded:**
- TFs are a *configurable lens* for finding PD-array confluence, not a fixed ladder.
- `alignment: pending` captures "price not ready yet" — a timing signal, not a disagreement. HTF bias holds; LTF hasn't confirmed.
- `primary_pd_array` is *derived* from the `pd_arrays` list — you hold multiple arrays in play; one emerges as primary as price approaches.
- No `confidence` field. `readiness` covers timing now; a `probability` field arrives in Phase 3 once we figure out how to compute probabilities.
- `horizon` + `timeframes_used` are fully dynamic per verdict — no instrument-fixed defaults (futures day-trading and stocks differ today but could converge).

**Verification criteria (what you / vision check):**
- Does `bias` align with the HTF DOL across the TFs used?
- Are `dealing_range` bounds and `equilibrium` correct against the data?
- Is `premium_discount_position` correct vs current price?
- Do the named `liquidity_pools` really exist as un-swept raids on the chart?
- Is `invalidation` a real level/condition, or hand-waving?
- Does `rationale` match what's on each TF (the per-TF `notes`)?
- Are `pd_arrays` states correct (unmitigated/mitigated/swept/fresh)?

**Correction format (field-level diff):**
```yaml
- field: htf_draw_on_liquidity
  was: "above PDH"
  should_be: "weekly high, not PDH"
  reason: "PDH already swept; the live HTF draw is the weekly high"
```
If the verdict is fundamentally wrong → you author a full `counter_example` verdict (gold-standard `live_read`); both the rejected verdict and the counter-example are stored.

**Action mapping (how this verdict frames the day — NOT an entry):**
- `bullish` + `discount` → long-biased session; seek sell-side liquidity arrays + discount OB/FVG
- `bearish` + `premium` → short-biased session; seek buy-side liquidity arrays + premium OB/FVG
- `neutral` / `range` → no directional bias; trade range extremes (PDH/PDL reactions), no DOL chase
- `readiness: not_ready` → bias holds; wait for LTF confirmation (don't flip bias)

This mapping is deliberately *not* an entry rule — it sets the day's posture. Entries are a separate schema family.

**Iteration history:**
- v0.1: Fixed TF ladder (M→W→D→1H→15m), single bias label, confidence field.
- v0.2: Made TF set configurable; introduced PD-array-driven structure (`target_pd_array`, `primary_pd_array`). User: "it has more to do with what PD array is available that price is looking for."
- v0.3: Added confluence map (`pd_arrays` with alignment/role); added `readiness` separate from bias; KB confirmed "conflict = not ready, not invalidated." Changed `alignment: contradicting` to `pending`.
- v0.4 (locked): Removed `confidence` (probability comes in Phase 3). Made `primary_pd_array` derived (not declared). `horizon`/`timeframes_used` fully dynamic. Multiple arrays held in play simultaneously.

---

## 6. Reuse map (what exists vs what we build)

| Capability | Existing module | Action |
|---|---|---|
| Text concept knowledge (RAG) | `kb_context.py`, `/ask` API (port 8900) | Reuse — reasoner queries it |
| Chart image → VLM structured read | `chart_extract.py` (producer) | Reuse/extend for vision verifier + annotation ingest |
| ICT concept vocabulary | `ict_chart_prompts.py` (producer) | Reuse — seeds style spec |
| Chart rendering (dark theme, ICT overlays) | `generate_ict_chart*.py` | Reuse — productize into `gen_charts.py` for thin slice |
| Confluence detection | `confluence_engine.py` (6 providers) | Reuse — feeds reasoner context |
| Backtest / MFE-MAE scoring | `scripts/trading_framework/` | Reuse — Phase 3 validation |
| Narrative scheduling | `trader_narrative.py` scheduling | Reuse — Phase 2 autonomous analyst |
| Data loading (live + historical) | `fused_data_loader.py`, live storage parquet | Reuse — reasoner inputs |
| KB merge | `merge_knowledge_base.py` | Reuse — Phase 1 consolidation |
| **New: reasoner script** | — | Build — `scripts/vision/reasoner.py` (Phase 0a) |
| **New: correction loop** | — | Build — `scripts/vision/correct.py` (Phase 0b) |
| **New: verdict schema registry** | — | Build — this doc + future `docs/vision/SCHEMA_REGISTRY.md` |
| **New: chart renderer (productized)** | extends `generate_ict_chart*.py` | Build — `scripts/vision/gen_charts.py` (Phase 0a) |

---

## 7. Open questions

1. **"Like me" threshold** — the X% accuracy target on held-out charts. You set it.
2. **Probability computation** — how to derive the `probability` field (Phase 3). Likely from historical hit-rates of similar confluence patterns (your profiler/NQStats already compute these).
3. **Vision model choice** — Gemini (cloud, via Antigravity CLI) vs local Ollama vision. Test both in Phase 0a.
4. **Schema doc split** — whether `daily_bias_mtf` moves to its own `docs/vision/SCHEMA_REGISTRY.md` once entry schemas arrive.
5. **Feature gaps** — whether the reasoner's verdict quality is limited by missing computed features (discovered in Phase 0a). If so, the fix is *more features*, not vision.
6. **Antigravity CLI integration** — how to call Gemini via Antigravity for vision verification (needs investigation in Phase 0a/0b).

---

## 8. Iteration log

| Date | Change |
|---|---|
| 2026-08-04 | Doc created. v0.4 schema locked. 12 architecture decisions locked. Value-first sequencing approved (0a first). Cloud vision + Antigravity/Gemini added as model options. Python-scripts-do-grunt-work principle added as decision L. |

---

## 9. References

- **KB bridge:** `docs/architecture/KB_BRIDGE.md` — how this repo consumes the KB API (port 8900)
- **Producer handover (canonical, do not edit here):** `C:\Users\vinay\video2pdf\knowledge_ingest\HANDOVER.md` — §22 cross-repo data flow, §20 RAG layer
- **Narrative engine design:** `docs/architecture/NARRATIVE_ENGINE_CURRENT_DESIGN.md`
- **Trading domain rules:** `docs/SecondBrain_Trading.md`
- **ICT concepts KB:** `docs/trading/ICT_CONCEPTS_KB.md`
- **ICT daily bias models (repo):** `docs/library/ict/ICT_DAILY_BIAS_MODELS.md`
- **Reuse modules:** see §6 above