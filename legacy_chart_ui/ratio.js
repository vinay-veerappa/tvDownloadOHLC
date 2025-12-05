const { LineSeries: f } = window.LightweightCharts;
class m {
  numbers;
  cache;
  constructor(e) {
    this.numbers = e, this.cache = /* @__PURE__ */ new Map();
  }
  findClosestIndex(e, a) {
    const s = `${e}:${a}`;
    if (this.cache.has(s))
      return this.cache.get(s);
    const t = this._performSearch(e, a);
    return this.cache.set(s, t), t;
  }
  _performSearch(e, a) {
    let s = 0, t = this.numbers.length - 1;
    if (e <= this.numbers[0].time) return 0;
    if (e >= this.numbers[t].time) return t;
    for (; s <= t; ) {
      const n = Math.floor((s + t) / 2), i = this.numbers[n].time;
      if (i === e)
        return n;
      i > e ? t = n - 1 : s = n + 1;
    }
    return a === "left" ? s : t;
  }
}
function d(r) {
  for (const e of r)
    if (typeof e.time != "number")
      throw new Error('All items must have a numeric "time" property.');
  return r;
}
function l(r) {
  for (const e of r) {
    if (typeof e.close == "number")
      return "close";
    if (typeof e.value == "number")
      return "value";
  }
  return null;
}
function _(r, e, a) {
  const s = a.primarySource ?? l(r);
  if (!s)
    throw new Error(
      "Please provide a `primarySource` for the primary data of the ratio indicator."
    );
  const t = a.secondarySource ?? l(e);
  if (!t)
    throw new Error(
      "Please provide a `secondarySource` for the secondary data of the ratio indicator."
    );
  d(r);
  const n = new m(
    d(e)
  );
  return r.map((i) => {
    const c = {
      time: i.time
    }, o = i[s];
    if (o === void 0)
      return c;
    const h = n.findClosestIndex(
      i.time,
      "left"
    ), u = e[h][t];
    return u === void 0 || !a.allowMismatchedDates && e[h].time !== i.time ? c : {
      time: i.time,
      value: o / u
    };
  });
}
function p(r, e, a) {
  class s {
    _baseSeries = null;
    _secondarySeries = null;
    _indicatorSeries = null;
    _chart = null;
    _options = null;
    attached(i) {
      const { chart: c, series: o } = i;
      this._chart = c, this._baseSeries = o, this._secondarySeries = e, this._indicatorSeries = this._chart.addSeries(f, {}, 1), this._options = a, o.subscribeDataChanged(this._updateData), this._secondarySeries.subscribeDataChanged(this._updateData), this._updateData();
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
        this._options || a
      );
      this._indicatorSeries.setData(o);
    };
  }
  const t = new s();
  return r.attachPrimitive(t), t.indicatorSeries();
}
export {
  p as applyRatioIndicator
};
