import { customSeriesDefaultOptions as T } from "lightweight-charts";
const W = {
  ...T,
  colors: ["#ACE5DC", "#42BDA8", "#FCCACD", "#F77C80"],
  borderRadius: [2, 0, 2, 0],
  maxHeight: 130
}, H = 4, P = 1;
function _(n, t) {
  return Math.ceil(n * t) <= P ? 0 : Math.max(1, Math.floor(t));
}
function C(n, t, o) {
  return Math.round(n * t) - (o ?? _(n, t));
}
function L(n, t) {
  const o = _(n, t), s = C(
    n,
    t,
    o
  ), i = s % 2 === 0, a = (s - (i ? 0 : 1)) / 2;
  return {
    spacing: o,
    shiftLeft: i,
    columnHalfWidthBitmap: a,
    horizontalPixelRatio: t
  };
}
function D(n, t, o) {
  const s = n * t.horizontalPixelRatio, i = Math.round(s), a = {
    left: i - t.columnHalfWidthBitmap,
    right: i + t.columnHalfWidthBitmap - (t.shiftLeft ? 1 : 0),
    shiftLeft: i > s
  }, u = t.spacing + 1;
  return o && a.left - o.right !== u && (o.shiftLeft ? o.right = a.left - u : a.left = o.right + u), a;
}
function w(n, t, o, s, i) {
  const a = L(t, o);
  let u;
  for (let e = s; e < Math.min(i, n.length); e++)
    n[e].column = D(n[e].x, a, u), u = n[e].column;
  const c = n.reduce(
    (e, l, r) => {
      if (!l.column || r < s || r > i)
        return e;
      l.column.right < l.column.left && (l.column.right = l.column.left);
      const h = l.column.right - l.column.left + 1;
      return Math.min(e, h);
    },
    Math.ceil(t * o)
  );
  a.spacing > 0 && c < H && n.forEach(
    (e, l) => !e.column || l < s || l > i ? void 0 : e.column.right - e.column.left + 1 <= c ? e : (e.column.shiftLeft ? e.column.right -= 1 : e.column.left += 1, e.column)
  );
}
function A(n, t, o) {
  const s = Math.round(o * n), i = Math.round(o * t);
  return {
    position: Math.min(s, i),
    length: Math.abs(i - s) + 1
  };
}
function E(n, t) {
  return n.map(
    (o) => o === 0 ? o : o + t
  );
}
function d(n, t, o, s, i, a) {
  if (n.beginPath(), n.roundRect) {
    n.roundRect(t, o, s, i, a);
    return;
  }
  n.lineTo(t + s - a[1], o), a[1] !== 0 && n.arcTo(t + s, o, t + s, o + a[1], a[1]), n.lineTo(t + s, o + i - a[2]), a[2] !== 0 && n.arcTo(t + s, o + i, t + s - a[2], o + i, a[2]), n.lineTo(t + a[3], o + i), a[3] !== 0 && n.arcTo(t, o + i, t, o + i - a[3], a[3]), n.lineTo(t, o + a[0]), a[0] !== 0 && n.arcTo(t, o, t + a[0], o, a[0]);
}
function O(n, t, o, s, i, a, u = 0, c = [0, 0, 0, 0], e = "") {
  if (n.save(), !u || !e || e === a) {
    d(n, t, o, s, i, c), n.fillStyle = a, n.fill(), n.restore();
    return;
  }
  const l = u / 2, r = E(c, -l);
  d(
    n,
    t + l,
    o + l,
    s - u,
    i - u,
    r
  ), a !== "transparent" && (n.fillStyle = a, n.fill()), e !== "transparent" && (n.lineWidth = u, n.strokeStyle = e, n.closePath(), n.stroke()), n.restore();
}
class S {
  _data = null;
  _options = null;
  draw(t, o) {
    t.useBitmapCoordinateSpace(
      (s) => this._drawImpl(s, o)
    );
  }
  update(t, o) {
    this._data = t, this._options = o;
  }
  _drawImpl(t, o) {
    if (this._data === null || this._data.bars.length === 0 || this._data.visibleRange === null || this._options === null)
      return;
    const s = this._options;
    let i = 0;
    for (let l = this._data.visibleRange.from; l < this._data.visibleRange.to; l++) {
      const r = this._data.bars[l].originalData.values;
      for (const h of r)
        Math.abs(h) > i && (i = Math.abs(h));
    }
    const a = s.maxHeight / 2, u = this._data.bars.map((l) => ({
      x: l.x,
      ys: l.originalData.values.map((r) => Math.abs(r) / i * Math.sign(r) * a),
      positive: l.originalData.values.map((r) => r >= 0)
    }));
    w(
      u,
      this._data.barSpacing,
      t.horizontalPixelRatio,
      this._data.visibleRange.from,
      this._data.visibleRange.to
    );
    const c = o(0) ?? 0, e = this._data.barSpacing * t.horizontalPixelRatio < 4 ? 0 : Math.max(1, 0.5 * t.horizontalPixelRatio);
    for (let l = this._data.visibleRange.from; l < this._data.visibleRange.to; l++) {
      const r = u[l], h = r.column;
      if (!h) continue;
      const p = Math.min(
        Math.max(
          t.horizontalPixelRatio,
          h.right - h.left
        ),
        this._data.barSpacing * t.horizontalPixelRatio
      );
      r.ys.forEach((R, m) => {
        const M = s.colors[m % s.colors.length], g = A(
          c,
          c - R,
          t.verticalPixelRatio
        ), v = s.borderRadius[m % s.borderRadius.length] * t.verticalPixelRatio, B = r.positive[m], f = Math.floor(
          Math.min(v, p / 2, Math.abs(g.length))
        ), b = B ? [f, f, 0, 0] : [0, 0, f, f];
        O(
          t.context,
          h.left,
          g.position,
          p,
          g.length,
          M,
          e,
          b,
          "transparent"
        );
      });
    }
  }
}
class F {
  _renderer;
  constructor() {
    this._renderer = new S();
  }
  priceValueBuilder() {
    return [0];
  }
  isWhitespace(t) {
    return !t.values?.length;
  }
  renderer() {
    return this._renderer;
  }
  update(t, o) {
    this._renderer.update(t, o);
  }
  defaultOptions() {
    return W;
  }
}
export {
  F as DualRangeHistogramSeries
};
