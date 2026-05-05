# NQ Session Specification (Second Brain)

## 1. Overview
This module defines the institutional sessions for Nasdaq (NQ) futures based on the NQStats methodology. Each session is anchored in **US/Eastern (New York)** time.

## 2. Session Definitions

| Session | Start (ET) | End (ET) | Description |
|---------|------------|----------|-------------|
| **Asia** | 18:00 (Y) | 02:00 (T) | Institutional accumulation / range establishment. |
| **London** | 03:00 (T) | 08:00 (T) | European open, often establishes a trend relative to Asia. |
| **Pre-NY** | 08:00 (T) | 09:30 (T) | Pre-Market window for final alignment. |
| **NY_AM** | 09:30 (T) | 12:00 (T) | Primary AM liquidity expansion (Equities Open). |
| **NY_PM** | 12:00 (T) | 16:00 (T) | PM expansion and Daily rebalancing (Equities Close). |

*(Y) = Previous Day, (T) = Current Day*

## 3. ALN Pattern Classification (Asia-London Relationship)
The relationship between Asia and London sessions determines the primary bias.

| Pattern | Logic | Interpretation |
|---------|-------|----------------|
| **LPEU** | London High > Asia High, London Low >= Asia Low | **Bullish Expansion** |
| **LPED** | London Low < Asia Low, London High <= Asia High | **Bearish Expansion** |
| **LEA** | London High > Asia High AND London Low < Asia Low | **Session Expansion** (volatile) |
| **AEL** | London High <= Asia High AND London Low >= Asia Low | **Consolidation** (wait for NY) |

## 4. Implementation Reference
This specification is implemented in the following library modules:
- Logic: `scripts/libs_py/nqstats/sessions.py`
- Classifiers: `scripts/libs_py/nqstats/classifiers.py`
