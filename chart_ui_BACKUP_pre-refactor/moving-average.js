const { LineSeries: f } = window.LightweightCharts;
function l(r) {
  for (const e of r)
    if (typeof e.time != "number")
      throw new Error('All items must have a numeric "time" property.');
  return r;
}
function d(r) {
  for (const e of r) {
    if (typeof e.close == "number")
      return "close";
    if (typeof e.value == "number")
      return "value";
  }
  return null;
}
function m(r, e) {
  const s = e.source ?? d(r);
  if (!s)
    throw new Error(
      "Please provide a `source` property for the moving average indicator."
    );
  l(r);
  const n = r.map(
    (c) => c[s]
  ), a = r.map((c) => c.time), i = h(
    n,
    e.length
  );
  let t = i;
  e.smoothingLine && e.smoothingLength && e.smoothingLength > 1 && (t = p(i, e.smoothingLine, e.smoothingLength));
  let o = e.offset ?? 0;
  return o !== 0 && (o > 0 ? t = Array(o).fill(void 0).concat(t.slice(0, t.length - o)) : o < 0 && (t = t.slice(-o).concat(Array(-o).fill(void 0)))), a.map(
    (c, u) => typeof t[u] == "number" ? { time: c, value: t[u] } : { time: c }
  );
}
function p(r, e, s) {
  switch (e) {
    case "SMA":
      return h(r, s);
    case "EMA":
      return v(r, s);
    case "WMA":
      return _(r, s);
    default:
      throw new Error("Unknown smoothing method: " + e);
  }
}
function h(r, e) {
  const s = [];
  let n = 0;
  const a = [];
  for (let i = 0; i < r.length; ++i) {
    const t = r[i];
    if (typeof t != "number") {
      s.push(void 0);
      continue;
    }
    if (a.push(t), n += t, a.length > e) {
      const o = a.shift();
      n -= o;
    }
    a.length === e && a.every((o) => !isNaN(o)) ? s.push(n / e) : s.push(void 0);
  }
  return s;
}
function v(r, e) {
  const s = [];
  let n;
  const a = 2 / (e + 1);
  for (let i = 0; i < r.length; ++i) {
    const t = r[i];
    if (typeof t != "number") {
      s.push(void 0);
      continue;
    }
    n === void 0 ? n = t : n = t * a + n * (1 - a), s.push(n);
  }
  for (let i = 0; i < e - 1 && i < s.length; ++i)
    s[i] = void 0;
  return s;
}
function _(r, e) {
  const s = [], n = Array.from({ length: e }, (i, t) => t + 1), a = n.reduce((i, t) => i + t, 0);
  for (let i = 0; i < r.length; ++i) {
    if (i < e - 1) {
      s.push(void 0);
      continue;
    }
    let t = 0, o = !0;
    for (let c = 0; c < e; ++c) {
      const u = r[i - e + 1 + c];
      if (typeof u != "number") {
        o = !1;
        break;
      }
      t += u * n[c];
    }
    s.push(o ? t / a : void 0);
  }
  return s;
}
function S(r, e) {
  class s {
    _baseSeries = null;
    _indicatorSeries = null;
    _chart = null;
    _options = null;
    attached(i) {
      const { chart: t, series: o } = i;
      this._chart = t, this._baseSeries = o, this._indicatorSeries = this._chart.addSeries(f), this._options = e, o.subscribeDataChanged(this._updateData), this._updateData();
    }
    detached() {
      this._baseSeries && this._baseSeries.unsubscribeDataChanged(this._updateData), this._indicatorSeries && this._chart?.removeSeries(this._indicatorSeries), this._indicatorSeries = null;
    }
    indicatorSeries() {
      if (!this._indicatorSeries)
        throw new Error("unable to provide indicator series");
      return this._indicatorSeries;
    }
    applyOptions(i) {
      this._options = {
        ...this._options || {},
        ...i
      }, this._updateData();
    }
    _updateData = () => {
      if (!this._indicatorSeries)
        return;
      if (!this._baseSeries) {
        this._indicatorSeries.setData([]);
        return;
      }
      const i = this._baseSeries.data(), t = m(
        i,
        this._options || e
      );
      this._indicatorSeries.setData(t);
    };
  }
  const n = new s();
  return r.attachPrimitive(n), n.indicatorSeries();
}
export {
  S as applyMovingAverageIndicator
};
