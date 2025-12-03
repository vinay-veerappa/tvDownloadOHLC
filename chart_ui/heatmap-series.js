import { customSeriesDefaultOptions as f } from "lightweight-charts";
const p = {
  ...f,
  lastValueVisible: !1,
  priceLineVisible: !1,
  cellShader: (o) => {
    const t = Math.min(Math.max(0, o), 100);
    return `rgba(0, ${100 + t * 1.55}, ${0 + t}, ${0.2 + t * 0.8})`;
  },
  cellBorderWidth: 1,
  cellBorderColor: "transparent"
};
function m(o, t, i) {
  const l = o - t, a = o + t, e = Math.round(
    l * i
  ), s = Math.round(
    a * i
  ) - e;
  return {
    position: e,
    length: s
  };
}
function _(o, t, i) {
  const l = Math.round(i * o), a = Math.round(i * t);
  return {
    position: Math.min(l, a),
    length: Math.abs(a - l) + 1
  };
}
class W {
  _data = null;
  _options = null;
  draw(t, i) {
    t.useBitmapCoordinateSpace(
      (l) => this._drawImpl(l, i)
    );
  }
  update(t, i) {
    this._data = t, this._options = i;
  }
  _drawImpl(t, i) {
    if (this._data === null || this._data.bars.length === 0 || this._data.visibleRange === null || this._options === null)
      return;
    const l = this._options, a = this._data.bars.map((n) => ({
      x: n.x,
      cells: n.originalData.cells.map((s) => ({
        amount: s.amount,
        low: i(s.low),
        high: i(s.high)
      }))
    })), e = this._data.barSpacing > l.cellBorderWidth * 3;
    for (let n = this._data.visibleRange.from; n < this._data.visibleRange.to; n++) {
      const s = a[n], h = m(
        s.x,
        this._data.barSpacing / 2,
        t.horizontalPixelRatio
      ), r = e ? l.cellBorderWidth * t.horizontalPixelRatio : 0, d = e ? l.cellBorderWidth * t.verticalPixelRatio : 0;
      for (const u of s.cells) {
        const c = _(
          u.low,
          u.high,
          t.verticalPixelRatio
        );
        t.context.fillStyle = l.cellShader(u.amount), t.context.fillRect(
          h.position + r,
          c.position + d,
          h.length - r * 2,
          c.length - 1 - d * 2
        ), e && l.cellBorderWidth && l.cellBorderColor !== "transparent" && (t.context.beginPath(), t.context.rect(
          h.position + r / 2,
          c.position + d / 2,
          h.length - r,
          c.length - 1 - d
        ), t.context.strokeStyle = l.cellBorderColor, t.context.lineWidth = r, t.context.stroke());
      }
    }
  }
}
class b {
  _renderer;
  constructor() {
    this._renderer = new W();
  }
  priceValueBuilder(t) {
    if (t.cells.length < 1)
      return [NaN];
    let i = 1 / 0, l = -1 / 0;
    t.cells.forEach((e) => {
      e.low < i && (i = e.low), e.high > l && (l = e.high);
    });
    const a = i + (l - i) / 2;
    return [i, l, a];
  }
  isWhitespace(t) {
    return t.cells === void 0 || t.cells.length < 1;
  }
  renderer() {
    return this._renderer;
  }
  update(t, i) {
    this._renderer.update(t, i);
  }
  defaultOptions() {
    return p;
  }
}
export {
  b as HeatMapSeries
};
