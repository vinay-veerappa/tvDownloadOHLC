# Chart Agent — Session Handover (v2)

**Session date:** 2026-08-05 (continued)
**Status:** Phase 0 (KB update) → Phase 1 (fix derived data) — ready to implement
**Plan doc:** `docs/architecture/CHART_AGENT_PLAN.md` (v2.0)

---

## What was accomplished this session

### Planning + critical review
- Built and tested the full chart agent pipeline: chart generation, reasoner, vision verifier, agent loop
- Ran 7-model reasoner comparison (all said bearish; Gemini vision said bullish — both valid)
- Evolved schema from v0.1 → v0.5 (added alternate_scenario, price_delivery_narrative)
- Extracted TBP (Trader Blue Print Series) content — all 7 Rules, ONS Profiles, macros, Order Pairing Hierarchy
- Corrected submission range definition (2PM-6:15PM ET OHLC + 50%, NOT prev day OHLC)
- Ran 3-model critical review (GLM, Gemma4, DeepSeek) — 8 consensus issues found
- Updated plan to v2.0 with all corrections

### Key findings from critical review
1. **7 Rules are entry rules, not bias rules** — must separate bias prompt from execution prompt
2. **Dealing range ≠ PDH-PDL** — it's a structural swing that takes liquidity from both sides
3. **FVG/OB data dump causes context degradation** — need geometric filter (nearest N above/below price)
4. **Vision verification has anchoring bias** — must run blind (no verdict context)
5. **Derived data must be fixed FIRST** — before reasoner rewrite
6. **DST timezone risk** — use zoneinfo everywhere
7. **Submission range was missing from implementation** — now added (14:00-18:15 ET)
8. **Missing DOL as singular objective** — reasoner needs "where is price going?" not just level lists

### Code built and tested
| File | Purpose | Status |
|---|---|---|
| `scripts/trader/chart_agent/__init__.py` | Package init | ✅ |
| `scripts/trader/chart_agent/schemas.py` | VerdictSchema v0.5 | ✅ |
| `scripts/trader/chart_agent/gen_charts.py` | 5m chart renderer | ✅ |
| `scripts/trader/chart_agent/reasoner.py` | Verdict emitter (needs rewrite) | ✅ works, needs Phase 2 rewrite |
| `scripts/trader/chart_agent/agent_loop.py` | Multi-model loop + Gemini SDK vision | ✅ |
| `scripts/trader/chart_agent/compare_reasoners.py` | Quick benchmark | ✅ |
| `scripts/trader/chart_agent/prompts/daily_bias_reasoner.md` | v0.5 prompt (needs v0.6) | ✅ works, needs Phase 3 update |
| `scripts/trader/chart_agent/audit_features.py` | Feature audit script | ✅ |
| `scripts/trader/chart_agent/extract_tbp.py` | TBP PDF extraction (quota limited) | ⚠️ partial |
| `scripts/trader/chart_agent/test_vision.py` | Vision verifier test | ✅ |
| `.env` | GEMINI_API_KEY (gitignored) | ✅ |

### Model integration status
- **Ollama cloud** (gemma4:31b, glm-5.2, deepseek-v4) — ✅ working, 20-41s per verdict
- **agy CLI** (Gemini 3.6 Flash, 3.1 Pro) — ✅ working for text prompts
- **google-antigravity SDK** — ✅ working for vision (Image.from_file), needs GEMINI_API_KEY in .env
- **Local vision (qwen3-vl:8b)** — ❌ removed (too slow on 8GB GPU)

---

## Next steps (execution order)

### Phase 0 — KB update (FIRST)
1. Ingest TBP markdown (`C:\Users\vinay\Downloads\Trader_Blue_Print_Series.md`) into KB via producer pipeline
2. Correct submission range definition in KB (currently says "prev day OHLC" — should be 2PM-6:15PM ET)
3. Add missing content: 7 Rules (full text), Order Pairing Hierarchy, TCM Timeframes, ONS Profiles, Intraday Macros, Dealing Range definition, Book Making sequence, 3-Hour Cycle, Hourly Rotation

### Phase 1 — Fix derived data (BEFORE reasoner rewrite)
4. Add session ranges to `compute_ict_features` (ICT killzone times: Asia 20:00-00:00, London 02:00-05:00, NY AM 09:30-12:00, NY PM 13:30-16:00)
5. Add ONS range (04:00-08:15), P12 range (18:00-06:00), NY P12 (prev day 06:00-17:59)
6. Add submission range (14:00-18:15) with OHLC + 50%
7. Add Prev PM 50%, dealing range (structural swing), mids (PDM, PWM, PMM, session mids)
8. Add geometric filtering for FVG/OB/liquidity (nearest N above/below price)
9. Define mitigation criteria (price trades through entire FVG/OB range)
10. Verify HTF levels against 1m data
11. Use `zoneinfo("America/New_York")` everywhere (DST-aware)

### Phase 1a — Scheduler integration
12. Add daily derived data refresh to scheduler (17:10 ET + on-demand)
13. Add gap detection + alerting
14. Script: `scripts/maintenance/refresh_derived_data.py`

### Phase 2 — Rewrite reasoner
15. New `assemble_features()` with corrected data (remove IPDA/bias, add all levels, session ranges, submission range, filtered PD arrays, DOL, active macro)
16. Update prompt to v0.6 (session-aware, HTF/DOL focus, NO 7 Rules, include Order Pairing Hierarchy, TCM timeframes, ONS profiles, macro awareness)

### Phase 3 — Blind vision + generate-validate-correct loop
17. 3 independent Gemini reads (no verdict context — blind)
18. Compare programmatically
19. Feed disagreements back to reasoner for re-evaluation

---

## Key files to read

| File | Why |
|---|---|
| `docs/architecture/CHART_AGENT_PLAN.md` | Master plan v2.0 — 14 decisions, phases, all levels |
| `C:\Users\vinay\Downloads\Trader_Blue_Print_Series.md` | TBP reference — 7 Rules, macros, ONS profiles |
| `docs/architecture/CHART_AGENT_FEATURE_AUDIT.md` | Feature audit — what's wrong, missing, redundant |
| `data/vision/critical_review_glm.txt` | GLM-5.2 critical review |
| `data/vision/critical_review_gemma4.txt` | Gemma4 critical review |
| `data/vision/critical_review_deepseek.txt` | DeepSeek critical review |
| `docs/architecture/CHART_AGENT_HANDOVER.md` | This handover (previous version) |

---

## Commits this session

```
f084086c docs: update handover — Gemini vision SDK working, .env setup, local vision removed
1516d28b fix(chart_agent): remove gemma4:latest local model from reasoners
059060af feat(chart_agent): .env loader + remove local vision LLM
efe0c94b feat(chart_agent): Gemini vision SDK integration working
2bf576f3 fix(chart_agent): remove session shading, use 5m candles, fix target_d reference
d9aaab31 feat(chart_agent): v0.5 schema — alternate_scenario + price_delivery_narrative
52e4311e feat(chart_agent): agy CLI integration + reasoner benchmark
e474bd47 fix(chart_agent): agy CLI integration — correct arg order + PATH setup
01d47152 feat(chart_agent): multi-model agent loop for chart analysis comparison
1c8008e2 feat(chart_agent): Phase 0a — schema registry, chart generator, bias reasoner
06138012 docs: add Chart Agent master plan (reasoner-primary, vision-verifier, daily_bias_mtf v0.4 schema)
b368943a docs: feature audit — what's wrong, missing, redundant in reasoner data
```

---

## Open issues

1. **Gemini free tier quota** — 20 requests/day for gemini-3.6-flash. Vision verification + PDF extraction can hit this. Consider paid tier or spreading requests across models.
2. **TBP PDF is image-based** — text extraction only gets annotations. The markdown file (`C:\Users\vinay\Downloads\Trader_Blue_Print_Series.md`) has the full content — use that for KB ingestion.
3. **Dealing range detection algorithm** — need to programmatically detect "a swing that took liquidity from both sides." Requires swing detection + liquidity sweep check. Not yet designed.
4. **Mitigation criteria** — exact definition of when FVG/OB is "mitigated" needs to be specified.
5. **Geometric filter N** — how many nearest arrays to feed the LLM (3? 5? 10?).
6. **Midnight open for futures** — keep or replace with Globex open? User to decide.