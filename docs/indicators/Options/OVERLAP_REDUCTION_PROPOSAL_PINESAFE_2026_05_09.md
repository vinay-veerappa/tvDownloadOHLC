# Overlap Reduction Proposal (Pine-Safe)

Date: 2026-05-09
Owner: options levels pipeline
Scope: daily levels, macro levels, scored levels, Discord, Pine display
Baseline: OPTIONS_LEVEL_OVERLAP_BASELINE_2026_05_09.md

## 1) Locked Direction

This proposal is now locked to the following direction:

- One unified communication contract for chart and Discord.
- Scored-style token format is the canonical wire format.
- Scored-first ownership: one strike, one owner.
- Legacy daily/scored text outputs are retained only for testing and current web UI transition.

This is a product-direction decision, not just a formatting change.

## 2) Mental Model

The three sources are not equal in purpose:

- Daily levels: trading-day actionable breadth.
- Macro levels: extension/context beyond immediate trading band.
- Scored levels: highest-conviction key-price layer.

Unified output should preserve all three roles, but avoid duplicate displayed strikes.

## 3) Canonical Token Contract

Canonical format (reusing scored grammar):

- First token: `TICKER:PRICE:FILTER|SIG|LABEL`
- Remaining tokens: `PRICE:FILTER|SIG|LABEL`
- Delimiter: comma-separated tokens

Reason for choosing this contract:

- It already exists in pipeline writer logic.
- It already exists in Pine parsing logic.
- It carries classification and priority, unlike plain daily text.

## 4) Ownership Rules (Scored-First)

For each ticker and strike:

1. If scored exists at strike: owner = scored.
2. Else owner = daily.
3. Emit exactly one token per displayed strike.

Tie-break order when multiple candidates collide at the same strike:

1. scored primary (`SIG=P`)
2. scored secondary (`SIG=S`)
3. daily key-structural
4. daily tactical
5. daily extension/context

## 5) Macro Policy (Extension Lane)

Macro is kept for computation and context, but not as a duplicate display lane.

Rules:

- Macro levels are shown only when they add incremental context.
- If macro strike is already owned in unified stream, suppress duplicate macro display token.
- Macro in Discord should be a separate extension section, not mixed with core key levels.

Default macro inclusion gates:

1. Outside near-price tactical band and inside configured extension band.
2. Explicit high-importance macro type.
3. User toggle to show far macro levels.

### 5.1) Locked Macro Policy Table

| Scenario | Condition | Action | Owner/Section | Token Note |
|---|---|---|---|---|
| Macro duplicates unified strike | Same ticker and same strike already emitted in unified owner map | Suppress duplicate macro display token | Unified owner only | Keep macro provenance in JSON only |
| Macro key wall in extension band | Macro Call Wall / Macro Put Wall, not duplicated, and within extension band | Include | Unified Key Levels + Macro Extensions | Keep scored-style grammar; LABEL keeps canonical macro wall naming |
| Macro key wall far away | Macro wall outside extension band | Include only if `show_far_macro=true` | Macro Extensions | Token unchanged; mark label suffix `[FAR]` |
| Macro extension level near spot but duplicate daily/scored meaning | Same strike cluster already represented by scored/daily owner | Suppress | Unified owner only | No second token at same strike |
| Macro extension level adds incremental context | Non-duplicate and outside near band but inside extension band | Include | Macro Extensions | Emit as scored-style token with macro label suffix `[MEXT]` |
| Macro level outside all display bands | Outside far band and no override | Suppress from chart/Discord | None | Keep in provenance for audit |

### 5.2) Macro Token Mapping (Same Grammar, Enhanced Semantics)

Grammar remains unchanged:

- First token: `TICKER:PRICE:FILTER|SIG|LABEL`
- Next tokens: `PRICE:FILTER|SIG|LABEL`

Macro semantics are encoded via `FILTER|SIG|LABEL` conventions, not a new grammar:

| Macro Level Type | FILTER | SIG | LABEL Convention |
|---|---|---|---|
| Macro Call Wall | `W` | `P` | `MACRO CALL WALL` |
| Macro Put Wall | `W` | `P` | `MACRO PUT WALL` |
| Macro structural anchor | `A` | `P` or `S` | Existing anchor label + optional `[MEXT]` |
| Macro extension target (EM/flip/vanna/charm/liquidity) | `I` or `X` | `S` | Canonical label + `[MEXT]` |
| Macro far-context level | unchanged | unchanged | Canonical label + `[FAR]` (only when shown by override) |

Notes:

- Keep canonical label text first so Pine style routing remains stable.
- Suffixes (`[MEXT]`, `[FAR]`) are additive hints and must not replace canonical names.
- Macro metadata that is too verbose for labels stays in JSON provenance, not token grammar.

## 6) Proximity / ADR Simplification Strategy

Because Pine supports proximity filtering, unified stream can stay information-complete while display stays clean.

Recommended display gating:

- Always show scored primary levels.
- Show scored secondary within configurable ADR band.
- Show daily tactical only within tighter ADR band.
- Show macro extension only within wider ADR band or when "show far macro" is enabled.
- Keep visible DTE limited to 0-7 days by default.

This reduces clutter without deleting intelligence.

## 7) Determinism / Output Naming Policy

The current generation flow versions files with timestamps or unique names. That is useful for audit history, but it should not be the default user-facing contract for the unified payload.

Policy direction:

- Canonical chart/Discord payload should have a stable name or stable content path where possible.
- Timestamped or uniquely named artifacts may remain as history/audit sidecars.
- If uniqueness is needed, it should not prevent a single paste-ready canonical payload from being produced.

## 8) Discord Alignment

Discord should use unified levels as the primary source.

Suggested alert layout:

1. Unified Key Levels (core section)
2. Macro Extensions (secondary section)

Discord transport policy:

- Prefer one ticker per line for direct copy/paste simplicity.
- If Discord can support a downloadable text attachment, that is preferred for full-payload delivery.
- The attachment should contain the raw paste-ready text with no markdown wrappers or explanatory prose.

This guarantees one communication language across chart and alerting.

## 9) Backward Compatibility Policy

Backward compatibility is not a product requirement, except:

- testing/regression comparison
- temporary web UI compatibility

Implementation policy:

- Unified output is primary.
- Legacy outputs are optional sidecar artifacts behind testing or transition flags.

## 10) Pine Safety Constraints

Must preserve:

- parser token contract above
- line/label object limits
- canonical labels used by style/color routing
- near-duplicate strike handling should happen either in Pine via close-level merge logic or in Python via symbol-aware tick tolerance and ADR-scaled tolerance

Do not aggressively rename canonical labels in output tokens.

## 11) Validation Checklist

For each run:

- one strike emits one owner token in unified output
- must-keep key-structural levels are present
- parser reads unified stream without errors
- Discord unified section matches chart-visible key levels
- proximity toggles change visibility, not underlying ownership
- legacy comparison outputs remain available for test mode
- visible DTE stays within 0-7 days unless an override is explicitly requested
- timestamped/unique file naming does not break the canonical paste-ready payload
- OI NODE appears in place of the old UNK placeholder

## 12) KPIs

Primary:

- duplicate displayed strike rate in unified stream (target near zero)

Secondary:

- must-keep recall (target 100%)
- scored-key visibility recall (target 100%)
- Discord/chart consistency rate
- chart readability score (manual)

## 13) Immediate Implementation Order

1. Add unified writer using scored-style tokens.
2. Apply scored-first owner map merge.
3. Feed Discord from unified stream.
4. Keep legacy files for testing/web UI transition only.
5. Add ADR/proximity display policy in Pine.
6. Decide whether near-duplicate suppression belongs in Pine, Python, or both, then lock the tolerance rule.
7. Reduce visible DTE to the 0-7 day window by default.

## 14) Decision

Approved direction to implement:

- unified scored-style contract as primary
- scored-first ownership
- macro as extension lane with dedupe/gating
- Discord aligned to unified contract
- legacy retained only for testing and temporary UI transition
