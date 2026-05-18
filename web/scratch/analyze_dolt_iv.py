import subprocess
import csv
import sys
import os
from datetime import datetime

DOLT_DIR = r"c:\Users\vinay\tvDownloadOHLC\data\options\options"
TICKERS = ["SPY", "AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "GOOGL", "AMD"]

def run_dolt_sql(sql_query):
    try:
        res = subprocess.run(
            ["dolt", "sql", "-r", "csv", "-q", sql_query],
            cwd=DOLT_DIR,
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error executing SQL: {sql_query}\nError details: {e.stderr}", file=sys.stderr)
        return None

def analyze_volatility():
    print("=====================================================================")
    print("AUDITING VOLATILITY METRICS FROM DOLT DATABASE")
    print("=====================================================================")

    # Get latest date
    max_date_stdout = run_dolt_sql("SELECT MAX(date) AS latest_date FROM volatility_history")
    if not max_date_stdout:
        print("Failed to get max date from Dolt.")
        return

    latest_date_str = ""
    reader = csv.reader(max_date_stdout.strip().splitlines())
    header = next(reader, None)
    first_row = next(reader, None)
    if first_row:
        latest_date_str = first_row[0]
    
    print(f"Latest database date: {latest_date_str}\n")

    results = []

    for ticker in TICKERS:
        # Fetch the latest EOD volatility metrics
        latest_metrics_sql = f"""
            SELECT date, iv_current, iv_year_high, iv_year_low, hv_current, 
                   iv_year_high_date, iv_year_low_date
            FROM volatility_history
            WHERE act_symbol = '{ticker}'
            ORDER BY date DESC
            LIMIT 1
        """
        metrics_stdout = run_dolt_sql(latest_metrics_sql)
        if not metrics_stdout:
            continue
        
        m_reader = csv.reader(metrics_stdout.strip().splitlines())
        m_header = next(m_reader, None)
        latest_metrics = next(m_reader, None)
        if not latest_metrics:
            print(f"No records found for {ticker}")
            continue

        date = latest_metrics[0]
        iv_curr = float(latest_metrics[1]) if latest_metrics[1] else None
        iv_high = float(latest_metrics[2]) if latest_metrics[2] else None
        iv_low = float(latest_metrics[3]) if latest_metrics[3] else None
        hv_curr = float(latest_metrics[4]) if latest_metrics[4] else None
        iv_high_date = latest_metrics[5]
        iv_low_date = latest_metrics[6]

        # Fetch the past 252 trading days IV to calculate dynamic 252-day IV Rank and Percentile
        history_sql = f"""
            SELECT iv_current 
            FROM volatility_history
            WHERE act_symbol = '{ticker}' AND date <= '{date}'
            ORDER BY date DESC
            LIMIT 252
        """
        history_stdout = run_dolt_sql(history_sql)
        iv_history = []
        if history_stdout:
            h_reader = csv.reader(history_stdout.strip().splitlines())
            h_header = next(h_reader, None)
            for h_row in h_reader:
                if h_row and h_row[0]:
                    try:
                        iv_history.append(float(h_row[0]))
                    except ValueError:
                        pass
        
        # Calculate dynamic 252-day IV Rank
        dynamic_ivr = None
        dynamic_ivp = None
        if iv_history and iv_curr is not None:
            h_min = min(iv_history)
            h_max = max(iv_history)
            if h_max != h_min:
                dynamic_ivr = 100.0 * (iv_curr - h_min) / (h_max - h_min)
            else:
                dynamic_ivr = 0.0

            # Calculate IV Percentile (percentage of past 252 days where IV was lower)
            lower_count = sum(1 for x in iv_history if x < iv_curr)
            dynamic_ivp = 100.0 * lower_count / len(iv_history)

        # Calculate Built-In IV Rank (using the database iv_year_high and iv_year_low)
        builtin_ivr = None
        if iv_curr is not None and iv_high is not None and iv_low is not None:
            if iv_high != iv_low:
                builtin_ivr = 100.0 * (iv_curr - iv_low) / (iv_high - iv_low)
            else:
                builtin_ivr = 0.0

        results.append({
            "ticker": ticker,
            "date": date,
            "iv": iv_curr,
            "hv": hv_curr,
            "builtin_ivr": builtin_ivr,
            "dynamic_ivr": dynamic_ivr,
            "dynamic_ivp": dynamic_ivp,
            "iv_high": iv_high,
            "iv_high_date": iv_high_date,
            "iv_low": iv_low,
            "iv_low_date": iv_low_date,
            "history_days": len(iv_history)
        })

    # Print a beautiful markdown table
    print("### Dolt Historical Volatility & Implied Volatility Audit")
    print(f"*Database Date: {latest_date_str}*\n")
    print("| Ticker | Date | Current IV | Current HV | IV Rank (Built-In) | IV Rank (252d) | IV Percentile (252d) | 52W IV Low | 52W IV High |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    
    for r in results:
        iv_pct = f"{r['iv']*100:.2f}%" if r['iv'] is not None else "N/A"
        hv_pct = f"{r['hv']*100:.2f}%" if r['hv'] is not None else "N/A"
        built_ivr_str = f"{r['builtin_ivr']:.2f}%" if r['builtin_ivr'] is not None else "N/A"
        dyn_ivr_str = f"{r['dynamic_ivr']:.2f}%" if r['dynamic_ivr'] is not None else "N/A"
        dyn_ivp_str = f"{r['dynamic_ivp']:.2f}%" if r['dynamic_ivp'] is not None else "N/A"
        iv_low_str = f"{r['iv_low']*100:.2f}%" if r['iv_low'] is not None else "N/A"
        iv_high_str = f"{r['iv_high']*100:.2f}%" if r['iv_high'] is not None else "N/A"
        
        print(f"| **{r['ticker']}** | {r['date']} | {iv_pct} | {hv_pct} | {built_ivr_str} | {dyn_ivr_str} | {dyn_ivp_str} | {iv_low_str} | {iv_high_str} |")

if __name__ == "__main__":
    analyze_volatility()
