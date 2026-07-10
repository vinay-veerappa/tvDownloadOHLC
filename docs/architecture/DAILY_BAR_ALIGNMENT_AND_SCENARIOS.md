# Daily Bar Alignment & Multi-Scenario Forecasting Architecture

## 1. Overview
The **Daily Bar Alignment & Multi-Scenario Forecasting** feature resolves critical date alignment inconsistencies between trading sessions (Open vs. Close modes) and introduces a multi-scenario historical projection engine for tomorrow's market open within the Narrative Engine V2.

Historically, the daily parquet storage is updated asynchronously. This component dynamically aligns daily bar slicing using calendar-date boundaries in US Eastern Time (`America/New_York`) and models tomorrow's open price scenarios when forecasting after-hours.

---

## 2. Key Responsibilities
- **Timezone-Aware Date Alignment**: Maps the last row in the daily parquet file against the current Eastern Time date. Automatically determines whether the last parquet row represents *today's active session* or *yesterday's completed session*.
- **Dynamic Slicing (Open vs. Close)**:
  - **Open Mode (08:00 AM ET)**: Predicts today's daily candle (C3). Utilizes yesterday's completed bar (C2) and two-days-ago (C1) as matching inputs.
  - **Close Mode (16:15 PM ET)**: Predicts tomorrow's upcoming daily candle (C3). Utilizes today's completed bar (C2) and yesterday's bar (C1) as inputs.
- **Multi-Scenario Forecasting (Close Mode)**: Since tomorrow's open price is unknown at the market close, the system generates and queries the historical matching engine for three distinct scenarios:
  1. **Gap Up**: Tomorrow opens $10\text{ pts}$ above today's High.
  2. **Flat / Inside**: Tomorrow opens at today's Close.
  3. **Gap Down**: Tomorrow opens $10\text{ pts}$ below today's Low.

---

## 3. Data Flow

```mermaid
flowchart TD
    Run["briefing_core.py (Session Run)"]
    Load["Read df_1d parquet"]
    Tz["Localize parquet index to US/Eastern"]
    DateCheck{"Last Parquet Date == Today's ET Date?"}
    
    OpenMode{"Mode == 'open'?"}
    CloseMode{"Mode == 'close'?"}
    
    OpenIloc1["C2 = iloc[-2] (Yesterday)\nC1 = iloc[-3] (2 Days Ago)"]
    OpenIloc2["C2 = iloc[-1] (Yesterday)\nC1 = iloc[-2] (2 Days Ago)"]
    
    CloseIloc1["C2 = iloc[-1] (Today)\nC1 = iloc[-2] (Yesterday)"]
    
    Run --> Load
    Load --> Tz
    Tz --> DateCheck
    
    DateCheck -->|Yes (Today's bar is in file)| OpenMode
    DateCheck -->|No (Last bar is yesterday)| OpenIloc2
    
    OpenMode -->|Yes| OpenIloc1
    OpenMode -->|No (Close Mode)| CloseIloc1
    
    OpenIloc1 --> SingleQuery["Query single C3O = C2 Close stats"]
    OpenIloc2 --> SingleQuery
    
    CloseIloc1 --> MultiQuery["Query Three Scenarios:\n1. Gap Up (opens > C2 High)\n2. Inside (opens @ C2 Close)\n3. Gap Down (opens < C2 Low)"]
    
    SingleQuery --> Assemble["Format and append to Cheat Sheet"]
    MultiQuery --> Assemble
```

---

## 4. Key Components
- **`scripts/trader/signals/candle_science.py`**: The core signal module containing the date alignment logic, scenario generation loops, and EOD formatting.
- **`scripts/trader/signals/ict_context.py`**: Utilizes the identical date-alignment checking mechanism to select the correct completed trading session for daily level calculations (PDH, PDL, PDC), resolving daily-level off-by-one errors.
- **`scripts/trader/briefing_core.py`**: Calls the Candle Science and ICT modules with the appropriate `--mode` flag, integrating the multi-scenario blocks into `== TOMORROW'S SETUP ==` during EOD runs.

---

## 5. Architectural Debate: Pros & Cons

The architectural design of the Narrative V2's confluence and signaling rules involves a balance between mathematical rigor and live trading execution constraints. Below is a detailed breakdown of these trade-offs.

### 1. Confluence Heuristics vs. Joint Probabilities
*   **The Design**: A voting heuristic combines Overnight, Open Scenario, and Candle Science signals to grade confluence (High, Medium, Low).
*   **Pros**:
    *   **Anti-Overfitting**: Prevents data-sparsity and over-fitting issues associated with high-dimensional joint probabilities ($P(\text{Bull} \mid X_1, X_2, X_3)$).
    *   **Horizon-Based Confirmation**: A simple vote captures fractal alignment across three distinct horizons (long-term trend, medium-term auction, short-term positioning).
*   **Cons**:
    *   **Multicollinearity**: The three signals are not statistically independent. An overnight sweep-and-rally causes a gap up, meaning we are effectively double-counting overnight momentum.

### 2. Static Volatility Regimes vs. Rolling Percentiles
*   **The Design**: Pinned VIX and VVIX absolute thresholds categorize market volatility.
*   **Pros**:
    *   **Structural Risk Grounding**: Pinned thresholds map directly to option implied volatility surfaces and dealer hedging risk boundaries.
    *   **No Regime Shift Lag**: Rolling percentiles suffer from severe lag during rapid regime transitions (e.g. classifying a high VIX as "low volatility" shortly after a major crash).
*   **Cons**:
    *   **Non-Stationarity**: Fails to capture long-term baseline drift in volatility regimes (e.g., VIX behave differently post-0DTE option explosion).

### 3. Exhaustion Boundaries vs. Directional Triggers
*   **The Design**: Expected Move (EM) boundaries are treated as key price exhaustion levels.
*   **Pros**:
    *   **Friction Zones**: The 1-standard-deviation Expected Move boundary is structurally prone to institutional profit-taking and inventory rebalancing, creating a natural reversion bias.
*   **Cons**:
    *   **Gamma Path Dependency**: In negative gamma, breaking the EM boundary triggers dealer hedging accelerant flows, transforming the exhaustion boundary into a breakout trigger.

### 4. Tight Invalidation vs. Volatility-Adjusted Stops
*   **The Design**: Bias invalidation triggers upon a 2-bar close below the London Low on a 5m chart.
*   **Pros**:
    *   **Capital Preservation**: Prevents taking massive drawdowns on failed structural setups. If the London Low fails, it is cheaper to exit and wait for re-entry.
*   **Cons**:
    *   **Stop-Running Sweeps**: Highly vulnerable to institutional liquidity hunts (sweeping Sell-Side Liquidity just below London Low before reversing).
