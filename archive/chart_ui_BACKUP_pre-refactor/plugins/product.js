import { LineSeries as f } from "lightweight-charts";
class m {
  numbers;
  cache;
  constructor(e) {
    this.numbers = e, this.cache = /* @__PURE__ */ new Map();
  }
  findClosestIndex(e, n) {
    const r = `${e}:${n}`;
    if (this.cache.has(r))
      return this.cache.get(r);
    const t = this._performSearch(e, n);
    return this.cache.set(r, t), t;
  }
  _performSearch(e, n) {
    let r = 0, t = this.numbers.length - 1;
    if (e <= this.numbers[0].time) return 0;
    if (e >= this.numbers[t].time) return t;
    for (; r <= t; ) {
      const a = Math.floor((r + t) / 2), i = this.numbers[a].time;
      if (i === e)
        return a;
      i > e ? t = a - 1 : r = a + 1;
    }
    return n === "left" ? r : t;
  }
}
function d(s) {
  for (const e of s)
    if (typeof e.time != "number")
      throw new Error('All items must have a numeric "time" property.');
  return s;
}
function l(s) {
  for (const e of s) {
    if (typeof e.close == "number")
      return "close";
    if (typeof e.value == "number")
      return "value";
  }
  return null;
}
function _(s, e, n) {
  const r = n.primarySource ?? l(s);
  if (!r)
    throw new Error(
      "Please provide a `primarySource` for the primary data of the product indicator."
    );
  const t = n.secondarySource ?? l(e);
  if (!t)
    throw new Error(
      "Please provide a `secondarySource` for the secondary data of the product indicator."
    );
  d(s);
  const a = new m(
    d(e)
  );
  return s.map((i) => {
    const c = {
      time: i.time
    }, o = i[r];
    if (o === void 0)
      return c;
    const h = a.findClosestIndex(
      i.time,
      "left"
    ), u = e[h][t];
    return u === void 0 || !n.allowMismatchedDates && e[h].time !== i.time ? c : {
      time: i.time,
      value: o * u
    };
  });
}
function p(s, e, n) {
  class r {
    _baseSeries = null;
    _secondarySeries = null;
    _indicatorSeries = null;
    _chart = null;
    _options = null;
    attached(i) {
      const { chart: c, series: o } = i;
      this._chart = c, this._baseSeries = o, this._secondarySeries = e, this._indicatorSeries = this._chart.addSeries(f), this._options = n, o.subscribeDataChanged(this._updateData), this._secondarySeries.subscribeDataChanged(this._updateData), this._updateData();
    }
    detached() {
      this._baseSeries && this._baseSeries.unsubscribeDataChanged(this._updateData), this._secondarySeries && this._secondarySeries.unsubscribeDataChanged(this._updateData), this._indicatorSeries && this._chart?.removeSeries(this._indicatorSeries), this._indicatorSeries = null;
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
      if (!this._baseSeries || !this._secondarySeries) {
        this._indicatorSeries.setData([]);
        return;
      }
      const i = this._baseSeries.data(), c = this._secondarySeries.data(), o = _(
        i,
        c,
        this._options || n
      );
      this._indicatorSeries.setData(o);
    };
  }
  const t = new r();
  return s.attachPrimitive(t), t.indicatorSeries();
}
export {
  p as applyProductIndicator
};
