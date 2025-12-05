function n(i) {
  if (i === void 0)
    throw new Error("Value is undefined");
  return i;
}
class g {
  _chart = void 0;
  _series = void 0;
  requestUpdate() {
    this._requestUpdate && this._requestUpdate();
  }
  _requestUpdate;
  attached({ chart: t, series: e, requestUpdate: a }) {
    this._chart = t, this._series = e, this._series.subscribeDataChanged(this._fireDataUpdated), this._requestUpdate = a, this.requestUpdate();
  }
  detached() {
    this._series?.unsubscribeDataChanged(this._fireDataUpdated), this._chart = void 0, this._series = void 0, this._requestUpdate = void 0;
  }
  get chart() {
    return n(this._chart);
  }
  get series() {
    return n(this._series);
  }
  // This method is a class property to maintain the
  // lexical 'this' scope (due to the use of the arrow function)
  // and to ensure its reference stays the same, so we can unsubscribe later.
  _fireDataUpdated = (t) => {
    this.dataUpdated && this.dataUpdated(t);
  };
}
class f {
  _viewData;
  constructor(t) {
    this._viewData = t;
  }
  draw(t) {
    const e = this._viewData.data;
    t.useBitmapCoordinateSpace((a) => {
      const h = a.context, c = 0, _ = a.bitmapSize.height, s = a.horizontalPixelRatio * this._viewData.barWidth / 2, u = -1 * (s + 1), l = a.bitmapSize.width;
      e.forEach((d) => {
        const r = d.x * a.horizontalPixelRatio;
        if (r < u) return;
        h.fillStyle = d.color || "rgba(0, 0, 0, 0)";
        const o = Math.max(0, Math.round(r - s)), p = Math.min(l, Math.round(r + s));
        h.fillRect(o, c, p - o, _);
      });
    });
  }
}
class w {
  _source;
  _data;
  constructor(t) {
    this._source = t, this._data = {
      data: [],
      barWidth: 6,
      options: this._source._options
    };
  }
  update() {
    const t = this._source.chart.timeScale();
    this._data.data = this._source._backgroundColors.map((e) => ({
      x: t.timeToCoordinate(e.time) ?? -100,
      color: e.color
    })), this._data.data.length > 1 ? this._data.barWidth = this._data.data[1].x - this._data.data[0].x : this._data.barWidth = 6;
  }
  renderer() {
    return new f(this._data);
  }
  zOrder() {
    return "bottom";
  }
}
const m = {};
class b extends g {
  _paneViews;
  _seriesData = [];
  _backgroundColors = [];
  _options;
  _highlighter;
  constructor(t, e = {}) {
    super(), this._highlighter = t, this._options = { ...m, ...e }, this._paneViews = [new w(this)];
  }
  updateAllViews() {
    this._paneViews.forEach((t) => t.update());
  }
  paneViews() {
    return this._paneViews;
  }
  attached(t) {
    super.attached(t), this.dataUpdated("full");
  }
  dataUpdated(t) {
    this._backgroundColors = this.series.data().map((e) => ({
      time: e.time,
      color: this._highlighter(e.time)
    })), this.requestUpdate();
  }
}
export {
  b as SessionHighlighting
};
