# NQ1 Wargaming Scenario Blueprint

Status: Draft v1 (operational)
Scope: Pre-market 08:30 ET wargame and EOD 16:00 ET reengineering
Sources: `docs/profiler/master_rule_catalog.json`, `docs/profiler/daily_profiler_wargaming.md`, `docs/profiler/mickey_austin_wargaming_reengineering.md`, `docs/profiler/p12_directional_blueprint.md`, `docs/features/CandleScience/BLUEPRINT.md`

## 1) Session Framing
- Instrument: NQ1
- Decision window: 08:30-09:30 ET
- Core check times:
  - 08:30 ET: pre-market handshake vs P12 midline
  - 09:30-09:45 ET: mode/cutoff window
  - 10:15 ET: final lock decision for True/False branch
  - 16:00 ET: EOD post-mortem

## 2) Outcome Universe
- Long True (LT): continuation long branch
- Long False (LF): failed long branch / reversion branch
- Short True (ST): continuation short branch
- Short False (SF): failed short branch / reversion branch

## 3) Day-Type Priors
Use these as priors only, then update by live context.

| Day Type | Prior Probability |
| :--- | :--- |
| R1 | 38.98% |
| DNP | 15.63% |
| DWP | 32.87% |
| R2 | 12.52% |

## 4) P12 and Sweep Rules
- 06:00-07:00 rejection cues:
  - P12 high rejection: HOD lock tendency 84.52%
  - P12 low rejection: LOD lock tendency 81.85%
- If no early lock, both-sides sweep tendency: 99.26%

## 5) 08:30 Decision Tree
1. Establish overnight key from Asia/London states and prior day type.
2. Read profiler NY1 probabilities for LT/LF/ST/SF.
3. Build top two branches:
   - Primary False branch: top probability in {LF, SF}
   - Primary True branch: top probability in {LT, ST}
4. Assign branch controls:
   - `mode_cutoff`: 09:30-09:45 ET
   - `final_cutoff`: 10:15 ET
5. Validate with confluence:
   - Candle Science bias
   - P12 pre-market bias
   - Weekly EMA 2-3% magnet flag

## 6) Scenario Cards

## 6.1 False Branch Card (Reversion)
- Trigger context:
  - Handshake weak or conflicted
  - Rejection behavior around P12 midline/key level
  - 2-3% weekly EMA magnet often increases reversion probability
- Required fields:
  - Outcome label (LF or SF)
  - Probability
  - HOD mode bucket / LOD mode bucket
  - HOD/LOD distance spans and medians
  - Key level hit rates (p12m, midnight_open, pdh, pdl)
  - 09:30-09:45 mode cutoff and 10:15 final lock

## 6.2 True Branch Card (Continuation)
- Trigger context:
  - Handshake aligned and accepted
  - Momentum confirms through key level instead of rejection
  - No immediate failure at mode window
- Required fields:
  - Outcome label (LT or ST)
  - Probability
  - HOD mode bucket / LOD mode bucket
  - HOD/LOD distance spans and medians
  - Key level hit rates (p12m, midnight_open, pdh, pdl)
  - 09:30-09:45 mode cutoff and 10:15 final lock

## 7) Risk and Position Sizing
- Risk budget: fixed dollars per trade from account and risk% policy
- Position size inputs:
  - stop distance in points
  - point value and tick size
- Position sizer output:
  - contract count
  - dollars at risk
- Rule:
  - if risk exceeds allowance at minimum size, hold size = 0

## 8) EOD Reengineering Checklist (16:00 ET)
- Compare planned branch vs realized branch.
- Record:
  - Actual handshake at open
  - RTH HOD/LOD timestamps
  - 3-hour line vs apex score
  - 4-step score and Step 4 confirmation
  - Winning scenario label
- Grade execution quality:
  - A: branch and cutoff logic matched and risk obeyed
  - B: branch right, timing late/early
  - C: branch wrong but risk respected
  - D: branch and risk both violated

## 9) Daily Markdown Artifact Template
Use this exact structure per day.

```markdown
# Wargame Report - NQ1 - YYYY-MM-DD

## Pre-Market 08:30 ET
- Overnight key:
- Prior day type:
- NY1 probabilities (LT/LF/ST/SF):
- Handshake:
- Confluence status:

## False Scenario Card
- Outcome:
- Probability:
- HOD mode:
- LOD mode:
- Distances:
- Key levels:
- Cutoffs: mode 09:30-09:45, final 10:15

## True Scenario Card
- Outcome:
- Probability:
- HOD mode:
- LOD mode:
- Distances:
- Key levels:
- Cutoffs: mode 09:30-09:45, final 10:15

## Risk Plan
- Stop distance:
- Contracts:
- Dollars at risk:

## EOD 16:00 ET Reengineering
- Open/High/Low/Close:
- HOD/LOD times:
- 3-hour line vs apex:
- 4-step score:
- Winning scenario:

## Lessons
- What validated:
- What failed:
- Rule update candidates:
```

## 10) Extension to Other Tickers
- Keep the same scenario-card protocol.
- Swap ticker-specific config from `scripts/config/ticker_registry.json`.
- Require a separate parity benchmark report per ticker before production adoption.
