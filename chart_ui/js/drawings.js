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
    changeTimeframe(state.currentTimeframe); // Hack to restore active class if cleared

    document.body.style.cursor = state.currentTool ? 'crosshair' : 'default';

    // Disable chart scrolling while drawing? No, better to keep it.
    window.chart.applyOptions({ handleScroll: !state.currentTool, handleScale: !state.currentTool });
}

export function clearDrawings() {
    const series = window.chartSeries;
    // Remove primitives
    state.drawings.forEach(d => {
        if (d.detach) d.detach(); // If primitive
        if (series.removePriceLine) try { series.removePriceLine(d); } catch (e) { } // If price line
    });
    state.drawings = [];
    setTool(null);
}

export function setupDrawingHandlers() {
    const chart = window.chart;
    const series = window.chartSeries;

    chart.subscribeClick((param) => {
        if (!state.currentTool || !param.point || !param.time) return;

        const price = series.coordinateToPrice(param.point.y);
        const time = param.time;

        if (state.currentTool === 'line') {
            // Horizontal Line (Simple)
            const line = series.createPriceLine({
                price: price, color: '#2962FF', lineWidth: 2, lineStyle: 0,
                axisLabelVisible: true, title: 'Line'
            });
            state.drawings.push(line);
            setTool(null);
        }
        else if (state.currentTool === 'ray') {
            // Trend Line (Diagonal) - 2 Click Process
            if (!state.startPoint) {
                // First Click
                state.startPoint = { time, price };

                // Create initial primitive (0 length)
                if (window.TrendLine) {
                    const tl = new window.TrendLine(chart, series, state.startPoint, state.startPoint, { lineColor: '#D500F9', lineWidth: 2 });
                    series.attachPrimitive(tl);
                    state.activeDrawing = tl;
                    state.drawings.push(tl);
                }
            } else {
                // Second Click - Finish
                if (state.activeDrawing) {
                    state.activeDrawing.updateEnd({ time, price });
                    state.activeDrawing = null;
                    state.startPoint = null;
                    setTool(null);
                }
            }
        }
        else if (state.currentTool === 'rect') {
            // Rectangle - 2 Click Process
            if (!state.startPoint) {
                // First Click
                state.startPoint = { time, price };

                // Create initial primitive
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
                // Second Click - Finish
                if (state.activeDrawing) {
                    state.activeDrawing.updateEnd({ time, price });
                    state.activeDrawing = null;
                    state.startPoint = null;
                    setTool(null);
                }
            }
        }
        else if (state.currentTool === 'fib') {
            // Fibonacci - 2 Click Process
            if (!state.startPoint) {
                // First Click
                state.startPoint = { time, price };

                // Create initial primitive
                if (window.FibonacciRetracement) {
                    const fib = new window.FibonacciRetracement(chart, series, state.startPoint, state.startPoint, {
                        lineColor: '#787b86'
                    });
                    series.attachPrimitive(fib);
                    state.activeDrawing = fib;
                    state.drawings.push(fib);
                }
            } else {
                // Second Click - Finish
                if (state.activeDrawing) {
                    state.activeDrawing.updateEnd({ time, price });
                    state.activeDrawing = null;
                    state.startPoint = null;
                    setTool(null);
                }
            }
        }
        else if (state.currentTool === 'vert') {
            // Vertical Line - 1 Click Process
            if (window.VertLine) {
                const vl = new window.VertLine(chart, series, time, {
                    color: '#2962FF',
                    labelText: new Date(time * 1000).toLocaleDateString(),
                    showLabel: true
                });
                series.attachPrimitive(vl);
                state.drawings.push(vl);
                setTool(null); // Finish immediately
            }
        }
    });

    // Mouse Move for Dragging
    document.getElementById('chart').addEventListener('mousemove', (e) => {
        if ((state.currentTool === 'ray' || state.currentTool === 'rect' || state.currentTool === 'fib') && state.activeDrawing && state.startPoint) {
            // We need to convert mouse X/Y to Time/Price

            const rect = document.getElementById('chart').getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            const time = chart.timeScale().coordinateToTime(x);
            const price = series.coordinateToPrice(y);

            if (time && price) {
                state.activeDrawing.updateEnd({ time, price });
            }
        }
    });
}
