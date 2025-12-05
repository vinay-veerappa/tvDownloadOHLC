import { state } from './state.js';
import { runStrategy } from './strategy.js';
import { renderLegend } from './ui.js';

export async function loadTickers() {
    try {
        const response = await fetch('/api/tickers');
        const result = await response.json();
        const tickerSelect = document.getElementById('ticker');
        const current = state.currentTicker;

        // Clear existing options
        tickerSelect.innerHTML = '';

        if (result.tickers && result.tickers.length > 0) {
            result.tickers.forEach(t => {
                const option = document.createElement('option');
                option.value = t;
                option.text = t;
                if (t === current) option.selected = true;
                tickerSelect.appendChild(option);
            });

            // If current ticker is not in the list, switch to the first available one
            if (!result.tickers.includes(current)) {
                state.currentTicker = result.tickers[0];
                tickerSelect.value = state.currentTicker;
                loadData(state.currentTimeframe);
            }
        }

        // Also load timeframes for this ticker
        loadTimeframes(state.currentTicker);

    } catch (error) {
        console.error('Error loading tickers:', error);
    }
}

export async function loadTimeframes(ticker) {
    try {
        const response = await fetch(`/api/timeframes?ticker=${ticker}`);
        const result = await response.json();
        const select = document.getElementById('more-timeframes');

        // Default options
        const defaults = ['1m', '5m', '15m', '30m', '1h', '4h', '1D', '1W'];
        const allOptions = new Set([...defaults, ...result.timeframes]);

        select.innerHTML = '<option value="" disabled selected>▼</option>';
        Array.from(allOptions).sort().forEach(tf => {
            const option = document.createElement('option');
            option.value = tf;
            option.text = tf;
            select.appendChild(option);
        });
    } catch (e) {
        console.error(e);
    }
}

export function changeTimeframe(tf) {
    if (!tf) return;
    state.currentTimeframe = tf;

    // Update buttons
    document.querySelectorAll('#tf-buttons button').forEach(b => {
        if (b.dataset.tf === tf) b.classList.add('active');
        else b.classList.remove('active');
    });

    // Update custom input if it's a custom value
    const customInput = document.getElementById('custom-tf');
    const isStandard = ['1m', '5m', '15m', '1h', '4h', '1D'].includes(tf);
    if (!isStandard) {
        customInput.value = tf;
        customInput.classList.add('active');
    } else {
        customInput.value = '';
        customInput.classList.remove('active');
    }

    // Reset dropdown
    document.getElementById('more-timeframes').value = "";

    loadData(tf);
    renderLegend(); // Update legend header
}

export async function loadData(timeframe) {
    document.getElementById('status').textContent = 'Loading...';
    const chart = window.chart;
    const series = window.chartSeries;

    try {
        const response = await fetch(`http://localhost:8000/api/ohlc/${timeframe}?limit=20000&ticker=${state.currentTicker}`);
        const result = await response.json();

        if (!result.data || !Array.isArray(result.data)) {
            throw new Error('Invalid data format');
        }

        state.allData = result.data; // Store for navigation
        series.setData(state.allData);
        // volumeSeries.setData(allData);

        // Calculate PDH/PDL
        calculatePDHPDL(state.allData);

        chart.timeScale().fitContent();
        document.getElementById('status').textContent = `${state.allData.length.toLocaleString()} bars`;

        // Re-run strategy if active
        if (state.isStrategyActive) runStrategy();

    } catch (error) {
        console.error(error);
        document.getElementById('status').textContent = 'Error: ' + error.message;
    }
}

function calculatePDHPDL(data) {
    const series = window.chartSeries;
    if (data.length === 0) return;

    const lastBar = data[data.length - 1];
    const lastDate = new Date(lastBar.time * 1000);
    lastDate.setHours(0, 0, 0, 0);
    const todayStart = Math.floor(lastDate.getTime() / 1000);
    const yesterdayStart = todayStart - 86400;

    const yesterdayBars = data.filter(bar => bar.time >= yesterdayStart && bar.time < todayStart);

    if (state.pdhLine) series.removePriceLine(state.pdhLine);
    if (state.pdlLine) series.removePriceLine(state.pdlLine);

    if (yesterdayBars.length > 0) {
        const pdh = Math.max(...yesterdayBars.map(b => b.high));
        const pdl = Math.min(...yesterdayBars.map(b => b.low));

        state.pdhLine = series.createPriceLine({
            price: pdh, color: '#2962FF', lineWidth: 2, lineStyle: 2,
            axisLabelVisible: true, title: 'PDH'
        });
        state.pdlLine = series.createPriceLine({
            price: pdl, color: '#FF6D00', lineWidth: 2, lineStyle: 2,
            axisLabelVisible: true, title: 'PDL'
        });
    }
}

export function jumpToDate() {
    const dateStr = document.getElementById('datePicker').value;
    if (!dateStr) return;

    const targetDate = new Date(dateStr).getTime() / 1000;
    // Find closest bar
    const targetIndex = state.allData.findIndex(d => d.time >= targetDate);

    if (targetIndex !== -1) {
        const range = 100; // Show 100 bars
        const from = Math.max(0, targetIndex - range / 2);
        const to = Math.min(state.allData.length - 1, targetIndex + range / 2);
        window.chart.timeScale().setVisibleLogicalRange({ from, to });
    } else {
        alert('Date not found in loaded data');
    }
}
