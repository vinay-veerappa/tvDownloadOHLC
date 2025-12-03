import { CrosshairMode as u, LineStyle as p } from "lightweight-charts";
function d(s) {
  if (s === void 0)
    throw new Error("Value is undefined");
  return s;
}
class v {
  _chart = void 0;
  _series = void 0;
  requestUpdate() {
    this._requestUpdate && this._requestUpdate();
  }
  _requestUpdate;
  attached({ chart: t, series: i, requestUpdate: e }) {
    this._chart = t, this._series = i, this._series.subscribeDataChanged(this._fireDataUpdated), this._requestUpdate = e, this.requestUpdate();
  }
  detached() {
    this._series?.unsubscribeDataChanged(this._fireDataUpdated), this._chart = void 0, this._series = void 0, this._requestUpdate = void 0;
  }
  get chart() {
    return d(this._chart);
  }
  get series() {
    return d(this._series);
  }
  // This method is a class property to maintain the
  // lexical 'this' scope (due to the use of the arrow function)
  // and to ensure its reference stays the same, so we can unsubscribe later.
  _fireDataUpdated = (t) => {
    this.dataUpdated && this.dataUpdated(t);
  };
}
function f(s) {
  return Math.floor(s * 0.5);
}
function b(s, t, i = 1, e) {
  const r = Math.round(t * s), h = Math.round(i * t), o = f(h);
  return { position: r - o, length: h };
}
function P(s, t, i) {
  const e = Math.round(i * s), r = Math.round(i * t);
  return {
    position: Math.min(e, r),
    length: Math.abs(r - e) + 1
  };
}
const n = 21, C = "M7.5,7.5 m -7,0 a 7,7 0 1,0 14,0 a 7,7 0 1,0 -14,0 M4 7.5H11 M7.5 4V11", m = new Path2D(C), g = 15;
class w {
  _y = 0;
  _data;
  constructor(t) {
    this._data = t;
  }
  update(t, i) {
    if (this._data = t, !this._data.price) {
      this._y = -1e4;
      return;
    }
    this._y = i.priceToCoordinate(this._data.price) ?? -1e4;
  }
}
class M {
  _data;
  constructor(t) {
    this._data = t;
  }
  draw(t) {
    this._data.visible && t.useBitmapCoordinateSpace((i) => {
      const e = i.context, r = n, h = r + 1, o = P(this._data.rightX - h, this._data.rightX - 1, i.horizontalPixelRatio), a = b(this._data.y, i.verticalPixelRatio, r);
      e.fillStyle = this._data.color;
      const l = [5, 0, 0, 5].map((_) => _ * i.horizontalPixelRatio);
      e.beginPath(), e.roundRect(o.position, a.position, o.length, a.length, l), e.fill(), this._data.hovered && (e.fillStyle = this._data.hoverColor, e.beginPath(), e.roundRect(o.position, a.position, o.length, a.length, l), e.fill()), e.translate(o.position + 3 * i.horizontalPixelRatio, a.position + 3 * i.verticalPixelRatio), e.scale(i.horizontalPixelRatio, i.verticalPixelRatio);
      const c = 15 / g;
      e.scale(c, c), e.strokeStyle = this._data.textColor, e.lineWidth = 1, e.stroke(m);
    });
  }
}
class L extends w {
  renderer() {
    const t = this._data.crosshairColor;
    return new M({
      visible: this._data.visible,
      y: this._y,
      color: t,
      textColor: this._data.crosshairLabelColor,
      rightX: this._data.timeScaleWidth,
      hoverColor: this._data.hoverColor,
      hovered: this._data.hovered ?? !1
    });
  }
  zOrder() {
    return "top";
  }
}
class U extends v {
  _paneViews;
  _data = {
    visible: !1,
    hovered: !1,
    timeScaleWidth: 0,
    crosshairLabelColor: "#000000",
    crosshairColor: "#ffffff",
    lineColor: "#000000",
    hoverColor: "#777777"
  };
  _source;
  constructor(t) {
    super(), this._paneViews = [new L(this._data)], this._source = t;
  }
  updateAllViews() {
    this._paneViews.forEach((t) => t.update(this._data, this.series));
  }
  priceAxisViews() {
    return [];
  }
  paneViews() {
    return this._paneViews;
  }
  showAddLabel(t, i) {
    const e = this.chart.options().crosshair.horzLine.labelBackgroundColor;
    this._data = {
      visible: !0,
      price: t,
      hovered: i,
      timeScaleWidth: this.chart.timeScale().width(),
      crosshairColor: e,
      crosshairLabelColor: "#FFFFFF",
      lineColor: this._source.currentLineColor(),
      hoverColor: this._source.currentHoverColor()
    }, this.updateAllViews(), this.requestUpdate();
  }
  hideAddLabel() {
    this._data.visible = !1, this.updateAllViews(), this.requestUpdate();
  }
}
const x = {
  color: "#000000",
  hoverColor: "#777777",
  limitToOne: !0
};
class B {
  _chart;
  _series;
  _options;
  _labelButtonPrimitive;
  constructor(t, i, e) {
    this._chart = t, this._series = i, this._options = {
      ...x,
      ...e
    }, this._chart.subscribeClick(this._clickHandler), this._chart.subscribeCrosshairMove(this._moveHandler), this._labelButtonPrimitive = new U(this), i.attachPrimitive(this._labelButtonPrimitive), this._setCrosshairMode();
  }
  currentLineColor() {
    return this._options.color;
  }
  currentHoverColor() {
    return this._options.hoverColor;
  }
  // We need to disable magnet mode for this to work nicely
  _setCrosshairMode() {
    if (!this._chart)
      throw new Error(
        "Unable to change crosshair mode because the chart instance is undefined"
      );
    this._chart.applyOptions({
      crosshair: {
        mode: u.Normal
      }
    });
  }
  _clickHandler = (t) => this._onClick(t);
  _moveHandler = (t) => this._onMouseMove(t);
  remove() {
    this._chart && (this._chart.unsubscribeClick(this._clickHandler), this._chart.unsubscribeCrosshairMove(this._moveHandler)), this._series && this._labelButtonPrimitive && this._series.detachPrimitive(this._labelButtonPrimitive), this._chart = void 0, this._series = void 0;
  }
  _onClick(t) {
    const i = this._getMousePrice(t), e = this._distanceFromRightScale(t);
    i === null || e === null || e > n || !this._series || this._series.createPriceLine({
      price: i,
      color: this._options.color,
      lineStyle: p.Dashed
    });
  }
  _onMouseMove(t) {
    const i = this._getMousePrice(t), e = this._distanceFromRightScale(t);
    if (i === null || e === null || e > n * 2) {
      this._labelButtonPrimitive.hideAddLabel();
      return;
    }
    this._labelButtonPrimitive.showAddLabel(i, e < n);
  }
  _getMousePrice(t) {
    return !t.point || !this._series ? null : this._series.coordinateToPrice(t.point.y);
  }
  _distanceFromRightScale(t) {
    if (!t.point || !this._chart) return null;
    const i = this._chart.timeScale().width();
    return Math.abs(i - t.point.x);
  }
}
export {
  B as UserPriceLines
};
