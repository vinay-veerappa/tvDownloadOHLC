import yfinance as yf
from datetime import datetime, timedelta

start = datetime.now()
end = start + timedelta(days=7)

print(f"Fetching from {start.date()} to {end.date()}...")
try:
    cal = yf.Calendars(start=start, end=end)
    df = cal.get_earnings_calendar(market_cap=1_000_000_000, filter_most_active=True)
    if df is not None:
        print("Success! Columns:", df.columns.tolist())
        print(df.head(5))
    else:
        print("Returned None")
except Exception as e:
    print(f"Error: {e}")
