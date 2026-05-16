# TCM Concepts Verification Hub

This folder is the living documentation for TCM concept validation.

## Documentation Contract

For every concept, we maintain:

1. A concept specification under `docs/TCM/concepts/TCM-XXX/README.md`.
2. Aspect-level verification checklists under the same concept folder.
3. A matching script entrypoint under `scripts/TCM/`.
4. Results persisted under `results/TCM/TCM-XXX/` (created when tests run).

## Master Concept List

| ID | Concept | Status | Spec | Script |
|---|---|---|---|---|
| TCM-001 | 08:15 AM 5m Anchor Candle Color Inverse Bias | Needs Review | [Spec](concepts/TCM-001/README.md) | [Script](../../scripts/TCM/tcm_001_0815_anchor_inverse.py) |

Latest output:

- [TCM-001 Report](../../results/TCM/TCM-001/report.md)

## Status Legend

- Planned: documented, not yet executed.
- In Progress: implementation/testing underway.
- Verified: passed with pre-defined statistical criteria.
- Rejected: failed criteria or no robust edge.
- Needs Review: conflicting or unstable results.
