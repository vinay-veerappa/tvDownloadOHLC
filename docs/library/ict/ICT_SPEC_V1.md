# ICT Unified Engine (V1.0) — Master Technical Specification

## 1. Introduction
This is the single "Source of Truth" for all ICT detection logic within the `tvDownloadOHLC` ecosystem. All implementations (Python `ict_engine` and PineScript `ICTLibV1`) must adhere strictly to these definitions.

## 2. Shared Domain Models (Entities)

### 2.1 PDArray (Price Delivery Array)
*   **Definition**: Any imbalanced or order-based price zone (FVG, OB, BB, BPR).
*   **Rules**: 
    - Must track `creation_time`, `origin_price_range`, and `mitigation_status`.
    - **Mitigation**: A zone is mitigated (and removed from active tracking) if price crosses its **CE (Consequent Encroachment)** or closes through its boundary.

### 2.2 Liquidity Pool
*   **Definition**: Price levels where institutional orders are clustered (BSL, SSL).
*   **Rules**: 
    - Track `type` (High/Low) and `source` (Previous Day, Session Max, etc.).
    - **Sweep Detection**: Confirmed when price trades through the level (Wick) but closes back inside (Body) on the LTF.

## 3. Core Structural Logic

### 3.1 CISD (Change in State of Delivery)
*   **Logic**: The earliest signal of institutional delivery shift.
*   **Detection**:
    1.  Wait for a sweep of HTF Liquidity.
    2.  Identify the extreme candle of the sweep.
    3.  Identify the first candle in the *opposing* direction.
    4.  The "State of Delivery" changes when price **closes beyond the opening** of that extreme sequence.

### 3.2 SMT Divergence (The Crack in Correlation)
*   **Triad**: Primary check is `NQ` vs `ES` vs `YM`.
*   **Logic**: 
    - NQ makes a **Higher High** while ES makes a **Lower High** = Bearish SMT.
    - NQ makes a **Lower Low** while ES makes a **Higher Low** = Bullish SMT.
    - SMT is only valid when occurring at a confirmed **PD Array** or Liquidity Level.

## 4. Platform Implementation Plan (Task List)

### 4.1 Phase 1: Python Core (`scripts/libs/ict_engine/core/`)
-   [ ] `pa.py`: Detection for FVG, OB, BB.
-   [ ] `structure.py`: MSS, BOS, and CISD logic.
-   [ ] `correlation.py`: SMT detection across multi-symbol Parquet data.

### 4.2 Phase 2: PineScript v6 Core (`scripts/indicators/ict/`)
-   [ ] `ICT_Types.pine`: UDT definitions for all PDArrays.
-   [ ] `ICT_Methods.pine`: High-performance detection methods using update-in-place patterns.

## 5. Maintenance Standards
-   **No Duplication**: Logic is written once in the SPEC, then coded.
-   **Clean Code**: All functions must be < 50 lines.
-   **Early Return**: Standardize guard clauses to prevent "indentation hell."
