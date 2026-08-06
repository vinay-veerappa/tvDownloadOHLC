# P12 Directional Bias & Pre-Market Alignment — Master Domain Blueprint

> **Source**: NotebookLM Query on *Pack Oct Bootcamp*, *Pack Live Wargaming*, & Daily Profiler SOP
> **Purpose**: Definitive operational guide documenting Matt Mickey & Austin's P12 (Previous 12-Hour) directional switch rules, 06:00–07:00 AM early rejection probabilities, NY Opening Handshake Vector, and the 99.26% "All Levels Hit" pre-market sweep rule.

---

## 1. What is P12? (18:00 – 06:00 EST)

**P12** refers to the **Previous 12-Hour range** calculated over the **18:00 (Globex Open) to 06:00 EST** pre-market segment. Fractally, P12 represents the **first half of the 22-hour daily candle** (18:00 to 16:00 EST).

### Quarters of P12:
- **$Q_1$ (18:00 – 21:00 EST) — Anticipation**: Establishes initial high or low relative to Globex open.
- **$Q_2$ (21:00 – 00:00 EST) — Confirmation**: Typically takes out $Q_1$ extreme during Asia session expansion.
- **$Q_3$ (00:00 – 03:00 EST) — Reversal or Heavy Expansion**: London session open; often fails to take $Q_2$ extreme or accelerates trend.
- **$Q_4$ (03:00 – 06:00 EST) — Continuation**: Follows $Q_3$'s direction or sets pre-market wick.

---

## 2. The P12 Midline Directional Switch (06:00 – 08:30 AM EST)

Between **06:00 and 08:30 AM EST**, price interaction with the **P12 Midline** (50% midpoint of P12 High/Low) acts as the ultimate **directional trigger**:

```
                  ┌─────────────────────────────────────┐
                  │ P12 High (18:00 - 06:00 EST)        │
                  ├─────────────────────────────────────┤
                  │                                     │
                  │  ▲ Footing Above P12 Mid -> BULLISH │
                  │  │ Target: P12 High                 │
                  ├──┼──────────────────────────────────┤ P12 Midline (06:00-08:30 Switch)
                  │  │ Target: P12 Low                  │
                  │  ▼ Rejection Below P12 Mid -> BEARISH│
                  │                                     │
                  ├─────────────────────────────────────┤
                  │ P12 Low (18:00 - 06:00 EST)         │
                  └─────────────────────────────────────┘
```

### Directional Rules:
1. **Footing Above P12 Mid**: If price steps above and finds footing (accepts) on P12 Mid between 06:00 and 08:30 AM, bias flips **BULLISH** $\rightarrow$ Primary Target: **P12 High**.
2. **Rejection Below P12 Mid**: If price rejects P12 Mid or accepts below it between 06:00 and 08:30 AM, bias flips **BEARISH** $\rightarrow$ Primary Target: **P12 Low**.
3. **The "Swiping" Signature (R1 Warning)**: If price repeatedly "swipes" across P12 Mid between 06:00 and 08:30 AM, expect a volatile **Range 1 (R1 chop) day** where both P12 High and Low will be swept.

---

## 3. The 06:00 – 07:00 AM P12 Rejection Window

Price action during the 06:00–07:00 AM pre-market hour provides high-probability early confirmation of whether daily extremes are locked in:

- **P12 High Early Rejection (06:00–07:00 AM)**: **84.52% statistical probability** that the **HOD (High of Day) is ALREADY LOCKED IN** overnight!
- **P12 Low Early Rejection (06:00–07:00 AM)**: **81.85% statistical probability** that the **LOD (Low of Day) is ALREADY LOCKED IN** overnight!
- **P12 Mid Early Rejection (06:00–07:00 AM)**: **49.52% probability** that one daily extreme is set, leading to a clean 3-hour line that does not retrace back past P12 Mid.

---

## 4. The NY Opening Handshake Vector (09:30 AM EST)

The **Opening Handshake** measures spatial alignment between the 09:30 AM RTH Open print and the P12 Midline:

- **Agreement ($\text{Handshake} = \text{Agreement}$)**:
  - RTH opens **above P12 Mid** when overnight profile is bullish (Long True $\text{LT}$).
  - RTH opens **below P12 Mid** when overnight profile is bearish (Short True $\text{ST}$).
  - *Outcome*: High-probability trend continuation day (**DNP** or **DWP**). Ride momentum.
- **Disagreement ($\text{Handshake} = \text{Disagreement}$)**:
  - RTH opens trapped inside pre-market consolidation or opposite to overnight expansion relative to P12 Mid.
  - *Outcome*: High-probability reversion / Goalpost chop day. Turn OFF trend-following models.

---

## 5. The 99.26% "All Levels Hit" Pre-Market Sweep Rule

When extreme pre-market volatility sweeps both session boundaries before 09:30 AM:

1. **The Both-Sides Sweep Rule**: If **BOTH Asia and London session extremes (or both P12 High & Low) are broken** between 06:00 and 08:30 AM:
   - There is a **99.26% statistical probability** that **BOTH HOD and LOD will form AFTER 08:30 AM**!
   - Overnight extremes are completely discarded as daily HOD/LOD.
   - Near-even split: 50.49% HOD forms first after 08:30; 49.51% LOD forms first after 08:30.
2. **Asia Broken Exception**: If Asia's extremes are broken (regardless of London), there is a **94.70% probability** that both HOD and LOD form after 09:00 AM (93.02% HOD / 95.35% LOD after 09:00 AM).

---

## 6. Software Verification Checklist

To verify our Python implementation (`scripts/validation/v_05_p12_pa.py`), the module must pass:

- [ ] **P12 Range Extraction**: Correctly extracts High, Low, and Midline over 18:00–06:00 ET window.
- [ ] **06:00–08:30 Directional Switch**: Accurately classifies footing vs rejection relative to P12 Mid.
- [ ] **06:00–07:00 Early Rejection**: Flags 84.52% HOD / 81.85% LOD locked-in signals.
- [ ] **NY Handshake Alignment**: Correctly outputs Agreement vs Disagreement vector at 09:30 RTH open.
- [ ] **99.26% Both-Sides Sweep Rule**: Detects pre-08:30 sweeps of both P12 High & Low and verifies HOD/LOD lock-in post-08:30.

---
*Document Location: `docs/profiler/p12_directional_blueprint.md`*
