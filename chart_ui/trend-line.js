class h {
  _p1;
  _p2;
  _text1;
  _text2;
  _options;
  constructor(t, i, e, n, o) {
    this._p1 = t, this._p2 = i, this._text1 = e, this._text2 = n, this._options = o;
  }
  draw(t) {
    t.useBitmapCoordinateSpace((i) => {
      if (this._p1.x === null || this._p1.y === null || this._p2.x === null || this._p2.y === null)
        return;
      const e = i.context, n = Math.round(this._p1.x * i.horizontalPixelRatio), o = Math.round(this._p1.y * i.verticalPixelRatio), s = Math.round(this._p2.x * i.horizontalPixelRatio), r = Math.round(this._p2.y * i.verticalPixelRatio);
      e.lineWidth = this._options.width, e.strokeStyle = this._options.lineColor, e.beginPath(), e.moveTo(n, o), e.lineTo(s, r), e.stroke(), this._options.showLabels && (this._drawTextLabel(i, this._text1, n, o, !0), this._drawTextLabel(i, this._text2, s, r, !1));
    });
  }
  _drawTextLabel(t, i, e, n, o) {
    t.context.font = "24px Arial", t.context.beginPath();
    const s = 5 * t.horizontalPixelRatio, r = t.context.measureText(i), a = o ? r.width + s * 4 : 0;
    t.context.fillStyle = this._options.labelBackgroundColor, t.context.roundRect(e + s - a, n - 24, r.width + s * 2, 24 + s, 5), t.context.fill(), t.context.beginPath(), t.context.fillStyle = this._options.labelTextColor, t.context.fillText(i, e + s * 2 - a, n);
  }
}
class _ {
  _source;
  _p1 = { x: null, y: null };
  _p2 = { x: null, y: null };
  constructor(t) {
    this._source = t;
  }
  update() {
    const t = this._source._series, i = t.priceToCoordinate(this._source._p1.price), e = t.priceToCoordinate(this._source._p2.price), n = this._source._chart.timeScale(), o = n.timeToCoordinate(this._source._p1.time), s = n.timeToCoordinate(this._source._p2.time);
    this._p1 = { x: o, y: i }, this._p2 = { x: s, y: e };
  }
  renderer() {
    return new h(
      this._p1,
      this._p2,
      "" + this._source._p1.price.toFixed(1),
      "" + this._source._p2.price.toFixed(1),
      this._source._options
    );
  }
}
const c = {
  lineColor: "rgb(0, 0, 0)",
  width: 6,
  showLabels: !0,
  labelBackgroundColor: "rgba(255, 255, 255, 0.85)",
  labelTextColor: "rgb(0, 0, 0)"
};
class p {
  _chart;
  _series;
  _p1;
  _p2;
  _paneViews;
  _options;
  _minPrice;
  _maxPrice;
  constructor(t, i, e, n, o) {
    this._chart = t, this._series = i, this._p1 = e, this._p2 = n, this._minPrice = Math.min(this._p1.price, this._p2.price), this._maxPrice = Math.max(this._p1.price, this._p2.price), this._options = {
      ...c,
      ...o
    }, this._paneViews = [new _(this)];
  }
  autoscaleInfo(t, i) {
    const e = this._pointIndex(this._p1), n = this._pointIndex(this._p2);
    return e === null || n === null || i < e || t > n ? null : {
      priceRange: {
        minValue: this._minPrice,
        maxValue: this._maxPrice
      }
    };
  }
  updateAllViews() {
    this._paneViews.forEach((t) => t.update());
  }
  paneViews() {
    return this._paneViews;
  }
  _pointIndex(t) {
    const i = this._chart.timeScale().timeToCoordinate(t.time);
    return i === null ? null : this._chart.timeScale().coordinateToLogical(i);
  }
}
export {
  p as TrendLine
};
