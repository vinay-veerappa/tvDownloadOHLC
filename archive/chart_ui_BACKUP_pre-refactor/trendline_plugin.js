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
}

// Export for use
window.TrendLine = TrendLine;
