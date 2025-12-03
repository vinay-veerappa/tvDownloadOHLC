// Indicator Manager for Lightweight Charts
// Provides modular indicator overlay system

class IndicatorManager {
    constructor(chart, candlestickSeries) {
        this.chart = chart;
        this.candlestickSeries = candlestickSeries;
        this.indicators = new Map(); // Store active indicators
        this.colors = ['#2962FF', '#FF6D00', '#00C853', '#D500F9', '#FFD600'];
        this.colorIndex = 0;
    }

    async addIndicator(name, timeframe, params = {}) {
        const key = `${name}_${JSON.stringify(params)}`;

        if (this.indicators.has(key)) {
            console.log(`Indicator ${name} already exists`);
            return;
        }

        try {
            // Build query string
            const queryParams = new URLSearchParams({
                limit: '20000',
                ...params
            });

            const response = await fetch(
                `http://localhost:8000/api/indicator/${timeframe}/${name}?${queryParams}`
            );
            const result = await response.json();

            // Add to chart based on indicator type
            const indicator = this._createIndicator(name, result.data, params);
            this.indicators.set(key, { name, series: indicator, params });

            return indicator;
        } catch (error) {
            console.error(`Error adding indicator ${name}:`, error);
        }
    }

    _createIndicator(name, data, params) {
        const color = this.colors[this.colorIndex % this.colors.length];
        this.colorIndex++;

        switch (name) {
            case 'sma':
            case 'ema':
            case 'vwap':
                // Single line series
                const lineSeries = this.chart.addLineSeries({
                    color: color,
                    lineWidth: 2,
                    title: `${name.toUpperCase()}(${params.period || ''})`,
                    priceLineVisible: false,
                    lastValueVisible: true
                });
                lineSeries.setData(data);
                return lineSeries;

            case 'bb':
                // Bollinger Bands - 3 lines
                const upperSeries = this.chart.addLineSeries({
                    color: '#2962FF',
                    lineWidth: 1,
                    title: 'BB Upper',
                    priceLineVisible: false
                });
                const middleSeries = this.chart.addLineSeries({
                    color: '#2962FF',
                    lineWidth: 2,
                    title: 'BB Middle',
                    priceLineVisible: false
                });
                const lowerSeries = this.chart.addLineSeries({
                    color: '#2962FF',
                    lineWidth: 1,
                    title: 'BB Lower',
                    priceLineVisible: false
                });

                upperSeries.setData(data.map(d => ({ time: d.time, value: d.upper })));
                middleSeries.setData(data.map(d => ({ time: d.time, value: d.middle })));
                lowerSeries.setData(data.map(d => ({ time: d.time, value: d.lower })));

                return { upper: upperSeries, middle: middleSeries, lower: lowerSeries };

            case 'rsi':
            case 'macd':
            case 'atr':
                console.warn(`${name} requires separate pane - not yet implemented`);
                return null;

            default:
                console.error(`Unknown indicator: ${name}`);
                return null;
        }
    }

    removeIndicator(name, params = {}) {
        const key = `${name}_${JSON.stringify(params)}`;
        const indicator = this.indicators.get(key);

        if (indicator) {
            if (Array.isArray(indicator.series)) {
                indicator.series.forEach(s => this.chart.removeSeries(s));
            } else if (typeof indicator.series === 'object' && indicator.series.upper) {
                // Bollinger Bands
                this.chart.removeSeries(indicator.series.upper);
                this.chart.removeSeries(indicator.series.middle);
                this.chart.removeSeries(indicator.series.lower);
            } else {
                this.chart.removeSeries(indicator.series);
            }
            this.indicators.delete(key);
        }
    }

    removeAll() {
        this.indicators.forEach((indicator, key) => {
            this.removeIndicator(indicator.name, indicator.params);
        });
    }

    listActive() {
        return Array.from(this.indicators.keys());
    }
}

// Export for use in HTML
window.IndicatorManager = IndicatorManager;
