import { isBusinessDay } from "lightweight-charts";

function ensureDefined(val) {
  if (val === undefined) throw new Error("Value is undefined");
  return val;
}

// ============================================================================
// Renderers
// ============================================================================

class RectangleRenderer {
  constructor(p1, p2, options) {
    this._p1 = p1;
    this._p2 = p2;
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

      const left = Math.min(x1, x2);
      const top = Math.min(y1, y2);
      const width = Math.abs(x2 - x1);
      const height = Math.abs(y2 - y1);

      ctx.fillStyle = this._options.fillColor;
      ctx.fillRect(left, top, width, height);
    });
  }
}

// ============================================================================
// Views
// ============================================================================

class RectanglePaneView {
  constructor(source) {
    this._source = source;
  }

  update() {
    // Logic handled in source._updatePoints() or renderer
  }

  renderer() {
    return new RectangleRenderer(
      this._source._p1Point,
      this._source._p2Point,
      this._source._options
    );
  }
}

// ============================================================================
// Main Primitive: Rectangle
// ============================================================================

const defaultOptions = {
  fillColor: "rgba(200, 50, 100, 0.75)",
  previewFillColor: "rgba(200, 50, 100, 0.25)",
  labelColor: "rgba(200, 50, 100, 1)",
  labelTextColor: "white",
  showLabels: true,
  priceLabelFormatter: (s) => (s !== undefined && s !== null) ? s.toFixed(2) : '',
  timeLabelFormatter: (s) => {
    if (s === undefined || s === null) return '';
    return typeof s == "string" ? s : (isBusinessDay(s) ? new Date(s.year, s.month, s.day) : new Date(s * 1e3)).toLocaleDateString();
  }
};

class Rectangle {
  constructor(chart, series, p1, p2, options) {
    this._chart = chart;
    this._series = series;
    this._p1 = p1;
    this._p2 = p2;
    this._options = { ...defaultOptions, ...options };

    this._p1Point = { x: null, y: null };
    this._p2Point = { x: null, y: null };

    this._paneViews = [new RectanglePaneView(this)];
    this._requestUpdate = null;
  }

  // Standard Plugin Methods
  attached({ chart, series, requestUpdate }) {
    this._requestUpdate = requestUpdate;
    this.updateAllViews();
  }

  detached() {
    this._requestUpdate = null;
  }

  updateAllViews() {
    this._updatePoints();
    if (this._requestUpdate) this._requestUpdate();
  }

  _updatePoints() {
    if (!this._chart || !this._series) return;

    const timeScale = this._chart.timeScale();

    if (this._p1.time) this._p1Point.x = timeScale.timeToCoordinate(this._p1.time);
    if (this._p1.price !== undefined) this._p1Point.y = this._series.priceToCoordinate(this._p1.price);

    if (this._p2.time) this._p2Point.x = timeScale.timeToCoordinate(this._p2.time);
    if (this._p2.price !== undefined) this._p2Point.y = this._series.priceToCoordinate(this._p2.price);
  }

  paneViews() {
    this._updatePoints();
    return this._paneViews;
  }

  // New Standard Methods for Properties Panel
  options() {
    return this._options;
  }

  applyOptions(options) {
    this._options = { ...this._options, ...options };
    this.updateAllViews();
  }

  // Hit Test for Selection
  hitTest(point) {
    if (!this._p1Point.x || !this._p1Point.y || !this._p2Point.x || !this._p2Point.y) return false;

    const x1 = this._p1Point.x;
    const y1 = this._p1Point.y;
    const x2 = this._p2Point.x;
    const y2 = this._p2Point.y;

    const left = Math.min(x1, x2);
    const right = Math.max(x1, x2);
    const top = Math.min(y1, y2);
    const bottom = Math.max(y1, y2);

    return (point.x >= left && point.x <= right && point.y >= top && point.y <= bottom);
  }

  // Method to update end point (used by tool during drawing)
  updateEndPoint(p2) {
    this._p2 = p2;
    this.updateAllViews();
  }
}

// ============================================================================
// Tool: RectangleDrawingTool
// ============================================================================

class RectangleDrawingTool {
  constructor(chart, series, toolbarContainer, defaultOpts) {
    this._chart = chart;
    this._series = series;
    this._defaultOptions = defaultOpts || {};
    this._rectangles = [];
    this._previewRectangle = null;
    this._points = [];
    this._drawing = false;

    // Bind handlers
    this._clickHandler = this._onClick.bind(this);
    this._moveHandler = this._onMouseMove.bind(this);

    // Subscribe
    this._chart.subscribeClick(this._clickHandler);
    this._chart.subscribeCrosshairMove(this._moveHandler);
  }

  remove() {
    this.stopDrawing();
    if (this._chart) {
      this._chart.unsubscribeClick(this._clickHandler);
      this._chart.unsubscribeCrosshairMove(this._moveHandler);
    }
    this._rectangles.forEach(r => {
      if (this._series) this._series.detachPrimitive(r);
    });
    this._rectangles = [];
    this._removePreviewRectangle();
  }

  startDrawing() {
    this._drawing = true;
    this._points = [];
  }

  stopDrawing() {
    this._drawing = false;
    this._points = [];
    this._removePreviewRectangle();
  }

  isDrawing() {
    return this._drawing;
  }

  _onClick(param) {
    if (!this._drawing || !param.point || !param.time || !this._series) return;

    const price = this._series.coordinateToPrice(param.point.y);
    if (price === null) return;

    this._addPoint({ time: param.time, price: price });
  }

  _onMouseMove(param) {
    if (!this._drawing || !param.point || !param.time || !this._series) return;

    const price = this._series.coordinateToPrice(param.point.y);
    if (price !== null && this._previewRectangle) {
      this._previewRectangle.updateEndPoint({ time: param.time, price: price });
    }
  }

  _addPoint(point) {
    this._points.push(point);

    if (this._points.length === 1) {
      this._addPreviewRectangle(point);
    } else if (this._points.length >= 2) {
      this._addNewRectangle(this._points[0], this._points[1]);
      this.stopDrawing();
    }
  }

  _addPreviewRectangle(point) {
    this._previewRectangle = new Rectangle(this._chart, this._series, point, point, {
      ...this._defaultOptions,
      fillColor: this._defaultOptions.previewFillColor || this._defaultOptions.fillColor
    });
    this._series.attachPrimitive(this._previewRectangle);
  }

  _removePreviewRectangle() {
    if (this._previewRectangle) {
      this._series.detachPrimitive(this._previewRectangle);
      this._previewRectangle = null;
    }
  }

  _addNewRectangle(p1, p2) {
    const rect = new Rectangle(this._chart, this._series, p1, p2, { ...this._defaultOptions });
    this._rectangles.push(rect);
    this._series.attachPrimitive(rect);

    // Dispatch event for drawings.js to pick up
    window.dispatchEvent(new CustomEvent('drawing-created', {
      detail: { drawing: rect, type: 'rectangle' }
    }));
  }
}

// Export
window.Rectangle = Rectangle;
window.RectangleDrawingTool = RectangleDrawingTool;

export { Rectangle, RectangleDrawingTool };
