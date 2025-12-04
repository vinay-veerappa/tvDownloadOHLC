import { MismatchDirection as a } from "lightweight-charts";
function c(r) {
  return Math.floor(r * 0.5);
}
function h(r, i, e = 1, t) {
  const s = Math.round(i * r), o = Math.round(e * i), n = c(o);
  return { position: s - n, length: o };
}
class u {
  _price = null;
  _x = null;
  _color = "#000000";
  update(i, e, t) {
    this._price = i, this._color = e, this._x = t;
  }
  draw(i) {
    i.useBitmapCoordinateSpace((e) => {
      if (this._price === null || this._x === null) return;
      const t = Math.round(this._x * e.horizontalPixelRatio), s = h(this._price, e.verticalPixelRatio, e.verticalPixelRatio), o = s.position + s.length / 2, n = e.context;
      n.beginPath(), n.setLineDash([
        4 * e.verticalPixelRatio,
        2 * e.verticalPixelRatio
      ]), n.moveTo(t, o), n.lineTo(e.bitmapSize.width, o), n.strokeStyle = this._color, n.lineWidth = e.verticalPixelRatio, n.stroke();
    });
  }
}
class _ {
  _renderer;
  constructor() {
    this._renderer = new u();
  }
  renderer() {
    return this._renderer;
  }
  update(i, e, t) {
    this._renderer.update(i, e, t);
  }
}
class f {
  _paneViews;
  _chart = null;
  _series = null;
  constructor() {
    this._paneViews = [new _()];
  }
  attached({ chart: i, series: e }) {
    this._chart = i, this._series = e, this._series.applyOptions({
      priceLineVisible: !1
    });
  }
  detached() {
    this._chart = null, this._series = null;
  }
  updateAllViews() {
    if (!this._series || !this._chart) return;
    const i = this._series.options();
    let e = i.priceLineColor || i.color || "#000000";
    const t = this._series.dataByIndex(
      1e5,
      a.NearestLeft
    );
    let s = null, o = null;
    t && (t.color !== void 0 && (e = t.color), s = d(t), o = this._chart.timeScale().timeToCoordinate(t.time));
    const n = s !== null ? this._series.priceToCoordinate(s) : null;
    this._paneViews.forEach((l) => l.update(n, e, o));
  }
  paneViews() {
    return this._paneViews;
  }
}
function d(r) {
  return r.value !== void 0 ? r.value : r.close !== void 0 ? r.close : null;
}
export {
  f as PartialPriceLine
};
