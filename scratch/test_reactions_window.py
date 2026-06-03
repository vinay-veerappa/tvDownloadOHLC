import yfinance as yf
from datetime import timedelta

ticker_sym = "CRWD"
ticker = yf.Ticker(ticker_sym)
dates_df = ticker.earnings_dates

if dates_df is not None and not dates_df.empty:
    reactions = []
    # Test first 3 completed earnings dates (index 1, 2, 3 since index 0 is tomorrow's upcoming date)
    for date_idx in dates_df.index[1:4]:
        edate = date_idx.date()
        try:
            # Query price window around the earnings date
            start_w = edate - timedelta(days=4)
            end_w = edate + timedelta(days=5)
            h = ticker.history(start=start_w, end=end_w)
            
            # Find the trading day of earnings and the next trading day
            # edate is the calendar date, so find nearest trading date in the index
            # close price on edate, and close price on the next trading day
            ts = [t for t in h.index if t.date() >= edate]
            if ts:
                day_of_ts = ts[0]
                pos = h.index.get_loc(day_of_ts)
                
                # Close-to-close return after announcement (next day close vs day of close)
                # Since earnings are AMC (post-market), the price reaction occurs on the next day
                price_day_of = h['Close'].iloc[pos]
                price_next = h['Close'].iloc[pos + 1]
                ret = (price_next / price_day_of - 1)
                reactions.append(f"{edate}: {ret:+.1%}")
        except Exception as e:
            print(f"Error for {edate}: {e}")
            
    print("Reactions:", reactions)
