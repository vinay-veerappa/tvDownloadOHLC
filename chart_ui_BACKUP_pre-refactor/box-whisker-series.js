const { customSeriesDefaultOptions: P } = window.LightweightCharts;
const w = {
  ...P,
  whiskerColor: "rgba(106, 27, 154, 1)",
  lowerQuartileFill: "rgba(103, 58, 183, 1)",
  upperQuartileFill: "rgba(233, 30, 99, 1)",
  outlierColor: "rgba(149, 152, 161, 1)"
};
function C(s) {
  return Math.floor(s * 0.5);
}
function u(s, t, i = 1, e) {
  const r = Math.round(t * s), a = e ? i : Math.round(i * t), l = C(a);
  return { position: r - l, length: a };
}
function d(s, t, i) {
  const e = Math.round(i * s), r = Math.round(i * t);
  return {
    position: Math.min(e, r),
    length: Math.abs(r - e) + 1
  };
}
function W(s) {
  return Math.max(1, Math.floor(s));
}
function M(s) {
  return W(s) / s;
}
function Y(s, t) {
  if (s >= 2.5 && s <= 4)
    return Math.floor(3 * t);
  const l = 1 - 0.2 * Math.atan(
    Math.max(4, s) - 4
  ) / (Math.PI * 0.5), h = Math.floor(s * l * t), n = Math.floor(s * t), o = Math.min(h, n);
  return Math.max(Math.floor(t), o);
}
function g(s, t) {
  let i = Y(s, t);
  return i >= 2 && Math.floor(t) % 2 !== i % 2 && i--, i;
}
function q(s) {
  const t = g(s, 1), i = Math.floor(s), e = g(s / 2, 1);
  return {
    body: t,
    medianLine: Math.max(i, t),
    extremeLines: e,
    outlierRadius: Math.min(t, 4)
  };
}
class k {
  _data = null;
  _options = null;
  draw(t, i) {
    t.useBitmapCoordinateSpace(
      (e) => this._drawImpl(e, i)
    );
  }
  update(t, i) {
    this._data = t, this._options = i;
  }
  _drawImpl(t, i) {
    if (this._data === null || this._data.bars.length === 0 || this._data.visibleRange === null || this._options === null)
      return;
    const e = this._options, r = this._data.bars.map((n) => ({
      quartilesY: n.originalData.quartiles.map((o) => i(o) ?? 0),
      outliers: (n.originalData.outliers || []).map((o) => i(o) ?? 0),
      x: n.x
    })), a = q(this._data.barSpacing), l = M(
      t.horizontalPixelRatio
    ), h = M(
      t.verticalPixelRatio
    );
    for (let n = this._data.visibleRange.from; n < this._data.visibleRange.to; n++) {
      const o = r[n];
      a.outlierRadius > 2 && this._drawOutliers(
        t.context,
        o,
        a.outlierRadius,
        e,
        t.horizontalPixelRatio,
        t.verticalPixelRatio
      ), this._drawWhisker(
        t.context,
        o,
        a.extremeLines,
        e,
        t.horizontalPixelRatio,
        t.verticalPixelRatio,
        l,
        h
      ), this._drawBox(
        t.context,
        o,
        a.body,
        e,
        t.horizontalPixelRatio,
        t.verticalPixelRatio
      ), this._drawMedianLine(
        t.context,
        o,
        a.medianLine,
        e,
        t.horizontalPixelRatio,
        t.verticalPixelRatio,
        h
      );
    }
  }
  _drawWhisker(t, i, e, r, a, l, h, n) {
    t.save(), t.fillStyle = r.whiskerColor;
    const o = u(
      i.x,
      a,
      h
    ), f = d(
      i.quartilesY[0],
      i.quartilesY[1],
      l
    );
    t.fillRect(
      o.position,
      f.position,
      o.length,
      f.length
    );
    const p = d(
      i.quartilesY[3],
      i.quartilesY[4],
      l
    );
    t.fillRect(
      o.position,
      p.position,
      o.length,
      p.length
    );
    const c = u(
      i.x,
      a,
      e
    ), m = u(
      i.quartilesY[4],
      l,
      n
    );
    t.fillRect(
      c.position,
      m.position,
      c.length,
      m.length
    );
    const _ = u(
      i.quartilesY[0],
      l,
      n
    );
    t.fillRect(
      c.position,
      _.position,
      c.length,
      _.length
    ), t.restore();
  }
  _drawBox(t, i, e, r, a, l) {
    t.save();
    const h = d(
      i.quartilesY[2],
      i.quartilesY[3],
      l
    ), n = d(
      i.quartilesY[1],
      i.quartilesY[2],
      l
    ), o = u(i.x, a, e);
    t.fillStyle = r.lowerQuartileFill, t.fillRect(
      o.position,
      n.position,
      o.length,
      n.length
    ), t.fillStyle = r.upperQuartileFill, t.fillRect(
      o.position,
      h.position,
      o.length,
      h.length
    ), t.restore();
  }
  _drawMedianLine(t, i, e, r, a, l, h) {
    const n = u(i.x, a, e), o = u(
      i.quartilesY[2],
      l,
      h
    );
    t.save(), t.fillStyle = r.whiskerColor, t.fillRect(n.position, o.position, n.length, o.length), t.restore();
  }
  _drawOutliers(t, i, e, r, a, l) {
    t.save();
    const h = u(i.x, a, 1, !0);
    t.fillStyle = r.outlierColor, t.lineWidth = 0, i.outliers.forEach((n) => {
      t.beginPath();
      const o = u(n, l, 1, !0);
      t.arc(h.position, o.position, e, 0, 2 * Math.PI), t.fill(), t.closePath();
    }), t.restore();
  }
}
class v {
  _renderer;
  constructor() {
    this._renderer = new k();
  }
  priceValueBuilder(t) {
    return [t.quartiles[4], t.quartiles[0], t.quartiles[2]];
  }
  isWhitespace(t) {
    return t.quartiles === void 0;
  }
  renderer() {
    return this._renderer;
  }
  update(t, i) {
    this._renderer.update(t, i);
  }
  defaultOptions() {
    return w;
  }
}
export {
  v as WhiskerBoxSeries
};
