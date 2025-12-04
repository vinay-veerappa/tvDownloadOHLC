const { customSeriesDefaultOptions: g } = window.LightweightCharts;
const f = {
  ...g,
  colors: [
    "#2962FF",
    "#E1575A",
    "#F28E2C",
    "rgb(164, 89, 209)",
    "rgb(27, 156, 133)"
  ]
};
function _(e) {
  return Math.floor(e * 0.5);
}
function m(e, t, s = 1, o) {
  const a = Math.round(t * e), c = Math.round(s * t), p = _(c);
  return { position: a - p, length: c };
}
function B(e, t, s) {
  const o = Math.round(s * e), a = Math.round(s * t);
  return {
    position: Math.min(o, a),
    length: Math.abs(a - o) + 1
  };
}
class v {
  _data = null;
  _options = null;
  draw(t, s) {
    t.useBitmapCoordinateSpace(
      (o) => this._drawImpl(o, s)
    );
  }
  update(t, s) {
    this._data = t, this._options = s;
  }
  _drawImpl(t, s) {
    if (this._data === null || this._data.bars.length === 0 || this._data.visibleRange === null || this._options === null)
      return;
    const o = this._options, a = this._data.barSpacing, c = this._data.bars.map((n) => {
      const u = n.originalData.values.length, i = a / (u + 1), d = i / 2 + n.x - a / 2 + i / 2;
      return {
        singleBarWidth: i,
        singleBars: n.originalData.values.map((r, l) => ({
          y: s(r) ?? 0,
          color: o.colors[l % o.colors.length],
          x: d + l * i
        }))
      };
    }), p = s(0) ?? 0;
    for (let n = this._data.visibleRange.from; n < this._data.visibleRange.to; n++) {
      const u = c[n];
      let i;
      u.singleBars.forEach((h) => {
        const d = B(
          p,
          h.y,
          t.verticalPixelRatio
        ), r = m(
          h.x,
          t.horizontalPixelRatio,
          u.singleBarWidth
        );
        t.context.beginPath(), t.context.fillStyle = h.color;
        const l = i ? r.position - i : 0;
        t.context.fillRect(
          r.position - l,
          d.position,
          r.length + l,
          d.length
        ), i = r.position + r.length;
      });
    }
  }
}
class P {
  _renderer;
  constructor() {
    this._renderer = new v();
  }
  priceValueBuilder(t) {
    return [
      0,
      ...t.values
    ];
  }
  isWhitespace(t) {
    return !t.values?.length;
  }
  renderer() {
    return this._renderer;
  }
  update(t, s) {
    this._renderer.update(t, s);
  }
  defaultOptions() {
    return f;
  }
}
export {
  P as GroupedBarsSeries
};
