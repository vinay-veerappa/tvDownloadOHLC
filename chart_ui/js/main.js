import { setupChart } from './chart_setup.js';
import { loadTickers, loadData, changeTimeframe, jumpToDate } from './data_loader.js';
import { setTool, clearDrawings, setupDrawingHandlers } from './drawings.js';
import { toggleStrategy, runStrategy } from './strategy.js';
import { loadAndApplyPlugin, updatePluginList, removePlugin, clearAllPlugins, togglePluginManager } from './plugins.js';
import { addIndicator, addWatermark } from './indicators.js';
import { setupModalListeners } from './ui.js';
import { state } from './state.js';

// Initialize Application
function initApp() {
    console.log('🚀 Initializing Chart App...');

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

    // 4. Initial Data Load
    loadTickers();
    loadData('1h');

    console.log('✅ App Initialized');
}

// Start when LightweightCharts is ready
if (window.LightweightCharts) {
    initApp();
} else {
    window.addEventListener('lightweightChartsReady', initApp);
}
