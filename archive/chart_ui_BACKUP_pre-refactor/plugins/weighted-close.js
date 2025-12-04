import { LineSeries as l } from "lightweight-charts";
const _ = 2;
function d(i, h) {
  if (i.length === 0)
    return [];
  const r = h.offset ?? 0, c = h.weight ?? _, n = new Array(i.length), s = r > 0 ? r : 0, a = r < 0 ? i.length - 1 + r : i.length - 1;
  let t = 0;
  for (let e = 0; e < s; e++)
    n[t] = { time: i[e].time }, t += 1;
  for (let e = s; e < a; e++) {
    const o = i[e];
    "close" in o ? n[t] = { time: o.time, value: (o.close * c + o.high + o.low) / (2 + c) } : n[t] = { time: o.time }, t += 1;
  }
  for (let e = a; e < i.length; e++)
    n[t] = { time: i[e].time }, t += 1;
  return n;
}
function S(i, h) {
  class r {
    _baseSeries = null;
    _indicatorSeries = null;
    _chart = null;
    _options = null;
    attached(s) {
      const { chart: a, series: t } = s;
      this._chart = a, this._baseSeries = t, this._indicatorSeries = this._chart.addSeries(l), this._options = h, t.subscribeDataChanged(this._updateData), this._updateData();
    }
    detached() {
      this._baseSeries && this._baseSeries.unsubscribeDataChanged(this._updateData), this._indicatorSeries && this._chart?.removeSeries(this._indicatorSeries), this._indicatorSeries = null;
    }
    indicatorSeries() {
      if (!this._indicatorSeries)
        throw new Error("unable to provide indicator series");
      return this._indicatorSeries;
    }
    applyOptions(s) {
      this._options = {
        ...this._options || {},
        ...s
      }, this._updateData();
    }
    _updateData = () => {
      if (!this._indicatorSeries)
        return;
      if (!this._baseSeries) {
        this._indicatorSeries.setData([]);
        return;
      }
      const s = this._baseSeries.data(), a = d(
        s,
        this._options || h
      );
      this._indicatorSeries.setData(a);
    };
  }
  const c = new r();
  return i.attachPrimitive(c), c;
}
export {
  S as applyWeightedCloseIndicator
};
