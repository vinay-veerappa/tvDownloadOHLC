# Python Indicator API

FastAPI service for technical indicator calculations using pandas-ta.

## Architecture Decision

### Data Flow

| Use Case | Data Source | Why |
|----------|-------------|-----|
| **Chart indicators** | Frontend sends OHLCV | 100% matches displayed data |
| **Backtesting** | Python reads JSON chunks | Same source as chart |
| **Derived timeframes** | Python aggregates base data | Same logic as TypeScript |

### Consistency Guarantee

- **Chart display** and **indicators** use exact same OHLCV data
- **Backtesting** reads from same JSON chunks as frontend
- **Resampling logic** in `api/services/resampling.py` matches `web/lib/resampling.ts`

---

## Running the Service

```bash
# From project root
.venv\Scripts\python -m uvicorn api.main:app --reload --port 8000
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/indicators/calculate` | POST | Calculate from client OHLCV (for chart) |
| `/api/indicators/calculate-from-file` | POST | Calculate from stored data (for backtest) |
| `/api/indicators/available` | GET | List available indicators |
| `/api/indicators/data` | GET | List available ticker/timeframe files |
| `/health` | GET | Health check |

## Available Indicators

- **vwap** - Volume Weighted Average Price
- **sma_{period}** - Simple Moving Average (e.g., sma_20)
- **ema_{period}** - Exponential Moving Average (e.g., ema_9)
- **atr_{period}** - Average True Range (e.g., atr_14)
- **rsi_{period}** - Relative Strength Index (e.g., rsi_14)
- **bbands_{period}** - Bollinger Bands (returns upper, mid, lower)
- **macd** - MACD (returns line, signal, histogram)

## Example Usage

### Chart Indicator (from frontend OHLCV)

```javascript
const response = await fetch('http://localhost:8000/api/indicators/calculate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    ohlcv: chartData,  // Array of {time, open, high, low, close, volume}
    indicators: ['vwap', 'sma_20', 'ema_9']
  })
});
const { indicators } = await response.json();
// indicators = { vwap: [...], sma_20: [...], ema_9: [...] }
```

### Backtest (from stored files)

```bash
curl -X POST http://localhost:8000/api/indicators/calculate-from-file \
  -H "Content-Type: application/json" \
  -d '{"ticker":"ES1","timeframe":"5m","indicators":["vwap","sma_20"]}'
```
