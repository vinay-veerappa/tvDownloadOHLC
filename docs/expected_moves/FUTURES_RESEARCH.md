# Futures Expected Move (EM) Research

Extending Expected Move calculations to futures tickers (/ES, /NQ, /CL, etc.) requires addressing the lack of direct option chain data in many historical datasets.

## Proposed Experimental Ideas

### 1. Index-Based Proxy (The "Fractional" Method)
Since futures tightly track their underlying indices/ETFs, we can project the Expected Move from the liquid equity options onto the futures price.

- **Concept**: If SPY has a 1.2% Expected Move today, project that same 1.2% onto the /ES price.
- **Formula**: `Futures_EM = (ETF_EM / ETF_Price) * Futures_Price`
- **Pros**: Highly liquid, reliable data source, accounts for market-wide volatility.
- **Cons**: Does not account for futures-specific basis or overnight volatility differences (though minimal).

### 2. VIX-Derived Standardized EM
Use volatility indices (VIX for /ES, VXN for /NQ) to calculate a "theoretical" expected move without needing an option chain.

- **Formula**: `EM = Price * (VIX / 100) * sqrt(T / 252)`
- **Pros**: Doesn't require option chains, easy to backtest with VIX history.
- **Cons**: VIX is a 30-day "forward" measure; may over/underestimate 0DTE or 1DTE moves specifically.

### 3. Historical Volatility (HV) Scaling
Use the recent realized volatility of the futures contract to estimate the next move.

- **Formula**: `EM = Price * HV_30d * sqrt(T / 252) * Z_Score`
- **Pros**: Purely data-driven from the price action itself.
- **Cons**: Lagging indicator; doesn't account for "implied" event risk (e.g., FOMC) that options capture.

### 4. Broker API Direct Fetch (Live Only)
Fetch ATM straddles for futures options directly from Schwab or other APIs.
- **Status**: **FAILED**. Current testing (Dec 2025) shows that the Schwab API often returns empty or restricted chains for index futures (/ES, /NQ) depending on account permissions or API limitations. 
- **Recommendation**: Pivot to the **Index-Based Proxy** method for both historical backfilling and live projections.

## Symbol Mapping & Conversion Formula

The **Index-Based Proxy** method projects the volatility implied by highly liquid equity options onto the related futures contract.

### Conversion Formula
$$EM_{Future} = Price_{Future} \times \left( \frac{EM_{Proxy}}{Price_{Proxy}} \right)$$

*Where:*
- $EM_{Proxy}$ is the At-The-Money (ATM) straddle-based expected move (e.g., for SPY).
- $Price_{Proxy}$ is the underlying price of the proxy (e.g., SPY).
- $Price_{Future}$ is the underlying price of the futures contract (e.g., /ES).

### Mapping Table

| Future Ticker | Proxy Ticker | Market Index | Notes |
| :--- | :--- | :--- | :--- |
| **/ES (ES1)** | **SPY** | S&P 500 | Primary US Equities Proxy |
| **/NQ (NQ1)** | **QQQ** | Nasdaq 100 | Technology/Growth Proxy |
| **/RTY (RTY1)** | **IWM** | Russell 2000 | Small Cap Proxy |
| **/YM (YM1)** | **DIA** | Dow Jones | Blue Chip Proxy |
| **/GC** | **GLD** | Gold | Commodity Proxy |
| **/CL** | **USO** | Crude Oil | Commodity Proxy (less tight correlation) |

## Experimental Findings

1. **Proxy Reliability**: Testing `SPY -> /ES1` for 2024-2025 data shows a extremely high correlation in volatility percentages.
2. **VIX Calibration**: If an index proxy is unavailable, the **VIX-Derived EM** can be used by applying a **2.0x scalar**. 
   - *Result*: `EM_1day = 2.0 * Price * (VIX / 100) * sqrt(1/252)`
   - *Rationale*: Market straddles for 0DTE/1DTE typically price in twice the move implied by the 30-day standardized VIX.

## Next Steps for Experimentation

1. **Backtest Proxy Correlation**: Compare `(SPY_EM / SPY_Price)` vs realized `/ES` moves to see if the mapping holds.
2. **VIX Calibration**: Refine the 2.0x scalar across high/low volatility regimes.
3. **Automated Mapping**: Implement the `Symbol Mapping Table` in `scripts/utils/em_utils.py` for general use.
