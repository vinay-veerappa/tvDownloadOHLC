# Fine-Tuning Dataset & Rule Catalog Audit Report

**Scope:** `docs/profiler/master_rule_catalog.json` + sample records from `data/wargaming_fine_tuning_dataset.jsonl`  
**Objective:** Evaluate suitability for supervised fine-tuning (SFT) of open-weight LLMs (Llama‑3, Qwen‑2.5, DeepSeek R1, Mistral) to act as an expert pre-market daily profiler / wargamer.  
**Auditor stance:** I assess dataset structure, rule fidelity, and leakage risk. I do **not** validate the profitability or market accuracy of the underlying trading rules.

---

## 1. Executive Summary

| Dimension | Verdict | Severity |
|---|---|---|
| **08:30 prompt leakage** | ✅ Clean — no future RTH data in prompt | Low |
| **Instruction-tuning format** | ⚠️ Sub-optimal — completion mixes oracle EOD labels with 08:30 briefing | **High** |
| **Rule completeness** | ❌ Incomplete — core R1/DNP/DWP/R2 logic is barely represented | **High** |
| **Overnight / P12 / streak rules** | ⚠️ Partial — P12 range present, but 06:00‑07:00 rejection stats, overnight profiles, and streak matrices absent | Medium |
| **Usability for Ollama/Unsloth/LoRA** | ⚠️ Usable after format conversion and feature enrichment | Medium |

**Bottom line:** The dataset is leak-free at the prompt level, but the current completion design trains the model to hallucinate post-market outcomes at 08:30. The four daily classifications (R1, DNP, DWP, R2) and several named rules from the catalog are not encoded in the features or the target text. Without restructuring, fine-tuning will produce a model that generates plausible-sounding but mechanically unreliable “winning scenario” labels.

---

## 2. Instruction-Tuning Format & Prompt Quality

### 2.1 What works
- **Structured, repeatable prompt template.** Each record uses a fixed bullet list: Candle Science Bias, HTF Weekly EMA excursion, P12 range, pre-market bias, handshake, confluence, sizing. Repetition is good for SFT — it teaches the model to expect the same fields and respond in a templated way.
- **Strict pre-market cutoff.** All inputs are observables available by 08:30 ET.
- **Role framing is explicit** (“Perform a pre-market 08:30 AM EST Wargaming briefing…”).

### 2.2 Critical format problem: Oracle leakage into the completion
The completion contains an **EOD Reengineering Post-Mortem** with:
- Actual RTH Open/High/Low/Close timestamps.
- A “🏆 WINNING SCENARIO” label derived from future price action.

**Why this is dangerous for SFT:**
- At inference time (08:30) the model will be asked to produce a briefing and will be rewarded during training for outputting future facts it cannot know.
- This encourages the model to memorize spurious correlations between pre-market features and the EOD label, then confidently emit false post-market details when deployed.
- If you serve this through Ollama at 08:30, the model will hallucinate an afternoon HOD/LOD timestamp and a “winning scenario” because that is exactly what the completion taught it to do.

**Recommended split:**
| Purpose | What the prompt asks for | What the completion contains |
|---|---|---|
| **Production inference / causal wargaming** | 08:30 briefing + 3 scenarios + risk plan | Only the briefing, scenarios, and reasoning |
| **Post-mortem / DPO / reward model** | Same prompt + EOD block as optional context | Actual classification (R1/DNP/DWP/R2), winning scenario, and deviation analysis |

**Better completion target (causal only):**
```
=== PRE-MARKET WARGAME BRIEFING (08:30 AM EST) ===
Confluence Assessment: ALIGNED (High Conviction)
Recommended Sizing: 0 contracts ($225.0 risk limit)

KEY RULES IN PLAY:
- HTF excursion is +4.81% (outside 2-3% magnet zone); trend continuation 
  models are preferred over pure mean reversion.
- 06:00-08:30 pre-market is BULLISH and in agreement with NY handshake; 
  no early False-day reversal flag is active.
- P12 Midline at 29066.50 is the primary bull/bear pivot.

SCENARIOS FOR TODAY'S SESSION:
  ➤ Scenario A (Bullish Continuation): Price holds above P12 Mid (29066.50) 
    and the 09:30 open print; target P12 High (29335.75) / structural 
    continuation toward the weekly EMA excursion.
  ➤ Scenario B (Bearish Reversion): Price accepts below P12 Mid 
    (29066.50) and breaks the first hourly low; target P12 Low (28797.25).
  ➤ Scenario C (R1 / Goalpost Chop): Price oscillates across P12 Mid 
    and touches/tests the 09:30 open print for 4+ hourly blocks; 
    mean-reversion scalps only.

INVALIDATION CHECKPOINTS:
- If the 09:30 open print is touched in ≥4 distinct hourly blocks, 
  escalate Scenario C to primary.
- If price trends away from 09:30 for ≥5 hourly blocks without breaking 
  preceding hourly highs/lows, escalate Scenario A/B (DNP) to primary.
```

### 2.3 Chat-template compliance
The raw `{prompt, completion}` pair is legacy GPT-3 / completion-style JSON. For modern instruction-tuned models (Llama‑3, Qwen‑2.5, Mistral, DeepSeek R1) you should convert to **chatml / chat-template format** so that LoRA adapters learn the correct turn boundaries.

Example target structure:
```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are an expert futures market profiler and wargamer. ..."
    },
    {
      "role": "user",
      "content": "PRE-MARKET PROFILER INPUTS:\n- Ticker: NQ1 ...\n..."
    },
    {
      "role": "assistant",
      "content": "=== PRE-MARKET WARGAME BRIEFING ... === ..."
    }
  ],
  "metadata": {
    "eod_class": "DWP",
    "winning_scenario": "A",
    "rth_high": 29691.25,
    "rth_low": 29303.75
  }
}
```

**System prompt should be static and include the rule catalog in a compressed, token-efficient form.** This is far more effective than hoping the model remembers the rules from sparse examples.

---

## 3. Rule Completeness & Logic Alignment

### 3.1 Daily classifications (R1 / DNP / DWP / R2)

| Rule | Catalog definition | Present in sample? | Gap |
|---|---|---|---|
| **R1** | Price touches/tests 09:30 open print for ≥4 hourly RTH blocks; both breakouts fail; mean-reversion scalps. | ❌ Weakly present only as generic “Goalpost Chop / R1” in Scenario C. No 09:30 open print in prompt; no hourly-block count. | **High** |
| **DNP** | Price moves away from 09:30 open for ≥5 hourly blocks; preceding hourly highs/lows not broken; hourly 50% midpoints respected; trend continuation. | ❌ Not represented. | **High** |
| **DWP** | Explosive morning move (first 45–90 min), never returns to open, then 11:00–14:00 range; momentum then range-bound. | ❌ Not represented. | **High** |
| **R2** | Explosive trend away from open, then collapse after 11:30 and full reversion to 09:30 open; “thigh gap.” | ⚠️ “Bearish Reversion” is a crude proxy but omits the 11:30 timing, full reversion to open, and thigh-gap visual. | Medium |

**Observation:** The current “Scenario A / B / C” framework is **too coarse** to teach the four daily modes. It conflates R1 with “goalpost chop” and R2 with “bearish reversion.” The model will not learn the precise hourly-block criteria that define each classification.

**Recommendation:**
1. Add a `daily_classification` field to every record (R1, DNP, DWP, R2).
2. Include 09:30 open print in the prompt as a feature.
3. In the completion, explicitly map scenarios to the catalog definitions, e.g.:
   - Scenario A → DNP or DWP continuation
   - Scenario B → R2 / bearish reversion
   - Scenario C → R1
4. Add rule-specific trigger counts: “Hourly block count since open: N / 4 for R1, N / 5 for DNP.”

### 3.2 Overnight profiles (LT / LF / ST / SF)

The catalog defines four overnight structures based on Fixed Constant High/Low and hourly 50% midpoint behavior.  
**Status:** Not present in the prompt or completion.  
**Impact:** Missing a major pre-market filter that would affect scenario probability.  
**Fix:** Add the overnight profile label and the Fixed Constant High/Low to the prompt.

### 3.3 P12 and pre-market rules

| Rule | Catalog definition | Present in sample? | Gap |
|---|---|---|---|
| P12 range 18:00–06:00 | High, Low, Midline | ✅ Present | — |
| 06:00–07:00 early rejection | 84.52% HOD locked, 81.85% LOD locked, 49.52% one extreme set | ❌ Not represented | **High** |
| Both-sides sweep 06:00–08:30 | 99.26% probability HOD/LOD form after 08:30 | ⚠️ Handled only as generic “Goalpost Chop / R1” | Medium |
| Asia broken 06:00–08:30 | 94.70% probability both extremes after 09:00 | ❌ Not represented | Medium |

**Recommendation:** Add boolean or probability features to the prompt:
```
- 06:00-07:00 Rejection Signal: HIGH_REJECTED (HOD locked in P12, p=0.845)
- Pre-market sweep status: NO_BOTH_SIDES_SWEEP
- Asia session status: INTACT (no Asian range break)
```

### 3.4 Sequential streaks / close matrix / weekly EMA

| Rule | Present? | Gap |
|---|---|---|
| True streak max 3 → False Day on D3/D4 | ❌ | High |
| False streak max 7 → True Day on D7 | ❌ | High |
| Daily close matrix (Up→Up 0.70, etc.) | ❌ | Medium |
| Weekly EMA excursion hit rate / miss multiplier | ⚠️ Partially present as HTF excursion value | Medium |

**Recommendation:** Add a short “Sequential Context” block:
```
- Prior day classification: DWP
- Prior day close direction: UP
- True/False streak count: 1 True day
- Weekly EMA excursion status: Week 1 hit / Week 1 miss (carryover)
```

### 3.5 “NY Opening Handshake”

The catalog you provided does **not** define this term, yet the prompt includes `08:30 Pre-Market Handshake: AGREEMENT` and the completion includes `Actual NY Handshake Vector`.  
**Issue:** If the handshake is a derived signal (e.g., agreement between overnight profile and Candle Science bias), it must be documented in the catalog or it becomes an un-auditable black box.  
**Fix:** Add a `ny_opening_handshake` section to the catalog documenting:
- What two (or more) inputs are being compared.
- What “AGREEMENT,” “CONFLICTED,” and “INVERSION” mean mechanically.
- How it differs from the generic `Signal Confluence Status`.

---

## 4. Data Quality & Leakage Prevention

### 4.1 Prompt leakage check ✅
I reviewed the three sample prompts. They contain:
- Ticker/date
- Bias probabilities
- Weekly EMA excursion percentage
- P12 range (18:00–06:00 ET)
- 06:00–08:30 pre-market bias
- 08:30 handshake vector
- Confluence status
- Capital risk sizing

None of these require data from after 08:30 ET. **The 08:30 cutoff is 100% strict in the prompt field.** No RTH Open, High, Low, Close, intraday timestamps, or afternoon labels appear.

### 4.2 Completion leakage — acceptable only if used correctly
The completion field contains EOD data. This is **not** leakage in the supervised-learning sense because the label is allowed to contain future information. However, it is a **deployment risk** if the same completion is expected at 08:30.

**Verification recommendation:** Add an automated test:
```python
def test_prompt_no_future_data(prompt: str):
    forbidden = ["RTH", "09:30", "Open=", "High=", "Low=", "Close=", "16:00", "EOD"]
    for token in forbidden:
        assert token not in prompt, f"Future leak: {token}"
```

### 4.3 Label consistency check ⚠️
Record `NQ1_2026-05-26` has `Candle Science Bias: BEARISH` and `Signal Confluence Status: CONFLICTED`, yet the “winning scenario” is Scenario A (Bullish Continuation). This is not necessarily an error (a bearish pre-market bias can be overrun by a bullish RTH), but without the 09:30 open print, hourly structure, and overnight profile in the prompt, the model has no feature basis to learn why. Ensure the metadata captures enough context so that the “winning” label is explicable from the 08:30 inputs plus the catalog rules.

---

## 5. Actionable Recommendations

### 5.1 Immediate dataset restructuring (do this first)
1. **Split into two datasets:**
   - `wargaming_sft.jsonl` — prompt asks for 08:30 briefing; completion contains only briefing + reasoning.
   - `wargaming_postmortem.jsonl` — same prompt; completion contains EOD facts + classification + winning scenario.
2. **Convert to chat format** with a system prompt that embeds the catalog rules in compressed form.
3. **Move oracle labels to `metadata`** rather than the assistant completion text.
4. **Add a `daily_classification` label** (R1, DNP, DWP, R2) to every record.
5. **Include 09:30 open print** and hourly structure hints in the prompt (still pre-market if previous day’s close / globex-derived open is used correctly — clarify source).

### 5.2 Feature enrichment plan
Add these blocks to every prompt:

```
=== SEQUENTIAL / STREAK CONTEXT ===
- Prior RTH close direction: UP / DOWN
- Current True/False streak length: N
- Prior day classification: R1/DNP/DWP/R2
- Weekly EMA excursion carryover status: HIT / MISS

=== OVERNIGHT PROFILE (Fixed Constant Range) ===
- Fixed Constant High: X
- Fixed Constant Low: Y
- Overnight profile: LT / LF / ST / SF
- 06:00-07:00 rejection signal: HOD_LOCKED / LOD_LOCKED / MID_REJECTED / NONE

=== P12 / PRE-MARKET STRUCTURE ===
- P12 High / Low / Midline
- 06:00-08:30 sweep status: BOTH_SIDES_SWEEP / ONE_SIDE_SWEEP / NO_SWEEP
- Asia broken flag: TRUE / FALSE
```

### 5.3 Completion quality improvements
- Force a **Chain-of-Thought** section before scenarios, e.g.:
  ```
  REASONING:
  1. HTF excursion is X%, so trend continuation bias is [high/low].
  2. Overnight profile is LT, so ...
  3. 06:00-07:00 HOD rejection locks one daily extreme, reducing ...
  ```
- Add **invalidation checkpoints** tied to the hourly-block rules.
- Add a **confidence score** or **primary / secondary / tertiary scenario ranking** rather than a single “winning” oracle.

### 5.4 Negative / counterfactual examples
Add records where:
- A high-confluence setup fails (R2 reversal).
- A conflicted setup produces an R1 chop day.
- A True streak reaches 3 and a False day occurs.
- A false streak reaches 6–7 and a True day occurs.
This prevents the model from overfitting to the most common bullish-continuation examples.

### 5.5 Local fine-tuning recipe (Ollama / Unsloth / LoRA)

**Model choice:**
- Start with **Qwen2.5‑7B/14B-Instruct** or **Llama‑3.1‑8B-Instruct** for local Ollama deployment.
- Use **DeepSeek R1 Distill** only if you want explicit CoT reasoning; otherwise the distilled Qwen/Llama variants are cheaper to serve.

**Hardware / framework:**
- **Unsloth** with `fast_language_model` and 4-bit NF4 QLoRA.
- Target modules: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`.
- `r=32` or `64`, `alpha=64` or `128`, `dropout=0.05`.
- Use **gradient checkpointing** and **max_seq_length=4096**.

**Training mix to avoid catastrophic forgetting:**
- 70% wargaming SFT data
- 20% general financial instruction following
- 10% generic chat / safety data

**Chat template:**
Use the model’s native chat template (Unsloth applies it automatically). Example system prompt:
```
You are an expert futures market profiler and wargamer. You have access
to the following rule catalog (memorized):
- R1: >=4 hourly blocks touching the 09:30 open print ...
- DNP: >=5 hourly blocks away from open without breaking preceding H/L ...
- DWP: explosive morning move, then 11:00-14:00 range ...
- R2: trend away from open, collapse after 11:30, reverts to open ...
- P12 early rejection: 06:00-07:00 rejection locks HOD/LOD with ...
Given only 08:30 AM EST pre-market inputs, produce a briefing with
ranked scenarios, key pivots, and invalidation checkpoints. Do NOT
invent post-market outcomes.
```

**Evaluation for Ollama deployment:**
- Export to **GGUF** (Q4_K_M or Q5_K_M) for Ollama.
- Hold out a time-based test set (e.g., last 60 days).
- Run rule-based accuracy checks:
  - Does the model name the correct `daily_classification`?
  - Does it reference the correct 09:30 open touch count for R1?
  - Does it refuse to output future HOD/LOD timestamps at 08:30?

### 5.6 Advanced: DPO / reward modeling
Once you have the causal SFT model, use the post-mortem dataset for **Direct Preference Optimization**:
- **Preferred completion:** The scenario that actually won.
- **Rejected completion:** A plausible but wrong scenario.
This is far better than baking oracle EOD labels into the SFT completion text.

---

## 6. Final Verdict & Priority Matrix

| Priority | Action | Effort | Impact |
|---|---|---|---|
| **P0** | Remove EOD oracle from SFT completion; split causal and post-mortem datasets | Low | **Critical** |
| **P0** | Add 09:30 open print + hourly-block rule criteria to prompt/completion | Low | **Critical** |
| **P1** | Add `daily_classification` labels and map scenarios to R1/DNP/DWP/R2 | Medium | High |
| **P1** | Add overnight profiles, 06:00–07:00 rejection stats, streak context | Medium | High |
| **P2** | Convert to chat-template format with embedded system catalog | Low | Medium |
| **P2** | Enrich with negative/counterfactual examples | Medium | Medium |
| **P3** | Train QLoRA adapter and evaluate on held-out time slice | High | High |
| **P3** | Build DPO/reward dataset from post-mortem labels | High | Medium |

**Immediate go/no-go recommendation:**  
Do not fine-tune on the current `prompt/completion` pairs as-is. The format trains the model to hallucinate future market outcomes. After restructuring the completion to be purely causal and adding the missing rule-derived features, the dataset will be a strong foundation for a local Ollama/Unsloth deployment.