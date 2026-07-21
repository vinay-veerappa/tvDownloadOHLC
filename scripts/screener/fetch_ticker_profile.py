"""
fetch_ticker_profile.py
=======================
Downloads price history, yfinance info, news, upgrades/downgrades, financial trends,
and insider trading data for a ticker and prints it as a single JSON payload.
Usage: python fetch_ticker_profile.py TICKER INTERVAL PERIOD
"""
import sys
import json
import logging
import pandas as pd
import numpy as np
import yfinance as yf

# Suppress warnings
logging.getLogger("yfinance").setLevel(logging.ERROR)

def clean_data(val):
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, (np.integer, np.floating)):
        return float(val)
    return val

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Missing symbol argument"}))
        sys.exit(1)

    ticker_sym = sys.argv[1]
    interval = sys.argv[2] if len(sys.argv) > 2 else "1d"
    period = sys.argv[3] if len(sys.argv) > 3 else "2y"

    try:
        ticker = yf.Ticker(ticker_sym)
        
        # 1. Download price history
        df = ticker.history(period=period, interval=interval)
        candles = []
        if not df.empty:
            df.reset_index(inplace=True)
            # Standardize Date/Datetime to timestamp in ISO format
            for _, row in df.iterrows():
                date_val = row['Date'].isoformat() if hasattr(row['Date'], 'isoformat') else str(row['Date'])
                candles.append({
                    "time": date_val,
                    "open": clean_data(row['Open']),
                    "high": clean_data(row['High']),
                    "low": clean_data(row['Low']),
                    "close": clean_data(row['Close']),
                    "volume": int(row['Volume']) if not pd.isna(row['Volume']) else 0
                })

        # 2. Download basic info
        info = {}
        try:
            raw_info = ticker.info
            keys = [
                'marketCap', 'sharesOutstanding', 'trailingPE', 'forwardPE', 
                'trailingEps', 'forwardEps', 'revenue', 'shortPercentOfFloat', 
                'beta', 'targetMeanPrice', 'recommendationKey', 'fiftyTwoWeekHigh', 
                'fiftyTwoWeekLow', 'averageVolume', 'dividendYield', 'dividendRate',
                'floatShares', 'sharesShort', 'shortRatio'
            ]
            info = {k: clean_data(raw_info.get(k)) for k in keys if raw_info and k in raw_info}
        except Exception:
            pass

        # 3. Download news
        news = []
        try:
            raw_news = ticker.news
            if raw_news:
                for item in raw_news[:4]:
                    content = item.get("content", {})
                    news.append({
                        "title": content.get("title", "No Title"),
                        "publisher": content.get("provider", {}).get("displayName", "Yahoo Finance"),
                        "link": content.get("canonicalUrl", {}).get("url", ""),
                        "pubDate": content.get("pubDate", "")
                    })
        except Exception:
            pass

        # 4. Download upgrades and downgrades
        upgrades = []
        try:
            ud_df = ticker.upgrades_downgrades
            if ud_df is not None and not ud_df.empty:
                ud_df = ud_df.head(5).reset_index()
                for _, row in ud_df.iterrows():
                    date_val = row['GradeDate'].isoformat() if hasattr(row['GradeDate'], 'isoformat') else str(row['GradeDate'])
                    upgrades.append({
                        "date": date_val.split('T')[0],
                        "firm": clean_data(row.get('Firm')),
                        "action": clean_data(row.get('Action')),
                        "rating": f"{row.get('FromGrade')} -> {row.get('ToGrade')}" if row.get('FromGrade') else str(row.get('ToGrade')),
                        "target": clean_data(row.get('currentPriceTarget'))
                    })
        except Exception:
            pass

        # 5. Annual Financial trends (EPS, Sales, Shares)
        financials = {"years": [], "eps": [], "sales": [], "shares": []}
        try:
            fin_df = ticker.financials
            if fin_df is not None and not fin_df.empty:
                # Sort columns (years) in ascending order
                cols = sorted(list(fin_df.columns))
                financials["years"] = [str(c.year) if hasattr(c, 'year') else str(c)[:4] for c in cols]
                
                if 'Basic EPS' in fin_df.index:
                    financials["eps"] = [clean_data(fin_df.loc['Basic EPS', c]) for c in cols]
                elif 'Diluted EPS' in fin_df.index:
                    financials["eps"] = [clean_data(fin_df.loc['Diluted EPS', c]) for c in cols]
                
                if 'Total Revenue' in fin_df.index:
                    financials["sales"] = [clean_data(fin_df.loc['Total Revenue', c]) for c in cols]
                
                if 'Diluted Average Shares' in fin_df.index:
                    financials["shares"] = [clean_data(fin_df.loc['Diluted Average Shares', c]) for c in cols]
                elif 'Basic Average Shares' in fin_df.index:
                    financials["shares"] = [clean_data(fin_df.loc['Basic Average Shares', c]) for c in cols]
        except Exception:
            pass

        # 6. Insider Trading Transactions & Purchases
        insider_tx = []
        try:
            tx_df = ticker.insider_transactions
            if tx_df is not None and not tx_df.empty:
                tx_df = tx_df.head(20).reset_index()
                for _, row in tx_df.iterrows():
                    insider_tx.append({
                        "insider": clean_data(row.get('Insider')),
                        "position": clean_data(row.get('Position')),
                        "date": str(row.get('Start Date')) if row.get('Start Date') else None,
                        "transaction": clean_data(row.get('Transaction')),
                        "shares": clean_data(row.get('Shares')),
                        "value": clean_data(row.get('Value')),
                        "ownership": clean_data(row.get('Ownership'))
                    })
        except Exception:
            pass

        insider_purchases = []
        try:
            purch_df = ticker.insider_purchases
            if purch_df is not None and not purch_df.empty:
                for _, row in purch_df.iterrows():
                    insider_purchases.append({
                        "metric": clean_data(row.iloc[0]),
                        "shares": clean_data(row.get('Shares')),
                        "trans": clean_data(row.get('Trans'))
                    })
        except Exception:
            pass

        # Package payload
        payload = {
            "success": True,
            "symbol": ticker_sym,
            "candles": candles,
            "info": info,
            "news": news,
            "upgrades": upgrades,
            "financials": financials,
            "insider_tx": insider_tx,
            "insider_purchases": insider_purchases
        }
        print(json.dumps(payload))

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))

if __name__ == "__main__":
    main()
