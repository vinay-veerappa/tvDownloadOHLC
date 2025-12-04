import { LineSeries as h } from "lightweight-charts";
function l(t, o) {
  if (t.length === 0)
    return [];
  const a = o.offset ?? 0, s = new Array(t.length), c = a > 0 ? a : 0, r = a < 0 ? t.length - 1 + a : t.length - 1;
  let i = 0;
  for (let e = 0; e < c; e++)
    s[i] = { time: t[e].time }, i += 1;
  for (let e = c; e < r; e++) {
    const n = t[e];
    "close" in n ? s[i] = { time: n.time, value: (n.open + n.high + n.low + n.close) / 4 } : s[i] = { time: n.time }, i += 1;
  }
  for (let e = r; e < t.length; e++)
    s[i] = { time: t[e].time }, i += 1;
  return console.log(s), s;
}
function u(t, o) {
  class a {
    _baseSeries = null;
    _indicatorSeries = null;
    _chart = null;
    _options = null;
    attached(r) {
      const { chart: i, series: e } = r;
      this._chart = i, this._baseSeries = e, this._indicatorSeries = this._chart.addSeries(h), this._options = o, e.subscribeDataChanged(this._updateData), this._updateData();
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
      const r = this._baseSeries.data(), i = l(
        r,
        this._options || o
      );
      this._indicatorSeries.setData(i);
    };
  }
  const s = new a();
  return t.attachPrimitive(s), s.indicatorSeries();
}
export {
  u as applyAveragePriceIndicator
};
