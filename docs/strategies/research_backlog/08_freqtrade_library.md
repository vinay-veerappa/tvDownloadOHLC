# Freqtrade Strategy Library — Cross-Reference (F10)

> Source: [github.com/freqtrade/freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies/tree/main/user_data/strategies) (~80 open-source Python strategies: root + `berlinguyinca/` (37) + `futures/` (8) + `lookahead_bias/`).
> **Framing**: crypto-native (BTC/ETH vs USDT), mostly 5m–1h TA-combo scalps whose raw backtest numbers are **market-specific to 2017–2021 crypto** — do NOT port numbers. The value here is (a) mechanical rule sets to re-test on NQ/ES/SPY, (b) structural ideas freqtrade pioneered that the repo lacks (time-decaying ROI tables, adaptive trailing, TD Sequential, hyperopt-shaped param spaces), and (c) a *falsification archive* — the repo maintains its own `lookahead_bias/` examples folder, same lesson: hyperopt'd crypto strategies famously died out-of-sample.

---

## A. Mapping to existing backlog (do not duplicate)

| Freqtrade strategy | Maps to | Delta |
|---|---|---|
| `Supertrend.py`, `FSupertrendStrategy.py` | §8.2 validated (PF 3.37 config) | Their version: ST + OTT hybrid; ours is ST + regime/time gates — merge candidates for P6-adjacent arms |
| `MultiMa.py`, `mabStra.py`, `TrendRiderStrategy.py` (25KB, multi-MA + trendlines) | **P2** EMA pullback / **F6.4** | Another MA-pullback family; use as extra arms |
| `UniversalMACD.py`, `MACDStrategy.py`, `AwesomeMacd.py`, `hlhb.py` (HLHB = RSI+EMA+MACD+ADX combo) | §8.1/§8.7 (MACD used as BB gate) | Standalone MACD-cross strategies — repo never tested MACD as primary trigger; cheap F4 test |
| `BbandRsi.py`, `Bandtastic.py`, `Low_BB.py`, `CombinedBinHAndCluc.py` | Q3-adjacent reversion | BB-pierce + RSI/MFI guard family — same reversion seat as F6.1; test as volume-confirmed vs plain variants |
| `CustomStoplossWithPSAR.py` (PSAR trailing stop), `BreakEven.py` (move to BE after +1%) | **T-series / exit modules** | Direct A/B arms for the repo's trailing-stop comparisons (Supertrend 1.0× trail vs PSAR vs BE-trigger) |
| `FixedRiskRewardLoss.py` (enforce fixed R exits), `minimal_roi` time-decay tables (Strategy005: 5%@0min decaying to 1%@1440min) | **T-series exit modules** | Freqtrade's *time-decaying ROI table* is an exit concept the repo's T1–T20 does not have — test "ROI decays with holding time" vs fixed-R on F5.2/Q3 signals |
| `TWAPStrategy.py` | out of scope (execution algo) | — |

## B. New mechanical patterns worth porting (NQ/ES testable)

### F10.1 Strategy005 family — volume-spike + multi-oscillator dip-buy with fisher-RSI
Full rules extracted from source:
- **Entry**: volume > 4× rolling-mean(volume, N) **AND** close < SMA(40) (dip condition) **AND** fastd > fastk (stoch turning) **AND** RSI > threshold **AND** fisher-RSI-normalized < threshold.
- **Exit**: RSI crosses above 74 + MACD<0 + −DI signal (alternate arm: SAR flip + fisher RSI>50).
- **Key learning candidate**: the **volume-4×-average confirmation** on a *counter-trend* entry (dip-buy with volume spike = capitulation signature). This composes with O5 (spike classifier: continuation vs exhaustion) and Q3 band fades — test whether "band-pierce + 3–4× volume" separates fade winners from knife-catches on NQ 5m.
- The **inverse Fisher transform on RSI** (`fisher_rsi_norma`): a bounded [0,100] RSI transformation designed for cleaner threshold crossovers. Cheap addition to §8.1's RSI variant table (which found Kaufman-ER wins and Chande/Connors lose) — one more adaptive-RSI arm.

### F10.2 Bandtastic — 4-tier Bollinger ladder as graded reversion entry
- Entry: close < BB(20, σ∈{1,2,3,4}) selectable tier; hyperopt chose **1σ** for its 1-year window with exit at upper bands. ROI table time-decaying; stop −34.5% (wide — crypto-native; NQ port needs bps-normalized stops per ADR-002).
- **Learning candidate**: which σ-tier of BB pierce is the fade sweet spot on intraday index futures — 1σ (frequent, shallow) vs 2σ (classic) vs 3σ+ (rare, fat). Directly merges with F6.1 IBS fade and Q3 VWAP-σ ladders: one graded-reversion test covers all three.

### F10.3 OTT (Optimized Trend Tracker) — CMO-adaptive Supertrend variant
From `futures/FOttStrategy.py`: VAR = EMA whose alpha is modulated by 9-period **Chande Momentum Oscillator** (CMO∈[0,1]); trailing stops ratchet on Var±k%; trend flips on cross of the ratcheted stops → OTT line = stop ± percent offset; entries on Var×OTT crosses; exit on ADX>60.
- **Learning candidate**: is CMO-adaptive alpha (fast in trends, slow in chop) better than the Kaufman-ER adaptive RSI the repo already crowned? Both implement "volatility-adaptive lookahead period" — test on equal footing in F4's trend seat. CMO is already close to Connors RSI components (§8.1: Connors RSI failed for BB — same family, different use).

### F10.4 `futures/` set — ADX+SMA trend, VolatilitySystem, ReinforcedQuickie, SmoothScalp
- `FAdxSmaStrategy` / `TrendFollowingStrategy`: ADX(>20–25) + SMA-direction entry — mirrors repo's ADX gate prior but as *primary* trend signal.
- `VolatilitySystem` (Chandelier-style stops): stop = highest-high − mult×ATR (long) — a trailing module candidate for TheStrat runners (P3) which currently use 9-EMA trail.
- `TDSequentialStrategy` (root, berlinguyinca): **Tom DeMark TD SequentialSetup** (9 consecutive closes beyond the close-4-bars-ago) as exhaustion counter-trend trigger — genuinely NEW to the backlog; pairs with F6.2 (consecutive-bars fade) as the formalized version of it. Test on NQ 15m: TD-9 up-count at session extremes → fade, gated by IB regime.

## C. Structural/mechanism ideas to borrow (not strategies per se)

1. **Time-decaying ROI tables** (most freqtrade strategies): `{0: 5%, 20: 4%, 40: 3%, 80: 2%, 1440: 1%}` — exit when profit ≥ decayed threshold. Maps to the repo's Cover-the-Queen scale-out as an alternative *time-based* risk-free-ization: test on F5.2 (Fair Value Theory) whose fixed 1.5R would be replaced by a decay table.
2. **Adaptive trailing tiers** (`trailing_stop_positive` + `trailing_stop_positive_offset` two-stage trailing): only starts trailing after +X%, then trails at −Y%. Equivalent to repo's BE-move after TP1 — parameterize both as one exit module family.
3. **`startup_candle_count` discipline + `process_only_new_candles`**: freqtrade bakes lookahead hygiene into the interface. Repo equivalent = the zero-lookahead tests in `test_trendline_structure.py` — extend that pattern to every new F-family hunter.
4. **Hyperopt spaces per side** (separate buy/sell param spaces): matches repo ADR-017 `get_param_grid()` convention — nothing to change, but the ~80 strategies provide a *grid-coverage benchmark* for Optuna arms (e.g., Bandtastic's tier-selector categorical parameters are a clean pattern for σ-tier tests).
5. **Falsification precedent**: freqtrade-strategies' own `lookahead_bias/` folder exists because the community found hyperopt'd winners that were look-ahead artifacts. Standing lesson for every test in this backlog: a strategy that looks too good on its source-market backtest gets a lookahead audit before its numbers are quoted.

## D. What to fetch when these enter the queue
Full sources are one raw.githubusercontent fetch away (ungated). Priority list: `SmoothScalp.py` + `ReinforcedSmoothScalp.py` (smoothed-oscillator scalp), `TDSequentialStrategy.py` (for F10.4), `TrendRiderStrategy.py` (multi-MA+trendline reference for S2's trendline engine), `CustomStoplossWithPSAR.py` (exit module), `SmoothOperator.py` (13KB — complex combo worth reading once). Note: crypto numbers (Bandtastic's "119% year") are era-specific — never cite as priors.