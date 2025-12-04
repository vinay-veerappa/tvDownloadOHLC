import { state } from './state.js';

export function runStrategy() {
    // Simple SMA Crossover Logic for Demo
    // v5.0 Workaround: Use PriceLines instead of Markers (since markers are now a plugin)

    const series = window.chartSeries;
    const allData = state.allData;

    let position = 0;

    for (let i = 1; i < allData.length; i++) {
        const prev = allData[i - 1];
        const curr = allData[i];

        // Green Candle = Buy, Red Candle = Sell (Simple Visual Test)
        if (position === 0 && curr.close > curr.open && prev.close < prev.open) {
            position = 1;
            const line = series.createPriceLine({
                price: curr.close, color: '#2196F3', lineWidth: 1, lineStyle: 0,
                axisLabelVisible: true, title: 'BUY'
            });
            state.strategyLines.push(line);
        } else if (position === 1 && curr.close < curr.open) {
            position = 0;
            const line = series.createPriceLine({
                price: curr.close, color: '#E91E63', lineWidth: 1, lineStyle: 0,
                axisLabelVisible: true, title: 'SELL'
            });
            state.strategyLines.push(line);
        }
    }
}

export function toggleStrategy() {
    state.isStrategyActive = !state.isStrategyActive;
    const btn = document.getElementById('strategyBtn');
    const series = window.chartSeries;

    if (state.isStrategyActive) {
        btn.classList.add('active');
        runStrategy();
    } else {
        btn.classList.remove('active');
        // Clear strategy lines
        state.strategyLines.forEach(l => series.removePriceLine(l));
        state.strategyLines = [];
    }
}
