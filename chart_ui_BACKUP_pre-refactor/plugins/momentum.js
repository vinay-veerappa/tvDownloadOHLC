import { LineSeries as u } from "lightweight-charts";
function c(e) {
  for (const t of e)
    if (typeof t.time != "number")
      throw new Error('All items must have a numeric "time" property.');
  return e;
}
function h(e) {
  for (const t of e) {
    if (typeof t.close == "number")
      return "close";
    if (typeof t.value == "number")
      return "value";
  }
  return null;
}
function m(e, t) {
  const s = t.source ?? h(e);
  if (!s)
    throw new Error(
      "Please provide a `source` property for the momentum indicator."
    );
  c(e);
  const n = e.map(
    (i) => i[s]
  ), o = e.map((i) => i.time), r = p(
    n,
    t.length
  );
  return o.map(
    (i, a) => typeof r[a] == "number" ? { time: i, value: r[a] } : { time: i }
  );
}
function p(e, t) {
  const s = [];
  for (let n = 0; n < e.length; ++n) {
    const o = e[n];
    if (typeof o != "number") {
      s.push(void 0);
      continue;
    }
    if (n < t)
      s.push(void 0);
    else {
      const r = e[n - t];
      if (typeof r != "number") {
        s.push(void 0);
        continue;
      }
      const i = o - r;
      s.push(i);
    }
  }
  return s;
}
function d(e, t) {
  class s {
    _baseSeries = null;
    _indicatorSeries = null;
    _chart = null;
    _options = null;
    attached(r) {
      const { chart: i, series: a } = r;
      this._chart = i, this._baseSeries = a, this._indicatorSeries = this._chart.addSeries(u), this._options = t, a.subscribeDataChanged(this._updateData), this._updateData();
    }
    detached() {
      this._baseSeries && this._baseSeries.unsubscribeDataChanged(this._updateData), this._indicatorSeries && this._chart?.removeSeries(this._indicatorSeries), this._indicatorSeries = null;
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
      if (!this._baseSeries) {
        this._indicatorSeries.setData([]);
        return;
      }
      const r = this._baseSeries.data(), i = m(
        r,
        this._options || t
      );
      this._indicatorSeries.setData(i);
    };
  }
  const n = new s();
  return e.attachPrimitive(n), n.indicatorSeries();
}
export {
  d as applyMomentumIndicator
};
