# ES Futures Data Downloader & Charting System

TradingView data downloader using Selenium + Professional charting interface

## 📁 Project Structure

```
tvDownloadOHLC/
├── selenium_downloader/          # Selenium-based TradingView downloader
│   ├── download_ohlc_selenium_enhanced.py  # Main download script
│   ├── download_ohlc_selenium.py           # Original version
│   ├── launch_chrome.bat                   # Chrome debug launcher
│   └── get_selenium_cookies.py             # Cookie helper
│
├── data_processing/              # Data processing & conversion
│   ├── process_market_data.py    # Stitch & validate CSVs
│   ├── stitch_and_validate.py    # Validation utilities
│   └── convert_to_parquet.py     # CSV → Parquet converter
│
├── chart_ui/                     # Chart visualization
│   ├── chart_server.py           # FastAPI backend
│   ├── chart_ui.html             # Main chart interface
│   ├── demo_klinechart.html      # KLineChart demo
│   ├── indicators.py             # Indicator library
│   ├── indicator_manager.js      # Frontend indicator manager
│   ├── create_html.py            # HTML generator
│   └── visualize_data.py         # Plotly chart (legacy)
│
├── tvdata_scripts/               # TvDatafeed experiments
│   ├── download_ohlc_lib.py      # TvDatafeed downloader
│   ├── download_ohlc_hack.py     # CDP message injection
│   ├── inspect_tv.py             # Library inspector
│   └── inspect_tv_source.py      # Source inspector
│
├── test_scripts/                 # Debug & test scripts
│   ├── test_go_to_date.py        # Date navigation tests
│   ├── test_export_only.py       # Export functionality test
│   ├── find_menu_items.py        # UI element finder
│   ├── find_replay_btn.py        # Replay button finder
│   └── inspect_page.py           # Page inspector
│
├── data/                         # Parquet data storage
│   ├── ES_1m.parquet
│   ├── ES_5m.parquet
│   ├── ES_15m.parquet
│   ├── ES_1h.parquet
│   ├── ES_4h.parquet
│   └── ES_1D.parquet
│
├── downloads_es_futures/         # Raw CSV downloads
│   └── ES1_1m_*.csv
│
├── backup/                       # Backup files
│
├── credentials.json              # TradingView credentials
├── requirements.txt              # Python dependencies
├── INDICATORS.md                 # Indicator system docs
├── CHART_COMPARISON.md           # Chart library comparison
└── README.md                     # This file
```

## 🚀 Quick Start

### 1. Download Data
```bash
cd selenium_downloader
.\launch_chrome.bat
# Login to TradingView, open ES1! chart
python download_ohlc_selenium_enhanced.py
```

### 2. Process Data
```bash
cd ../data_processing
python process_market_data.py
python convert_to_parquet.py
```

### 3. Launch Chart
```bash
cd ../chart_ui
python chart_server.py
# Open http://localhost:8000
```

## 📊 Chart Options

### Main Chart (Lightweight Charts v5.0)
- **URL**: `http://localhost:8000`
- **Features**: 
    - **Multi-Ticker**: Support for ES1, NQ1, etc.
    - **Volume Support**: Histogram overlay
    - **Drawing Tools**: Trend Line, Rectangle, Fibonacci, Vertical Line, Anchored Text
    - **Indicators**: SMA, EMA, VWAP, Bollinger Bands, RSI, MACD, ATR (Multi-pane support)
    - **Plugins**: Custom ported plugins (Vert, Text)
- **Indicators**: Select from dropdown menu

## 🔧 Key Scripts

### Data Download
- **Main**: `selenium_downloader/download_ohlc_selenium_enhanced.py`
- **Features**: Bar Replay mode, auto-resume, file renaming
- **Target**: 3 months of 1-minute data

### Data Processing
- **Stitch**: `data_processing/process_market_data.py` - Combines CSVs
- **Convert**: `data_processing/convert_to_parquet.py` - Creates timeframes

### Chart Server
- **Backend**: `chart_ui/chart_server.py` - FastAPI + indicator API
- **Frontend**: `chart_ui/chart_ui.html` - Lightweight Charts UI

## 📝 Documentation

- **Indicators**: See `INDICATORS.md` for adding custom indicators
- **Chart Comparison**: See `CHART_COMPARISON.md` for library options

## 🛠 Dependencies

```bash
pip install -r requirements.txt
```

## 📈 Data Flow

```
TradingView → Selenium → CSV → Parquet → FastAPI → Chart UI
                ↓
          downloads_es_futures/
                ↓
          process_market_data.py
                ↓
          ES_1m_continuous.csv
                ↓
          convert_to_parquet.py
                ↓
            data/*.parquet
                ↓
          chart_server.py (API)
                ↓
          Browser (localhost:8000)
```

## 🎯 Next Steps

1. ✅ Organized codebase
2. ⏳ Choose chart library (KLineChart vs Lightweight Charts)
3. ⏳ Implement strategy testing
4. ⏳ Add more custom indicators
5. ⏳ Build backtesting engine

## 📦 Git Workflow

```bash
git status                    # Check changes
git add .                     # Stage all
git commit -m "message"       # Commit
git push origin main          # Push to GitHub
```

## 🔐 Credentials

Store TradingView credentials in `credentials.json`:
```json
{
  "username": "your_email",
  "password": "your_password"
}
```

## ⚡ Performance

- **Data Size**: ~100K bars = ~10MB Parquet
- **Chart Load**: <2 seconds for 20K bars
- **Indicator Calc**: <500ms for most indicators

## 📞 Support

Check individual directories for specific README files.
