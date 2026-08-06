# 📑 Profiler Verification & TradingView Replay Handover

This document summarizes the complete state, bug fixes, operational protocols, and verification results of the **Daily Profiler 3-Way Verification Workflow** (Python Engine ↔ TradingView Pine Studies ↔ NotebookLM Wargaming Transcripts).

---

## 🎯 Executive Summary & Objectives
Achieve **100% 1-to-1 mathematical and structural parity** across three independent analysis engines:
1. **Python Analytical Engine** (`SessionBoxEngine`, `compute_profiler`, `live_prediction.py`)
2. **TradingView PineScript Studies** (`Daily Profiler [VxV]`, `The Daily Profile vTDL`)
3. **NotebookLM Institutional Wargaming Transcripts** (Matt Mickey & Austin Clark)

---

## ✅ Key Fixes & Infrastructure Enhancements

### 1. 🐞 Logical Trading Date Bug Fix in `sessions.py` (Commit `2f7ca213`)
- **Problem:** `extract_all_sessions()` was grouping session boxes by calendar date (`df_et.index.date`). Because the Asia classification box is set from **18:00 – 19:30 ET** on the prior evening, when midnight struck (`00:00:00 ET`), the calendar date rolled, resetting `asiabox_mid` to `NaN`. This caused Python to miss midpoint touches during London/NY (e.g. 02:44 ET touch on July 23) and report `broken: false` while TradingView correctly showed `broken: true (BK)`.
- **Fix:** Updated [`scripts/libs_py/nqstats/sessions.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/nqstats/sessions.py#L133) to group by `get_logical_trading_date(df_et.index)` (ADR-001 compliant). Session midpoints and broken flags now propagate seamlessly across the entire 18:00–17:00 trading day.

### 2. 🕒 Timezone-Safe Replay Jump Protocol
- **Protocol:** Always convert target ET datetimes to **UTC Unix Epoch Seconds** (`timestamp` parameter in `replay_start`). This eliminates local client/browser timezone ambiguities (EDT vs PDT).
- **Example:** `2026-07-28 09:15:00 ET` = `1785158100`.

### 3. 🖼️ Visual Chart View Synchronization
- **Protocol:** TradingView's Bar Replay API sets the replay bar in memory, but does not re-center the horizontal canvas view. Always execute:
  1. `tradingview/replay_start` with `timestamp: <epoch>`
  2. `tradingview/chart_scroll_to_date` with `date: "<YYYY-MM-DD>"`, `time: "<HH:MM:SS>"`

### 4. ⏰ 09:15 AM ET Target Standard
- **Protocol:** Always perform pre-market evaluations at **09:15 ET** (or **09:00 ET**). Evaluating during the pre-market NY1 window resolves NY1's initial direction (`Long True` or `Short True` pending), collapsing the 4-outcome tree down to the active conditional set.

### 5. 🔍 Full Indicator Stack Extraction (Visible & Hidden Studies)
- **Protocol:** Issue extraction calls (`data_get_pine_labels`, `data_get_pine_lines`, `data_get_pine_boxes`, `data_get_study_values`) with `study_filter: ""` (empty string) to extract complete data arrays across **all indicators on the chart**, including hidden studies.

---

## 📊 Ground-Truth Parity Audit Summary

| Target Date & Time | Python Engine Output | TradingView Pine Labels | NotebookLM Wargame Alignment | Audit Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **2026-07-22 08:30 ET** | Asia: LT, London: SF | `Short False HOD/LOD` | Post-market review (Inside bar sequence warning) | ✅ 1-to-1 Match |
| **2026-07-23 08:30 ET** | Asia: LT (BK), London: SF | `Short False HOD/LOD` | Mickey: 7-day False streak maxed out; Short True bias | ✅ 1-to-1 Match |
| **2026-07-24 08:30 ET** | Asia: ST (BK), London: LT | `Short True / Short False` | Mickey: "Asia short true broken, London long true" | ✅ Verbatim Match |
| **2026-07-28 09:15 ET** | Asia: ST, London: SF (BK), NY1: LT (Pending) | `Long True / Long False` (LF: 42.1%, ST: 31.6%, SF: 26.3%) | Austin Solo: P12 Mid rejection, 67% False / 33% True | ✅ 1-to-1 Match |

---

## 🧠 Generic Skill Reference
The generic skill governing this workflow is documented at:  
👉 **[`TradingView Replay & Indicator Extractor`](file:///c:/Users/vinay/tvDownloadOHLC/.agents/skills/tradingview-wargame-verifier/SKILL.md)**

Use this skill whenever replaying charts, extracting study data (visible or hidden), or running analytical verification.
