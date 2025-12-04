const { customSeriesDefaultOptions: p } = window.LightweightCharts;
const _ = {
  ...p,
  lineWidth: 2
};
function f(o) {
  return Math.floor(o * 0.5);
}
function x(o, t, i = 1, s) {
  const a = Math.round(t * o), e = Math.round(i * t), r = f(e);
  return { position: a - r, length: e };
}
function m(o, t, i) {
  const s = Math.round(i * o), a = Math.round(i * t);
  return {
    position: Math.min(s, a),
    length: Math.abs(a - s) + 1
  };
}
class P {
  _data = null;
  _options = null;
  draw(t, i) {
    t.useBitmapCoordinateSpace(
      (s) => this._drawImpl(s, i)
    );
  }
  update(t, i) {
    this._data = t, this._options = i;
  }
  _drawImpl(t, i) {
    if (this._data === null || this._data.bars.length === 0 || this._data.visibleRange === null || this._options === null)
      return;
    const s = this._options, a = this._data.bars.map((n) => ({
      x: n.x,
      y: i(n.originalData.value) ?? 0
    })), e = Math.min(this._options.lineWidth, this._data.barSpacing), r = this._data.barSpacing, h = Math.floor(r / 2), d = i(0);
    for (let n = this._data.visibleRange.from; n < this._data.visibleRange.to; n++) {
      const l = a[n], u = x(
        l.x,
        t.horizontalPixelRatio,
        e
      ), c = m(
        d ?? 0,
        l.y,
        t.verticalPixelRatio
      );
      t.context.beginPath(), t.context.fillStyle = s.color, t.context.fillRect(
        u.position,
        c.position,
        u.length,
        c.length
      ), t.context.arc(
        l.x * t.horizontalPixelRatio,
        l.y * t.verticalPixelRatio,
        h * t.horizontalPixelRatio,
        0,
        Math.PI * 2
      ), t.context.fill();
    }
  }
}
class M {
  _renderer;
  constructor() {
    this._renderer = new P();
  }
  priceValueBuilder(t) {
    return [0, t.value];
  }
  isWhitespace(t) {
    return t.value === void 0;
  }
  renderer() {
    return this._renderer;
  }
  update(t, i) {
    this._renderer.update(t, i);
  }
  defaultOptions() {
    return _;
  }
}
export {
  M as LollipopSeries
};
