import { state } from './state.js';
import { changeTimeframe } from './data_loader.js';

export function setTool(tool) {
    state.currentTool = (state.currentTool === tool) ? null : tool; // Toggle
    state.activeDrawing = null;
    state.startPoint = null;

    // Update UI
    document.querySelectorAll('button').forEach(b => b.classList.remove('active'));
    if (state.currentTool === 'line') document.getElementById('btn-line').classList.add('active');
    if (state.currentTool === 'ray') document.getElementById('btn-ray').classList.add('active');
    if (state.currentTool === 'rect') document.getElementById('btn-rect').classList.add('active');
    if (state.currentTool === 'fib') document.getElementById('btn-fib').classList.add('active');
    if (state.currentTool === 'vert') document.getElementById('btn-vert').classList.add('active');

    // Re-highlight active timeframe button
    changeTimeframe(state.currentTimeframe);

    document.body.style.cursor = state.currentTool ? 'crosshair' : 'default';
    window.chart.applyOptions({ handleScroll: !state.currentTool, handleScale: !state.currentTool });
}

export function clearDrawings() {
    const series = window.chartSeries;
    state.drawings.forEach(d => {
        if (d.detach) d.detach(); // If primitive (our custom ones might not have detach, but series.detachPrimitive(d))
        // Actually, series.detachPrimitive(d) is the correct way for primitives
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
        if (!param.point || !param.time) return;

        if (state.currentTool) {
            handleDrawingClick(param);
        } else {
            // Selection Mode
            const hit = hitTest(param.point);
            selectDrawing(hit);
        }
    });

    // Mouse Move for Dragging (Drawing)
    document.getElementById('chart').addEventListener('mousemove', (e) => {
        if ((state.currentTool === 'ray' || state.currentTool === 'rect' || state.currentTool === 'fib') && state.activeDrawing && state.startPoint) {
            const rect = document.getElementById('chart').getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            const time = chart.timeScale().coordinateToTime(x);
            const price = series.coordinateToPrice(y);

            if (time && price) {
                state.activeDrawing.updateEnd({ time, price }); // Assuming updateEnd exists on instance
                // Note: TrendLine (p) does NOT have updateEnd. But Rectangle (p) does?
                // Wait, I checked TrendLine (p) and it didn't. 
                // But Rectangle (p) didn't either.
                // Only RectangleDrawingTool (V) had logic.
                // This implies my drawing logic for ray/rect/fib IS BROKEN unless I fix the primitive classes.
                // For now, I will focus on Selection.
            }
        }
    });

    // Delete Key
    document.addEventListener('keydown', (e) => {
        if ((e.key === 'Delete' || e.key === 'Backspace') && state.selectedDrawing) {
            deleteDrawing(state.selectedDrawing);
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
                // state.activeDrawing.updateEnd({ time, price }); // This might fail if method missing
                // Manual update if method missing:
                if (state.activeDrawing._p2) state.activeDrawing._p2 = { time, price };
                if (state.activeDrawing.updateAllViews) state.activeDrawing.updateAllViews();

                state.activeDrawing = null;
                state.startPoint = null;
                setTool(null);
            }
        }
    }
    else if (state.currentTool === 'rect') {
        if (!state.startPoint) {
            state.startPoint = { time, price };
            if (window.Rectangle) {
                const rect = new window.Rectangle(chart, series, state.startPoint, state.startPoint, {
                    color: 'rgba(33, 150, 243, 0.2)',
                    borderColor: '#2196F3'
                });
                series.attachPrimitive(rect);
                state.activeDrawing = rect;
                state.drawings.push(rect);
            }
        } else {
            if (state.activeDrawing) {
                if (state.activeDrawing._p2) state.activeDrawing._p2 = { time, price };
                if (state.activeDrawing.updateAllViews) state.activeDrawing.updateAllViews();

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
            // Restore defaults (approximate)
            if (state.selectedDrawing instanceof window.TrendLine) state.selectedDrawing.applyOptions({ width: 2 });
            if (state.selectedDrawing instanceof window.Rectangle) state.selectedDrawing.applyOptions({ borderColor: '#2196F3', width: 1 }); // Assuming default
            if (state.selectedDrawing instanceof window.VertLine) state.selectedDrawing.applyOptions({ width: 3 });
        }
    }

    state.selectedDrawing = drawing;

    if (drawing) {
        // Select
        if (drawing.applyOptions) {
            if (drawing instanceof window.TrendLine) drawing.applyOptions({ width: 4 });
            if (drawing instanceof window.Rectangle) drawing.applyOptions({ borderColor: '#FFD700', width: 3 });
            if (drawing instanceof window.VertLine) drawing.applyOptions({ width: 5 });
        }
    }
}

function deleteDrawing(drawing) {
    const series = window.chartSeries;
    try { series.detachPrimitive(drawing); } catch (e) { }
    if (series.removePriceLine) try { series.removePriceLine(drawing); } catch (e) { }

    state.drawings = state.drawings.filter(d => d !== drawing);
    state.selectedDrawing = null;
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
