# Indicator System Documentation

## Overview
A modular, extensible indicator system for ES Futures charting.

## Architecture

```
┌─────────────────┐
│  Frontend (JS)  │  ← Indicator Manager
│  Chart UI       │  ← Renders indicators
└────────┬────────┘
         │ REST API
┌────────▼────────┐
│  Backend (Py)   │  ← FastAPI Server
│  chart_server   │  ← Calculates indicators
└────────┬────────┘
         │
┌────────▼────────┐
│  indicators.py  │  ← Pure calculation library
│  Modular calcs  │  ← No dependencies on API
└─────────────────┘
```

## Available Indicators

### Overlay Indicators (on price chart)
1. **SMA** - Simple Moving Average
   - Parameter: `period` (default: 20)
   - Example: SMA(50), SMA(200)

2. **EMA** - Exponential Moving Average
   - Parameter: `period` (default: 20)
   - Example: EMA(9), EMA(21)

3. **Bollinger Bands**
   - Parameters: `period` (20), `std_dev` (2)
   - Returns: upper, middle, lower bands

4. **VWAP** - Volume Weighted Average Price
   - No parameters
   - Uses typical price approximation

5. **ATR** - Average True Range
   - Parameter: `period` (default: 14)

### Oscillator Indicators (require separate pane)
6. **RSI** - Relative Strength Index
   - Parameter: `period` (default: 14)
   - Range: 0-100

7. **MACD** - Moving Average Convergence Divergence
   - Parameters: `fast` (12), `slow` (26), `signal` (9)
   - Returns: macd, signal, histogram

## Usage Examples

### Backend (Python API)

```python
# Get SMA(20) for 1-hour chart
GET /api/indicator/1h/sma?period=20&limit=1000

# Get Bollinger Bands
GET /api/indicator/1h/bb?period=20&std_dev=2

# Get MACD
GET /api/indicator/1h/macd?fast=12&slow=26&signal=9
```

### Frontend (JavaScript)

```javascript
// Create indicator manager
const indicators = new IndicatorManager(chart, candlestickSeries);

// Add SMA(50)
await indicators.addIndicator('sma', '1h', { period: 50 });

// Add EMA(20)
await indicators.addIndicator('ema', '1h', { period: 20 });

// Add Bollinger Bands
await indicators.addIndicator('bb', '1h', { period: 20, std_dev: 2 });

// Remove an indicator
indicators.removeIndicator('sma', { period: 50 });

// Remove all
indicators.removeAll();

// List active indicators
console.log(indicators.listActive());
```

## Adding New Indicators

### Step 1: Add calculation function to `indicators.py`

```python
@staticmethod
def my_indicator(data, param1=10, param2=20):
    """Your indicator description"""
    df = pd.DataFrame(data)
    # Your calculation logic here
    df['result'] = ...  # calculate
    return df['result'].dropna().tolist()
```

### Step 2: Register in `calculate_indicator()` function

```python
elif indicator_name == 'my_indicator':
    param1 = params.get('param1', 10)
    param2 = params.get('param2', 20)
    return {'values': indicators.my_indicator(data, param1, param2)}
```

### Step 3: Add rendering logic to `indicator_manager.js`

```javascript
case 'my_indicator':
    const series = this.chart.addLineSeries({
        color: color,
        lineWidth: 2,
        title: 'My Indicator'
    });
    series.setData(data);
    return series;
```

## Best Practices

1. **Modularity**: Keep calculation logic separate from API/UI
2. **Parameters**: Always provide sensible defaults
3. **Performance**: Use `limit` parameter to avoid loading too much data
4. **Validation**: Handle edge cases (insufficient data, invalid params)
5. **Documentation**: Document parameters and return format

## Future Enhancements

- [ ] Separate panes for oscillators (RSI, MACD)
- [ ] Custom indicator colors/styles
- [ ] Indicator presets/templates
- [ ] Save/load indicator configurations
- [ ] Real-time indicator updates
- [ ] Performance optimization (server-side caching)

## File Structure

```
tvDownloadOHLC/
├── indicators.py           # Pure calculation library
├── chart_server.py         # API with /api/indicator endpoint
├── indicator_manager.js    # Frontend manager class
├── create_html.py          # UI generator
└── INDICATORS.md           # This file
```

## Testing

Test individual indicators:

```bash
# Test API endpoint
curl "http://localhost:8000/api/indicator/1h/sma?period=20"

# In browser console
indicators.addIndicator('sma', '1h', { period: 50 });
```
