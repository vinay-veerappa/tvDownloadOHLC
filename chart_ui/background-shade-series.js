const { customSeriesDefaultOptions: d } = window.LightweightCharts;
const p = {
  ...d,
  lowColor: "rgb(50, 50, 255)",
  highColor: "rgb(255, 50, 50)",
  lowValue: 0,
  highValue: 100,
  opacity: 0.8
};
function f(i, t, o) {
  const a = i - t, l = i + t, e = Math.round(
    a * o
  ), s = Math.round(
    l * o
  ) - e;
  return {
    position: e,
    length: s
  };
}
function h(i) {
  const t = i.match(/^rgb\((\d+),\s*(\d+),\s*(\d+)\)$/);
  if (!t)
    throw new Error("Invalid RGB string");
  return [
    parseInt(t[1], 10),
    parseInt(t[2], 10),
    parseInt(t[3], 10)
  ];
}
class g {
  color1;
  color2;
  constructor(t, o) {
    this.color1 = h(t), this.color2 = h(o);
  }
  createInterpolator(t, o) {
    const a = o - t, l = [
      this.color2[0] - this.color1[0],
      this.color2[1] - this.color1[1],
      this.color2[2] - this.color1[2]
    ];
    return (e) => {
      const r = (e - t) / a;
      return `rgb(${[
        Math.round(this.color1[0] + l[0] * r),
        Math.round(this.color1[1] + l[1] * r),
        Math.round(this.color1[2] + l[2] * r)
      ].join(",")})`;
    };
  }
}
class _ {
  _data = null;
  _options = null;
  draw(t) {
    t.useBitmapCoordinateSpace((o) => this._drawImpl(o));
  }
  update(t, o) {
    this._data = t, this._options = o;
  }
  _drawImpl(t) {
    if (this._data === null || this._data.bars.length === 0 || this._data.visibleRange === null || this._options === null)
      return;
    const o = this._options, a = new g(
      o.lowColor,
      o.highColor
    ).createInterpolator(o.lowValue, o.highValue), l = this._data.bars.map((r) => ({
      color: a(r.originalData.value),
      x: r.x
    })), e = this._data.barSpacing / 2;
    for (let r = this._data.visibleRange.from; r < this._data.visibleRange.to; r++) {
      const s = l[r], n = f(s.x, e, t.horizontalPixelRatio), c = 0, u = t.bitmapSize.height;
      t.context.fillStyle = s.color || "rgba(0, 0, 0, 0)", t.context.fillRect(n.position, c, n.length, u);
    }
  }
}
class b {
  _renderer;
  constructor() {
    this._renderer = new _();
  }
  priceValueBuilder(t) {
    return [NaN];
  }
  isWhitespace(t) {
    return t.value === void 0;
  }
  renderer() {
    return this._renderer;
  }
  update(t, o) {
    this._renderer.update(t, o);
  }
  defaultOptions() {
    return p;
  }
}
export {
  b as BackgroundShadeSeries
};
