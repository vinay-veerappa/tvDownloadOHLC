# Dealer Levels Primer (Day Trading Playbook)

## Purpose

This document is a practical refresher for using the dealer-level output in `data/daily_levels.txt` for intraday decision-making.

It answers:
- what each level means,
- what behavior to expect around each level,
- what trade actions are reasonable,
- what invalidates a setup,
- and where this framework can fail.

Use this together with the generated **Narrative Plan** and **Detailed Summary** blocks.

---

## Core Principles (Read First)

1. **Levels are reaction zones, not guaranteed turning points.**
2. **Acceptance vs rejection matters more than first touch.**
3. **Context first, trigger second.** Start from regime + location, then execute.
4. **Invalidation must be predefined before entry.**
5. **If price action disagrees with your level thesis, trust price action.**

---

## How to Read the Daily Block

Typical order in copy-ready lines:

`Upper EM, Absolute Call Wall, Local Call Node, 0DTE Call Wall, DEX Call Node, Gamma Flip Upper, Gamma Cliff Up, Zero Gamma, Gamma Cliff Down, Gamma Flip Lower, Max Pain, 0DTE Put Wall, Local Put Node, DEX Put Node, Hedge Wall, Lower EM`

Think in layers:
- **Risk envelope layer**: `Upper EM`, `Lower EM`
- **Dealer positioning layer**: walls, nodes, zero gamma, flips
- **Flow/acceleration layer**: DEX nodes, gamma cliffs
- **Magnet/settlement layer**: max pain, hedge wall

---

## Level-by-Level Meaning and Playbook

## 1) `Upper EM` / `Lower EM`

What it is:
- The expected-move envelope for the session.

What to expect:
- Inside EM: more two-way behavior and chop is common.
- Outside EM: expansion risk increases (trend continuation or squeeze behavior).

How to use:
- Use as outer risk map and profit-target context.
- If entering late near an EM boundary, require stronger confirmation.

Invalidation cues:
- A clean reclaim back inside EM after brief break can invalidate breakout continuation.

---

## 2) `Absolute Call Wall` / `0DTE Call Wall` / `Local Call Node`

What it is:
- Overhead call-heavy concentration areas; often resistance or speed-bump zones.

What to expect:
- First tests often stall or reject.
- Reclaims with acceptance can become squeeze launchpads.

How to use:
- In bearish context, look for fade setups on failed reclaims.
- In bullish transition, wait for acceptance above and retest hold before continuation entries.

Invalidation cues:
- Multiple closes above the zone with failed breakdown retests.

---

## 3) `0DTE Put Wall` / `Local Put Node` / `Hedge Wall`

What it is:
- Put-heavy and hedge-interest zones; often support or downside decision points.

What to expect:
- First tests often bounce.
- Clean breaks with acceptance can open path to lower liquidity and faster downside.

How to use:
- In bearish trends, use failed bounce attempts as continuation entries.
- In mean-reversion conditions, use strong rejection wicks + reclaim to attempt countertrend longs.

Invalidation cues:
- Fast reclaim and hold back above broken support cluster.

---

## 4) `Zero Gamma`

What it is:
- Approximate pivot where dealer hedging feedback can shift between damping and amplifying.

What to expect:
- Choppy rotational behavior around this line.
- Acceptance away from zero gamma often starts directional phase.

How to use:
- Treat as central regime pivot for the session.
- Combine with gamma-flip bounds for “decision box” logic.

Invalidation cues:
- Reversion back through zero gamma after attempted directional breakout.

---

## 5) `Gamma Flip Upper` / `Gamma Flip Lower`

What it is:
- A zone, not a single exact line, where flow dynamics can change.

What to expect:
- Inside zone: indecision/chop risk.
- Acceptance beyond zone: better odds of continuation.

How to use:
- Wait for close + retest outside the zone before sizing up.
- Use opposite boundary as structural invalidation reference.

Invalidation cues:
- Failed acceptance (breakout candle followed by immediate close back into the zone).

---

## 6) `DEX Call Node` / `DEX Put Node`

What it is:
- Delta-exposure concentration strikes; useful intraday flow inflection markers.

What to expect:
- Price can pin, hesitate, or accelerate through these points depending on tape quality.

How to use:
- Mark as “decision nodes” for continuation vs rejection.
- Good for trade management: partials or stop tightening near node interaction.

Invalidation cues:
- Node breaks with immediate reclaim against your position direction.

---

## 7) `Gamma Cliff Up` / `Gamma Cliff Down`

What it is:
- Steep changes in gamma profile slope; often associated with volatility/pace changes.

What to expect:
- Rejection or sudden acceleration around cliff interaction.

How to use:
- Treat cliffs as momentum checkpoints.
- If trend reaches cliff and tape weakens, reduce risk.
- If trend reaches cliff and pushes through with acceptance, continuation probability increases.

Invalidation cues:
- Cliff break without follow-through + immediate snap-back.

---

## 8) `Max Pain`

What it is:
- A magnet-like reference where aggregate options payout is minimized.

What to expect:
- Pinning tendency can appear, especially later in session or near expiry dynamics.

How to use:
- Use as an intermediate target, not a guaranteed destination.

Invalidation cues:
- Strong directional trend days can ignore max pain completely.

---

## Session Workflow (Practical)

## Step 1: Define default bias
- Start with `gex_regime` from narrative (`NEGATIVE` or `POSITIVE`).
- Mark zero gamma and gamma-flip zone as primary decision area.

## Step 2: Mark expansion boundaries
- [ ] Mark call/put clusters, DEX nodes, gamma cliffs
- [ ] Write bullish and bearish trigger/invalidation pairs

During session:
- [ ] Trade only confirmed acceptance/rejection
- [ ] Manage risk at decision nodes
- [ ] Respect invalidations without exception

After session:
- [ ] Review which levels were respected/ignored
- [ ] Note whether failures came from context, execution, or risk discipline

---

## Final Guidance

Use levels as a **decision framework**, not prediction certainty.

Your edge comes from:
- disciplined context filtering,
- consistent confirmation rules,
- strict invalidation handling,
- and repeatable risk control.

That process matters more than any single level.
