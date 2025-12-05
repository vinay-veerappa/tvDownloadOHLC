import { setupChart } from './chart_setup.js';
import { loadTickers, loadData, changeTimeframe, jumpToDate, loadTimeframes } from './data_loader.js';
import { setTool, clearDrawings, setupDrawingHandlers } from './drawings.js';
import { toggleStrategy, runStrategy } from './strategy.js';
import { loadAndApplyPlugin, updatePluginList, removePlugin, clearAllPlugins, togglePluginManager } from './plugins.js';
import { addIndicator, addWatermark } from './indicators.js';
import { setupModalListeners, renderLegend } from './ui.js';
import { state } from './state.js';

import { TrendLine } from '../trendline_plugin.js';
import { Rectangle } from '../plugins/rectangle-drawing-tool.js';
import { VertLine } from '../vertical_line_plugin.js';
import { FibonacciRetracement } from '../fibonacci_plugin.js';

// Initialize Application
function initApp() {
    console.log('🚀 Initializing Chart App...');

    // Expose Primitives for drawings.js
    window.TrendLine = TrendLine;
    window.Rectangle = Rectangle;
    window.VertLine = VertLine;
    window.FibonacciRetracement = FibonacciRetracement;

    // 1. Setup Chart
    setupChart('chart');

    // 2. Setup Drawing Handlers
    setupDrawingHandlers();

    // 3. Setup UI Listeners
    setupModalListeners();

    // 4. Expose Functions Globally (for HTML onclick handlers)
    window.changeTimeframe = changeTimeframe;
    window.setTool = setTool;
    window.clearDrawings = clearDrawings;
    window.jumpToDate = jumpToDate;
    window.toggleStrategy = toggleStrategy;
    window.addIndicator = addIndicator;
    window.addWatermark = addWatermark;

    // Plugin functions
    window.loadAndApplyPlugin = loadAndApplyPlugin;
    window.updatePluginList = updatePluginList;
    window.removePlugin = removePlugin;
    window.clearAllPlugins = clearAllPlugins;
    window.togglePluginManager = togglePluginManager;

    // Indicator removal
    window.removeIndicator = (name, params) => {
        if (state.indicatorManager) {
            state.indicatorManager.removeIndicator(name, params);
            renderLegend();
        }
    };

    // 5. Event Listeners
    document.getElementById('ticker').addEventListener('change', (e) => {
        state.currentTicker = e.target.value;
        loadTimeframes(state.currentTicker);
        loadData(state.currentTimeframe);
        renderLegend();
    });

    document.getElementById('timezone').addEventListener('change', (e) => {
        state.currentTimezone = e.target.value;
        window.chart.applyOptions({
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
        renderLegend();
    });

    // 6. Initial Data Load
    loadTickers();
    loadData('1h');
    renderLegend();

    console.log('✅ App Initialized');
}

// Start when LightweightCharts is ready
if (window.LightweightCharts) {
    initApp();
} else {
    window.addEventListener('lightweightChartsReady', initApp);
}
