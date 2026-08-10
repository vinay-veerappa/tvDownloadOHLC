---
name: tos-expected-moves
description: Multi-expiry ThinkorSwim (TOS) Expected Move extraction for all dates up to next Friday's expiry
allowed-tools: Read, Write, Edit, Run
version: 1.1
priority: HIGH
---

# ThinkorSwim (TOS) Multi-Expiry Expected Moves Skill

> **RULE:** Whenever the user asks for Expected Move (EM) data, ALWAYS extract/compute values for **ALL available expiration dates starting from today/current day up to and including the next Friday's expiration date** (0DTE, 1DTE, 2DTE... through next Friday). Never limit output to a single expiration date unless explicitly requested.

---

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

- **ES** (`/ES:XCME`) — E-mini S&P 500 Futures
- **NQ** (`/NQ:XCME`) — E-mini Nasdaq 100 Futures
- **SPX** (`SPX` / `$SPX`) — S&P 500 Index
- **SPY** (`SPY`) — SPDR S&P 500 ETF
- **QQQ** (`QQQ`) — Invesco QQQ Trust
- **DIA** (`DIA`) — SPDR Dow Jones Industrial Average ETF
- **IWM** (`IWM`) — iShares Russell 2000 ETF

---

## Execution Command

To run the full multi-expiry extraction manually or verify output:

```bash
.\.venv\Scripts\python.exe scripts/market_data/extract_all_expiries_em.py
```

### Options Pipeline Schedule Integration

The extraction runs automatically as part of the streaming options pipeline:
- **Frequency:** Every Friday (and last trading day of the week) at **16:15 ET (4:15 PM EST)**.
- **Pipeline entry:** `scripts/streaming/options/run_options_levels.py` (`weekly_multi_expiry_tos_em` job).

---

## Output Artifacts

1. **JSON Data File:** `data/tos_expected_moves_all_expiries.json`
2. **Markdown Summary Report:** `data/tos_expected_moves_all_expiries.md`

---

## Extraction Formula & Model

Expected moves are calculated using the TOS empirically calibrated time-scaling model:
$$\text{EM}_{\text{TOS}} = \text{Spot} \times \text{IV} \times \sqrt{\frac{0.6368 \times \text{DTE} + \text{Intercept}}{365}}$$

Where `Intercept` scales by session/weekend state (0.6900 for futures, 0.2400 for equities).
