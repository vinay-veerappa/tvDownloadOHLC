import { state } from './state.js';

export async function addIndicatorFromMenu(select) {
    const type = select.value;
    select.value = ""; // Reset

    if (!state.indicatorManager) {
        // Need to import IndicatorManager dynamically or assume it's loaded
        // Since IndicatorManager is a class in indicator_manager.js (not a module yet), 
        // we rely on it being loaded via script tag or we should modularize it.
        // For now, let's assume it's available on window or we import it.

        // Better: Modularize IndicatorManager. But it's a separate file.
        // Let's assume window.IndicatorManager exists for now (from script tag).
        if (window.IndicatorManager) {
            state.indicatorManager = new window.IndicatorManager(window.chart, window.chartSeries, 'indicator-container');
        } else {
            console.error("IndicatorManager not found");
            return;
        }
    }

    let params = {};
    if (type === 'sma') params = { period: 20 };
    if (type === 'ema') params = { period: 50 };
    if (type === 'bb') params = { period: 20, stdDev: 2 };
    if (type === 'vwap') params = {};
    if (type === 'rsi') params = { period: 14 };
    if (type === 'macd') params = { fast: 12, slow: 26, signal: 9 };
    if (type === 'atr') params = { period: 14 };

    await state.indicatorManager.addIndicator(type, state.currentTimeframe, params, state.currentTicker);
}

export function addWatermark() {
    if (window.AnchoredText) {
        const text = new window.AnchoredText({
            text: 'ES Futures ' + state.currentTimeframe,
            vertAlign: 'top',
            horzAlign: 'right',
            color: 'rgba(255, 255, 255, 0.5)',
            font: 'bold 24px Arial'
        });
        window.chartSeries.attachPrimitive(text);
        state.drawings.push(text);
    }
}
