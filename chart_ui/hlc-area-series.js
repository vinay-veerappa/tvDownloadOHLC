const { customSeriesDefaultOptions: g } = window.LightweightCharts;
const w = {
  ...g,
  highLineColor: "#049981",
  lowLineColor: "#F23645",
  closeLineColor: "#878993",
  areaBottomColor: "rgba(242, 54, 69, 0.2)",
  areaTopColor: "rgba(4, 153, 129, 0.2)",
  highLineWidth: 2,
  lowLineWidth: 2,
  closeLineWidth: 2
};
class v {
  _data = null;
  _options = null;
  draw(t, l) {
    t.useBitmapCoordinateSpace(
      (o) => this._drawImpl(o, l)
    );
  }
  update(t, l) {
    this._data = t, this._options = l;
  }
  _drawImpl(t, l) {
    if (this._data === null || this._data.bars.length === 0 || this._data.visibleRange === null || this._options === null)
      return;
    const o = this._options, d = this._data.bars.map((e) => ({
      x: e.x * t.horizontalPixelRatio,
      high: l(e.originalData.high) * t.verticalPixelRatio,
      low: l(e.originalData.low) * t.verticalPixelRatio,
      close: l(e.originalData.close) * t.verticalPixelRatio
    })), i = t.context;
    i.beginPath();
    const u = new Path2D(), x = new Path2D(), r = new Path2D(), a = d[this._data.visibleRange.from];
    u.moveTo(a.x, a.low), x.moveTo(a.x, a.high);
    for (let e = this._data.visibleRange.from + 1; e < this._data.visibleRange.to; e++) {
      const s = d[e];
      u.lineTo(s.x, s.low), x.lineTo(s.x, s.high);
    }
    const n = d[this._data.visibleRange.to - 1];
    r.moveTo(n.x, n.close);
    for (let e = this._data.visibleRange.to - 2; e >= this._data.visibleRange.from; e--) {
      const s = d[e];
      r.lineTo(s.x, s.close);
    }
    const h = new Path2D(x);
    h.lineTo(n.x, n.close), h.addPath(r), h.lineTo(a.x, a.high), h.closePath(), i.fillStyle = o.areaTopColor, i.fill(h);
    const c = new Path2D(u);
    c.lineTo(n.x, n.close), c.addPath(r), c.lineTo(a.x, a.low), c.closePath(), i.fillStyle = o.areaBottomColor, i.fill(c), i.lineJoin = "round", i.strokeStyle = o.lowLineColor, i.lineWidth = o.lowLineWidth * t.verticalPixelRatio, i.stroke(u), i.strokeStyle = o.highLineColor, i.lineWidth = o.highLineWidth * t.verticalPixelRatio, i.stroke(x), i.strokeStyle = o.closeLineColor, i.lineWidth = o.closeLineWidth * t.verticalPixelRatio, i.stroke(r);
  }
}
class P {
  _renderer;
  constructor() {
    this._renderer = new v();
  }
  priceValueBuilder(t) {
    return [t.low, t.high, t.close];
  }
  isWhitespace(t) {
    return t.close === void 0;
  }
  renderer() {
    return this._renderer;
  }
  update(t, l) {
    this._renderer.update(t, l);
  }
  defaultOptions() {
    return w;
  }
}
export {
  P as HLCAreaSeries
};
