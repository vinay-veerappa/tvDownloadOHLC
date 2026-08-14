---
name: tos-expected-moves
description: Multi-expiry ThinkorSwim (TOS) Expected Move extraction for all dates up to next Friday's expiry
allowed-tools: Read, Write, Edit, Run
version: 1.1
priority: HIGH
applyTo: "**/*.py"
---

# ThinkorSwim (TOS) Multi-Expiry Expected Moves Skill

> **RULE:** Whenever the user asks for Expected Move (EM) data, ALWAYS extract/compute values for **ALL available expiration dates starting from today/current day up to and including the next Friday's expiration date** (0DTE, 1DTE, 2DTE... through next Friday). Never limit output to a single expiration date unless explicitly requested.

---

## When to use

Use when the user needs ThinkorSwim (TOS) Expected Move data — multi-expiry extraction for all dates up to next Friday.

## 🔍 Data Source Failover Hierarchy

The extraction engine automatically detects system state and executes in order:

1. **Primary (TOS Desktop Application):**
   - Checks if `thinkorswim.exe` process is active on Windows.
   - If running, streams live quotes & IVs directly from ThinkorSwim Desktop via **COM RTD**.
2. **Fallback (ThinkorSwim Web UI):**
   - If TOS Desktop is NOT running, launches Chromium via Playwright using persistent profile (`~/.tos_web_profile`).
   - Navigates `https://trade.thinkorswim.com/trade?symbol={ticker}` and extracts platform-rendered Expected Moves from Web DOM.
3. **Secondary Fallback (Schwab REST API Proxy / Hub):**
   - Used for missing strike chains or quote fallback.

---

## Tickers Covered

- **Priority 1 (Time-Critical Futures):** `ES` (`/ES:XCME`), `NQ` (`/NQ:XCME`)
- **Priority 2 (Core Indices & ETFs):** `SPX`, `SPY`, `QQQ`, `IWM`, `DIA`, `NDX`, `SMH`, `SPCX`
- **Priority 3 (Monitored Stocks):** `AAPL`, `MSFT`, `NVDA`, `AMZN`, `GOOGL`, `META`, `TSLA`, `AVGO`, `CSCO`, `ORCL`, `AMD`, `TSM`, `ARM`, `MRVL`, `MU`, `QCOM`, `INTC`, `ASML`, `LRCX`, `AMAT`, `SKHY`, `SNDK`, `DELL`, `VRT`, `ANET`, `PLTR`, `CRWD`, `PANW`, `SNOW`, `NET`, `DDOG`, `MDB`, `NOW`, `MSTR`, `COIN`, `HOOD`, `SOFI`, `LLY`, `NVO`

---

## Execution Command

To run the full multi-expiry extraction manually or verify output:

```bash
.\.venv\Scripts\python.exe scripts/market_data/extract_all_expiries_em.py
```

### Options Pipeline Schedule Integration

The extraction runs automatically as part of the streaming options pipeline:
- **Frequency:** Daily Monday through Friday at **16:14 ET (4:14 PM EST)**.
- **Pipeline entry:** `scripts/streaming/options/run_options_levels.py` (`daily_multi_expiry_tos_em` job).

---

## Database & Output Artifacts

1. **Database Tables (`web/prisma/dev.db`):**
   - **`ExpectedMove`:** Stores `manualEm` for each weekly expiry, keyed by `(ticker, calculationDate, expiryDate)`. Non-destructive: preserves previous days' S/R levels.
   - **`HistoricalVolatility`:** Stores daily closing `iv` and `closePrice`, keyed by `(ticker, date)`.
2. **JSON Data File:** `data/options/ExpectedMoves/tos_expected_moves_all_expiries.json`
3. **Markdown Summary Report:** `data/options/ExpectedMoves/tos_expected_moves_all_expiries.md`

---

## Extraction Formula & Model

Expected moves are calculated using the TOS empirically calibrated time-scaling model:
$$\text{EM}_{\text{TOS}} = \text{Spot} \times \text{IV} \times \sqrt{\frac{0.6368 \times \text{DTE} + \text{Intercept}}{365}}$$

Where `Intercept` scales by session/weekend state (0.6900 for futures, 0.2400 for equities).
