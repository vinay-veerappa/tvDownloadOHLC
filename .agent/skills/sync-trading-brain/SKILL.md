---
name: sync-trading-brain
description: Mandatory startup skill to synchronize with the Trading Second Brain and institutional rules.
---

# Sync Trading Brain Protocol

This skill MUST be invoked at the start of every session to ensure alignment with the "Source of Truth" for trading logic, session probabilities, and data protocols.

## Startup Checklist

Before initiating any analysis or code modification, perform the following:

1.  **Read the Second Brain & ADRs**: View `docs/SecondBrain_Trading.md` and `docs/architecture/ADR.md` to refresh:
    *   ALN Session Probabilities (LEA, AEL, LPEU, LPED).
    *   Initial Balance (IB) 96% Rule.
    *   NQ Hourly Personalities (Expansion vs. Reversion).
2.  **Verify Data Freshness**: 
    *   Run `nq-data-bridge:get_detailed_data_status` to check parity between historical `data/` and `data/live/`.
    *   Ensure current timestamp is within the 15-minute tolerance for active sessions.
3.  **Check Profiler Configuration**:
    *   Verify `scripts/profiler/PROFILER_ARCHITECTURE.md` or `PROFILER_REQUIREMENTS.md` for any recent logic updates to Quadrants/Hourly personalities.
4.  **Announce Loaded Rules & ADRs**:
    *   State the current ALN, NQStats baseline, and any applicable ADRs (e.g., Statistical Normalization) you are operating under.
    *   **MANDATORY**: Explicitly state: "I have synchronized with ADR-015 (Bootstrapping), ADR-014 (Shell Native), and ADR-012 (Traceable Research)."

## Logic Guardrails

*   **Rule Integrity**: Never propose trading logic changes that conflict with `docs/SecondBrain_Trading.md` without explicit user confirmation of a "Regime Shift."
*   **Timezone Consistency**: Always use **ET (New York)** for session calculations and **UTC** for data storage.
*   **Data Fusion & Precision**: Ensure all analysis scripts utilize the fusion layer (`data_loader.py`) and adhere to the **Statistical Normalization Standard (ADR-002)** for [MAE/MFE/Returns %].

## When to Invoke
- At the beginning of EVERY new conversation.
- When shifting focus from UI development to Trading Logic/Data analysis.
- After a long pause in the session where context might be stale.
