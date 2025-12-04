const { MismatchDirection: c, LineSeries: f } = window.LightweightCharts;
const m = {
  interval: 60 * 60 * 24,
  clearTimeout: 3e3
};
function d(n) {
  if (n === void 0)
    throw new Error("Value is undefined");
  return n;
}
class w {
  _chart = void 0;
  _series = void 0;
  requestUpdate() {
    this._requestUpdate && this._requestUpdate();
  }
  _requestUpdate;
  attached({ chart: e, series: s, requestUpdate: i }) {
    this._chart = e, this._series = s, this._series.subscribeDataChanged(this._fireDataUpdated), this._requestUpdate = i, this.requestUpdate();
  }
  detached() {
    this._series?.unsubscribeDataChanged(this._fireDataUpdated), this._chart = void 0, this._series = void 0, this._requestUpdate = void 0;
  }
  get chart() {
    return d(this._chart);
  }
  get series() {
    return d(this._series);
  }
  // This method is a class property to maintain the
  // lexical 'this' scope (due to the use of the arrow function)
  // and to ensure its reference stays the same, so we can unsubscribe later.
  _fireDataUpdated = (e) => {
    this.dataUpdated && this.dataUpdated(e);
  };
}
const u = new Path2D(
  "M5.22 14.78a.75.75 0 001.06 0l7.22-7.22v5.69a.75.75 0 001.5 0v-7.5a.75.75 0 00-.75-.75h-7.5a.75.75 0 000 1.5h5.69l-7.22 7.22a.75.75 0 000 1.06z"
), v = new Path2D(
  "M6.28 5.22a.75.75 0 00-1.06 1.06l7.22 7.22H6.75a.75.75 0 000 1.5h7.5a.747.747 0 00.75-.75v-7.5a.75.75 0 00-1.5 0v5.69L6.28 5.22z"
), _ = new Path2D(
  "M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
), p = new Path2D(
  "M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
), g = 20;
function x(n) {
  return Math.floor(n * 0.5);
}
function S(n, e, s = 1, i) {
  const t = Math.round(e * n), r = Math.round(s * e), o = x(r);
  return { position: t - o, length: r };
}
class D {
  _data = [];
  draw(e) {
    let s = 1;
    e.useBitmapCoordinateSpace((i) => {
      s = i.verticalPixelRatio;
    }), e.useMediaCoordinateSpace((i) => {
      const t = i.context;
      t.lineWidth = 2, this._data.forEach((r) => {
        const o = S(r.priceY, s, t.lineWidth), a = (o.position + o.length / 2) / s;
        t.fillStyle = r.color, t.strokeStyle = r.color, t.lineDashOffset = 0, t.globalAlpha = r.fade ? 0.5 : 1, t.beginPath(), t.moveTo(r.startX + 4, a), t.lineTo(r.endX - 4, a), t.stroke(), t.beginPath(), t.setLineDash([3, 6]), t.lineCap = "round", t.moveTo(r.startX - 30, a), t.lineTo(i.mediaSize.width, a), t.stroke(), t.setLineDash([]), t.beginPath(), t.arc(r.startX, a, 4, 0, 2 * Math.PI), t.arc(r.endX, a, 4, 0, 2 * Math.PI), t.fill(), t.font = "10px sans-serif";
        const h = t.measureText(r.text);
        t.beginPath(), t.roundRect(r.startX - 30 - 20 - h.width, a - 7, h.width + 20, 14, 4), t.fill(), t.fillStyle = "#FFFFFF", t.fillText(r.text, r.startX - 30 - 15 - h.width, a + 3), t.save(), t.translate(r.startX - 30 - 14, a - 6);
        const l = 12 / g;
        t.scale(l, l), t.fill(r.icon, "evenodd"), t.restore();
      });
    });
  }
  update(e) {
    this._data = e;
  }
}
class C {
  _source;
  _renderer;
  constructor(e) {
    this._source = e, this._renderer = new D();
  }
  renderer() {
    return this._renderer;
  }
  update() {
    const e = [], s = this._source._chart?.timeScale();
    if (s)
      for (const i of this._source._alerts.values()) {
        const t = this._source._series.priceToCoordinate(i.price);
        if (t === null) continue;
        let r = s.timeToCoordinate(i.start), o = s.timeToCoordinate(i.end);
        if (r === null && o === null) continue;
        r || (r = 0), o || (o = s.width());
        let a = "#000000", h = u;
        i.parameters.crossingDirection === "up" ? (a = i.crossed ? "#386D2E" : i.expired ? "#30472C" : "#64C750", h = i.crossed ? _ : i.expired ? p : u) : i.parameters.crossingDirection === "down" && (a = i.crossed ? "#7C1F3E" : i.expired ? "#4A2D37" : "#C83264", h = i.crossed ? _ : i.expired ? p : v), e.push({
          priceY: t,
          startX: r,
          endX: o,
          icon: h,
          color: a,
          text: i.parameters.title,
          fade: i.expired
        });
      }
    this._renderer.update(e);
  }
}
class P extends w {
  _source;
  _views;
  constructor(e) {
    super(), this._source = e, this._views = [new C(this._source)];
  }
  requestUpdate() {
    super.requestUpdate();
  }
  updateAllViews() {
    this._views.forEach((e) => e.update());
  }
  paneViews() {
    return this._views;
  }
  autoscaleInfo() {
    let e = 1 / 0, s = -1 / 0;
    for (const i of this._source._alerts.values())
      i.price < e && (e = i.price), i.price > s && (s = i.price);
    return e > s ? null : {
      priceRange: {
        maxValue: s,
        minValue: e
      }
    };
  }
}
function E(n) {
  return n.value !== void 0;
}
class M {
  _options;
  _chart = null;
  _series;
  _primitive;
  _whitespaceSeriesStart = null;
  _whitespaceSeriesEnd = null;
  _whitespaceSeries;
  _alerts = /* @__PURE__ */ new Map();
  _dataChangedHandler;
  constructor(e, s) {
    this._series = e, this._options = {
      ...m,
      ...s
    }, this._primitive = new P(this), this._series.attachPrimitive(this._primitive), this._dataChangedHandler = this._dataChanged.bind(this), this._series.subscribeDataChanged(this._dataChangedHandler);
    const i = this._series.dataByIndex(
      1e4,
      c.NearestLeft
    );
    i && this.checkedCrossed(i), this._chart = this._primitive.chart, this._whitespaceSeries = this._chart.addSeries(f);
  }
  destroy() {
    this._series.unsubscribeDataChanged(this._dataChangedHandler), this._series.detachPrimitive(this._primitive);
  }
  alerts() {
    return this._alerts;
  }
  chart() {
    return this._chart;
  }
  series() {
    return this._series;
  }
  addExpiringAlert(e, s, i, t) {
    let r = (Math.random() * 1e5).toFixed();
    for (; this._alerts.has(r); )
      r = (Math.random() * 1e5).toFixed();
    return this._alerts.set(r, {
      price: e,
      start: s,
      end: i,
      parameters: t,
      crossed: !1,
      expired: !1
    }), this._update(), r;
  }
  removeExpiringAlert(e) {
    this._alerts.delete(e), this._update();
  }
  toggleCrossed(e) {
    const s = this._alerts.get(e);
    s && (s.crossed = !0, setTimeout(() => {
      this.removeExpiringAlert(e);
    }, this._options.clearTimeout), this._update());
  }
  checkExpired(e) {
    for (const [s, i] of this._alerts.entries())
      i.end <= e && (i.expired = !0, setTimeout(() => {
        this.removeExpiringAlert(s);
      }, this._options.clearTimeout));
    this._update();
  }
  _lastValue = void 0;
  checkedCrossed(e) {
    if (E(e)) {
      if (this._lastValue !== void 0)
        for (const [s, i] of this._alerts.entries()) {
          let t = !1;
          i.parameters.crossingDirection === "up" ? this._lastValue <= i.price && e.value > i.price && (t = !0) : i.parameters.crossingDirection === "down" && this._lastValue >= i.price && e.value < i.price && (t = !0), t && this.toggleCrossed(s);
        }
      this._lastValue = e.value;
    }
  }
  _update() {
    let e = 1 / 0, s = 0;
    const i = this._alerts.size > 0;
    for (const [t, r] of this._alerts.entries())
      r.end > s && (s = r.end), r.start < e && (e = r.start);
    if (i || (e = null, s = null), e) {
      const t = this._series.dataByIndex(1e6, c.NearestLeft)?.time ?? e;
      t < e && (e = t);
    }
    (this._whitespaceSeriesStart !== e || this._whitespaceSeriesEnd !== s) && (this._whitespaceSeriesStart = e, this._whitespaceSeriesEnd = s, !this._whitespaceSeriesStart || !this._whitespaceSeriesEnd ? this._whitespaceSeries.setData([]) : this._whitespaceSeries.setData(
      this._buildWhitespace(
        this._whitespaceSeriesStart,
        this._whitespaceSeriesEnd
      )
    )), this._primitive.requestUpdate();
  }
  _buildWhitespace(e, s) {
    const i = [];
    for (let t = e; t <= s; t += this._options.interval)
      i.push({ time: t });
    return i;
  }
  _dataChanged() {
    const e = this._series.dataByIndex(
      1e5,
      c.NearestLeft
    );
    e && (this.checkedCrossed(e), this.checkExpired(e.time));
  }
}
export {
  M as ExpiringPriceAlerts
};
