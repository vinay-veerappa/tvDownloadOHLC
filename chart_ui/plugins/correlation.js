import { BaselineSeries as V } from "lightweight-charts";
class X {
  numbers;
  cache;
  constructor(e) {
    this.numbers = e, this.cache = /* @__PURE__ */ new Map();
  }
  findClosestIndex(e, a) {
    const n = `${e}:${a}`;
    if (this.cache.has(n))
      return this.cache.get(n);
    const s = this._performSearch(e, a);
    return this.cache.set(n, s), s;
  }
  _performSearch(e, a) {
    let n = 0, s = this.numbers.length - 1;
    if (e <= this.numbers[0].time) return 0;
    if (e >= this.numbers[s].time) return s;
    for (; n <= s; ) {
      const u = Math.floor((n + s) / 2), r = this.numbers[u].time;
      if (r === e)
        return u;
      r > e ? s = u - 1 : n = u + 1;
    }
    return a === "left" ? n : s;
  }
}
function D(o) {
  for (const e of o)
    if (typeof e.time != "number")
      throw new Error('All items must have a numeric "time" property.');
  return o;
}
function v(o) {
  for (const e of o) {
    if (typeof e.close == "number")
      return "close";
    if (typeof e.value == "number")
      return "value";
  }
  return null;
}
function Y(o, e, a) {
  const n = a.primarySource ?? v(o);
  if (!n)
    throw new Error(
      "Please provide a `primarySource` for the primary data of the correlation indicator."
    );
  const s = a.secondarySource ?? v(e);
  if (!s)
    throw new Error(
      "Please provide a `secondarySource` for the secondary data of the correlation indicator."
    );
  D(o);
  const u = new X(
    D(e)
  ), r = a.length, t = [], i = [];
  return o.map((d) => {
    const m = {
      time: d.time
    }, S = d[n];
    if (S === void 0)
      return t.push(NaN), i.push(NaN), t.length > r && (t.shift(), i.shift()), m;
    const N = u.findClosestIndex(
      d.time,
      "left"
    ), b = e[N], y = b?.[s], C = b?.time === d.time;
    if (y === void 0 || !a.allowMismatchedDates && !C)
      return t.push(NaN), i.push(NaN), t.length > r && (t.shift(), i.shift()), m;
    if (t.push(S), i.push(y), t.length > r && (t.shift(), i.shift()), t.length < r || t.some(isNaN) || i.some(isNaN))
      return m;
    const f = r, _ = t.reduce((h, c) => h + c, 0), p = i.reduce((h, c) => h + c, 0), g = t.reduce(
      (h, c, E) => h + c * i[E],
      0
    ), x = t.reduce((h, c) => h + c * c, 0), I = i.reduce((h, c) => h + c * c, 0), M = f * g - _ * p, w = Math.sqrt(
      (f * x - _ * _) * (f * I - p * p)
    );
    let l;
    return w === 0 ? l = 0 : (l = M / w, l = Math.max(-1, Math.min(1, l))), {
      time: d.time,
      value: l
    };
  });
}
function T(o, e, a) {
  class n {
    _baseSeries = null;
    _secondarySeries = null;
    _indicatorSeries = null;
    _chart = null;
    _options = null;
    attached(r) {
      const { chart: t, series: i } = r;
      this._chart = t, this._baseSeries = i, this._secondarySeries = e, this._indicatorSeries = this._chart.addSeries(V), this._options = a, i.subscribeDataChanged(this._updateData), this._secondarySeries.subscribeDataChanged(this._updateData), this._updateData();
    }
    detached() {
      this._baseSeries && this._baseSeries.unsubscribeDataChanged(this._updateData), this._secondarySeries && this._secondarySeries.unsubscribeDataChanged(this._updateData), this._indicatorSeries && this._chart?.removeSeries(this._indicatorSeries), this._indicatorSeries = null;
    }
    indicatorSeries() {
      if (!this._indicatorSeries)
        throw new Error("unable to provide indicator series");
      return this._indicatorSeries;
    }
    applyOptions(r) {
      this._options = {
        ...this._options || {},
        ...r
      }, this._updateData();
    }
    _updateData = () => {
      if (!this._indicatorSeries)
        return;
      if (!this._baseSeries || !this._secondarySeries) {
        this._indicatorSeries.setData([]);
        return;
      }
      const r = this._baseSeries.data(), t = this._secondarySeries.data(), i = Y(
        r,
        t,
        this._options || a
      );
      this._indicatorSeries.setData(i);
    };
  }
  const s = new n();
  return o.attachPrimitive(s), s.indicatorSeries();
}
export {
  T as applyCorrelationIndicator
};
