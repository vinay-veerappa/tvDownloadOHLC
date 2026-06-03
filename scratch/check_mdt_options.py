import yfinance as yf
from datetime import datetime

ticker = yf.Ticker("MDT")
print("Current spot price:", ticker.info.get("currentPrice") or ticker.info.get("regularMarketPrice"))
expiries = ticker.options
print("Expiries:", expiries)
for exp in expiries[:5]:
    try:
        chain = ticker.option_chain(exp)
        calls = chain.calls
        puts = chain.puts
        spot = ticker.info.get("currentPrice") or ticker.info.get("regularMarketPrice") or 74.0
        closest_call = calls.iloc[(calls['strike'] - spot).abs().argsort()[:1]]
        closest_put = puts.iloc[(puts['strike'] - spot).abs().argsort()[:1]]
        call_strike = closest_call['strike'].values[0]
        call_bid = closest_call['bid'].values[0]
        call_ask = closest_call['ask'].values[0]
        put_strike = closest_put['strike'].values[0]
        put_bid = closest_put['bid'].values[0]
        put_ask = closest_put['ask'].values[0]
        call_mid = (call_bid + call_ask) / 2
        put_mid = (put_bid + put_ask) / 2
        straddle = call_mid + put_mid
        print(f"Expiry: {exp} | Spot: {spot:.2f} | Call Strike: {call_strike} Mid: {call_mid:.2f} | Put Strike: {put_strike} Mid: {put_mid:.2f} | Straddle: {straddle:.2f} ({(straddle/spot)*100:.2f}%)")
    except Exception as e:
        print(f"Error for {exp}: {e}")
