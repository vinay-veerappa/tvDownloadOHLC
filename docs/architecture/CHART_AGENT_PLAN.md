# Chart Agent — Master Plan (v2.0)

**Status:** Living doc. Updated: 2026-08-05.
**Owner:** Vinay. Master plan for building an AI agent that analyzes charts the way you do.

---

## 1. Goal

An AI agent (Python scripts + LLM) that analyzes charts the way you do — generating a **verifiable verdict** you can act on, where **vision is the verifier, not the generator**. The primary agent is a feature-and-reasoner; vision models (Gemini via SDK) confirm whether the verdict matches the real chart.

**North star ("like me"):** on held-out charts, the reasoner matches your `{bias, primary_pd_array, readiness}` at a target accuracy you set, with a vision check agreeing the verdict matches the chart.

---

## 2. Locked architecture decisions (14)

| # | Decision | Rationale |
|---|---|---|
| A | **Reasoner = primary; vision = critic.** | Your edge is in selection/framework, not visual. Vision verifies, doesn't generate. |
| B | **Single knowledge root:** `data/knowledge/`, raw external, one merged DB, `KB_DATA_DIR`. | One source of truth. |
| C | **Verdict Schema Registry:** one schema per perspective; each a unit `kind`. | Different perspectives need different fields. |
| D | **Three feedback modes:** correction (diff), counter-example (full re-author), vision-assisted diff. | "If wrong, provide an example of what I actually mean." |
| E | **Corrections flow immediate + offline.** | In-session self-correct AND accumulate in KB/eval. |
| F | **No vision fine-tuning at 50-100 samples.** | That volume is eval data, not fine-tune data. |
| G | **De-risk first:** thin slice before infra. | Validate schema + reasoner before consolidation. |
| H | **Reuse, don't rebuild:** chart_extract, kb_context.py, /ask, confluence_engine, backtest engine, generate_ict_chart*.py, session_ranges.py. | Most infrastructure exists. |
| I | **NotebookLM = one-time export** to seed style spec, not runtime. | Google silo; only text output matters. |
| J | **Reconcile produced LanceDB** → `data/knowledge/`. ICT_Videos = raw staging. | Single root. |
| K | **Cloud vision + agy/Gemini** are valid model options. 8GB local GPU not on critical path. | Hardware not a constraint. |
| L | **Python scripts do grunt work.** You only do eyeball-verify + corrections. | Manual grunt work eliminated. |
| M | **Bias and execution are SEPARATE prompts.** The 7 TCM Rules are entry/execution rules, NOT bias rules. | Category error to feed entry rules to a bias reasoner. |
| N | **Vision analyses are BLIND.** No verdict context fed to vision — independent reads, then compare. | Anchoring bias prevention. |

---

## 3. Critical review findings (3-model consensus)

Three LLMs (GLM-5.2, Gemma4-31b, DeepSeek-v4-pro) critically reviewed the plan. Consensus issues:

1. **7 Rules are entry rules, not bias rules** → separate bias prompt from execution prompt (Decision M)
2. **Dealing range ≠ PDH-PDL** → TBP defines it as "any price swing that takes liquidity from both sides." Compute structural swing, not calendar range. Feed both but label correctly.
3. **Submission range (2PM-6:15PM) was missing from implementation** → add it
4. **FVG/OB data dump causes context degradation** → geometric filter: only N nearest arrays above/below price + most recent HTF arrays
5. **Vision verification has anchoring bias** → blind independent reads, then compare (Decision N)
6. **Derived data must be fixed FIRST** → before reasoner rewrite
7. **Midnight open is questionable for futures** → keep but document limited relevance; use 00:00 ET price explicitly
8. **DST timezone risk** → use `zoneinfo("America/New_York")` everywhere

Additional findings:
- Missing DOL as singular objective (where is price going?)
- Missing macro awareness (which intraday macro is active?)
- MSS vs BOS distinction needed
- Mitigation criteria undefined for "unmitigated" FVGs/OBs
- Data freshness check needed before feature computation

---

## 4. ICT/TCM Reference (from TBP + KB)

### Session times (ICT standard killzones, ET)
| Session | Start | End | Mid at |
|---|---|---|---|
| Asia | 20:00 | 00:00 | 00:00 |
| London | 02:00 | 05:00 | 05:00 |
| ONS | 04:00 | 08:15 | 08:15 |
| NY AM | 09:30 | 12:00 | 12:00 |
| NY PM | 13:30 | 16:00 | 16:00 |
| Submission | 14:00 | 18:15 | — |
| P12 (overnight) | 18:00 | 06:00 | 06:00 |

### Intraday Settlement Macros (from TBP)
| Macro | Time (ET) | Purpose |
|---|---|---|
| Price Discovery | 04:00 - 08:15 | ONS creation, establishing H/L for London/NY |
| Liquidity Hunt | 08:15 - 09:30 | Targeting ONS H/L to build positions |
| Offset | 09:45 - 10:00 | Position settlements, sharp reactions |
| Rebalance | 11:00 - 13:30 | Revisiting inefficient deliveries (FVG, gaps) |
| Lunch | 12:45 - 13:45 | Sweeping pending liquidity for PM session |
| Settlement Check | 13:45 - 14:45/15:15 | Order batching/matching. No new H/L after 14:45 typically |

### TCM 7 Rules (entry/execution — NOT for bias prompt)
| Rule | Summary |
|---|---|
| Rule 1 | OB must produce a swing that trades through a high (choose the displacement candle) |
| Rule 2 | Buy after a DOWN candle returns to a bullish OB (patience — second entry creates speed) |
| Rule 3 | Entry confluences: inefficiency in OB → enter at inefficiency; large body → 50% of body; small body → open and high/low |
| Rule 4 | If you miss the trade: price breaks low, creates up candle, next candle trades to FVG above and expands lower |
| Rule 5 | Timeframe filter: London → m15 for structure; NY → m5 for structure |
| Rule 6 | Liquidity at swing points: down candle wick high = skeptical stop; up candle wick low = skeptical; inside FVG = anticipate raid |
| Rule 7 | Order of Delivery: SSL Run → FVG tag → Short term low → CSD → high probability shorts |

### Order Pairing Hierarchy
- **Bullish:** Inception SSL → Discount Arrays → Equilibrium → Old highs + FVG/EO → Terminus - BSL
- **Bearish:** Inception BSL → Premium Arrays → Equilibrium → Old lows + FVG/EO → Terminus - SSL

### TCM Timeframes
| TF | Purpose |
|---|---|
| Daily | Orderflow, DOL, DO |
| H1 | Refined TRUE DAY liquidity levels, refined market structure |
| M5 | Anticipating ONS Profiles |
| M1 | Anticipating Timed Delivery |

### ONS Profiles
| Profile | Description |
|---|---|
| 1 & 2 | Support near the low of the session (OB at the low) |
| 3 | Offset Macro (morning push up, then drop) |
| 4 | Seek and Destroy (8:15 fails to get out of range — wild swings) |
| 5 | PM session — retracement up into 11:00, then pushing down into PM |

### Dealing Range (TBP definition)
- "Any price swing that takes liquidity from both sides of the market"
- One part should be inside a liquidity pool in any timeframe
- Sequence: Highest Up-candle → First untapped low to the left → Willingness to trade through → Retracement → Expand

### Submission Range (user-confirmed)
- **Time window:** 14:00 - 18:15 ET (2:00 PM to 6:15 PM)
- **OHLC** of this range
- **50%** = (H + L) / 2
- Each level (O, H, L, C, 50%) is a **target**

### Kish chart setup process
1. Daily → dealing range, EO, drawn liquidity, 50% level
2. Check daily candle closure (breakaway gap?)
3. Failure swings below the candle that left the dealing range
4. H1 → refine bias, 50% level, overlapping wicks
5. M5 → CSD, FVGs, OBs for entry
6. Supporting confluence: DOL, order flow, key levels

---

## 5. Features for the Bias Reasoner

### Remove
- IPDA-20/60 positions (user doesn't use)
- Pre-computed 4-model bias (what we're replacing)
- Killzone pivots (defer)
- 7 TCM Rules from bias prompt (they're entry rules — Decision M)

### HTF Levels + Mids
| Level | Computation |
|---|---|
| PDH | Prior day high |
| PDL | Prior day low |
| PDC | Prior day close |
| PDO | Prior day open |
| PDM | (PDH + PDL) / 2 |
| PWH | Prior week high |
| PWL | Prior week low |
| PWM | (PWH + PWL) / 2 |
| PMH | Prior month high (resample 1m) |
| PML | Prior month low (resample 1m) |
| PMM | (PMH + PML) / 2 |
| Midnight Open | 00:00 ET price (document limited futures relevance) |

### Session Ranges + Mids (ICT killzones, computed from 1m with DST-aware tz)
| Session | Time (ET) | H, L, Mid, Range |
|---|---|---|
| Asia | 20:00-00:00 | ✅ ADD |
| London | 02:00-05:00 | ✅ ADD |
| NY AM | 09:30-12:00 | ✅ ADD |
| NY PM | 13:30-16:00 | ✅ ADD |

### ONS Range
| Level | Time (ET) |
|---|---|
| ONS H/L/Mid | 04:00-08:15 |
| ONS efficiency | efficient (both sides) / inefficient (one-sided) |

### P12 Range
| Level | Time (ET) |
|---|---|
| P12 H/L/Mid | 18:00-06:00 |
| NY P12 H/L/Mid | Prev day 06:00-17:59 |

### Submission Range (user-confirmed)
| Level | Time (ET) |
|---|---|
| Open | 14:00 price |
| High | max of 14:00-18:15 |
| Low | min of 14:00-18:15 |
| Close | 18:15 price |
| 50% | (H + L) / 2 |

### Prev PM 50%
| Level | Computation |
|---|---|
| Prev PM 50% | (Prev NY PM High + Prev NY PM Low) / 2 |

### Dealing Range (structural, NOT PDH-PDL)
| Level | Computation |
|---|---|
| Dealing Range High | Most recent swing high that swept both sides |
| Dealing Range Low | Most recent swing low that swept both sides |
| Dealing Range 50% | (DR High + DR Low) / 2 |
| Note | Keep PDH/PDL/PDM separately — they're calendar levels, not dealing range |

### PD Arrays (geometrically filtered — NOT raw dump)
| Array | Filter |
|---|---|
| FVGs | N nearest unmitigated above + below current price; most recent HTF (4H/1H) FVGs |
| OBs | Same geometric filter |
| Liquidity levels | EQH, EQL, BSL, SSL — nearest above/below price |
| Market structure | Recent BOS/MSS/CISD — distinguish MSS (change in state) from BOS (continuation) |
| DOL | Singular draw on liquidity objective — "where is price going?" |

### HTF Structure
| Data | Source |
|---|---|
| 4H OHLC | Resample 1m |
| 1H OHLC | Resample 1m |

### Current State
| Data | Computation |
|---|---|
| Current price | Last 1m close |
| Premium/discount | Relative to dealing range (not PDH-PDL) |
| BSL/SSL targets | Nearest unswept levels above/below |
| Active macro | Which intraday settlement macro is currently active |

### KB Context (session-aware)
Session-specific ICT concepts injected based on current/next session.

---

## 6. Execution phases (value-first, data-first)

| Phase | Goal | Gate |
|---|---|---|
| **0 — KB update** | Ingest TBP markdown into KB. Correct submission range definition. Add 7 Rules, ONS Profiles, macros, Order Pairing Hierarchy. | KB has complete TBP content |
| **1 — Fix derived data** | Fix session ranges (ICT killzones), add ONS/P12/submission range/prev PM 50%/dealing range. Add geometric filtering for FVG/OB/liquidity. Verify HTF levels against 1m. Use DST-aware tz everywhere. | Features compute correctly from 1m |
| **1a — Scheduler** | Add daily derived data refresh to scheduler. Bridge gaps on demand. | Runs daily + on-demand |
| **2 — Rewrite reasoner** | New `assemble_features()` with corrected data. Remove IPDA/bias. Add all levels, session ranges, submission range, filtered PD arrays, DOL, active macro. | Features block is clean and correct |
| **3 — Update prompt v0.6** | Session-aware, HTF/DOL focus. NO 7 Rules (those go in execution prompt later). Include Order Pairing Hierarchy, TCM timeframes, ONS profiles, macro awareness. | Prompt produces good bias verdicts |
| **4 — Blind vision analyses** | 3 independent Gemini reads of chart (no verdict context). Compare programmatically. | Vision reads match chart reality |
| **5 — Generate-validate-correct loop** | Reasoner emits → blind vision reads → compare → if disagreement, feed vision observations back to reasoner for re-evaluation | Loop converges |
| **6 — KB root consolidation** | Migrate DB → data/knowledge/. Add unit kinds. Wire merge. | One queryable store |
| **7 — Copilot + autonomous analyst** | Reasoner as interactive copilot + scheduled analyst | Daily briefs you trust |
| **8 — Probabilities + validation** | Add probability field. Score through backtest/MFE-MAE. | Measured edge |
| **Later — Entry/trade schemas** | Separate execution prompt with 7 Rules. Different schema. | After bias is locked |

---

## 7. Scheduler integration

### Daily derived data refresh
- **When:** Every day at 17:10 ET (after market close) + on-demand
- **What:** Run `compute_ict_features` to refresh all derived parquets (htf_levels, imbalances, orderblocks, liquidity, structure)
- **Gap detection:** Check last bar timestamp; if >2 hours stale, alert + attempt backfill
- **Bridge gaps:** On-demand script to backfill missing dates from streaming/TV/NT8

### Implementation
- Add to existing scheduler (`nt_schedule` or cron-based)
- Script: `scripts/maintenance/refresh_derived_data.py`
- Checks data freshness, runs compute pipeline, alerts on gaps

---

## 8. Derived data to fix (Phase 1 — before reasoner rewrite)

| Dataset | Issue | Fix | Priority |
|---|---|---|---|
| Session ranges | Not in derived parquets | Add to compute_ict_features (ICT killzone times) | HIGH |
| ONS range (04:00-08:15) | Not computed | Add to session computation | HIGH |
| P12 range (18:00-06:00) | Not in derived data | Add to session computation | HIGH |
| NY P12 (prev day 06:00-17:59) | Not computed | Add | HIGH |
| Submission range (14:00-18:15) | Not computed | Add OHLC + 50% | HIGH |
| Prev PM 50% | Not computed | Add | HIGH |
| Dealing range (structural) | Not computed — was using PDH-PDL | Add structural swing detection | HIGH |
| FVG/OB/liquidity filtering | Massive unfiltered (717K rows) | Add geometric filter (nearest N above/below price) | HIGH |
| Mitigation criteria | Undefined | Define: price trades through entire FVG/OB range | HIGH |
| HTF levels | May be stale | Verify against 1m, recompute if needed | HIGH |
| DST timezone | Hardcoded offsets | Use zoneinfo("America/New_York") everywhere | HIGH |
| IPDA | User doesn't use | Keep in derived data for backtesting, remove from reasoner | LOW |
| Data freshness check | Missing | Add pre-computation freshness verification | MEDIUM |
| Scheduler integration | Missing | Add daily refresh + gap detection | MEDIUM |

---

## 9. Model options

| Role | Model | Provider | Notes |
|---|---|---|---|
| Bias Reasoner | glm-5.2:cloud | Ollama cloud | 21s, good detail |
| Bias Reasoner | deepseek-v4-pro:cloud | Ollama cloud | 41s, structured |
| Bias Reasoner | gemini-3.6-flash | agy CLI | 20s, clean structure |
| Bias Reasoner | gemini-3.1-pro | agy CLI | 23s, detailed |
| Vision Verifier | gemini-3.6-flash | google-antigravity SDK | 20s, Image.from_file() |
| Vision Verifier | gemini-3.1-pro | google-antigravity SDK | 20s |
| Execution Reasoner (later) | TBD | TBD | 7 Rules prompt — future |

---

## 10. Open questions

1. **"Like me" threshold** — the X% accuracy target on held-out charts. You set it.
2. **Dealing range detection algorithm** — how to programmatically detect "a swing that took liquidity from both sides." Need swing detection + liquidity sweep check.
3. **Mitigation criteria** — exact definition of when an FVG/OB is "mitigated" (price trades through entire range? touches midpoint?).
4. **Geometric filter N** — how many nearest arrays above/below price to feed (3? 5? 10?).
5. **Midnight open for futures** — keep or replace with Globex open (18:00 ET)?

---

## 11. Iteration log

| Date | Change |
|---|---|
| 2026-08-04 | v1.0 — initial plan, 12 decisions, v0.4 schema |
| 2026-08-05 | v1.1 — v0.5 schema (alternate_scenario + price_delivery_narrative) |
| 2026-08-05 | v2.0 — critical review (3-model), added Decisions M-N, corrected submission range, dealing range, split bias/execution, geometric filter, blind vision, derived data first, scheduler integration, TBP reference, DST awareness |

---

## 12. References

- **TBP reference:** `C:\Users\vinay\Downloads\Trader_Blue_Print_Series.md`
- **Feature audit:** `docs/architecture/CHART_AGENT_FEATURE_AUDIT.md`
- **KB bridge:** `docs/architecture/KB_BRIDGE.md`
- **Producer handover:** `C:\Users\vinay\video2pdf\knowledge_ingest\HANDOVER.md`
- **Profiler KB (levels):** `docs/library/PROFILER_KNOWLEDGE_BASE.md`
- **Session ranges:** `scripts/trader/signals/session_ranges.py`
- **ICT data loader:** `scripts/trader/signals/ict_data_loader.py`
- **Critical reviews:** `data/vision/critical_review_glm.txt`, `critical_review_gemma4.txt`, `critical_review_deepseek.txt`