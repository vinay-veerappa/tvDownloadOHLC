# MNQ Position Size Calculator
## $3,000 Account | MNQ = $2/point

### Quick Reference: Contracts by Range Size

*Assumes NQ @ 20,000. Adjust proportionally for different NQ levels.*

| Range % | Range Pts | Risk $ | 2.5% ($75) | 5% ($150) | 10% ($300) |
|---------|-----------|--------|------------|-----------|------------|
| 0.05% | 10 pts | $20 | **3** | **7** | **15** |
| 0.10% | 20 pts | $40 | **1** | **3** | **7** |
| 0.15% | 30 pts | $60 | **1** | **2** | **5** |
| 0.20% | 40 pts | $80 | **0** | **1** | **3** |
| 0.25% | 50 pts | $100 | **0** | **1** | **3** |
| 0.30% | 60 pts | $120 | **0** | **1** | **2** |
| 0.35% | 70 pts | $140 | **0** | **1** | **2** |
| 0.40% | 80 pts | $160 | **0** | **0** | **1** |
| 0.45% | 90 pts | $180 | **0** | **0** | **1** |
| 0.50% | 100 pts | $200 | **0** | **0** | **1** |

---

### How to Use

1. **Measure your opening range** (High - Low of 9:30 candle)
2. **Calculate Range %** = (Range / NQ Price) × 100
3. **Find row** matching your Range %
4. **Read contracts** under your risk tolerance column

---

### Formula
```
Contracts = Floor(Account × Risk% / (Range_Points × $2))
```

### Example
- NQ @ 20,500
- Range = 41 points (0.20%)
- Risk = 5% ($150)
- Contracts = Floor($150 / (41 × $2)) = Floor(1.83) = **1 contract**

---

### ⚠️ Rules

- **0 contracts = SKIP THE TRADE** (Range too large for your risk)
- **Sweet Spot:** 0.10% - 0.18% range (best edge)
- **Never exceed:** 10% risk per trade

---

### Scaling by Account Size

| Account | 2.5% Risk | 5% Risk | 10% Risk |
|---------|-----------|---------|----------|
| $3,000 | $75 | $150 | $300 |
| $5,000 | $125 | $250 | $500 |
| $10,000 | $250 | $500 | $1,000 |
| $25,000 | $625 | $1,250 | $2,500 |

*Multiply contract counts accordingly.*
