# Risk Management — Narrative Sub-Package

This sub-package contains the **narrative-chain** risk validation layer.
It is one half of `scripts.libs_py.risk`:

| Sub-area | Concern | Audience |
|---|---|---|
| **Backtest (root `scripts.libs_py.risk/`)** | Realtime trade gating, equity tracking, trade-management policies | Backtest / live trading engine |
| **Narrative (this sub-package)** | Geometry and position-sizing validation of LLM-generated trade plans | LLM-output → DB write path |

## Why a separate sub-package

The two halves of the risk module answer different questions:

- The backtest module answers: **"May this strategy enter NOW?"**
  Realtime, stateful, integrates with the trading engine, uses
  `AccountRiskConfig` and `SessionRiskConfig` from
  `scripts/trading_framework/config/sessions.yaml`.

- The narrative module answers: **"Is this LLM-generated trade plan
  safe to write to the DB?"** Offline, pure-functional, runs after
  the LLM call, uses locally-scoped data in `constants.py`.

Coupling them would force the narrative chain to import the backtest
config, pandas, and a large config object just to read three numbers.
It would also force the two to share a change cadence, which slows
both down.

## Files

| File | Purpose |
|---|---|
| `constants.py` | All risk data as Python (not YAML). Single edit-point. |
| `config.py` | Typed dataclass view of `constants.py` (frozen, cached). |
| `validator.py` | `validate_trade_plan()` — pure function, no I/O. |
| `__init__.py` | Public re-exports. |
| `README.md` | This file. |

## Public API

```python
from scripts.libs_py.risk.narrative import (
    validate_trade_plan,   # main entry point
    get_risk_config,       # returns frozen RiskConfig (cached)
    RiskConfig,            # typed config dataclass
    InstrumentSpec,        # per-instrument spec
    AccountPhase,          # per-phase rule set
    ValidatorRules,        # validator behaviour switches
    reset_cache,           # for tests / hot-reload
)
```

## Usage in the narrative chain

```python
# In scripts/trader/daily_narrative.py
from scripts.libs_py.risk.narrative import validate_trade_plan

raw_plan = json.loads(plan_match.group(1).strip())
validated, warnings = validate_trade_plan(raw_plan)
# `warnings` is logged via the module logger only; not sent to Discord.
# `validated["trades"]` is what we save to the DB.
```

## Evolution roadmap

This sub-package is at v0.1.0. The eventual goal is a complete risk
management module. The roadmap below lists the planned additions; do
not remove the TODO block in `constants.py` until the items are
delivered.

### Phase 1 — current
- [x] Per-instrument contract specs (multiplier, tick size, tick value)
- [x] Account-phase risk profiles (EVAL vs FUNDED)
- [x] Per-instrument risk caps
- [x] Validator rules (price decimals, drop-on-unknown-asset)
- [x] `validate_trade_plan()`: drop on bad geometry, cap contracts,
      compute stop/dollar/rr from Python truth, R:R block + warn.

### Phase 2 — short term
- [ ] Per-prop-firm profiles (Apex 50K, Topstep 50K, FTMO 100K, etc.)
      sourced from a single `firm_profiles.py` with shared schema.
- [ ] Daily-stop awareness: read realised P&L from Prisma `Trade`
      table and refuse to validate a new trade if the day's realised
      loss >= `phase.daily_stop_usd`.
- [ ] Trailing-DD awareness: read account equity and `total_dd_buffer`
      from `AccountRiskManager.state` and refuse trades that would
      breach it.

### Phase 3 — medium term
- [ ] Volatility-scaled contract sizing: cap contracts to
      `floor(risk_cap / (ATR * point_value))`.
- [ ] Time-of-day scaling: reduce size during NY lunch, block during
      news blackouts.
- [ ] Correlation caps across correlated instruments (ES+MES, NQ+MNQ).
- [ ] News-blackout windows (CPI/FOMC minutes, fed-speak days).

### Phase 4 — long term
- [ ] Realized-loss carry-over across days (eval-trail logic).
- [ ] Auto-flush at `flatten_by` from `SessionConfig`.
- [ ] Per-account profit targets (eval pass / consistency rules).
- [ ] Live broker integration (Topstep / Tradovate API status read).

## Editing the constants

The risk numbers live in `constants.py` as Python. They mirror
`scripts/trading_framework/config/sessions.yaml`. If you change a
value in one place, change it in the other and add an entry to the
change-log at the bottom of `constants.py`.

| Source-of-truth table | Mirror location |
|---|---|
| `scripts/trading_framework/config/sessions.yaml` → `execution.point_value` | `INSTRUMENT_SPECS[*].multiplier_dollar_per_pt` |
| `scripts/trading_framework/config/sessions.yaml` → `execution.tick_size` | `INSTRUMENT_SPECS[*].tick_size` |
| `scripts/trading_framework/config/sessions.yaml` → `session_risk.daily_max_loss` | `ACCOUNT_PHASES[*].daily_stop_usd` |
| `scripts/trading_framework/config/sessions.yaml` → `session_risk.max_trades_per_day` | `ACCOUNT_PHASES[*].max_open_trades` |
| `scripts/trading_framework/config/sessions.yaml` → `account_risk.trailing_drawdown` | `ACCOUNT_PHASES.FUNDED.total_dd_buffer_usd` |
| `scripts/trading_framework/config/sessions.yaml` → `account_risk.starting_equity` | (TBD — used in Phase 4 for sizing) |

## Testing

Run `pytest tests/test_risk_validator.py -v` to execute the unit tests.
The tests pin behaviour for every rule in `validate_trade_plan()` and
are the contract this module guarantees.
