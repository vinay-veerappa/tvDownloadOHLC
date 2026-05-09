# Unified Options Levels Implementation and Testing Plan

Date: 2026-05-09
Scope: daily levels, macro levels, scored levels, Discord delivery, Pine display
Source of truth: OVERLAP_REDUCTION_PROPOSAL_PINESAFE_2026_05_09.md

## 1) Goal

Deliver a single scored-style payload contract that can be used consistently by Pine and Discord, while preserving scored-first ownership, macro extension behavior, and readable display rules.

The rollout must also address:

- stable canonical payload naming despite timestamped audit files
- single ticker per line or downloadable attachment delivery in Discord
- near-duplicate strike handling
- visible DTE limited to 0-7 days by default
- OI NODE as the replacement for the old UNK placeholder

## 2) Implementation Plan

### Phase 1: Canonical Writer Contract

Implement one canonical output shape for the unified stream.

Tasks:

- keep scored-style token grammar as the wire format
- ensure scored-first ownership emits one owner token per strike
- preserve macro provenance without letting macro duplicate owned strikes
- keep legacy outputs only as sidecars for transition and regression testing

Exit criteria:

- unified payload can be generated without changing Pine parser expectations
- canonical token format is stable and paste-ready

### Phase 2: Deterministic Output Policy

Separate audit naming from user-facing payload identity.

Tasks:

- keep timestamped or uniquely named files for history if needed
- define a stable canonical payload path or stable content target for paste workflows
- ensure unique naming does not fragment the paste-ready contract

Exit criteria:

- the canonical payload is reproducible without depending on a timestamped filename

### Phase 3: Discord Delivery Rules

Make Discord a delivery surface for the same unified payload, not a separate formatting system.

Tasks:

- support a one-ticker-per-line delivery mode for direct copy/paste
- prefer a downloadable text attachment if the integration supports it
- send raw paste-ready content only, without explanatory prose or markdown wrappers

Exit criteria:

- Discord content can be copied into Pine with minimal manual cleanup

### Phase 4: Near-Duplicate Suppression

Reduce clutter at the strike level before the payload reaches Pine or Discord.

Tasks:

- decide whether the suppression rule lives in Python, Pine, or both
- define a symbol-aware tick tolerance policy
- define an ADR-scaled tolerance policy for wider markets or higher-volatility names
- merge close levels before display if they represent the same practical price band

Exit criteria:

- near-duplicate levels are consistently collapsed according to the chosen rule

### Phase 5: Visibility Rules

Apply display rules without changing ownership semantics.

Tasks:

- limit visible DTE to 0-7 days by default
- keep macro extension levels gated by proximity and override flags
- preserve canonical labels so Pine styling remains stable

Exit criteria:

- the visible chart/Discord output is compact, but the underlying ownership model remains intact

### Phase 6: Validation and Cleanup

Retire transition-only behavior once the unified path is proven.

Tasks:

- remove or demote transitional output paths if they are no longer needed
- regenerate any reference artifacts used for review
- update docs if the final implementation differs from the proposal in any material way

Exit criteria:

- the new contract is the default path and the old formatting is not required for normal use

## 3) Testing Plan

### A. Unit Tests

Add or extend unit coverage for the writer and ownership logic.

Must cover:

- scored-first owner selection
- one strike, one owner emission
- OI NODE substitution for the old UNK placeholder
- macro suppression when a strike is already owned by the unified stream
- stable token grammar formatting
- deterministic handling of the canonical payload name/path

### B. Proximity and Dedup Tests

Add tests for duplicate collapse behavior.

Must cover:

- identical strike suppression
- close-level merge behavior within tick tolerance
- close-level merge behavior within ADR-scaled tolerance
- no accidental removal of distinct levels that should remain visible

### C. Discord Payload Tests

Add tests for delivery content and chunking behavior.

Must cover:

- one ticker per line delivery mode
- raw text attachment content if attachment support is added
- no markdown fence contamination in paste-ready payloads
- no truncation of the canonical payload without a clear fallback

### D. Pine Compatibility Tests

Validate that the output still parses and styles correctly in Pine.

Must cover:

- parser acceptance of the unified token grammar
- style/color routing for canonical labels
- no breakage from any label suffix convention used for macro hints
- visible DTE gating behavior

### E. Regression Checks

Run the current comparison and verification flow after the change.

Must compare:

- old daily/scored output versus unified output
- chart-visible levels versus Discord output
- macro inclusion versus suppression rules

## 4) Suggested Order of Work

1. Lock the canonical unified writer shape in Python.
2. Add or confirm scored-first ownership and OI NODE output.
3. Implement deterministic payload naming rules.
4. Add Discord delivery mode for raw copy/paste or attachment-based delivery.
5. Implement near-duplicate suppression and tolerance rules.
6. Apply 0-7 day DTE visibility gating.
7. Verify Pine parsing and style routing against the final token shape.
8. Regenerate reference artifacts and confirm the final docs match behavior.

## 5) Risks to Watch

- Label suffixes can break exact Pine comparisons if they are applied too early.
- Discord message chunking can split the paste-ready payload if the delivery mode is not explicit.
- Timestamped filenames can accidentally become the de facto user interface if no stable canonical payload is defined.
- A single tolerance rule may be too coarse if it is not symbol-aware.
- Over-aggressive dedupe can hide distinct levels that should remain visible.

## 6) Acceptance Criteria

The work is complete when all of the following are true:

- the unified payload is the primary contract
- OI NODE replaces UNK in current outputs
- macro levels are visible only when they add distinct value
- Discord output is copyable into Pine without manual reshaping
- visible DTE is limited to 0-7 days by default
- near duplicates are handled by an explicit tolerance policy
- timestamped audit files do not interfere with the canonical payload

## 7) Execution Status (2026-05-09)

Completed live validations:

- Live webhook ping to test channel succeeded (HTTP 204).
- Live `send_discord_update` path test succeeded with attachment + embed delivery.
- Live pipeline E2E for `SPY` succeeded with Discord enabled and canonical payload generation.
- Live multi-ticker pipeline E2E for `SPY, QQQ, AAPL` succeeded with Discord enabled.
- Live pipeline E2E for `SPY` succeeded using `discord_target_key='test_channel'` (no monkeypatch routing).
- Controlled production-key run for `SPY` succeeded using `discord_target_key='option-levels'`.
- Final controlled production-key run for `SPY` succeeded using `discord_target_key='option-levels'` after macro extension lane rollout.

Observed runtime evidence:

- Canonical file generated in-run: `data/options/unified_levels.txt`.
- Multi-ticker canonical output contained 3 lines and sorted ticker order (`AAPL, QQQ, SPY`).
- Discord transport in live run returned success codes for attachment and JSON embed posts.
- Keyed Discord routing path returned successful delivery via notifier (`Discord update sent ... with file`).
- Controlled production-key run payload fingerprint:
	- `unified_levels.txt` bytes: `242`
	- SHA256: `60d1f73c6398cdc8500d200ecf5b263abfe3861ba5c1b8b3ca39e030433e7511`
- Final controlled production-key run payload fingerprints:
	- `unified_levels.txt` bytes: `269`
	- `unified_levels.txt` SHA256: `489bc95ed93f2ceaa329030fbf0cb911f983daee803484c6ac868fd5d8bee920`
	- `unified_levels.json` bytes: `2352`
	- `unified_levels.json` SHA256: `fb59efc83989fb9134232173c08cba98901b9129315be757d28393abcd885e30`
- Canonical structured artifact now generated: `data/options/unified_levels.json`.
- Pipeline now logs unified TXT and unified JSON fingerprints each run (exists/bytes/lines/SHA256).
- Unified path now has an explicit runtime control flag: `ENABLE_UNIFIED_CONTRACT_OUTPUTS`.
- Unified owner-map now merges macro as extension lane with strike dedupe and policy labels (`[MEXT]` in-band, `[FAR]` when far levels are explicitly enabled).
- Discord delivery now includes attachment failure fallback to raw chunked lines.

Current focused test status:

- `tests/streaming/test_options_output_contract.py`: passing.
- Coverage includes deterministic sidecar naming, raw/attachment Discord behavior, unified file parity, DTE filtering, and near-duplicate suppression.
- Coverage also includes unified TXT/JSON parity, token field parsing, and unified payload fingerprint helper validation.
- Coverage also includes macro extension lane behavior: dedupe against intraday owner strikes, in-band extension tagging, and far-level gating.
- Coverage also includes Discord negative-path behavior: invalid webhook key handling, empty unified file fallback to scored lines, and attachment failure fallback.
- Coverage now includes pipeline orchestration integration checks for unified output wiring and Discord unified source selection when unified mode is enabled/disabled.
