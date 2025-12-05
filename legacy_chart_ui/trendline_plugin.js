// TrendLine Plugin for Lightweight Charts v5.0
// Ported from official examples

class TrendLineRenderer {
    constructor(p1, p2, color, width) {
        this._p1 = p1; // { x, y }
        this._p2 = p2; // { x, y }
        this._color = color;
        this._width = width;
    }

    draw(target) {
        target.useBitmapCoordinateSpace(scope => {
            if (this._p1.x === null || this._p1.y === null || this._p2.x === null || this._p2.y === null) return;

            const ctx = scope.context;
            const horizontalPixelRatio = scope.horizontalPixelRatio;
            const verticalPixelRatio = scope.verticalPixelRatio;

            ctx.lineWidth = this._width * horizontalPixelRatio;
            ctx.strokeStyle = this._color;
            ctx.beginPath();
            ctx.moveTo(this._p1.x * horizontalPixelRatio, this._p1.y * verticalPixelRatio);
            ctx.lineTo(this._p2.x * horizontalPixelRatio, this._p2.y * verticalPixelRatio);
            ctx.stroke();
        });
    }
}

class TrendLinePaneView {
    constructor(source) {
        this._source = source;
    }

    renderer() {
        return new TrendLineRenderer(
            this._source._p1Point,
            this._source._p2Point,
            this._source._options.lineColor,
            this._source._options.lineWidth
        );
    }
}

class TrendLine {
    constructor(chart, series, p1, p2, options) {
        this._chart = chart;
        this._series = series;
        this._p1 = p1; // { time, price }
        this._p2 = p2; // { time, price }
        this._options = options || { lineColor: '#2962FF', lineWidth: 2 };

        this._p1Point = { x: null, y: null };
        this._p2Point = { x: null, y: null };

        this._paneViews = [new TrendLinePaneView(this)];
    }

    updateEnd(p2) {
        this._p2 = p2;
        this._requestUpdate();
    }

    applyOptions(options) {
        this._options = { ...this._options, ...options };
        this._requestUpdate();
    }

    options() {
        return this._options;
    }

    attached({ chart, series, requestUpdate }) {
        this._requestUpdate = requestUpdate;
    }

    detached() {
        this._requestUpdate = null;
    }

    paneViews() {
        this._updatePoints();
        return this._paneViews;
    }

    _updatePoints() {
        if (!this._chart || !this._series) return;

        const timeScale = this._chart.timeScale();
        const priceScale = this._series.priceScale(); // v5: get price scale from series

        // Convert Time -> X
        // Note: coordinateToTime is easy, but Time -> Coordinate requires internal index lookup usually.
        // However, v5 exposes timeToCoordinate!

        this._p1Point.x = timeScale.timeToCoordinate(this._p1.time);
        this._p1Point.y = this._series.priceToCoordinate(this._p1.price);

        this._p2Point.x = timeScale.timeToCoordinate(this._p2.time);
        this._p2Point.y = this._series.priceToCoordinate(this._p2.price);
    }

    // Hit test for selection
    hitTest(point) {
        if (!this._chart || !this._series) return false;
        if (!this._p1 || !this._p2 || !this._p1.time || !this._p2.time) return false;
        if (this._p1.price === undefined || this._p2.price === undefined) return false;

        const timeScale = this._chart.timeScale();
        const x1 = timeScale.timeToCoordinate(this._p1.time);
        const y1 = this._series.priceToCoordinate(this._p1.price);
        const x2 = timeScale.timeToCoordinate(this._p2.time);
        const y2 = this._series.priceToCoordinate(this._p2.price);

        if (x1 === null || y1 === null || x2 === null || y2 === null) return false;

        const dist = this._distanceToSegment(point.x, point.y, x1, y1, x2, y2);
        return dist < 10;
    }

    // Helper: Calculate distance from point to line segment
    _distanceToSegment(x, y, x1, y1, x2, y2) {
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
}

// ============================================================================
// Tool: TrendLineTool
// ============================================================================

class TrendLineTool {
    constructor(chart, series) {
        this._chart = chart;
        this._series = series;
        this._startPoint = null;
        this._activeDrawing = null;
        this._drawing = false;

        // Bind handlers
        this._clickHandler = this._onClick.bind(this);
        this._moveHandler = this._onMouseMove.bind(this);
    }

    startDrawing() {
        this._drawing = true;
        this._startPoint = null;
        this._activeDrawing = null;
        this._chart.subscribeClick(this._clickHandler);
        this._chart.subscribeCrosshairMove(this._moveHandler);
    }

    stopDrawing() {
        this._drawing = false;
        this._startPoint = null;
        this._activeDrawing = null;
        this._chart.unsubscribeClick(this._clickHandler);
        this._chart.unsubscribeCrosshairMove(this._moveHandler);
    }

    isDrawing() {
        return this._drawing;
    }

    _onClick(param) {
        if (!this._drawing || !param.point || !param.time || !this._series) return;

        const price = this._series.coordinateToPrice(param.point.y);
        if (price === null) return;

        if (!this._startPoint) {
            // First click: Start drawing
            this._startPoint = { time: param.time, price: price };
            this._activeDrawing = new TrendLine(
                this._chart,
                this._series,
                this._startPoint,
                this._startPoint,
                { lineColor: '#D500F9', lineWidth: 2 }
            );
            this._series.attachPrimitive(this._activeDrawing);

            // Dispatch event for tracking (optional, but good for immediate feedback)
            window.dispatchEvent(new CustomEvent('drawing-created', {
                detail: { drawing: this._activeDrawing, type: 'trendline', partial: true }
            }));
        } else {
            // Second click: Finish drawing
            if (this._activeDrawing) {
                this._activeDrawing._p2 = { time: param.time, price: price };
                this._activeDrawing.updateAllViews();

                // Dispatch final event
                window.dispatchEvent(new CustomEvent('drawing-created', {
                    detail: { drawing: this._activeDrawing, type: 'trendline', partial: false }
                }));

                this.stopDrawing();
            }
        }
    }

    _onMouseMove(param) {
        if (!this._drawing || !this._activeDrawing || !this._startPoint || !param.point || !param.time) return;

        const price = this._series.coordinateToPrice(param.point.y);
        if (price !== null) {
            this._activeDrawing._p2 = { time: param.time, price: price };
            this._activeDrawing.updateAllViews();
        }
    }
}

// Export for use
window.TrendLine = TrendLine;
window.TrendLineTool = TrendLineTool;
export { TrendLine, TrendLineTool };
