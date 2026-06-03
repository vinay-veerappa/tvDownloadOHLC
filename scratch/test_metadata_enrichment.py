import yfinance as yf
from datetime import datetime

ticker_sym = "CRWD"
print(f"Testing metadata enrichment for {ticker_sym}...")

ticker = yf.Ticker(ticker_sym)
info = ticker.info

# 1. Short Interest & Float
short_float = info.get("shortPercentOfFloat")
print(f"Short % of Float: {short_float}")

# 2. Analyst Consensus
rec = info.get("recommendationKey")
target = info.get("targetMeanPrice")
current = info.get("currentPrice") or info.get("regularMarketPrice")
premium = (target / current - 1) if target and current else 0.0
print(f"Analyst Rec: {rec} | Target: {target} | Current: {current} | Premium: {premium:.1%}")

# 3. Expected Numbers (EPS Estimate)
try:
    calendar = ticker.calendar
    print(f"Calendar: {calendar}")
except Exception as e:
    print(f"Calendar error: {e}")

# 4. Option Chain ATM Straddle & Expected Move
try:
    expiries = ticker.options
    if expiries:
        nearest_expiry = expiries[0]
        print(f"Nearest Option Expiry: {nearest_expiry}")
        opt_chain = ticker.option_chain(nearest_expiry)
        calls = opt_chain.calls
        puts = opt_chain.puts
        
        # Find ATM options
        underlying_price = current or info.get("regularMarketPrice")
        if underlying_price:
            closest_call = calls.iloc[(calls['strike'] - underlying_price).abs().argsort()[:1]]
            closest_put = puts.iloc[(puts['strike'] - underlying_price).abs().argsort()[:1]]
            
            call_mid = (closest_call['bid'].values[0] + closest_call['ask'].values[0]) / 2
            put_mid = (closest_put['bid'].values[0] + closest_put['ask'].values[0]) / 2
            straddle_cost = call_mid + put_mid
            implied_move = straddle_cost / underlying_price
            
            print(f"ATM Strike: {closest_call['strike'].values[0]}")
            print(f"Straddle Cost: {straddle_cost:.2f} | Implied Move: {implied_move:.1%}")
except Exception as e:
    print(f"Option Chain error: {e}")
