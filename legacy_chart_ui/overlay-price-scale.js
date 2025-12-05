class _ {
  _data = null;
  update(e) {
    this._data = e;
  }
  draw(e) {
    e.useMediaCoordinateSpace((i) => {
      if (!this._data) return;
      const s = this._calculatePriceScale(
        i.mediaSize.height,
        this._data
      ), a = s.reduce((c, l) => Math.max(c, l.label.length), 0), n = "".padEnd(a, "0"), t = i.context, r = this._data.options.side === "left";
      t.font = "12px -apple-system, BlinkMacSystemFont, 'Trebuchet MS', Roboto, Ubuntu, sans-serif", t.textAlign = "center", t.textBaseline = "top";
      const o = t.measureText(n).width, p = r ? 10 : i.mediaSize.width - 10 - o, u = p + 3 + Math.round(o / 2);
      s.forEach((c) => {
        t.beginPath();
        const l = c.y - 12 / 2;
        t.roundRect(
          p,
          l,
          o + 3 * 2,
          12 + 2 * 2,
          4
        ), t.fillStyle = this._data.options.backgroundColor, t.fill(), t.beginPath(), t.fillStyle = this._data.options.textColor, t.fillText(c.label, u, l + 2, o);
      });
    });
  }
  _calculatePriceScale(e, i) {
    const s = [], a = Math.round(10);
    let n = a;
    for (; n <= e - a; )
      s.push(n), n += 40;
    return s.map((r) => {
      const d = i.coordinateToPrice(r);
      return d === null ? null : {
        label: i.priceFormatter.format(d),
        y: r
      };
    }).filter((r) => !!r);
  }
}
class f {
  _renderer;
  constructor() {
    this._renderer = new _();
  }
  renderer() {
    return this._renderer;
  }
  update(e) {
    this._renderer.update(e);
  }
}
const g = {
  textColor: "rgb(0, 0, 0)",
  backgroundColor: "rgba(255, 255, 255, 0.6)",
  side: "left"
};
class S {
  _paneViews;
  _chart = null;
  _series = null;
  _requestUpdate;
  _options;
  constructor(e) {
    this._options = {
      ...g,
      ...e
    }, this._paneViews = [new f()];
  }
  applyOptions(e) {
    this._options = {
      ...this._options,
      ...e
    }, this._requestUpdate && this._requestUpdate();
  }
  attached({ chart: e, series: i, requestUpdate: s }) {
    this._chart = e, this._series = i, this._requestUpdate = s;
  }
  detached() {
    this._chart = null, this._series = null;
  }
  updateAllViews() {
    if (!this._series || !this._chart) return;
    const e = (t) => this._series.coordinateToPrice(t), i = (t) => this._series.priceToCoordinate(t), s = this._series.priceFormatter(), a = this._options, n = {
      coordinateToPrice: e,
      priceToCoordinate: i,
      priceFormatter: s,
      options: a
    };
    this._paneViews.forEach((t) => t.update(n));
  }
  paneViews() {
    return this._paneViews;
  }
}
export {
  S as OverlayPriceScale
};
