# Data Download Instructions

This guide provides clear examples for downloading 1-minute OHLC data from TradingView using the `download_ohlc_selenium_enhanced.py` script.

## ✅ Prerequisites

1.  **Launch Chrome in Debug Mode:**
    You **must** start Chrome with the provided batch file before running any download scripts. This allows the script to control the browser.
    ```powershell
    cd selenium_downloader
    .\launch_chrome.bat
    ```

2.  **Prepare TradingView:**
    *   Log in to your TradingView account.
    *   Open a chart.
    *   **Set the timeframe to 1 minute.**
    *   Ensure you have a "Pro" or "Premium" subscription if you need extensive historical data (TradingView limits bar export for free accounts).

---

## 💻 CLI Arguments

| Argument | Description |
| :--- | :--- |
| `--ticker` | The ticker symbol to download (e.g., `ES1!`, `NQ1!`). The script will switch the chart to this ticker. |
| `--months` | Number of months of history to download (default: `3`). |
| `--resume` | Resume downloading history backwards from the **oldest** existing data found in your downloads folder. |
| `--check-gap` | Check for a gap between "Now" and the **newest** existing data, and fill it (download forward). |
| `--parquet-file` | Path to an existing Parquet file (e.g., `../data/ES1_1m.parquet`) to help determine data bounds. |
| `--iterations` | Safety limit for the number of download chunks (default: `100`). |

---

## 📋 Examples

### 1. Start Fresh (Download Recent History)
Use this if you are starting from scratch. It will download the last **3 months** of 1-minute data starting from today backwards.

**For ES (S&P 500 Futures):**
```powershell
python download_ohlc_selenium_enhanced.py --ticker ES1! --months 3
```

**For NQ (Nasdaq 100 Futures):**
```powershell
python download_ohlc_selenium_enhanced.py --ticker NQ1! --months 3
```

---

### 2. Resume History (Download Older Data)
Use this if you already have some data and want to extend your history further back in time. This command will find your oldest downloaded file and continue downloading **6 months** prior to that date.

**For ES:**
```powershell
python download_ohlc_selenium_enhanced.py --ticker ES1! --resume --months 6 --parquet-file "../data/ES1_1m.parquet"
```

**For NQ:**
```powershell
python download_ohlc_selenium_enhanced.py --ticker NQ1! --resume --months 6 --parquet-file "../data/NQ1_1m.parquet"
```

---

### 3. Update Data (Fill Recent Gaps)
Use this if you haven't downloaded data in a while (e.g., a few days or weeks) and want to bring your dataset up to date with "Now".

**For ES:**
```powershell
python download_ohlc_selenium_enhanced.py --ticker ES1! --check-gap
```

**For NQ:**
```powershell
python download_ohlc_selenium_enhanced.py --ticker NQ1! --check-gap
```

---

### 4. Comprehensive Update (Fill Gap + Extend History)
You can combine arguments to fill recent gaps AND extend history in one run.

```powershell
python download_ohlc_selenium_enhanced.py --ticker ES1! --check-gap --resume --months 3
```

---

### 5. Advanced: Resume using Parquet File
If you have already processed your data into Parquet files, you can use the Parquet file to tell the downloader exactly what data you already have.

```powershell
python download_ohlc_selenium_enhanced.py --ticker ES1! --resume --parquet-file "../data/ES1_1m.parquet"
```
