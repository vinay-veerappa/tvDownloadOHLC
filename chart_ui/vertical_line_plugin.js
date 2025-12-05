// Vertical Line Plugin for Lightweight Charts v5.0
// Ported from official examples

function positionsLine(position, pixelRatio, width) {
    const scaledWidth = Math.max(1, Math.floor(width * pixelRatio));
    const scaledPosition = Math.round(position * pixelRatio);
    // Adjust for crispness (if width is odd, offset by 0.5)
    // Actually, for fillRect, we just need integer coordinates.
    // The official helper does more complex centering.
    // Simplified:
    return {
        position: scaledPosition - Math.floor(scaledWidth / 2),
        length: scaledWidth
    };
}

class VertLinePaneRenderer {
    constructor(x, options) {
        this._x = x;
        this._options = options;
    }

    draw(target) {
        target.useBitmapCoordinateSpace(scope => {
            if (this._x === null) return;
            const ctx = scope.context;
            const position = positionsLine(
                this._x,
                scope.horizontalPixelRatio,
                this._options.width
            );
            ctx.fillStyle = this._options.color;
            ctx.fillRect(
                position.position,
                0,
                position.length,
                scope.bitmapSize.height
            );
        });
    }
}

class VertLinePaneView {
    constructor(source, options) {
        this._source = source;
        this._options = options;
        this._x = null;
    }

    update() {
        const timeScale = this._source._chart.timeScale();
        this._x = timeScale.timeToCoordinate(this._source._time);
    }

    renderer() {
        return new VertLinePaneRenderer(this._x, this._options);
    }
}

class VertLineTimeAxisView {
    constructor(source, options) {
        this._source = source;
        this._options = options;
        this._x = null;
    }

    update() {
        const timeScale = this._source._chart.timeScale();
        this._x = timeScale.timeToCoordinate(this._source._time);
    }

    visible() {
        return this._options.showLabel;
    }

    tickVisible() {
        return this._options.showLabel;
    }

    coordinate() {
        return this._x ?? 0;
    }

    text() {
        return this._options.labelText;
    }

    textColor() {
        return this._options.labelTextColor;
    }

    backColor() {
        return this._options.labelBackgroundColor;
    }
}

const defaultOptions = {
    color: 'green',
    labelText: '',
    width: 3,
    labelBackgroundColor: 'green',
    labelTextColor: 'white',
    showLabel: false,
};

class VertLine {
    constructor(chart, series, time, options) {
        this._chart = chart;
        this._series = series;
        this._time = time;
        this._options = { ...defaultOptions, ...options };

        this._paneViews = [new VertLinePaneView(this, this._options)];
        this._timeAxisViews = [new VertLineTimeAxisView(this, this._options)];
    }

    updateAllViews() {
        this._paneViews.forEach(pw => pw.update());
        this._timeAxisViews.forEach(tw => tw.update());
    }

    timeAxisViews() {
        return this._timeAxisViews;
    }

    paneViews() {
        return this._paneViews;
    }

    // Helper to update position if needed
    updateTime(time) {
        this._time = time;
        this.updateAllViews();
    }

    // Apply options for property modification
    applyOptions(options) {
        this._options = { ...this._options, ...options };
        // Update the views with new options
        this._paneViews = [new VertLinePaneView(this, this._options)];
        this._timeAxisViews = [new VertLineTimeAxisView(this, this._options)];
        this.updateAllViews();
        if (this._requestUpdate) this._requestUpdate();
    }

    // Get current options
    options() {
        return this._options;
    }

    // Required for v5 primitives
    attached({ chart, series, requestUpdate }) {
        this._requestUpdate = requestUpdate;
        this.updateAllViews();
    }

    detached() {
        this._requestUpdate = null;
    }
}

window.VertLine = VertLine;
