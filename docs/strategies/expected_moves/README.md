# Expected Move (EM) Methodology & Playbooks

Expected Move (EM) represents the market's anticipated range for an underlying asset, typically derived from option pricing (ATM Straddles) or implied volatility (IV365).

---

## 📈 Trading Playbooks
We have developed specific strategies based on daily and weekly Expected Moves. Detailed guides are available in the [**playbooks/**](playbooks/) folder:

- **[Intraday Trading Playbook](playbooks/INTRADAY_TRADING_PLAYBOOK.md)**: Rules for trading at EM boundaries during RTH.
- **[S/R Analysis](playbooks/INTRADAY_SR_ANALYSIS.md)**: Statistical bounce vs. break rates at 1.0x and 1.25x EM.
- **[Overnight Analysis](playbooks/OVERNIGHT_ANALYSIS.md)**: EM behavior during the GLOBEX session.
- **[ES Comprehensive Analysis](playbooks/ES_COMPREHENSIVE_ANALYSIS.md)**: Specific findings for S&P 500 futures.
- **[Ensemble Analysis](playbooks/ENSEMBLE_ANALYSIS.md)**: Combining EM with other indicators (VWAP, IB, etc.).

> [!TIP]
> **Key Finding**: Price is **82% likely** to stay within the 1.0x Expected Move on a daily basis. Touches of the 1.25x boundary often signal significant exhaustion or trend reversals.

---

## 🔬 Methodology & Research
Technical documentation on how we calculate and validate Expected Moves is in the [**methodology/**](methodology/) folder:

- **[Calculation Methodology](methodology/COMPREHENSIVE_EM_ANALYSIS.md)**: Straddle vs. IV methods and the 0.85 haircut logic.
- **[Methodology Comparison](methodology/METHODOLOGY_COMPARISON.md)**: Pros/cons of 252-day vs 365-day IV models.
- **[Data Dictionary](methodology/DATA_DICTIONARY.md)**: Definitions for all EM-related database fields.
- **[Analysis Results](methodology/ANALYSIS_RESULTS.md)**: Summary of calculation accuracy across tickers.

---

## Calculation Methods Summary
1.  **ATM Straddle**: `EM = Straddle Price * 0.85` (Most accurate for 0-7 DTE)
2.  **365-Day IV**: `EM = Price * IV * sqrt(T/365)`
3.  **252-Day IV**: `EM = Price * IV * sqrt(T/252)`
4.  **Open-Based EM**: Re-calibrated using actual session open.

---

## Data Sources
- **Options Chain**: [option_chain.csv](../../../data/options/options/doltdump/option_chain.csv) (DoltDB)
- **IV History**: [volatility_history.csv](../../../data/options/options/doltdump/volatility_history.csv)
- **Pipeline**: Unified via `scripts/data_processing/build_unified_em_history.py`.

---

## Next Steps / TODO
- [ ] Automate 0DTE EM calculations for SPX/NQ.
- [ ] Add live EM boundary visualization to the web dashboard.
- [ ] Backtest "EM Overshoot" mean-reversion trades.
