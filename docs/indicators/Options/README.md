# Options Tactical Dashboard & Indicators

## Overview
The Options stack delivers intraday and macro dealer-level structure for index and ETF families, then fans it out to Discord, file outputs, and Pine overlays.

Primary pipeline entrypoint:
- `scripts/streaming/options/run_options_levels.py`

Primary outputs:
- `data/options/daily_levels.json`
- `data/options/intraday_levels.json`
- `data/options/macro_levels.json`
- `data/options/daily_levels.txt`
- `data/options/unified_levels.txt`
- `data/options/unified_levels.json`

## Current Spec Highlights (2026-05)

### 1. Expected Move + EM85
- Multi-expiry expected moves are generated per ticker (`expected_moves`).
- EM85 bounds (`straddle_85_upper`, `straddle_85_lower`) are propagated through:
	- ETF fallback rescale (`rescale_levels_to_target_spot`)
	- Cash-to-futures translation (`translate_to_futures`)
- Discord and copy-ready outputs include EM85 fields when present.

### 2. Weekly EOD Scope Persistence
- Friday EOD captures the weekly scope candidate (next Friday target window).
- Persisted cache file:
	- `data/options/weekly_em_scope.json`
- Mon-Fri runs reuse the cached scope until expiry rollover.
- Weekly scope is attached to both cash and translated futures payloads.

### 3. Persistent State
- Basis anchors (open/basis translation consistency):
	- `data/options/basis_anchors.json`
- Regime/state diff tracking:
	- `data/options/pipeline_state.json`

### 4. Discord Delivery Hardening
- Embed payloads are compacted and batched by size budget.
- On embed rejection, fallback to text-first payload is attempted.
- Discord failures do not block output file generation.

### 5. Operational Level Semantics (Canonical)
- EM/EM85:
	- `EM HI/LO` defines expected range envelope.
	- `EM85 HI/LO` is the tighter straddle-derived confidence envelope.
- Core structural levels:
	- `ZERO GEX` is the primary pivot.
	- `CW/PW` are top resistance and support walls.
	- `FLIP UP/DN` and `CLIFF UP/DN` define regime transition and acceleration boundaries.
- Tactical levels:
	- `0D CW/PW`, `LOC C/P`, `DEX C/P` are short-horizon reaction and flow nodes.
- Weekly scope:
	- Friday EOD snapshot is carried Mon-Fri and emitted as `Weekly Scope` fields/metadata.

## Modes of Operation
- Manual one-shot run
- `--schedule` scheduler mode
- `--loop` priority loop mode

## Key Config Surfaces
Defined in `scripts/streaming/options/config.py`:
- Active and priority ticker sets
- ETF fallback mappings
- Index-to-futures mappings
- Scheduler times and timezone
- Discord defaults and output toggles

## Pine Consumption
Recommended TradingView paste sources:
- `data/options/unified_levels.txt` (scored-first)
- `data/options/daily_levels.txt` (legacy-rich output)
- `data/options/macro_levels.txt` (macro context)

## Core Documentation Set
- `README.md` (this file): source of truth for runtime behavior and outputs.
- `DESIGN.md`: architecture and component responsibilities.
- `REQUIREMENTS.md`: normative functional/non-functional requirements and acceptance checks.

## Notes
Point-in-time analysis/report documents (dated files) are stored in `docs/indicators/Options/archive/` as historical references and are not part of the normative runtime spec.
