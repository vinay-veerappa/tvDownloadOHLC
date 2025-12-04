import { loadAndApplyPlugin } from './plugins.js';
import { addIndicator } from './indicators.js';

// Configuration of available items
const availableItems = [
    // Indicators
    { id: 'sma', name: 'SMA (Simple Moving Average)', type: 'indicator', category: 'Trend', desc: 'The Simple Moving Average is the unweighted mean of the previous n data.' },
    { id: 'ema', name: 'EMA (Exponential Moving Average)', type: 'indicator', category: 'Trend', desc: 'The Exponential Moving Average is a type of moving average that places a greater weight and significance on the most recent data points.' },
    { id: 'vwap', name: 'VWAP (Volume Weighted Average Price)', type: 'indicator', category: 'Trend', desc: 'The Volume Weighted Average Price (VWAP) is a trading benchmark used by traders that gives the average price a security has traded at throughout the day, based on both volume and price.' },
    { id: 'bb', name: 'Bollinger Bands', type: 'indicator', category: 'Volatility', desc: 'Bollinger Bands are a type of statistical chart characterizing the prices and volatility over time of a financial instrument or commodity.' },
    { id: 'rsi', name: 'RSI (Relative Strength Index)', type: 'indicator', category: 'Oscillators', desc: 'The Relative Strength Index (RSI) is a momentum indicator used in technical analysis that measures the magnitude of recent price changes to evaluate overbought or oversold conditions.' },
    { id: 'macd', name: 'MACD (Moving Average Convergence Divergence)', type: 'indicator', category: 'Oscillators', desc: 'MACD is a trend-following momentum indicator that shows the relationship between two moving averages of a security’s price.' },
    { id: 'atr', name: 'ATR (Average True Range)', type: 'indicator', category: 'Volatility', desc: 'The Average True Range (ATR) is a technical analysis indicator that measures market volatility by decomposing the entire range of an asset price for that period.' },

    // Plugins - Tooltips
    { id: 'tooltip', name: 'Crosshair Tooltip', type: 'plugin', category: 'Tooltips', module: 'tooltip', pluginType: 'primitive', desc: 'Displays data values at the crosshair position.' },
    { id: 'delta-tooltip', name: 'Delta Tooltip', type: 'plugin', category: 'Tooltips', module: 'delta-tooltip', pluginType: 'primitive', desc: 'Displays the price difference between two points.' },

    // Plugins - Visual
    { id: 'volume-profile', name: 'Volume Profile', type: 'plugin', category: 'Volume', module: 'volume-profile', pluginType: 'primitive', desc: 'Displays trading activity over a specified time period at specified price levels.' },
    { id: 'session-highlighting', name: 'Session Highlighting', type: 'plugin', category: 'Visuals', module: 'session-highlighting', pluginType: 'primitive', desc: 'Highlights trading sessions (RTH, ETH) on the chart.' },

    // Plugins - Price Lines
    { id: 'user-price-lines', name: 'User Price Lines', type: 'plugin', category: 'Drawing', module: 'user-price-lines', pluginType: 'primitive', desc: 'Allows users to draw horizontal price lines.' },
    { id: 'user-price-alerts', name: 'Price Alerts', type: 'plugin', category: 'Alerts', module: 'user-price-alerts', pluginType: 'primitive', desc: 'Set alerts at specific price levels.' },

    // Plugin Indicators
    { id: 'moving-average', name: 'Moving Average (Plugin)', type: 'plugin', category: 'Trend', module: 'moving-average', pluginType: 'indicator', desc: 'Moving Average implemented as a plugin.' },
    { id: 'momentum', name: 'Momentum', type: 'plugin', category: 'Oscillators', module: 'momentum', pluginType: 'indicator', desc: 'Momentum indicator.' },
    { id: 'average-price', name: 'Average Price', type: 'plugin', category: 'Price Analysis', module: 'average-price', pluginType: 'indicator', desc: 'Calculates the average price.' },
    { id: 'median-price', name: 'Median Price', type: 'plugin', category: 'Price Analysis', module: 'median-price', pluginType: 'indicator', desc: 'Calculates the median price.' },
    { id: 'weighted-close', name: 'Weighted Close', type: 'plugin', category: 'Price Analysis', module: 'weighted-close', pluginType: 'indicator', desc: 'Calculates the weighted close price.' },
    { id: 'percent-change', name: 'Percent Change', type: 'plugin', category: 'Price Analysis', module: 'percent-change', pluginType: 'indicator', desc: 'Calculates the percentage change in price.' }
];

let currentCategory = 'All';

export function openIndicatorsModal() {
    const modal = document.getElementById('indicators-modal');
    modal.classList.add('active');
    renderCategories();
    renderItems();
    document.getElementById('indicator-search').focus();
}

export function closeIndicatorsModal() {
    const modal = document.getElementById('indicators-modal');
    modal.classList.remove('active');
}

function renderCategories() {
    const categories = ['All', ...new Set(availableItems.map(item => item.category))].sort();
    const container = document.getElementById('modal-categories');

    container.innerHTML = categories.map(cat => `
        <button class="category-btn ${cat === currentCategory ? 'active' : ''}" 
                onclick="window.selectCategory('${cat}')">
            ${cat}
        </button>
    `).join('');
}

export function selectCategory(cat) {
    currentCategory = cat;
    renderCategories(); // Re-render to update active class
    renderItems();
}

function renderItems() {
    const container = document.getElementById('modal-items');
    const searchTerm = document.getElementById('indicator-search').value.toLowerCase();

    const filtered = availableItems.filter(item => {
        const matchesCategory = currentCategory === 'All' || item.category === currentCategory;
        const matchesSearch = item.name.toLowerCase().includes(searchTerm) ||
            (item.desc && item.desc.toLowerCase().includes(searchTerm));
        return matchesCategory && matchesSearch;
    });

    if (filtered.length === 0) {
        container.innerHTML = '<div style="color: #888; text-align: center; padding: 20px;">No results found</div>';
        return;
    }

    container.innerHTML = filtered.map(item => `
        <div class="item-card" onclick="window.addItem('${item.id}')">
            <div>
                <div class="item-name">${item.name}</div>
                <div class="item-desc">${item.desc}</div>
            </div>
            <div class="item-tags">
                <span class="item-tag">${item.category}</span>
                <span class="item-tag">${item.type === 'plugin' ? 'Plugin' : 'Built-in'}</span>
            </div>
        </div>
    `).join('');
}

export async function addItem(id) {
    const item = availableItems.find(i => i.id === id);
    if (!item) return;

    if (item.type === 'indicator') {
        await addIndicator(item.id);
        alert(`Added ${item.name}`);
    } else if (item.type === 'plugin') {
        await loadAndApplyPlugin(item.module, item.name, item.pluginType);
        // loadAndApplyPlugin handles alerts
    }
}

export function setupModalListeners() {
    document.getElementById('indicator-search').addEventListener('input', renderItems);

    // Close on click outside
    document.getElementById('indicators-modal').addEventListener('click', (e) => {
        if (e.target.id === 'indicators-modal') {
            closeIndicatorsModal();
        }
    });

    // Expose functions for onclick
    window.selectCategory = selectCategory;
    window.addItem = addItem;
    window.openIndicatorsModal = openIndicatorsModal;
    window.closeIndicatorsModal = closeIndicatorsModal;
}
