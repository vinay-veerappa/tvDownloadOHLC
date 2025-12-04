import { state } from './state.js';

export function setupChart(containerId) {
    if (!window.LightweightCharts) {
        document.getElementById('status').textContent = 'Error: Library not loaded.';
        throw new Error('LightweightCharts not found');
    }

    const chart = window.LightweightCharts.createChart(document.getElementById(containerId), {
        autoSize: true,
        layout: { background: { color: '#1e222d' }, textColor: '#d1d4dc' },
        grid: { vertLines: { color: '#2a2e39' }, horzLines: { color: '#2a2e39' } },
        timeScale: { timeVisible: true, rightOffset: 5 },
        crosshair: { mode: window.LightweightCharts.CrosshairMode.Normal },
        localization: {
            timeFormatter: function (timestamp) {
                const date = new Date(timestamp * 1000);
                return date.toLocaleString('en-US', {
                    timeZone: state.currentTimezone,
                    month: 'short', day: 'numeric',
                    hour: '2-digit', minute: '2-digit', hour12: false
                });
            }
        }
    });

    // Main Series (Candlestick) - v5 Syntax
    const series = chart.addSeries(window.LightweightCharts.CandlestickSeries, {
        upColor: '#26a69a', downColor: '#ef5350',
        wickUpColor: '#26a69a', wickDownColor: '#ef5350'
    });

    // Expose globally for plugins and console access
    window.chart = chart;
    window.chartSeries = series;

    // Handle resize
    window.addEventListener('resize', () => {
        chart.applyOptions({ width: window.innerWidth, height: window.innerHeight - 54 });
    });

    return { chart, series };
}
