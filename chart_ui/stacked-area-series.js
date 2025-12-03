const { customSeriesDefaultOptions: y } = window.LightweightCharts;
const b = {
  ...y,
  colors: [
    { line: "rgb(41, 98, 255)", area: "rgba(41, 98, 255, 0.2)" },
    { line: "rgb(225, 87, 90)", area: "rgba(225, 87, 90, 0.2)" },
    { line: "rgb(242, 142, 44)", area: "rgba(242, 142, 44, 0.2)" },
    { line: "rgb(164, 89, 209)", area: "rgba(164, 89, 209, 0.2)" },
    { line: "rgb(27, 156, 133)", area: "rgba(27, 156, 133, 0.2)" }
  ],
  lineWidth: 2
};
function v(d) {
  let t = 0;
  return d.map((e) => {
    const a = t + e;
    return t = a, a;
  });
}
class w {
  _data = null;
  _options = null;
  draw(t, e) {
    t.useBitmapCoordinateSpace(
      (a) => this._drawImpl(a, e)
    );
  }
  update(t, e) {
    this._data = t, this._options = e;
  }
  _drawImpl(t, e) {
    if (this._data === null || this._data.bars.length === 0 || this._data.visibleRange === null || this._options === null)
      return;
    const a = this._options, o = this._data.bars.map((n) => ({
      x: n.x,
      ys: v(n.originalData.values).map(
        (u) => e(u) ?? 0
      )
    })), p = e(0) ?? 0, f = this._createLinePaths(
      o,
      this._data.visibleRange,
      t,
      p * t.verticalPixelRatio
    ), s = this._createAreas(f), c = a.colors.length;
    s.forEach((n, u) => {
      t.context.fillStyle = a.colors[u % c].area, t.context.fill(n);
    }), t.context.lineWidth = a.lineWidth * t.verticalPixelRatio, t.context.lineJoin = "round", f.forEach((n, u) => {
      u != 0 && (t.context.beginPath(), t.context.strokeStyle = a.colors[(u - 1) % c].line, t.context.stroke(n.path));
    });
  }
  _createLinePaths(t, e, a, o) {
    const { horizontalPixelRatio: p, verticalPixelRatio: f } = a, s = [], c = [];
    let n = !0;
    for (let r = e.from; r < e.to; r++) {
      const x = t[r];
      let l = 0;
      x.ys.forEach((m, P) => {
        if (P % 2 !== 0)
          return;
        const i = x.x * p, h = m * f;
        n ? (s[l] = {
          path: new Path2D(),
          first: { x: i, y: h },
          last: { x: i, y: h }
        }, s[l].path.moveTo(i, h)) : (s[l].path.lineTo(i, h), s[l].last.x = i, s[l].last.y = h), l += 1;
      }), n = !1;
    }
    n = !0;
    for (let r = e.to - 1; r >= e.from; r--) {
      const x = t[r];
      let l = 0;
      x.ys.forEach((m, P) => {
        if (P % 2 === 0)
          return;
        const i = x.x * p, h = m * f;
        n ? (c[l] = {
          path: new Path2D(),
          first: { x: i, y: h },
          last: { x: i, y: h }
        }, c[l].path.moveTo(i, h)) : (c[l].path.lineTo(i, h), c[l].last.x = i, c[l].last.y = h), l += 1;
      }), n = !1;
    }
    const u = {
      path: new Path2D(),
      first: { x: s[0].last.x, y: o },
      last: { x: s[0].first.x, y: o }
    };
    u.path.moveTo(s[0].last.x, o), u.path.lineTo(s[0].first.x, o);
    const _ = [u];
    for (let r = 0; r < s.length; r++)
      _.push(s[r]), r < c.length && _.push(c[r]);
    return _;
  }
  _createAreas(t) {
    const e = [];
    for (let a = 1; a < t.length; a++) {
      const o = new Path2D(t[a - 1].path);
      o.lineTo(t[a].first.x, t[a].first.y), o.addPath(t[a].path), o.lineTo(t[a - 1].first.x, t[a - 1].first.y), o.closePath(), e.push(o);
    }
    return e;
  }
}
class T {
  _renderer;
  constructor() {
    this._renderer = new w();
  }
  priceValueBuilder(t) {
    return [
      0,
      t.values.reduce(
        (e, a) => e + a,
        0
      )
    ];
  }
  isWhitespace(t) {
    return !t.values?.length;
  }
  renderer() {
    return this._renderer;
  }
  update(t, e) {
    this._renderer.update(t, e);
  }
  defaultOptions() {
    return b;
  }
}
export {
  T as StackedAreaSeries
};
