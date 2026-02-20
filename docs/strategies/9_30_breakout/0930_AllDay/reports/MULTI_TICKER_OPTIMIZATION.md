# 09:30 ORB Multi-Ticker Optimization Report
**Generated:** 2026-02-18 16:45
**Strategy:** Standard 09:30 Breakout (Immediate)
**Data:** 1-minute Parquet (Localized to America/New_York)
**Metric Basis:** Percentage of Price (Asset Class Agnostic)

## Summary of Optimal Parameters
Determined by historical distribution analysis (Median, P80, P90).

| Ticker | Rec. Range % Max | Rec. TP1 (P50 MFE) | Rec. TP2 (P80 MFE) | P90 MAE | Median MAE | Median MAE/Range |
|---|---|---|---|---|---|---|
| **ES1** | 0.14% | 0.28% | 0.65% | 0.48% | 0.13% | 1.86x |
| **RTY1** | 0.32% | 0.54% | 1.14% | 0.77% | 0.24% | 1.35x |
| **YM1** | 0.17% | 0.30% | 0.66% | 0.47% | 0.14% | 1.60x |
| **GC1** | 0.10% | 0.23% | 0.51% | 0.34% | 0.11% | 2.25x |
| **CL1** | 0.43% | 1.05% | 2.43% | 1.73% | 0.48% | 2.72x |

## Detailed Distributions

### ES1 Analysis (7043 trades)
**1. Opening Range Size**
- Median: 0.072%
- P90 (Max Filter): 0.142%

**2. Max Favorable Excursion (MFE)**
- Median (TP1): 0.280%
- P80 (Runner): 0.646%

**3. Max Adverse Excursion (MAE) - Winners Only**
- Median (Sniper): 0.133%
- P90 (Hard Stop): 0.477%
- **Survival Rate at 1.0x Range Stop**: 28.7%
**4. Sniper Analysis (MAE vs Range)**
- Median MAE/Range: 1.86x
- P90 MAE/Range: 5.50x

---
### RTY1 Analysis (3902 trades)
**1. Opening Range Size**
- Median: 0.178%
- P90 (Max Filter): 0.319%

**2. Max Favorable Excursion (MFE)**
- Median (TP1): 0.542%
- P80 (Runner): 1.137%

**3. Max Adverse Excursion (MAE) - Winners Only**
- Median (Sniper): 0.239%
- P90 (Hard Stop): 0.774%
- **Survival Rate at 1.0x Range Stop**: 39.1%
**4. Sniper Analysis (MAE vs Range)**
- Median MAE/Range: 1.35x
- P90 MAE/Range: 4.21x

---
### YM1 Analysis (6933 trades)
**1. Opening Range Size**
- Median: 0.087%
- P90 (Max Filter): 0.174%

**2. Max Favorable Excursion (MFE)**
- Median (TP1): 0.297%
- P80 (Runner): 0.662%

**3. Max Adverse Excursion (MAE) - Winners Only**
- Median (Sniper): 0.141%
- P90 (Hard Stop): 0.470%
- **Survival Rate at 1.0x Range Stop**: 33.7%
**4. Sniper Analysis (MAE vs Range)**
- Median MAE/Range: 1.60x
- P90 MAE/Range: 5.00x

---
### GC1 Analysis (7123 trades)
**1. Opening Range Size**
- Median: 0.047%
- P90 (Max Filter): 0.099%

**2. Max Favorable Excursion (MFE)**
- Median (TP1): 0.233%
- P80 (Runner): 0.513%

**3. Max Adverse Excursion (MAE) - Winners Only**
- Median (Sniper): 0.106%
- P90 (Hard Stop): 0.339%
- **Survival Rate at 1.0x Range Stop**: 23.3%
**4. Sniper Analysis (MAE vs Range)**
- Median MAE/Range: 2.25x
- P90 MAE/Range: 7.50x

---
### CL1 Analysis (7244 trades)
**1. Opening Range Size**
- Median: 0.179%
- P90 (Max Filter): 0.429%

**2. Max Favorable Excursion (MFE)**
- Median (TP1): 1.046%
- P80 (Runner): 2.427%

**3. Max Adverse Excursion (MAE) - Winners Only**
- Median (Sniper): 0.484%
- P90 (Hard Stop): 1.733%
- **Survival Rate at 1.0x Range Stop**: 20.7%
**4. Sniper Analysis (MAE vs Range)**
- Median MAE/Range: 2.72x
- P90 MAE/Range: 8.34x

---
