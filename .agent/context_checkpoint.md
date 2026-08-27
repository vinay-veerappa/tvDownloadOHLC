# Context Checkpoint: Initial Balance Suite Modernization & Quantitative Confluence Architecture
*Timestamp: 2026-08-26T17:51:00-07:00*

## 1. Executive Summary
Completed comprehensive modernization, forensic loss categorization, 7.5-year IS/OOS multi-asset validation (2019–2026), and established the Master Strategy Confluence Playbook with the 5m FVG Anti-Chop Gate (68.1% WR, 1.88 PF) and Pack Trading Quarters Theory.

## 2. Key Files & State
- docs/strategies/STRATEGY_CONFLUENCE_PLAYBOOK.md: Master catalog of the 5 Orthogonal Confluence Layers & 10-Point Composite Scoring System.
- docs/strategies/initial_balance_break/research/EXPERIMENT_JOURNAL.md: Permanent chronological experiment journal containing EXP-IB-001 through EXP-IB-011.
- scripts/strategies/initial_balance/core/run_is_oos_validation.py: Vectorized 7.5-year IS (2019-2023) vs OOS (2024-2026) backtest engine.
- scripts/strategies/initial_balance/core/analyze_six_level_failures.py: 6-Level hierarchical failure taxonomy extraction script.
- scripts/strategies/initial_balance/core/analyze_ib_size_vs_plays.py: Empirical study of IB size quintiles & ATR ratios vs Play expectancy.
- scripts/strategies/initial_balance/core/analyze_confluences_study.py: Empirical validation of IB Midpoint, 10:00 AM sweep, and First 10:00 FVG.
- scripts/strategies/initial_balance/core/test_fvg_chop_filter.py: 5m FVG / iFVG Respect chop gate validation engine.
- scripts/strategies/initial_balance/core/test_hierarchical_fvg_fallbacks.py: 3-Tier FVG Fallback hierarchy engine.
- scripts/ninjatrader/strategies/ib_breakout/IBStrategyBase.cs, IBBreakoutBot.cs, IBRetestBot.cs, IBFadeBot.cs: Modernized C# NinjaTrader 8 bots.
- scripts/ninjatrader/strategies/base/RiskManagerBase.cs: Fixed target inflation and OCO runner stop signal naming bugs.

## 3. Critical Decisions & Invariants
1. **Universal Basis Points & Pack Trading Standard**: All stops/targets/excursions defined in bps (1 bps = 0.01%). TP1 +10 bps (50% scale + BE lock), TP2 +25 bps runner, 12 bps MAE Stop Ceiling.
2. **Master Anti-Chop Rule**: Entry permitted ONLY if a 5m FVG is respected (Continuation) or 5m Inversion FVG is respected (Fade). No FVG -> Stay Cash (68.1% WR, 1.88 PF).
3. **Regime Router**: IB Range < 0.35x ATR -> Play 3 Sweep Fade (73.5% WR); IB Range >= 0.50x ATR -> Play 1 Breakout / Play 2 Retest (88-95% WR).
4. **IB Midpoint Gravitational Pivot**: Longs only above Mid (75% green odds); Shorts only below Mid (68.4% red odds).
5. **10:00 AM Hourly Sweep**: Single sweep of 09:00 high/low -> 78%/73% continuation; Double sweep of both -> R1 Whipsaw lockout.
6. **Hourly Time Quarters**: High in Q1 (00-15m) -> 89.5% Red close; Low in Q1 -> 87.7% Green close.
7. **Ex-Post Classification Guard**: R1, DNP, DWP are ex-post end results and must never be used as forward entry conditions.

## 4. Current Blockers & Unresolved Items
- None. All backtests, codebases, and docs are passing, validated, and committed to git.

## 5. Next Actions
1. Integrate the Confluence Playbook filters (IB Midpoint gate, 5m FVG respect, 10:30 fence, Quarters filter) into IBStrategyBase.cs and the Pine Script indicator IB_3Play_Strategy.pine.
2. Compile and backtest the unified strategy in NinjaTrader 8 Strategy Analyzer via 
t_backtest.
