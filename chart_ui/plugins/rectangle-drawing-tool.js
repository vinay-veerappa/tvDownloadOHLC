import { isBusinessDay as d } from "lightweight-charts";
function o(s) {
  if (s === void 0)
    throw new Error("Value is undefined");
  return s;
}
class w {
  _chart = void 0;
  _series = void 0;
  requestUpdate() {
    this._requestUpdate && this._requestUpdate();
  }
  _requestUpdate;
  attached({ chart: t, series: e, requestUpdate: i }) {
    this._chart = t, this._series = e, this._series.subscribeDataChanged(this._fireDataUpdated), this._requestUpdate = i, this.requestUpdate();
  }
  detached() {
    this._series?.unsubscribeDataChanged(this._fireDataUpdated), this._chart = void 0, this._series = void 0, this._requestUpdate = void 0;
  }
  get chart() {
    return o(this._chart);
  }
  get series() {
    return o(this._series);
  }
  // This method is a class property to maintain the
  // lexical 'this' scope (due to the use of the arrow function)
  // and to ensure its reference stays the same, so we can unsubscribe later.
  _fireDataUpdated = (t) => {
    this.dataUpdated && this.dataUpdated(t);
  };
}
function a(s, t, e) {
  const i = Math.round(e * s), r = Math.round(e * t);
  return {
    position: Math.min(i, r),
    length: Math.abs(r - i) + 1
  };
}
class g {
  _p1;
  _p2;
  _fillColor;
  constructor(t, e, i) {
    this._p1 = t, this._p2 = e, this._fillColor = i;
  }
  draw(t) {
    t.useBitmapCoordinateSpace((e) => {
      if (this._p1.x === null || this._p1.y === null || this._p2.x === null || this._p2.y === null)
        return;
      const i = e.context, r = a(
        this._p1.x,
        this._p2.x,
        e.horizontalPixelRatio
      ), n = a(
        this._p1.y,
        this._p2.y,
        e.verticalPixelRatio
      );
      i.fillStyle = this._fillColor, i.fillRect(
        r.position,
        n.position,
        r.length,
        n.length
      );
    });
  }
}
class x {
  _source;
  _p1 = { x: null, y: null };
  _p2 = { x: null, y: null };
  constructor(t) {
    this._source = t;
  }
  update() {
    const t = this._source.series, e = t.priceToCoordinate(this._source._p1.price), i = t.priceToCoordinate(this._source._p2.price), r = this._source.chart.timeScale(), n = r.timeToCoordinate(this._source._p1.time), u = r.timeToCoordinate(this._source._p2.time);
    this._p1 = { x: n, y: e }, this._p2 = { x: u, y: i };
  }
  renderer() {
    return new g(
      this._p1,
      this._p2,
      this._source._options.fillColor
    );
  }
}
class v {
  _p1;
  _p2;
  _fillColor;
  _vertical = !1;
  constructor(t, e, i, r) {
    this._p1 = t, this._p2 = e, this._fillColor = i, this._vertical = r;
  }
  draw(t) {
    t.useBitmapCoordinateSpace((e) => {
      if (this._p1 === null || this._p2 === null) return;
      const i = e.context;
      i.globalAlpha = 0.5;
      const r = a(
        this._p1,
        this._p2,
        this._vertical ? e.verticalPixelRatio : e.horizontalPixelRatio
      );
      i.fillStyle = this._fillColor, this._vertical ? i.fillRect(0, r.position, 15, r.length) : i.fillRect(r.position, 0, r.length, 15);
    });
  }
}
class c {
  _source;
  _p1 = null;
  _p2 = null;
  _vertical = !1;
  constructor(t, e) {
    this._source = t, this._vertical = e;
  }
  update() {
    [this._p1, this._p2] = this.getPoints();
  }
  renderer() {
    return new v(
      this._p1,
      this._p2,
      this._source._options.fillColor,
      this._vertical
    );
  }
  zOrder() {
    return "bottom";
  }
}
class f extends c {
  getPoints() {
    const t = this._source.series, e = t.priceToCoordinate(this._source._p1.price), i = t.priceToCoordinate(this._source._p2.price);
    return [e, i];
  }
}
class m extends c {
  getPoints() {
    const t = this._source.chart.timeScale(), e = t.timeToCoordinate(this._source._p1.time), i = t.timeToCoordinate(this._source._p2.time);
    return [e, i];
  }
}
class _ {
  _source;
  _p;
  _pos = null;
  constructor(t, e) {
    this._source = t, this._p = e;
  }
  coordinate() {
    return this._pos ?? -1;
  }
  visible() {
    return this._source._options.showLabels;
  }
  tickVisible() {
    return this._source._options.showLabels;
  }
  textColor() {
    return this._source._options.labelTextColor;
  }
  backColor() {
    return this._source._options.labelColor;
  }
  movePoint(t) {
    this._p = t, this.update();
  }
}
class l extends _ {
  update() {
    const t = this._source.chart.timeScale();
    this._pos = t.timeToCoordinate(this._p.time);
  }
  text() {
    return this._source._options.timeLabelFormatter(this._p.time);
  }
}
class h extends _ {
  update() {
    const t = this._source.series;
    this._pos = t.priceToCoordinate(this._p.price);
  }
  text() {
    return this._source._options.priceLabelFormatter(this._p.price);
  }
}
const C = {
  fillColor: "rgba(200, 50, 100, 0.75)",
  previewFillColor: "rgba(200, 50, 100, 0.25)",
  labelColor: "rgba(200, 50, 100, 1)",
  labelTextColor: "white",
  showLabels: !0,
  priceLabelFormatter: (s) => s.toFixed(2),
  timeLabelFormatter: (s) => typeof s == "string" ? s : (d(s) ? new Date(s.year, s.month, s.day) : new Date(s * 1e3)).toLocaleDateString()
};
class p extends w {
  _options;
  _p1;
  _p2;
  _paneViews;
  _timeAxisViews;
  _priceAxisViews;
  _priceAxisPaneViews;
  _timeAxisPaneViews;
  constructor(t, e, i = {}) {
    super(), this._p1 = t, this._p2 = e, this._options = {
      ...C,
      ...i
    }, this._paneViews = [new x(this)], this._timeAxisViews = [
      new l(this, t),
      new l(this, e)
    ], this._priceAxisViews = [
      new h(this, t),
      new h(this, e)
    ], this._priceAxisPaneViews = [new f(this, !0)], this._timeAxisPaneViews = [new m(this, !1)];
  }
  updateAllViews() {
    this._paneViews.forEach((t) => t.update()), this._timeAxisViews.forEach((t) => t.update()), this._priceAxisViews.forEach((t) => t.update()), this._priceAxisPaneViews.forEach((t) => t.update()), this._timeAxisPaneViews.forEach((t) => t.update());
  }
  priceAxisViews() {
    return this._priceAxisViews;
  }
  timeAxisViews() {
    return this._timeAxisViews;
  }
  paneViews() {
    return this._paneViews;
  }
  priceAxisPaneViews() {
    return this._priceAxisPaneViews;
  }
  timeAxisPaneViews() {
    return this._timeAxisPaneViews;
  }
  applyOptions(t) {
    this._options = { ...this._options, ...t }, this.requestUpdate();
  }
}
class b extends p {
  constructor(t, e, i = {}) {
    super(t, e, i), this._options.fillColor = this._options.previewFillColor;
  }
  updateEndPoint(t) {
    this._p2 = t, this._paneViews[0].update(), this._timeAxisViews[1].movePoint(t), this._priceAxisViews[1].movePoint(t), this.requestUpdate();
  }
}
class V {
  _chart;
  _series;
  _drawingsToolbarContainer;
  _defaultOptions;
  _rectangles;
  _previewRectangle = void 0;
  _points = [];
  _drawing = !1;
  _toolbarButton;
  constructor(t, e, i, r) {
    this._chart = t, this._series = e, this._drawingsToolbarContainer = i, this._addToolbarButton(), this._defaultOptions = r, this._rectangles = [], this._chart.subscribeClick(this._clickHandler), this._chart.subscribeCrosshairMove(this._moveHandler);
  }
  _clickHandler = (t) => this._onClick(t);
  _moveHandler = (t) => this._onMouseMove(t);
  remove() {
    this.stopDrawing(), this._chart && (this._chart.unsubscribeClick(this._clickHandler), this._chart.unsubscribeCrosshairMove(this._moveHandler)), this._rectangles.forEach((t) => {
      this._removeRectangle(t);
    }), this._rectangles = [], this._removePreviewRectangle(), this._chart = void 0, this._series = void 0, this._drawingsToolbarContainer = void 0;
  }
  startDrawing() {
    this._drawing = !0, this._points = [], this._toolbarButton && (this._toolbarButton.style.fill = "rgb(100, 150, 250)");
  }
  stopDrawing() {
    this._drawing = !1, this._points = [], this._toolbarButton && (this._toolbarButton.style.fill = "rgb(0, 0, 0)");
  }
  isDrawing() {
    return this._drawing;
  }
  _onClick(t) {
    if (!this._drawing || !t.point || !t.time || !this._series) return;
    const e = this._series.coordinateToPrice(t.point.y);
    e !== null && this._addPoint({
      time: t.time,
      price: e
    });
  }
  _onMouseMove(t) {
    if (!this._drawing || !t.point || !t.time || !this._series) return;
    const e = this._series.coordinateToPrice(t.point.y);
    e !== null && this._previewRectangle && this._previewRectangle.updateEndPoint({
      time: t.time,
      price: e
    });
  }
  _addPoint(t) {
    this._points.push(t), this._points.length >= 2 && (this._addNewRectangle(this._points[0], this._points[1]), this.stopDrawing(), this._removePreviewRectangle()), this._points.length === 1 && this._addPreviewRectangle(this._points[0]);
  }
  _addNewRectangle(t, e) {
    const i = new p(t, e, { ...this._defaultOptions });
    this._rectangles.push(i), o(this._series).attachPrimitive(i);
  }
  _removeRectangle(t) {
    o(this._series).detachPrimitive(t);
  }
  _addPreviewRectangle(t) {
    this._previewRectangle = new b(t, t, {
      ...this._defaultOptions
    }), o(this._series).attachPrimitive(this._previewRectangle);
  }
  _removePreviewRectangle() {
    this._previewRectangle && (o(this._series).detachPrimitive(this._previewRectangle), this._previewRectangle = void 0);
  }
  _addToolbarButton() {
    if (!this._drawingsToolbarContainer) return;
    const t = document.createElement("div");
    t.style.width = "20px", t.style.height = "20px", t.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path d="M315.4 15.5C309.7 5.9 299.2 0 288 0s-21.7 5.9-27.4 15.5l-96 160c-5.9 9.9-6.1 22.2-.4 32.2s16.3 16.2 27.8 16.2H384c11.5 0 22.2-6.2 27.8-16.2s5.5-22.3-.4-32.2l-96-160zM288 312V456c0 22.1 17.9 40 40 40H472c22.1 0 40-17.9 40-40V312c0-22.1-17.9-40-40-40H328c-22.1 0-40 17.9-40 40zM128 512a128 128 0 1 0 0-256 128 128 0 1 0 0 256z"/></svg>', t.addEventListener("click", () => {
      this.isDrawing() ? this.stopDrawing() : this.startDrawing();
    }), this._drawingsToolbarContainer.appendChild(t), this._toolbarButton = t;
    const e = document.createElement("input");
    e.type = "color", e.value = "#C83264", e.style.width = "24px", e.style.height = "20px", e.style.border = "none", e.style.padding = "0px", e.style.backgroundColor = "transparent", e.addEventListener("change", () => {
      const i = e.value;
      this._defaultOptions.fillColor = i + "CC", this._defaultOptions.previewFillColor = i + "77", this._defaultOptions.labelColor = i;
    }), this._drawingsToolbarContainer.appendChild(e);
  }
}
export {
  V as RectangleDrawingTool
};
