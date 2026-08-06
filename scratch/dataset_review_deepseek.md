### 1. Instruction-Tuning Format & Prompt Quality

**Current Structure**
- **Prompt:** A single instruction asking for a “pre-market 08:30 AM EST Wargaming briefing and scenario formulation,” followed by a list of pre-market profiler inputs (Candle Science bias, HTF Weekly EMA excursion, P12 range, 06:00–08:30 bias, NY Handshake, signal confluence, risk sizing).
- **Completion:** A block that contains both the requested pre-market briefing (scenarios A/B/C) **and** an “EOD REENGINEERING POST-MORTEM” with RTH session summary, handshake vector, 3-Hour Line vs Apex score, and the winning scenario.

**Critical Flaw – Task Contamination**
The prompt explicitly asks for a **pre-market** briefing, yet the completion includes **post-hoc EOD data** (open, high, low, close, apex score, winning scenario). This teaches the model that when asked for a pre‑market analysis, it should also generate future RTH outcomes. For a model intended to act as an expert daily profiler and wargamer *before the open*, this is a severe data leakage and will lead to hallucinations of future prices and classifications.

**Format Recommendations**
- **Split into two distinct tasks:**
  - **Task A (Pre‑Market Wargame):** Prompt → only pre‑market inputs; Completion → only the briefing, scenario logic, and sizing recommendation. No RTH data.
  - **Task B (EOD Post‑Mortem / Classification):** Prompt → pre‑market inputs + actual RTH summary; Completion → daily classification (R1/DNP/DWP/R2), overnight profile label, handshake vector, apex score, and a comparison of predicted vs actual scenario.
- **Use a consistent instruction template** (e.g., `### Instruction: ... ### Input: ... ### Response: ...`) to align with Llama‑3, Qwen‑2.5, DeepSeek, and Mistral chat templates.
- **Add system prompts** that define the model’s role: “You are a professional futures market profiler trained on the Pack’s reengineering framework. You only use data available up to 08:30 AM ET.”

**Verdict:** The current prompt/completion structure is **not optimal** and will produce a model that confuses pre‑market forecasting with post‑market reporting.

---

### 2. Rule Completeness & Logic Alignment

The Master Rule Catalog defines a rich set of daily classifications, overnight profiles, sequential streak logic, and P12/pre‑market rejection rules. **None of these are represented in the sample fine‑tuning records.**

| Rule from Catalog | Present in Dataset? | Observation |
|-------------------|---------------------|-------------|
| R1 (4‑hour open print touch) | ❌ | No mention of open print touches, hourly blocks, or mean‑reversion scalps. |
| DNP (5‑hour trend, no pullback) | ❌ | No trend continuation logic or hourly midpoint respect. |
| DWP (morning explosion → afternoon range) | ❌ | No transition to range‑bound strategies after 11:00. |
| R2 (thigh gap reversion) | ❌ | No fade‑to‑open logic. |
| Overnight profiles (LT/LF/ST/SF) | ❌ | Not used as input or output. |
| Sequential streaks (True/False day probabilities) | ❌ | No streak context or probability shifts. |
| P12 early rejection 06:00–07:00 (84.52% HOD locked, etc.) | ❌ | Prompt only gives P12 range and a generic “06:00–08:30 Pre‑Market Bias: BULLISH,” not whether a rejection occurred. |
| Both‑sides sweep 06:00–08:30 (99.26% goalpost chop) | ❌ | Not referenced. |
| Asia broken 06:00–08:30 (94.70% HOD/LOD after 09:00) | ❌ | Not referenced. |
| Daily close matrix & weekly EMA excursion hit rate | ❌ | Weekly EMA excursion is listed but not linked to the 91% hit rate or the 2‑week miss multiplier. |

**The dataset’s scenarios (A/B/C) are generic** – they only reference the P12 midline and a simple bullish/bearish/chop framework. This does not teach the model to apply the specific, high‑probability rules that define the Pack’s edge.

**Verdict:** The dataset is **completely disconnected** from the Master Rule Catalog. It cannot train a model to behave as an expert daily profiler or wargamer under this framework.

---

### 3. Data Quality & Leakage Prevention

**Prompt Leakage Check**
- The prompt contains **only pre‑market data** (Candle Science bias, HTF excursion, P12 range, 06:00–08:30 bias, handshake, confluence, risk sizing).  
- **No RTH open, high, low, close, or any post‑08:30 AM information is present.**  
- ✅ The 08:30 AM cutoff is strictly respected in the prompt.

**Completion Leakage (Critical)**
- The completion includes the full RTH session summary (open, high, low, close) and the winning scenario, which is **future information relative to the prompt’s timestamp**.  
- This is a **direct data leakage** for any model trained to generate completions from these prompts. The model will learn to “predict” the exact RTH values it saw during training, leading to severe overfitting and hallucination when deployed on unseen pre‑market data.

**Verdict:** The prompt is clean, but the **completion leaks future RTH data**, making the dataset unsuitable for training a pre‑market forecasting model. The dataset must be restructured to separate pre‑market and post‑market tasks.

---

### 4. Actionable Recommendations for Dataset Expansion & Fine‑Tuning

To train local Ollama models (or fine‑tune with Unsloth/LoRA) that truly internalize the Pack’s reengineering framework, rebuild the dataset from the ground up:

#### A. Create Two Independent Task Types

1. **Pre‑Market Wargame Task**  
   - **Prompt:** All pre‑market inputs (add P12 rejection flags, overnight profile label, streak context, weekly EMA magnet zone status).  
   - **Completion:**  
     - Predicted daily classification (R1/DNP/DWP/R2) with confidence.  
     - Predicted overnight profile outcome (LT/LF/ST/SF) if applicable.  
     - Scenario planning (A/B/C) tied to specific rule triggers (e.g., “If price touches open print for 4+ hours → R1, turn on mean‑reversion scalps”).  
     - Sizing recommendation.  
     - **No RTH data.**

2. **EOD Post‑Mortem & Classification Task**  
   - **Prompt:** Pre‑market inputs + actual RTH summary (open, high, low, close, hourly block behavior).  
   - **Completion:**  
     - Actual daily classification with justification (e.g., “R1: price touched 09:30 open print at 10:30, 12:00, 14:00, 15:00 – 4 hourly blocks”).  
     - Overnight profile label.  
     - Handshake vector, 3‑Hour Line vs Apex score.  
     - Comparison to pre‑market prediction (if available).  
     - Streak update and next‑day probability shift.

#### B. Enrich Input Features

Add the following to every pre‑market prompt to activate the rule catalog:
- **P12 Early Rejection Status (06:00–07:00):** `P12_High_Rejected: True/False`, `P12_Low_Rejected: True/False` → triggers 84.52%/81.85% HOD/LOD locked rules.
- **Both‑Sides Sweep Flag (06:00–08:30):** `Both_Sides_Swept: True/False` → 99.26% goalpost chop.
- **Asia Broken Flag:** `Asia_Session_Broken: True/False` → 94.70% HOD/LOD after 09:00.
- **Overnight Profile Label:** `Overnight_Profile: LT/LF/ST/SF` (computed from variable vs fixed constant phases).
- **Sequential Streak Context:** `True_Streak: 2`, `False_Streak: 5` → apply streak probability shifts.
- **Weekly EMA Magnet Zone:** `In_Magnet_Zone: True/False` and `Week_Miss_Count: 0/1` → adjust excursion hit rate expectation.

#### C. Generate Synthetic Examples Covering All Rules

Use the rule catalog to programmatically create thousands of labeled examples:
- For each daily classification (R1, DNP, DWP, R2), generate 200–300 examples with varying pre‑market conditions that historically preceded that outcome.
- Include edge cases: streak extremes (True streak=3 → False day), weekly EMA miss sequences, P12 rejection combinations.
- Ensure the dataset reflects the exact frequency distribution (R1 ~39%, DWP ~33%, DNP ~16%, R2 ~12%) to avoid class imbalance.

#### D. Fine‑Tuning Strategy for Local Models

- **Base Models:** Llama‑3.1‑8B, Qwen‑2.5‑7B, Mistral‑7B (good balance of reasoning and speed for Ollama).
- **Method:** QLoRA (4‑bit) via Unsloth for efficient fine‑tuning on a single GPU.
- **Training Data Format:** Use the chat template with a system prompt that encodes the model’s role and the rule catalog’s core logic as a preamble (or embed it in the system message). Example:
  ```
  <|system|>
  You are a futures market profiler trained on the Pack's reengineering framework. 
  Daily classifications: R1 (4+ hourly touches of 09:30 open), DNP (5+ hours trend, no pullback), 
  DWP (morning explosion, afternoon range), R2 (thigh gap reversion to open). 
  Overnight profiles: LT, LF, ST, SF. 
  P12 early rejection 06:00-07:00: 84.5% HOD locked if high rejected, 81.9% LOD locked if low rejected.
  ...
  <|user|>
  {pre_market_inputs}
  <|assistant|>
  {pre_market_briefing}
  ```
- **Evaluation:** Hold out a test set of recent dates and measure classification accuracy, scenario win rate, and adherence to rule logic (e.g., does the model correctly identify R1 conditions when given a touch count?).

#### E. Immediate Fix for Existing Dataset

If you must salvage the current records, **strip the EOD post‑mortem from every completion** and retain only the pre‑market briefing. Then create a separate set of EOD classification examples using the same dates, with the RTH summary moved to the prompt. This will at least remove the leakage and allow the model to learn the briefing task cleanly.

---

**Summary:** The dataset in its current form is not fit for purpose. It leaks future data, ignores the entire rule catalog, and uses a task structure that will confuse the model. A complete rebuild following the above recommendations is necessary to produce a reliable, rule‑faithful profiler that can run locally via Ollama.