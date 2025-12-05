function _(o) {
  if (o === void 0)
    throw new Error("Value is undefined");
  return o;
}
class w {
  _chart = void 0;
  _series = void 0;
  requestUpdate() {
    this._requestUpdate && this._requestUpdate();
  }
  _requestUpdate;
  attached({ chart: e, series: t, requestUpdate: i }) {
    this._chart = e, this._series = t, this._series.subscribeDataChanged(this._fireDataUpdated), this._requestUpdate = i, this.requestUpdate();
  }
  detached() {
    this._series?.unsubscribeDataChanged(this._fireDataUpdated), this._chart = void 0, this._series = void 0, this._requestUpdate = void 0;
  }
  get chart() {
    return _(this._chart);
  }
  get series() {
    return _(this._series);
  }
  // This method is a class property to maintain the
  // lexical 'this' scope (due to the use of the arrow function)
  // and to ensure its reference stays the same, so we can unsubscribe later.
  _fireDataUpdated = (e) => {
    this.dataUpdated && this.dataUpdated(e);
  };
}
function m(o) {
  return JSON.parse(JSON.stringify(o));
}
class p {
  numbers;
  cache;
  constructor(e) {
    this.numbers = e, this.cache = /* @__PURE__ */ new Map();
  }
  findClosestIndex(e, t) {
    const i = `${e}:${t}`;
    if (this.cache.has(i))
      return this.cache.get(i);
    const s = this._performSearch(e, t);
    return this.cache.set(i, s), s;
  }
  _performSearch(e, t) {
    let i = 0, s = this.numbers.length - 1;
    if (e <= this.numbers[0].time) return 0;
    if (e >= this.numbers[s].time) return s;
    for (; i <= s; ) {
      const r = Math.floor((i + s) / 2), a = this.numbers[r].time;
      if (a === e)
        return r;
      a > e ? s = r - 1 : i = r + 1;
    }
    return t === "left" ? i : s;
  }
}
class f {
  _arr;
  _chunkSize;
  _cache;
  constructor(e, t = 10) {
    this._arr = e, this._chunkSize = t, this._cache = /* @__PURE__ */ new Map();
  }
  getMinMax(e, t) {
    const i = `${e}:${t}`;
    if (i in this._cache)
      return this._cache.get(i);
    const s = {
      lower: 1 / 0,
      upper: -1 / 0
    }, r = Math.floor(e / this._chunkSize), a = Math.floor(t / this._chunkSize);
    for (let h = r; h <= a; h++) {
      const n = h * this._chunkSize, u = Math.min(
        (h + 1) * this._chunkSize - 1,
        this._arr.length - 1
      ), d = `${n}:${u}`;
      if (d in this._cache.keys()) {
        const c = this._cache.get(i);
        this._check(c, s);
      } else {
        const c = {
          lower: 1 / 0,
          upper: -1 / 0
        };
        for (let l = n; l <= u; l++)
          this._check(this._arr[l], c);
        this._cache.set(d, c), this._check(c, s);
      }
    }
    return this._cache.set(i, s), s;
  }
  _check(e, t) {
    e.lower < t.lower && (t.lower = e.lower), e.upper > t.upper && (t.upper = e.upper);
  }
}
class I {
  _viewData;
  constructor(e) {
    this._viewData = e;
  }
  draw() {
  }
  drawBackground(e) {
    const t = this._viewData.data;
    e.useBitmapCoordinateSpace((i) => {
      const s = i.context;
      s.scale(i.horizontalPixelRatio, i.verticalPixelRatio), s.strokeStyle = this._viewData.options.lineColor, s.lineWidth = this._viewData.options.lineWidth, s.beginPath();
      const r = new Path2D(), a = new Path2D();
      r.moveTo(t[0].x, t[0].upper), a.moveTo(t[0].x, t[0].upper);
      for (const n of t)
        r.lineTo(n.x, n.upper), a.lineTo(n.x, n.upper);
      const h = t.length - 1;
      r.lineTo(t[h].x, t[h].lower), a.moveTo(t[h].x, t[h].lower);
      for (let n = t.length - 2; n >= 0; n--)
        r.lineTo(t[n].x, t[n].lower), a.lineTo(t[n].x, t[n].lower);
      r.lineTo(t[0].x, t[0].upper), r.closePath(), s.stroke(a), s.fillStyle = this._viewData.options.fillColor, s.fill(r);
    });
  }
}
class x {
  _source;
  _data;
  constructor(e) {
    this._source = e, this._data = {
      data: [],
      options: this._source._options
    };
  }
  update() {
    const e = this._source.series, t = this._source.chart.timeScale();
    this._data.data = this._source._bandsData.map((i) => ({
      x: t.timeToCoordinate(i.time) ?? -100,
      upper: e.priceToCoordinate(i.upper) ?? -100,
      lower: e.priceToCoordinate(i.lower) ?? -100
    }));
  }
  renderer() {
    return new I(this._data);
  }
}
function T(o) {
  if (o.close) return o.close;
  if (o.value) return o.value;
}
const g = {
  lineColor: "rgb(25, 200, 100)",
  fillColor: "rgba(25, 200, 100, 0.25)",
  lineWidth: 1
};
class D extends w {
  _paneViews;
  _seriesData = [];
  _bandsData = [];
  _options;
  _timeIndices;
  _upperLower;
  constructor(e = {}) {
    super(), this._options = { ...g, ...e }, this._paneViews = [new x(this)], this._timeIndices = new p([]), this._upperLower = new f([]);
  }
  updateAllViews() {
    this._paneViews.forEach((e) => e.update());
  }
  paneViews() {
    return this._paneViews;
  }
  attached(e) {
    super.attached(e), this.dataUpdated("full");
  }
  dataUpdated(e) {
    this._seriesData = m(this.series.data()), this.calculateBands(), e === "full" && (this._timeIndices = new p(
      this._seriesData
    ));
  }
  _minValue = Number.POSITIVE_INFINITY;
  _maxValue = Number.NEGATIVE_INFINITY;
  calculateBands() {
    const e = new Array(this._seriesData.length);
    let t = 0;
    this._minValue = Number.POSITIVE_INFINITY, this._maxValue = Number.NEGATIVE_INFINITY, this._seriesData.forEach((i) => {
      const s = T(i);
      if (s === void 0) return;
      const r = s * 1.1, a = s * 0.9;
      r > this._maxValue && (this._maxValue = r), a < this._minValue && (this._minValue = a), e[t] = {
        upper: r,
        lower: a,
        time: i.time
      }, t += 1;
    }), e.length = t, this._bandsData = e, this._upperLower = new f(this._bandsData, 4);
  }
  autoscaleInfo(e, t) {
    const i = this.chart.timeScale(), s = i.coordinateToTime(
      i.logicalToCoordinate(e) ?? 0
    ) ?? 0, r = i.coordinateToTime(
      i.logicalToCoordinate(t) ?? 5e9
    ) ?? 5e9, a = this._timeIndices.findClosestIndex(s, "left"), h = this._timeIndices.findClosestIndex(r, "right"), n = this._upperLower.getMinMax(a, h);
    return {
      priceRange: {
        minValue: n.lower,
        maxValue: n.upper
      }
    };
  }
}
export {
  D as BandsIndicator
};
