// Rectangle Plugin for Lightweight Charts v5.0

class RectangleRenderer {
    constructor(p1, p2, color, borderColor) {
        this._p1 = p1; // { x, y }
        this._p2 = p2; // { x, y }
        this._color = color;
        this._borderColor = borderColor;
    }

    draw(target) {
        target.useBitmapCoordinateSpace(scope => {
            if (this._p1.x === null || this._p1.y === null || this._p2.x === null || this._p2.y === null) return;

            const ctx = scope.context;
            const horizontalPixelRatio = scope.horizontalPixelRatio;
            const verticalPixelRatio = scope.verticalPixelRatio;

            const x1 = this._p1.x * horizontalPixelRatio;
            const y1 = this._p1.y * verticalPixelRatio;
            const x2 = this._p2.x * horizontalPixelRatio;
            const y2 = this._p2.y * verticalPixelRatio;

            const width = x2 - x1;
            const height = y2 - y1;

            ctx.fillStyle = this._color;
            ctx.fillRect(x1, y1, width, height);

            if (this._borderColor) {
                ctx.strokeStyle = this._borderColor;
                ctx.lineWidth = 2 * horizontalPixelRatio; // 2px border
                ctx.strokeRect(x1, y1, width, height);
            }
        });
    }
}

class RectanglePaneView {
    constructor(source) {
        this._source = source;
    }

    renderer() {
        return new RectangleRenderer(
            this._source._p1Point,
            this._source._p2Point,
            this._source._options.color,
            this._source._options.borderColor
        );
    }
}

class Rectangle {
    constructor(chart, series, p1, p2, options) {
        this._chart = chart;
        this._series = series;
        this._p1 = p1; // { time, price }
        this._p2 = p2; // { time, price }
        this._options = options || {
            color: 'rgba(33, 150, 243, 0.2)',
            borderColor: '#2196F3'
        };

        this._p1Point = { x: null, y: null };
        this._p2Point = { x: null, y: null };

        this._paneViews = [new RectanglePaneView(this)];
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

        this._p1Point.x = timeScale.timeToCoordinate(this._p1.time);
        this._p1Point.y = this._series.priceToCoordinate(this._p1.price);

        this._p2Point.x = timeScale.timeToCoordinate(this._p2.time);
        this._p2Point.y = this._series.priceToCoordinate(this._p2.price);
    }
}

// Export for use
window.Rectangle = Rectangle;
