// Fibonacci Retracement Plugin for Lightweight Charts v5.0

class FibonacciRenderer {
    constructor(p1, p2, options) {
        this._p1 = p1; // { x, y }
        this._p2 = p2; // { x, y }
        this._options = options;
    }

    draw(target) {
        target.useBitmapCoordinateSpace(scope => {
            if (this._p1.x === null || this._p1.y === null || this._p2.x === null || this._p2.y === null) return;

            const ctx = scope.context;
            const hPR = scope.horizontalPixelRatio;
            const vPR = scope.verticalPixelRatio;

            const x1 = this._p1.x * hPR;
            const y1 = this._p1.y * vPR;
            const x2 = this._p2.x * hPR;
            const y2 = this._p2.y * vPR;

            // Draw Trendline
            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.strokeStyle = this._options.lineColor;
            ctx.lineWidth = 1 * hPR;
            ctx.setLineDash([5 * hPR, 5 * hPR]);
            ctx.stroke();
            ctx.setLineDash([]);

            // Calculate Levels
            // Y coordinates are pixels, so we need to be careful.
            // Price scale: Higher price = Lower Y.
            // So if p1 is High and p2 is Low:
            // 0% = p1.y (High Price)
            // 100% = p2.y (Low Price)

            const dy = y2 - y1;
            const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
            const colors = [
                '#787b86', '#f44336', '#ff9800', '#4caf50', '#2196f3', '#9c27b0', '#787b86'
            ];

            // Draw Levels
            levels.forEach((level, index) => {
                const y = y1 + (dy * level);

                ctx.beginPath();
                // Extend lines to the right? For now, just width of the trendline x-range
                // Or maybe full width? Let's stick to the x-range defined by p1 and p2 for now,
                // but usually Fib extends. Let's extend slightly.

                // Actually, standard Fib tool draws from x1 to x2 horizontally.
                ctx.moveTo(x1, y);
                ctx.lineTo(x2, y);

                ctx.strokeStyle = colors[index] || '#888';
                ctx.lineWidth = 1 * hPR;
                ctx.stroke();

                // Draw Text? (Hard in canvas without font loading issues, but let's try)
                ctx.font = `${10 * hPR}px sans-serif`;
                ctx.fillStyle = colors[index] || '#888';
                ctx.fillText(`${level * 100}%`, x2 + (5 * hPR), y + (3 * hPR));
            });
        });
    }
}

class FibonacciPaneView {
    constructor(source) {
        this._source = source;
    }

    renderer() {
        return new FibonacciRenderer(
            this._source._p1Point,
            this._source._p2Point,
            this._source._options
        );
    }
}

class FibonacciRetracement {
    constructor(chart, series, p1, p2, options) {
        this._chart = chart;
        this._series = series;
        this._p1 = p1;
        this._p2 = p2;
        this._options = options || { lineColor: '#787b86' };

        this._p1Point = { x: null, y: null };
        this._p2Point = { x: null, y: null };

        this._paneViews = [new FibonacciPaneView(this)];
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

window.FibonacciRetracement = FibonacciRetracement;
