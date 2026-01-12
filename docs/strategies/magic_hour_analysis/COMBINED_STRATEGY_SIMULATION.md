
# Combined Strategy Simulation Results (Realistic)
## Magic Hour 07:00 - Bar-by-Bar Simulation

### Configuration
- Magic Hour: 07:00 ET
- Entry: At 9:40 (after 10m range forms)
- Target: MH Midline (50% reversion)
- Stop: 100% extension
- NY Protected Stop: True
- Period: 2023-01-03 to 2024-12-30

---

### Overall Performance

| Metric | Value |
|--------|-------|
| Total Trades | 515 |
| Wins (Target Hit) | 306 (59.4%) |
| Losses (Stop Hit) | 207 (40.2%) |
| Time Exits | 2 (0.4%) |
| **Win Rate** | **59.4%** |

---

### P&L Analysis (Points)

| Metric | Value |
|--------|-------|
| Total P&L | 995.1 pts |
| Average P&L | 1.9 pts |
| Average Win | 21.7 pts |
| Average Loss | -31.3 pts |
| Profit Factor | 0.69 |

---

### Trade Duration

| Metric | Value |
|--------|-------|
| Avg Bars to Exit | 32 bars (~32 min) |
| Avg Bars for Winners | 32 bars (~32 min) |

---

### Risk Metrics

| Metric | Value |
|--------|-------|
| Avg MAE (adverse) | 23.5 pts |
| Avg MFE (favorable) | 20.9 pts |
| MFE/MAE Ratio | 0.89 |

---

### Direction Breakdown

| Direction | Trades | Wins | Win Rate | Avg P&L |
|-----------|--------|------|----------|---------|
| SHORT | 274 | 156 | 56.9% | 1.4 |
| LONG | 241 | 150 | 62.2% | 2.6 |

---

### MH Break Analysis

| Break Side | Trades | Wins | Win Rate |
|------------|--------|------|----------|
| HIGH break → SHORT | 274 | 156 | 56.9% |
| LOW break → LONG | 241 | 150 | 62.2% |

---

### Comparison to Report Benchmarks

| Metric | Our Simulation | Report (07:00) |
|--------|----------------|----------------|
| Win Rate | 59.4% | 83.4% |
| Sample Size | 515 trades | 3,336 sessions |

---

### Notes
- This simulation uses bar-by-bar tracking to determine exact order of target/stop hits
- Entry is at 9:40 after the 10-minute range forms
- Walk-away logic: tracking stops once target is hit
