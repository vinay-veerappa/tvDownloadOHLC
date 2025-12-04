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

    // Handle UserPriceLines cleanup
    if (state.userPriceLinesTool && state.currentTool !== 'price_line') {
        state.userPriceLinesTool.remove();
        state.userPriceLinesTool = null;
    }

    // Handle UserPriceAlerts cleanup
    if (state.userPriceAlertsTool && state.currentTool !== 'alert') {
        state.userPriceAlertsTool.detached();
        state.userPriceAlertsTool = null;
    }

    // Handle DeltaTooltipPrimitive cleanup
    if (state.deltaTooltipTool && state.currentTool !== 'measure') {
        state.deltaTooltipTool.detached();
        window.chartSeries.detachPrimitive(state.deltaTooltipTool);
        state.deltaTooltipTool = null;
    }

    // Handle RectangleDrawingTool cleanup
    if (state.rectangleTool && state.currentTool !== 'rect') {
        state.rectangleTool.stopDrawing();
    }

    // Update UI
    document.querySelectorAll('button').forEach(b => b.classList.remove('active'));
    if (state.currentTool === 'line') document.getElementById('btn-line').classList.add('active');
    if (state.currentTool === 'ray') document.getElementById('btn-ray').classList.add('active');
    if (state.currentTool === 'rect') document.getElementById('btn-rect').classList.add('active');
    if (state.currentTool === 'fib') document.getElementById('btn-fib').classList.add('active');
    if (state.currentTool === 'vert') document.getElementById('btn-vert').classList.add('active');
    if (state.currentTool === 'price_line') document.getElementById('btn-price-line').classList.add('active');
    if (state.currentTool === 'alert') document.getElementById('btn-alert').classList.add('active');
    if (state.currentTool === 'measure') document.getElementById('btn-measure').classList.add('active');

    // Initialize UserPriceLines if selected
    if (state.currentTool === 'price_line') {
        if (!state.userPriceLinesTool) {
            state.userPriceLinesTool = new UserPriceLines(window.chart, window.chartSeries, {
                color: '#2962FF',
                hoverColor: '#E91E63'
            });
        }
    }

    // Initialize UserPriceAlerts if selected
    if (state.currentTool === 'alert') {
        if (!state.userPriceAlertsTool) {
            state.userPriceAlertsTool = new UserPriceAlerts();
            // We need to manually attach it because it's designed as a primitive but also handles events
            // The class has an 'attached' method but it's usually called by the series when attached.
            // However, UserPriceAlerts extends L (listener) and seems to be a primitive.
            // Let's check if it needs to be attached to series.
            // Yes, it has paneViews() etc.
            window.chartSeries.attachPrimitive(state.userPriceAlertsTool);
        }
    }

    // Initialize DeltaTooltipPrimitive if selected
    if (state.currentTool === 'measure') {
        if (!state.deltaTooltipTool) {
            state.deltaTooltipTool = new DeltaTooltipPrimitive({
                lineColor: 'rgba(41, 98, 255, 0.5)',
                showTime: true
            });
            window.chartSeries.attachPrimitive(state.deltaTooltipTool);
        }
    }

    // Initialize RectangleDrawingTool if selected
    if (state.currentTool === 'rect') {
        if (!state.rectangleTool) {
            // Pass null for toolbar container to avoid UI creation
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

    chart.subscribeClick((param) => {
        if (!param.point) return;

        if (state.currentTool) {
            // Drawing mode - need time for drawing
            if (!param.time) return;
            handleDrawingClick(param);
        } else {
            // Selection Mode - don't need time to select
            const hit = hitTest(param.point);
            selectDrawing(hit);
        }
    });

    // Mouse Move for Dragging (Drawing)
    document.getElementById('chart').addEventListener('mousemove', (e) => {
        if ((state.currentTool === 'ray' || state.currentTool === 'fib') && state.activeDrawing && state.startPoint) {
            const rect = document.getElementById('chart').getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            const time = chart.timeScale().coordinateToTime(x);
            const price = series.coordinateToPrice(y);

            if (time && price !== null && price !== undefined) {
                state.activeDrawing._p2 = { time, price };
                if (state.activeDrawing.updateAllViews) {
                    state.activeDrawing.updateAllViews();
                } else if (state.activeDrawing._requestUpdate) {
                    state.activeDrawing._requestUpdate();
                }
            }
        }
    });

    // Delete Key
    document.addEventListener('keydown', (e) => {
        if ((e.key === 'Delete' || e.key === 'Backspace') && state.selectedDrawing) {
            deleteDrawing(state.selectedDrawing);
        }
    });

    // Listen for drawings created by plugins
    window.addEventListener('drawing-created', (e) => {
        if (e.detail && e.detail.drawing) {
            state.drawings.push(e.detail.drawing);
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
    const series = window.chartSeries;
    const chart = window.chart;
    const price = series.coordinateToPrice(param.point.y);
    const time = param.time;

    if (state.currentTool === 'line') {
        const line = series.createPriceLine({
            price: price, color: '#2962FF', lineWidth: 2, lineStyle: 0,
            axisLabelVisible: true, title: 'Line'
        });
        state.drawings.push(line);
        setTool(null);
    }
    else if (state.currentTool === 'ray') {
        if (!state.startPoint) {
            state.startPoint = { time, price };
            if (window.TrendLine) {
                const tl = new window.TrendLine(chart, series, state.startPoint, state.startPoint, { lineColor: '#D500F9', lineWidth: 2 });
                series.attachPrimitive(tl);
                state.activeDrawing = tl;
                state.drawings.push(tl);
            }
        } else {
            if (state.activeDrawing) {
                state.activeDrawing._p2 = { time, price };
                if (state.activeDrawing.updateAllViews) state.activeDrawing.updateAllViews();

                state.activeDrawing = null;
                state.startPoint = null;
                setTool(null);
            }
        }
    }

    else if (state.currentTool === 'fib') {
        if (!state.startPoint) {
            if (!time || price === null || price === undefined) return;
            state.startPoint = { time, price };
            if (window.FibonacciRetracement) {
                const fib = new window.FibonacciRetracement(chart, series, state.startPoint, state.startPoint, { lineColor: '#2962FF' });
                series.attachPrimitive(fib);
                state.activeDrawing = fib;
                state.drawings.push(fib);
            }
        } else {
            if (state.activeDrawing) {
                state.activeDrawing._p2 = { time, price };
                // Fib plugin uses requestUpdate internally when p2 changes if we used updateEnd, 
                // but here we set _p2 directly. We need to trigger update.
                // The library calls paneViews() on update, so we just need to ensure the chart redraws.
                // But let's add updateAllViews to Fib plugin for consistency or check if it has it.
                if (state.activeDrawing.updateAllViews) state.activeDrawing.updateAllViews();
                else if (state.activeDrawing._requestUpdate) state.activeDrawing._requestUpdate();

                state.activeDrawing = null;
                state.startPoint = null;
                setTool(null);
            }
        }
    }
    else if (state.currentTool === 'vert') {
        if (window.VertLine) {
            const vl = new window.VertLine(chart, series, time, {
                color: '#2962FF',
                labelText: new Date(time * 1000).toLocaleDateString(),
                showLabel: true
            });
            series.attachPrimitive(vl);
            state.drawings.push(vl);
            setTool(null);
        }
    }
}

function hitTest(point) {
    const series = window.chartSeries;
    const chart = window.chart;
    const timeScale = chart.timeScale();

    for (const drawing of state.drawings) {
        if (window.TrendLine && drawing instanceof window.TrendLine) {
            const p1 = drawing._p1;
            const p2 = drawing._p2;
            if (!p1 || !p2 || !p1.time || !p2.time || p1.price === undefined || p2.price === undefined) continue;

            const x1 = timeScale.timeToCoordinate(p1.time);
            const y1 = series.priceToCoordinate(p1.price);
            const x2 = timeScale.timeToCoordinate(p2.time);
            const y2 = series.priceToCoordinate(p2.price);

            if (x1 === null || y1 === null || x2 === null || y2 === null) continue;

            const dist = distanceToSegment(point.x, point.y, x1, y1, x2, y2);
            if (dist < 10) return drawing;
        }
        else if (window.Rectangle && drawing instanceof window.Rectangle) {
            const p1 = drawing._p1;
            const p2 = drawing._p2;
            if (!p1 || !p2 || !p1.time || !p2.time || p1.price === undefined || p2.price === undefined) continue;

            const x1 = timeScale.timeToCoordinate(p1.time);
            const y1 = series.priceToCoordinate(p1.price);
            const x2 = timeScale.timeToCoordinate(p2.time);
            const y2 = series.priceToCoordinate(p2.price);

            if (x1 === null || y1 === null || x2 === null || y2 === null) continue;

            const left = Math.min(x1, x2);
            const right = Math.max(x1, x2);
            const top = Math.min(y1, y2);
            const bottom = Math.max(y1, y2);

            if (point.x >= left && point.x <= right && point.y >= top && point.y <= bottom) {
                return drawing;
            }
        }
        else if (window.VertLine && drawing instanceof window.VertLine) {
            if (!drawing._time) continue;
            const x = timeScale.timeToCoordinate(drawing._time);
            if (Math.abs(point.x - x) < 10) return drawing;
        }
    }
    return null;
}

function selectDrawing(drawing) {
    if (state.selectedDrawing) {
        // Deselect
        if (state.selectedDrawing.applyOptions) {
            if (state.selectedDrawing instanceof window.TrendLine) state.selectedDrawing.applyOptions({ lineWidth: 2 });
            if (state.selectedDrawing instanceof window.Rectangle) state.selectedDrawing.applyOptions({ fillColor: 'rgba(33, 150, 243, 0.75)', labelColor: '#2196F3' });
            if (state.selectedDrawing instanceof window.VertLine) state.selectedDrawing.applyOptions({ width: 3 });
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
    const panel = document.getElementById('drawing-properties');
    const colorInput = document.getElementById('prop-color');
    const widthInput = document.getElementById('prop-width');

    if (!drawing || !drawing.options) return;

    panel.style.display = 'flex';

    const opts = drawing.options();

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
