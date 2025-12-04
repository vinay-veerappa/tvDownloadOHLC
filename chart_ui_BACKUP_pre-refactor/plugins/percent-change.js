import { LineSeries as u } from "lightweight-charts";
function _(t, o) {
  if (t.length === 0)
    return [];
  const n = o.offset ?? 0, s = new Array(t.length), c = n > 0 ? n : 0, r = n < 0 ? t.length - 1 + n : t.length - 1;
  let i = 0;
  for (let e = 0; e < c; e++)
    s[i] = { time: t[e].time }, i += 1;
  for (let e = c; e < r; e++) {
    const a = t[e];
    if (e === 0) {
      s[i] = { time: a.time, value: void 0 }, i += 1;
      continue;
    }
    const h = t[e - 1];
    if ("close" in a && "close" in h) {
      const l = (a.close - h.close) * 100 / h.close;
      s[i] = { time: a.time, value: l };
    } else
      s[i] = { time: a.time };
    i += 1;
  }
  for (let e = r; e < t.length; e++)
    s[i] = { time: t[e].time }, i += 1;
  return s;
}
function S(t, o) {
  class n {
    _baseSeries = null;
    _indicatorSeries = null;
    _chart = null;
    _options = null;
    attached(r) {
      const { chart: i, series: e } = r;
      this._chart = i, this._baseSeries = e, this._indicatorSeries = this._chart.addSeries(u), this._options = o, e.subscribeDataChanged(this._updateData), this._updateData();
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
      const r = this._baseSeries.data(), i = _(
        r,
        this._options || o
      );
      this._indicatorSeries.setData(i);
    };
  }
  const s = new n();
  return t.attachPrimitive(s), s.indicatorSeries();
}
export {
  S as applyPercentChangeIndicator
};
