# ThinkorSwim (TOS) Option Hacker Setup & Exact Scan Parameters

This document details the exact **9-filter ThinkorSwim (TOS) Option Hacker** setup used by **Ben (@PatternProfits)** to generate the raw CSP candidate universe.

---

## 📸 Ben's Exact ThinkorSwim Option Hacker Scan Setup

```text
Scan in: All Optionable   |   Intersect with: <none>   |   Exclude: <none>
Condition: All of the following
```

| # | Filter Type | Field / Study | Min Value | Max Value | Exact Purpose |
| :-: | :--- | :--- | :---: | :---: | :--- |
| **1** | **Stock** | `Close` | **`$8.00`** | *[blank]* | Eliminates low-priced penny stocks. |
| **2** | **Option** | `Impl Vol` (Implied Volatility) | **`70.00 %`** | *[blank]* | **High-IV Juice**: Ensures option premium is rich and heavily overpriced. |
| **3** | **Option** | `Delta` | **`-.30`** | **`-.10`** | Out-of-the-Money (OTM) Put sweet spot ($\sim 70\% - 90\%$ win rate). |
| **4** | **Option** | `Days to exp` (DTE) | **`25`** | **`45`** | Theta acceleration window (30-day monthly/weekly cycles). |
| **5** | **Option** | `Open Interest` | **`100`** | *[blank]* | Baseline liquidity depth. |
| **6** | **Option** | `Return on risk` (ROR) | **`2.00 %`** | **`5.00 %`** | Yield on collateral for the 30-day period ($\sim 24\% - 60\%$ Ann. ROR). |
| **7** | **Fundam.** | `Earnings Per Share - TTM` | **`$0.01`** | *[blank]* | **Profitable Base**: Eliminates chronically money-losing companies. |
| **8** | **Study** | `MovingAverage_Scan` | `0.01 % Above` | `200 SMA` | **Institutional Trend**: Stock MUST be trading above its 200 Simple Moving Average. |
| **9** | **Study** | `Custom (Earnings Offset)` | *ThinkScript* | *See below* | **Earnings Filter**: Excludes stocks with binary earnings before expiration. |

---

## 💻 2. ThinkScript Custom Earnings Code Snippet (Filter #9)

In ThinkorSwim $\rightarrow$ Click **Add filter** $\rightarrow$ **Study** $\rightarrow$ Select **Custom...** $\rightarrow$ Paste this ThinkScript formula:

```thinkscript
# Exclude if earnings event is within current cycle
IsNaN(GetEventOffset(Events.EARNINGS, 0)) or GetEventOffset(Events.EARNINGS, 0) > 45
```

---

## 📋 3. Sorting & Result Controls
* **Show**: `500 Options`
* **Sorted by**: `Return on risk`
* **Sort Order**: `Ascending` (or `Descending`)

---

## 📊 4. Required Export Columns (Customize View)

In ThinkorSwim $\rightarrow$ Click the **Gear icon (`⚙️`)** $\rightarrow$ **Customize...** and add these columns in order:
1. `Symbol` (e.g. `.CRCL260925P79`)
2. `Description` (e.g. `CRCL 100 (Weeklys) 25 SEP 26 79 PUT`)
3. `Last`
4. `Net Chng`
5. `%Change`
6. `Volume`
7. `Bid`
8. `Ask`
9. `High`
10. `Low`
11. `Delta`
12. `Gamma`
13. `Theta`
14. `Vega`

---

## ⚡ 5. Running the Pipeline

### Mode A: Run with your ThinkorSwim CSV Export
Export your scan to `Downloads` $\rightarrow$ run:
```powershell
.\launch\run_csp_scanner.ps1
```

### Mode B: Run 100% Autonomously without ThinkorSwim
If you don't want to open ThinkorSwim or export CSVs, the Python engine will execute all 9 filters automatically:
```powershell
.\launch\run_csp_scanner.ps1 --live
```
