// Indicator Manager for Lightweight Charts v5.0
// Supports Main Chart Overlays and Separate Panes

class IndicatorManager {
    constructor(chart, mainSeries, containerId) {
        this.mainChart = chart;
        this.mainSeries = mainSeries;
        this.container = document.getElementById(containerId);
        this.indicators = new Map(); // Store active indicators
        this.panes = []; // Store separate chart instances
        this.colors = ['#2962FF', '#FF6D00', '#00C853', '#D500F9', '#FFD600'];
        this.colorIndex = 0;
    }

    async addIndicator(name, timeframe, params = {}, ticker = 'ES1') {
        const key = `${name}_${JSON.stringify(params)}`;

        if (this.indicators.has(key)) {
            console.log(`Indicator ${name} already exists`);
            return;
        }

        try {
            // Build query string
            const queryParams = new URLSearchParams({
                limit: '20000',
                ticker: ticker,
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
                // Overlay on Main Chart
                const lineSeries = this.mainChart.addSeries(window.LightweightCharts.LineSeries, {
                    color: color,
                    lineWidth: 2,
                    title: `${name.toUpperCase()}(${params.period || ''})`,
                    priceLineVisible: false,
                    lastValueVisible: true
                });
                lineSeries.setData(data);
                return lineSeries;

            case 'bb':
                // Overlay on Main Chart
                const upperSeries = this.mainChart.addSeries(window.LightweightCharts.LineSeries, {
                    color: '#2962FF', lineWidth: 1, title: 'BB Upper', priceLineVisible: false
                });
                const middleSeries = this.mainChart.addSeries(window.LightweightCharts.LineSeries, {
                    color: '#2962FF', lineWidth: 2, title: 'BB Middle', priceLineVisible: false
                });
                const lowerSeries = this.mainChart.addSeries(window.LightweightCharts.LineSeries, {
                    color: '#2962FF', lineWidth: 1, title: 'BB Lower', priceLineVisible: false
                });

                upperSeries.setData(data.map(d => ({ time: d.time, value: d.upper })));
                middleSeries.setData(data.map(d => ({ time: d.time, value: d.middle })));
                lowerSeries.setData(data.map(d => ({ time: d.time, value: d.lower })));

                return { upper: upperSeries, middle: middleSeries, lower: lowerSeries };

            case 'rsi':
            case 'atr':
                return this._createSeparatePane(name, data, params, (chart) => {
                    const series = chart.addSeries(window.LightweightCharts.LineSeries, {
                        color: color,
                        lineWidth: 2,
                        title: name.toUpperCase()
                    });
                    series.setData(data);

                    // Add levels for RSI
                    if (name === 'rsi') {
                        // v5.0: Use PriceLines for levels
                        series.createPriceLine({ price: 70, color: '#FF5252', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
                        series.createPriceLine({ price: 30, color: '#2962FF', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
                    }
                    return series;
                });

            case 'macd':
                return this._createSeparatePane(name, data, params, (chart) => {
                    const histogramSeries = chart.addSeries(window.LightweightCharts.HistogramSeries, {
                        color: '#26a69a',
                        priceFormat: { type: 'volume' },
                        priceScaleId: 'right',
                    });
                    const macdSeries = chart.addSeries(window.LightweightCharts.LineSeries, {
                        color: '#2962FF', lineWidth: 2, title: 'MACD'
                    });
                    const signalSeries = chart.addSeries(window.LightweightCharts.LineSeries, {
                        color: '#FF6D00', lineWidth: 2, title: 'Signal'
                    });

                    histogramSeries.setData(data.map(d => ({
                        time: d.time,
                        value: d.histogram,
                        color: d.histogram >= 0 ? '#26a69a' : '#ef5350'
                    })));
                    macdSeries.setData(data.map(d => ({ time: d.time, value: d.macd })));
                    signalSeries.setData(data.map(d => ({ time: d.time, value: d.signal })));

                    return { histogram: histogramSeries, macd: macdSeries, signal: signalSeries };
                });

            default:
                console.error(`Unknown indicator: ${name}`);
                return null;
        }
    }

    _createSeparatePane(name, data, params, createSeriesCallback) {
        // Create Container
        const paneId = `pane-${name}-${Date.now()}`;
        const paneDiv = document.createElement('div');
        paneDiv.id = paneId;
        paneDiv.style.width = '100%';
        paneDiv.style.height = '150px'; // Fixed height for now
        paneDiv.style.borderTop = '1px solid #363c4e';
        this.container.appendChild(paneDiv);

        // Create Chart
        const paneChart = window.LightweightCharts.createChart(paneDiv, {
            autoSize: true,
            height: 150,
            layout: { background: { color: '#1e222d' }, textColor: '#d1d4dc' },
            grid: { vertLines: { color: '#2a2e39' }, horzLines: { color: '#2a2e39' } },
            timeScale: { timeVisible: true, rightOffset: 5 },
            crosshair: { mode: window.LightweightCharts.CrosshairMode.Normal },
        });

        // Sync TimeScale
        // We need to sync both ways: Main -> Pane AND Pane -> Main
        // But to avoid infinite loops, we usually just sync Main -> Pane or use a master controller.
        // Simple sync:
        this.mainChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
            paneChart.timeScale().setVisibleLogicalRange(range);
        });
        paneChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
            this.mainChart.timeScale().setVisibleLogicalRange(range);
        });

        // Also sync Crosshair? Harder.

        // Create Series
        const series = createSeriesCallback(paneChart);

        this.panes.push({ id: paneId, chart: paneChart, div: paneDiv });

        return { chart: paneChart, series: series, paneId: paneId };
    }

    removeIndicator(name, params = {}) {
        const key = `${name}_${JSON.stringify(params)}`;
        const indicator = this.indicators.get(key);

        if (indicator) {
            if (indicator.series.paneId) {
                // Remove Separate Pane
                const paneIndex = this.panes.findIndex(p => p.id === indicator.series.paneId);
                if (paneIndex !== -1) {
                    const pane = this.panes[paneIndex];
                    pane.chart.remove(); // Destroy chart
                    pane.div.remove(); // Remove DOM
                    this.panes.splice(paneIndex, 1);
                }
            } else {
                // Remove Overlay Series
                if (Array.isArray(indicator.series)) {
                    indicator.series.forEach(s => this.mainChart.removeSeries(s));
                } else if (typeof indicator.series === 'object' && indicator.series.upper) {
                    this.mainChart.removeSeries(indicator.series.upper);
                    this.mainChart.removeSeries(indicator.series.middle);
                    this.mainChart.removeSeries(indicator.series.lower);
                } else {
                    this.mainChart.removeSeries(indicator.series);
                }
            }
            this.indicators.delete(key);
        }
    }

    removeAll() {
        this.indicators.forEach((indicator, key) => {
            this.removeIndicator(indicator.name, indicator.params);
        });
    }
}

window.IndicatorManager = IndicatorManager;
