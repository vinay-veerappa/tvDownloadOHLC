# NT vs TV Deep P&L Analysis
**Period**: 2023-01-12 to 2023-12-31
## Global Financials
| Metric | NinjaTrader | TradingView | Diff |
|---|---|---|---|
| **Total Net P&L** | **$1,723.00** | **$2,129.50** | **$-406.50** |
| **Avg Trade P&L** | $1.42 | $1.76 | $-0.34 |
| **Total Trades** | 1213 | 1208 | 5 |
| **Commission Paid** | $0.00 | (Not in Export) | - |

## Matched Trade Analysis
Matching trades by Date and approx Time (within 5 mins)...
### Significant P&L Divergences (>$20)
Found 19 trades with significant P&L difference.

| Date | Time | Dir | NT P&L | TV P&L | Diff | NT Exit | TV Exit |
|---|---|---|---|---|---|---|---|
| 2023-08-30 | 09:52 | Long | $71.00 | $-31.50 | **$102.50** | TP1 | MAE Exit |
| 2023-01-17 | 09:52 | Short | $-31.50 | $57.50 | **$-89.00** | MAE Exit | TP1 |
| 2023-03-08 | 10:01 | Short | $0.00 | $82.50 | **$-82.50** | SL | TP1 |
| 2023-12-15 | 09:37 | Long | $0.00 | $75.50 | **$-75.50** | SL | TP1 |
| 2023-07-12 | 11:41 | Short | $0.00 | $71.50 | **$-71.50** | SL | TP1 |
| 2023-12-08 | 10:01 | Long | $139.00 | $73.00 | **$66.00** | SL | TP1 |
| 2023-03-07 | 10:02 | Short | $125.50 | $60.00 | **$65.50** | SL | TP1 |
| 2023-02-15 | 10:18 | Long | $0.00 | $61.00 | **$-61.00** | SL | TP1 |
| 2023-02-06 | 09:46 | Long | $0.00 | $61.00 | **$-61.00** | SL | TP1 |
| 2023-01-16 | 11:20 | Short | $46.00 | $-12.00 | **$58.00** | Exit on session close | TP1 |
| 2023-01-19 | 10:13 | Short | $0.00 | $56.50 | **$-56.50** | SL | TP1 |
| 2023-10-31 | 09:34 | Short | $14.50 | $66.50 | **$-52.00** | MAE Exit | TP1 |
| 2023-12-11 | 09:35 | Long | $-51.50 | $-14.50 | **$-37.00** | MAE Exit | MAE Exit |
| 2023-01-17 | 09:35 | Short | $-5.00 | $28.00 | **$-33.00** | MAE Exit | MAE Exit |
| 2023-06-19 | 09:36 | Short | $18.00 | $-13.00 | **$31.00** | Exit on session close | TP1 |
| 2023-06-12 | 09:33 | Short | $-33.50 | $-4.50 | **$-29.00** | MAE Exit | MAE Exit |
| 2023-07-03 | 12:59 | Long | $-2.00 | $-30.50 | **$28.50** | Exit on session close | TP1 |
| 2023-12-04 | 09:33 | Short | $-10.00 | $-37.50 | **$27.50** | MAE Exit | MAE Exit |
| 2023-06-29 | 10:07 | Long | $-35.00 | $-13.00 | **$-22.00** | SL | MAE Exit |

## Hypotheses Checklist
1. **Commission**: Is NT P&L net of commissions? (Check 'Global Financials' table)
2. **Contract Value**: Are huge differences multiples of 2? (MNQ is $2/pt)
3. **Outcome Flip**: Did one hit TP and the other MAE/SL?