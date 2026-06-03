import yfinance as yf
import pandas as pd

ticker_sym = "CRWD"
print(f"Testing earnings dates structure for {ticker_sym}...")

ticker = yf.Ticker(ticker_sym)
try:
    dates_df = ticker.earnings_dates
    if dates_df is not None and not dates_df.empty:
        print("Success! Columns:", dates_df.columns.tolist())
        print(dates_df.head(4))
        
        # Download historical daily data for past year to calculate reaction moves
        hist = ticker.history(period="1y")
        
        # Look at the first 3 historical earnings dates
        reactions = []
        for date_idx in dates_df.index[:3]:
            # Convert to date
            edate = date_idx.date()
            # Find the closing price on the day of earnings and the next day
            # If AMC, reaction is next day close vs day of earnings close
            # If BMO, reaction is day of earnings close vs previous day close
            try:
                # Get the nearest date in the history
                pos = hist.index.get_indexer([pd.Timestamp(edate)], method='nearest')[0]
                price_day_of = hist['Close'].iloc[pos]
                price_prev = hist['Close'].iloc[pos - 1]
                price_next = hist['Close'].iloc[pos + 1]
                
                # Close-to-close return
                ret_close = (price_next / price_day_of - 1)
                reactions.append(f"{edate}: {ret_close:+.1%}")
            except Exception as e:
                pass
        print("Historical reactions:", reactions)
    else:
        print("Returned None or Empty")
except Exception as e:
    print(f"Error: {e}")
