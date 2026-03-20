# Product Requirements Document: Live Options Dashboard

## 1. Overview
The Live Options Dashboard is a real-time command center designed for active day trading. It integrates the robust options statistics engine (GEX, Vanna, Magnet, Expected Moves) currently powering Discord and TradingView exports directly into a web application.

The goal is to provide immediate, actionable visibility into shifting dealer positioning, gamma walls, and regime changes using high-refresh live data from Schwab.

## 2. Architecture & Data Flow
**Strategy: Hybrid Data Fetching (On-Demand + Configurable Refresh)**
*   **API Limits Optimization:** The Schwab API rate limits make it difficult to fetch full option chains for all symbols constantly.
*   **Priority Queue:** 
    *   **Tier 1 (Focus Active):** SPX and QQQ (or up to 2-3 user-selectable tickers) operate on a fast cycle (e.g., exactly every 1–2 minutes) during RTH.
    *   **Tier 2 (Background Scan):** Remaining active tickers (AAPL, NVDA, IWM, etc.) operate on a slow polling cycle (every 10-15 minutes).
*   **Manual Override:** Any ticker can be toggled by the user into the "Fast" tier via the UI.
*   **Payload Reduction:** We will optimize the chain fetches by limiting the target strikes (e.g., strikes within ±10% of spot, or delta > 0.05) to dramatically speed up request times and calculation speed.

## 3. User Interface (UI) Design
**Command Center Aesthetic:** Dark mode, Shadcn/UI components, glassmorphism overlays, and a "Bloomberg-lite" professional financial style.

### 3.1 Layout Components
1.  **High-Density Monitor Table (Left/Top):** An uncluttered data table showing all `ACTIVE_TICKERS`. Columns include *Current Regime, Bias, Total GEX, Spot Price, Distance to Magnet, Distance to Z-Gamma*.
2.  **Detailed Narrative Cards (Right Panel/Modal):** Clicking a ticker opens its deep-dive "Coach's Briefing" card containing the narrative text layout you are familiar with from Discord.

### 3.2 Immersive State Alerts (Crucial for Day Trading)
*   **Audio Cues:** Subtle, professional chimes trigger on massive state shifts (e.g. `TRENDING BULLISH` to `BATTLE ZONE`).
*   **Persistent Alert Banner:** A top-of-screen floating banner appears when a major narrative change is detected. It requires a manual dismiss.
*   **Symbol Color Pulsing:** The background of a specific ticker row/card flashes high-contrast warnings (e.g., Vivid Orange for coiled, Red for trending bearish) instantly upon calculation change.

---

## 4. Visualizations Sandbox

These are the three core chart options we've brainstormed for the Detailed View.

````carousel
![Gamma Profile Mockup](C:\Users\vinay\.gemini\antigravity\brain\aa230481-c08f-4b5f-b439-9dd6ff303754\gamma_profile_mockup_1773973720431.png)
<!-- slide -->
![GEX Trend Mockup](C:\Users\vinay\.gemini\antigravity\brain\aa230481-c08f-4b5f-b439-9dd6ff303754\gex_trend_mockup_1773973743635.png)
<!-- slide -->
![Price Ladder Mockup](C:\Users\vinay\.gemini\antigravity\brain\aa230481-c08f-4b5f-b439-9dd6ff303754\price_ladder_mockup_1773973763541.png)
````

1.  **The Gamma Strike Profile (Column Chart):**
    Visualizes Call and Put walls natively as giant towers on a chart. Easily identify where price gravity is clustered.
2.  **The GEX State Trend (Time-Series Chart):**
    Tracks Total GEX, Spot Price, and Gamma Magnet over the course of the session. Useful for identifying structural momentum. Color-coded background regions indicate the dominant regime.
3.  **The Interactive Price Ladder (DOM Style):**
    A vertical ladder aligning calculated reaction zones (`Zero Gamma`, `Hedge Wall`, `EM Upper`) alongside live price movement and OHLC candles, highlighting precise levels for immediate trade execution.

## 5. Implementation Status: ACHIEVED (v2.0)
The dashboard is now fully operational with the following core modules:
1.  **Real-Time Telemetry Engine**: Powered by `run_options_levels.py --loop`, providing a 60s priority refresh for SPX/QQQ.
2.  **Options Tactical Command UI**: A Next.js/React frontend with dual-tower architecture (Charts + Info).
3.  **Advanced Metric Export**: Now includes Volume/OI profiles, Centroids, and Vanna/Charm exposure.
4.  **Precision Scaling**: Implemented basis-ratio normalization for futures (/ES, /NQ) to ensure UI alignment with spot prices.

## 6. Future Roadmap
1.  **Sentiment Overlay**: Integrate Discord/News sentiment scores into the Briefing panel.
2.  **Historical Analysis**: Add the ability to "Time Travel" through previous sessions' GEX trends.
3.  **Prisma DB Integration**: Migrate intermediate JSON state to the project's PostgreSQL/SQLite Prisma store for faster historical queries.
