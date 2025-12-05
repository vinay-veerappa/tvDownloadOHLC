import { state } from './state.js';
import { changeTimeframe } from './data_loader.js';
import { UserPriceLines } from '../plugins/user-price-lines.js';
import { DeltaTooltipPrimitive } from '../plugins/delta-tooltip.js';
import { UserPriceAlerts } from '../plugins/user-price-alerts.js';
import { RectangleDrawingTool, Rectangle } from '../plugins/rectangle-drawing-tool.js';

// Expose Rectangle class globally for hit testing
window.Rectangle = Rectangle;

console.log("Drawings module loaded (v9 - Measure & Alert Tools)");

export function setTool(tool) {
    state.currentTool = (state.currentTool === tool) ? null : tool; // Toggle
    state.activeDrawing = null;
    state.startPoint = null;

    // Cleanup all tools
    if (state.userPriceLinesTool && state.currentTool !== 'price_line') {
        state.userPriceLinesTool.remove();
        state.userPriceLinesTool = null;
    }
    if (state.userPriceAlertsTool && state.currentTool !== 'alert') {
        state.userPriceAlertsTool.detached();
        state.userPriceAlertsTool = null;
    }
    if (state.deltaTooltipTool && state.currentTool !== 'measure') {
        state.deltaTooltipTool.detached();
        window.chartSeries.detachPrimitive(state.deltaTooltipTool);
        state.deltaTooltipTool = null;
    }
    if (state.rectangleTool && state.currentTool !== 'rect') state.rectangleTool.stopDrawing();
    if (state.trendLineTool && state.currentTool !== 'ray') state.trendLineTool.stopDrawing();
    if (state.fibonacciTool && state.currentTool !== 'fib') state.fibonacciTool.stopDrawing();
    if (state.vertLineTool && state.currentTool !== 'vert') state.vertLineTool.stopDrawing();

    // Update UI
    document.querySelectorAll('button').forEach(b => b.classList.remove('active'));
    if (state.currentTool === 'ray') document.getElementById('btn-ray').classList.add('active');
    if (state.currentTool === 'rect') document.getElementById('btn-rect').classList.add('active');
    if (state.currentTool === 'fib') document.getElementById('btn-fib').classList.add('active');
    if (state.currentTool === 'vert') document.getElementById('btn-vert').classList.add('active');
    if (state.currentTool === 'price_line') document.getElementById('btn-price-line').classList.add('active');
    if (state.currentTool === 'alert') document.getElementById('btn-alert').classList.add('active');
    if (state.currentTool === 'measure') document.getElementById('btn-measure').classList.add('active');

    // Initialize Tools
    if (state.currentTool === 'price_line') {
        if (!state.userPriceLinesTool) {
            state.userPriceLinesTool = new UserPriceLines(window.chart, window.chartSeries, {
                color: '#2962FF',
                hoverColor: '#E91E63'
            });
        }
    }
    else if (state.currentTool === 'alert') {
        if (!state.userPriceAlertsTool) {
            state.userPriceAlertsTool = new UserPriceAlerts();
            window.chartSeries.attachPrimitive(state.userPriceAlertsTool);
        }
    }
    else if (state.currentTool === 'measure') {
        if (!state.deltaTooltipTool) {
            state.deltaTooltipTool = new DeltaTooltipPrimitive({
                lineColor: 'rgba(41, 98, 255, 0.5)',
                showTime: true
            });
            window.chartSeries.attachPrimitive(state.deltaTooltipTool);
        }
    }
    else if (state.currentTool === 'rect') {
        if (!state.rectangleTool) {
            state.rectangleTool = new RectangleDrawingTool(window.chart, window.chartSeries, null, {
                fillColor: 'rgba(33, 150, 243, 0.2)',
                previewFillColor: 'rgba(33, 150, 243, 0.1)',
                labelColor: '#2196F3',
                labelTextColor: 'white',
                showLabels: true
            });
        }
        state.rectangleTool.startDrawing();
    }
    else if (state.currentTool === 'ray') {
        if (!state.trendLineTool) {
            state.trendLineTool = new window.TrendLineTool(window.chart, window.chartSeries);
        }
        state.trendLineTool.startDrawing();
    }
    else if (state.currentTool === 'fib') {
        if (!state.fibonacciTool) {
            state.fibonacciTool = new window.FibonacciTool(window.chart, window.chartSeries);
        }
        state.fibonacciTool.startDrawing();
    }
    else if (state.currentTool === 'vert') {
        if (!state.vertLineTool) {
            state.vertLineTool = new window.VertLineTool(window.chart, window.chartSeries);
        }
        state.vertLineTool.startDrawing();
    }

    // Re-highlight active timeframe button
    changeTimeframe(state.currentTimeframe);

    document.body.style.cursor = state.currentTool ? 'crosshair' : 'default';
    window.chart.applyOptions({ handleScroll: !state.currentTool, handleScale: !state.currentTool });
}

export function clearDrawings() {
    const series = window.chartSeries;
    state.drawings.forEach(d => {
        if (d.detach) d.detach();
        try { series.detachPrimitive(d); } catch (e) { }
        if (series.removePriceLine) try { series.removePriceLine(d); } catch (e) { }
    });
    state.drawings = [];
    state.selectedDrawing = null;
    setTool(null);
}

export function setupDrawingHandlers() {
    const chart = window.chart;
    const series = window.chartSeries;

    // Listen for drawings created by plugins
    window.addEventListener('drawing-created', (e) => {
        if (e.detail && e.detail.drawing) {
            // Only add if not already in list (for partial updates)
            if (!state.drawings.includes(e.detail.drawing)) {
                console.log('New drawing created via event:', e.detail.type);
                state.drawings.push(e.detail.drawing);
            }

            // If it's a finished drawing (not partial), select it
            if (e.detail.partial === false) {
                selectDrawing(e.detail.drawing);
            }
        }
    });

    chart.subscribeClick((param) => {
        if (!param.point) return;

        // If not in a drawing tool mode, check for selection
        // Note: Drawing tools now handle their own clicks via startDrawing()
        if (!state.currentTool) {
            const hit = hitTest(param.point);
            selectDrawing(hit);
        }
    });

    // Delete Key
    document.addEventListener('keydown', (e) => {
        if ((e.key === 'Delete' || e.key === 'Backspace') && state.selectedDrawing) {
            deleteDrawing(state.selectedDrawing);
        }
    });

    // Properties Panel Listeners
    document.getElementById('prop-color').addEventListener('input', (e) => {
        if (state.selectedDrawing && state.selectedDrawing.applyOptions) {
            const color = e.target.value;
            const updates = {};
            if (state.selectedDrawing instanceof window.TrendLine) {
                updates.lineColor = color;
            }
            else if (state.selectedDrawing instanceof window.Rectangle) {
                updates.fillColor = color + 'BF'; // Add 75% opacity
                updates.labelColor = color;
            }
            else if (state.selectedDrawing instanceof window.VertLine) {
                updates.color = color;
            }
            else if (state.selectedDrawing.options && state.selectedDrawing.options().price !== undefined) {
                updates.color = color; // PriceLine
            }
            state.selectedDrawing.applyOptions(updates);
        }
    });

    document.getElementById('prop-width').addEventListener('input', (e) => {
        if (state.selectedDrawing && state.selectedDrawing.applyOptions) {
            const width = parseInt(e.target.value);
            const updates = {};
            if (state.selectedDrawing instanceof window.TrendLine) updates.lineWidth = width;
            else if (state.selectedDrawing instanceof window.VertLine) updates.width = width;
            else if (state.selectedDrawing.options && state.selectedDrawing.options().price !== undefined) updates.lineWidth = width;
            // Rectangle doesn't have a border width property
            state.selectedDrawing.applyOptions(updates);
        }
    });

    document.getElementById('prop-delete').addEventListener('click', () => {
        if (state.selectedDrawing) {
            deleteDrawing(state.selectedDrawing);
            document.getElementById('drawing-properties').style.display = 'none';
        }
    });
}

function handleDrawingClick(param) {
    // Deprecated: Tools now handle their own clicks
}

function hitTest(point) {
    const series = window.chartSeries;
    const chart = window.chart;
    const timeScale = chart.timeScale();

    for (const drawing of state.drawings) {
        // Use plugin's own hit test if available (Phase 2 Standardization)
        if (drawing.hitTest && typeof drawing.hitTest === 'function') {
            if (drawing.hitTest(point)) return drawing;
            continue;
        }


        // Fallback for PriceLine (UserPriceLines plugin)
        else if (drawing.options && typeof drawing.options === 'function') {
            const opts = drawing.options();
            if (opts.price !== undefined) {
                // This is a PriceLine
                const y = series.priceToCoordinate(opts.price);
                if (y !== null && Math.abs(point.y - y) < 10) {
                    return drawing;
                }
            }
        }
    }
    return null;
}

function selectDrawing(drawing) {
    console.log('[SELECT] Drawing:', drawing);
    console.log('[SELECT] Drawing type:', drawing ? drawing.constructor.name : 'null');
    console.log('[SELECT] Has applyOptions:', drawing ? typeof drawing.applyOptions : 'N/A');
    console.log('[SELECT] Has _options:', drawing ? !!drawing._options : 'N/A');

    if (state.selectedDrawing) {
        // Deselect
        if (state.selectedDrawing.applyOptions) {
            if (state.selectedDrawing instanceof window.TrendLine) state.selectedDrawing.applyOptions({ lineWidth: 2 });
            if (state.selectedDrawing instanceof window.Rectangle) state.selectedDrawing.applyOptions({ fillColor: 'rgba(33, 150, 243, 0.75)', labelColor: '#2196F3' });
            if (state.selectedDrawing instanceof window.VertLine) state.selectedDrawing.applyOptions({ width: 3 });
            if (state.selectedDrawing instanceof window.FibonacciRetracement) state.selectedDrawing.applyOptions({ lineColor: '#2962FF' });
            // Price Line Deselection
            if (state.selectedDrawing.options && typeof state.selectedDrawing.options === 'function' && state.selectedDrawing.options().price !== undefined) {
                state.selectedDrawing.applyOptions({ lineWidth: 1, color: '#2962FF' });
            }
        }
    }

    state.selectedDrawing = drawing;

    if (drawing) {
        // Select
        if (drawing.applyOptions) {
            if (drawing instanceof window.TrendLine) drawing.applyOptions({ lineWidth: 4 });
            if (drawing instanceof window.Rectangle) drawing.applyOptions({ fillColor: 'rgba(255, 215, 0, 0.9)', labelColor: '#FFD700' });
            if (drawing instanceof window.VertLine) drawing.applyOptions({ width: 5 });
            if (drawing instanceof window.FibonacciRetracement) drawing.applyOptions({ lineColor: '#FFD700' });
            // Price Line Selection
            if (drawing.options && typeof drawing.options === 'function' && drawing.options().price !== undefined) {
                drawing.applyOptions({ lineWidth: 3, color: '#FFD700' });
            }
        }
        // Show Properties Panel
        updatePropertiesPanel(drawing);
    } else {
        // Hide Properties Panel
        document.getElementById('drawing-properties').style.display = 'none';
    }
}

function deleteDrawing(drawing) {
    const series = window.chartSeries;
    try { series.detachPrimitive(drawing); } catch (e) { }
    if (series.removePriceLine) try { series.removePriceLine(drawing); } catch (e) { }

    state.drawings = state.drawings.filter(d => d !== drawing);
    state.selectedDrawing = null;
}

function updatePropertiesPanel(drawing) {
    console.log('[UPDATE_PANEL] Drawing:', drawing);
    console.log('[UPDATE_PANEL] Drawing type:', drawing ? drawing.constructor.name : 'null');

    const panel = document.getElementById('drawing-properties');
    const colorInput = document.getElementById('prop-color');
    const widthInput = document.getElementById('prop-width');

    if (!drawing) return;

    // Get options - handle both options() method and _options property
    let opts;
    if (typeof drawing.options === 'function') {
        opts = drawing.options();
        console.log('[UPDATE_PANEL] Got options from options() method:', opts);
    } else if (drawing._options) {
        opts = drawing._options;
        console.log('[UPDATE_PANEL] Got options from _options property:', opts);
    } else {
        console.log('[UPDATE_PANEL] No options available!');
        return; // No options available
    }

    panel.style.display = 'flex';

    // Color - handle different property names
    let color = opts.color || opts.lineColor || opts.fillColor || opts.labelColor || '#2962FF';

    // Convert rgba to hex if needed
    if (color.startsWith('rgba') || color.startsWith('rgb')) {
        const match = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
        if (match) {
            const r = parseInt(match[1]).toString(16).padStart(2, '0');
            const g = parseInt(match[2]).toString(16).padStart(2, '0');
            const b = parseInt(match[3]).toString(16).padStart(2, '0');
            color = `#${r}${g}${b}`;
        } else {
            color = '#2962FF';
        }
    }

    colorInput.value = color;

    // Width
    let width = opts.width || opts.lineWidth || 1;
    widthInput.value = width;
}

function distanceToSegment(x, y, x1, y1, x2, y2) {
    const A = x - x1;
    const B = y - y1;
    const C = x2 - x1;
    const D = y2 - y1;
    const dot = A * C + B * D;
    const len_sq = C * C + D * D;
    let param = -1;
    if (len_sq !== 0) param = dot / len_sq;
    let xx, yy;
    if (param < 0) { xx = x1; yy = y1; }
    else if (param > 1) { xx = x2; yy = y2; }
    else { xx = x1 + param * C; yy = y1 + param * D; }
    const dx = x - xx;
    const dy = y - yy;
    return Math.sqrt(dx * dx + dy * dy);
}
