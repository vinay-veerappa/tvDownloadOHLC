const { isUTCTimestamp: E, isBusinessDay: D, CrosshairMode: y, ColorType: B } = window.LightweightCharts;
class L {
  _listeners = [];
  subscribe(t, e, i) {
    const o = {
      callback: t,
      linkedObject: e,
      singleshot: i === !0
    };
    this._listeners.push(o);
  }
  unsubscribe(t) {
    const e = this._listeners.findIndex(
      (i) => t === i.callback
    );
    e > -1 && this._listeners.splice(e, 1);
  }
  unsubscribeAll(t) {
    this._listeners = this._listeners.filter(
      (e) => e.linkedObject !== t
    );
  }
  fire(t) {
    const e = [...this._listeners];
    this._listeners = this._listeners.filter(
      (i) => !i.singleshot
    ), e.forEach(
      (i) => i.callback(t)
    );
  }
  hasListeners() {
    return this._listeners.length > 0;
  }
  destroy() {
    this._listeners = [];
  }
}
function F(s) {
  if (E(s)) return s * 1e3;
  if (D(s)) return new Date(s.year, s.month, s.day).valueOf();
  const [t, e, i] = s.split("-").map(parseInt);
  return new Date(t, e, i).valueOf();
}
function O(s) {
  if (!s) return ["", ""];
  const t = new Date(s), e = t.getFullYear(), i = t.toLocaleString("default", { month: "short" }), n = `${t.getDate().toString().padStart(2, "0")} ${i} ${e}`, a = t.getHours().toString().padStart(2, "0"), h = t.getMinutes().toString().padStart(2, "0"), l = `${a}:${h}`;
  return [n, l];
}
function X(s) {
  return Math.floor(s * 0.5);
}
function R(s, t, e = 1, i) {
  const o = Math.round(t * s), n = Math.round(e * t), a = X(n);
  return { position: o - a, length: n };
}
class k {
  _data;
  constructor(t) {
    this._data = t;
  }
  draw(t) {
    this._data.length && t.useBitmapCoordinateSpace((e) => {
      const i = e.context;
      this._data.forEach((o) => {
        const n = R(
          o.x,
          e.horizontalPixelRatio,
          1
        );
        i.fillStyle = o.color, i.fillRect(
          n.position,
          o.topMargin * e.verticalPixelRatio,
          n.length,
          e.bitmapSize.height
        ), o.priceY && (i.beginPath(), i.ellipse(
          o.x * e.horizontalPixelRatio,
          o.priceY * e.verticalPixelRatio,
          6 * e.horizontalPixelRatio,
          6 * e.verticalPixelRatio,
          0,
          0,
          Math.PI * 2
        ), i.fillStyle = o.markerBorderColor, i.fill(), i.beginPath(), i.ellipse(
          o.x * e.horizontalPixelRatio,
          o.priceY * e.verticalPixelRatio,
          4 * e.horizontalPixelRatio,
          4 * e.verticalPixelRatio,
          0,
          0,
          Math.PI * 2
        ), i.fillStyle = o.markerColor, i.fill());
      });
    });
  }
}
class Y {
  _data;
  constructor(t) {
    this._data = t;
  }
  update(t) {
    this._data = t;
  }
  renderer() {
    return new k(this._data);
  }
  zOrder() {
    return "top";
  }
}
const r = {
  background: "#ffffff",
  fontFamily: "-apple-system, BlinkMacSystemFont, 'Trebuchet MS', Roboto, Ubuntu, sans-serif",
  borderRadius: 5,
  shadowColor: "rgba(0, 0, 0, 0.2)",
  shadowBlur: 4,
  shadowOffsetX: 0,
  shadowOffsetY: 2,
  itemBlockPadding: 5,
  itemInlinePadding: 10,
  tooltipLineFontWeights: [590, 400, 400],
  tooltipLineFontSizes: [14, 12, 12],
  tooltipLineLineHeights: [18, 16, 16],
  tooltipLineColors: ["#131722", "#787B86", "#787B86"],
  deltaFontWeights: [590, 400],
  deltaFontSizes: [14, 12],
  deltaLineHeights: [18, 16]
};
function P(s, t, e, i) {
  let o = 0;
  return s.save(), t.forEach((n, a) => {
    s.font = `${i[a]} ${e[a]}px ${r.fontFamily}`;
    const h = s.measureText(n);
    h.width > o && (o = h.width);
  }), s.restore(), o + r.itemInlinePadding * 2;
}
function v(s, t) {
  let e = r.itemBlockPadding * 1.5;
  return s.forEach((i, o) => {
    e += t[o];
  }), e;
}
function V(s) {
  const t = s.topSpacing, e = s.tooltips.length < 1 ? 0 : v(
    s.tooltips[0].lineContent,
    r.tooltipLineLineHeights
  ), i = s.tooltips.length < 2 ? 0 : v(
    s.tooltips[1].lineContent,
    r.tooltipLineLineHeights
  ), o = v(
    [s.deltaTopLine, s.deltaBottomLine].filter(Boolean),
    r.deltaLineHeights
  ), n = Math.max(
    e,
    i,
    o
  ), a = Math.round(
    r.itemBlockPadding + (n - e) / 2
  ), h = Math.round(
    r.itemBlockPadding + (n - i) / 2
  ), l = Math.round(
    r.itemBlockPadding + (n - o) / 2
  );
  return {
    mainY: t,
    mainHeight: n,
    leftTooltipTextY: a,
    rightTooltipTextY: h,
    deltaTextY: l
  };
}
function b(s, t, e, i) {
  const o = s.tooltips[t].lineContent, n = P(
    e,
    o,
    r.tooltipLineFontSizes,
    r.tooltipLineFontWeights
  ), a = n / 2, h = Math.min(
    Math.max(0, s.tooltips[t].x - a),
    i.width - n
  ), l = h, u = i.width - n - l;
  return {
    x: h,
    leftSpace: l,
    rightSpace: u,
    width: n
  };
}
function W(s, t, e) {
  const i = b(s, 0, t, e);
  if (s.tooltips.length < 2)
    return {
      mainX: Math.round(i.x),
      mainWidth: Math.round(i.width),
      leftTooltipCentreX: Math.round(i.x + i.width / 2),
      rightTooltipCentreX: 0,
      deltaCentreX: 0,
      deltaWidth: 0
    };
  const o = b(
    s,
    1,
    t,
    e
  ), a = (s.tooltips.length < 2 ? 0 : P(
    t,
    [s.deltaTopLine, s.deltaBottomLine].filter(Boolean),
    r.deltaFontSizes,
    r.deltaFontWeights
  )) + i.x + i.width - o.x;
  if (a > 0) {
    const u = a / 2;
    if (i.leftSpace >= u && o.rightSpace >= u)
      i.x -= u, o.x += u;
    else if (i.leftSpace < o.rightSpace) {
      const c = a - i.leftSpace;
      i.x -= i.leftSpace, o.x += c;
    } else {
      const c = a - o.rightSpace;
      i.x = Math.max(0, i.x - c), o.x += o.rightSpace;
    }
  }
  const h = Math.round(
    o.x - i.x - i.width
  ), l = Math.round(o.x - h / 2);
  return {
    mainX: Math.round(i.x),
    mainWidth: Math.round(
      i.width + h + o.width
    ),
    leftTooltipCentreX: Math.round(i.x + i.width / 2),
    rightTooltipCentreX: Math.round(o.x + o.width / 2),
    deltaCentreX: l,
    deltaWidth: h
  };
}
function H(s, t, e) {
  return {
    ...V(s),
    ...W(s, t, e)
  };
}
class z {
  _data;
  constructor(t) {
    this._data = t;
  }
  draw(t) {
    this._data.tooltips.length < 1 || t.useMediaCoordinateSpace((e) => {
      const i = e.context, o = H(
        this._data,
        i,
        e.mediaSize
      );
      this._drawMainTooltip(i, o), this._drawDeltaArea(i, o), this._drawTooltipsText(i, o), this._drawDeltaText(i, o);
    });
  }
  _drawMainTooltip(t, e) {
    t.save(), t.fillStyle = r.background, t.shadowBlur = r.shadowBlur, t.shadowOffsetX = r.shadowOffsetX, t.shadowOffsetY = r.shadowOffsetY, t.shadowColor = r.shadowColor, t.beginPath(), t.roundRect(
      e.mainX,
      e.mainY,
      e.mainWidth,
      e.mainHeight,
      r.borderRadius
    ), t.fill(), t.restore();
  }
  _drawDeltaArea(t, e) {
    t.save(), t.fillStyle = this._data.deltaBackgroundColor, t.beginPath();
    const i = Math.round(e.deltaWidth / 2);
    t.fillRect(
      e.deltaCentreX - i,
      e.mainY,
      e.deltaWidth,
      e.mainHeight
    ), t.restore();
  }
  _drawTooltipsText(t, e) {
    t.save(), this._data.tooltips.forEach(
      (i, o) => {
        const n = o === 0 ? e.leftTooltipCentreX : e.rightTooltipCentreX;
        let a = e.mainY + (o === 0 ? e.leftTooltipTextY : e.rightTooltipTextY);
        i.lineContent.forEach((h, l) => {
          t.font = `${r.tooltipLineFontWeights[l]} ${r.tooltipLineFontSizes[l]}px ${r.fontFamily}`, t.fillStyle = r.tooltipLineColors[l], t.textAlign = "center", t.textBaseline = "top", t.fillText(h, n, a), a += r.tooltipLineLineHeights[l];
        });
      }
    ), t.restore();
  }
  _drawDeltaText(t, e) {
    t.save();
    const i = e.deltaCentreX;
    let o = e.mainY + e.deltaTextY;
    [this._data.deltaTopLine, this._data.deltaBottomLine].forEach((a, h) => {
      t.font = `${r.deltaFontWeights[h]} ${r.deltaFontSizes[h]}px ${r.fontFamily}`, t.fillStyle = this._data.deltaTextColor, t.textAlign = "center", t.textBaseline = "top", t.fillText(a, i, o), o += r.deltaLineHeights[h];
    }), t.restore();
  }
}
class $ {
  _data;
  constructor(t) {
    this._data = {
      ...A,
      ...t
    };
  }
  update(t) {
    this._data = {
      ...this._data,
      ...t
    };
  }
  renderer() {
    return new z(this._data);
  }
  zOrder() {
    return "top";
  }
}
const A = {
  deltaTopLine: "",
  deltaBottomLine: "",
  deltaBackgroundColor: "#ffffff",
  deltaTextColor: "#",
  topSpacing: 20,
  tooltips: []
};
function C(s, t, e) {
  const i = s.getBoundingClientRect(), o = e - i.left - t.priceScale("left").width();
  return o < 0 || o > t.timeScale().width() ? null : o;
}
function S(s, t) {
  return t === null ? null : s.timeScale().coordinateToLogical(t);
}
function T(s, t) {
  const e = s.getBoundingClientRect();
  return t - e.y;
}
class I {
  _chartElement;
  _chart;
  _options;
  _mouseState = {
    drawing: !1,
    startLogical: null,
    startCoordinate: null,
    startX: null
  };
  _touchLeave = new L();
  _touchInteraction = new L();
  _unSubscribers = [];
  constructor(t, e) {
    this._options = e, this._chart = t, this._chartElement = t.chartElement(), this._addMouseEventListener(
      this._chartElement,
      "mouseleave",
      this._mouseLeave
    ), this._addMouseEventListener(
      this._chartElement,
      "mousemove",
      this._mouseMove
    ), this._addMouseEventListener(
      this._chartElement,
      "mousedown",
      this._mouseDown
    ), this._addMouseEventListener(this._chartElement, "mouseup", this._mouseUp), this._addTouchEventListener(
      this._chartElement,
      "touchstart",
      this._touchOther
    ), this._addTouchEventListener(
      this._chartElement,
      "touchmove",
      this._touchMove
    ), this._addTouchEventListener(
      this._chartElement,
      "touchcancel",
      this._touchFinish
    ), this._addTouchEventListener(
      this._chartElement,
      "touchend",
      this._touchFinish
    );
  }
  destroy() {
    this._touchLeave.destroy(), this._touchInteraction.destroy(), this._unSubscribers.forEach((t) => {
      t();
    }), this._unSubscribers = [];
  }
  leave() {
    return this._touchLeave;
  }
  move() {
    return this._touchInteraction;
  }
  _addMouseEventListener(t, e, i) {
    const o = i.bind(this);
    t.addEventListener(e, o);
    const n = () => {
      t.removeEventListener(e, o);
    };
    this._unSubscribers.push(n);
  }
  _addTouchEventListener(t, e, i) {
    const o = i.bind(this);
    t.addEventListener(e, o);
    const n = () => {
      t.removeEventListener(e, o);
    };
    this._unSubscribers.push(n);
  }
  _mouseLeave() {
    this._mouseState.drawing = !1, this._touchLeave.fire();
  }
  _mouseMove(t) {
    const e = C(
      this._chartElement,
      this._chart,
      t.clientX
    ), i = S(this._chart, e), o = T(this._chartElement, t.clientY), n = [];
    this._options.simulateMultiTouchUsingMouseDrag && this._mouseState.drawing && this._mouseState.startLogical !== null && this._mouseState.startCoordinate !== null && this._mouseState.startX !== null && n.push({
      x: this._mouseState.startX,
      index: this._mouseState.startLogical,
      y: this._mouseState.startCoordinate
    }), i !== null && o !== null && e !== null && n.push({
      x: e,
      index: i,
      y: o
    });
    const a = {
      points: n
    };
    this._touchInteraction.fire(a);
  }
  _mouseDown(t) {
    this._mouseState.startX = C(
      this._chartElement,
      this._chart,
      t.clientX
    ), this._mouseState.startLogical = S(
      this._chart,
      this._mouseState.startX
    ), this._mouseState.startCoordinate = T(
      this._chartElement,
      t.clientY
    ), this._mouseState.drawing = this._mouseState.startLogical !== null && this._mouseState.startCoordinate !== null;
  }
  _mouseUp() {
    this._mouseState.drawing = !1;
  }
  _touchMove(t) {
    t.preventDefault();
    const e = [];
    for (let o = 0; o < t.targetTouches.length; o++) {
      const n = t.targetTouches.item(o);
      if (n !== null) {
        const a = C(
          this._chartElement,
          this._chart,
          n.clientX
        ), h = S(this._chart, a), l = T(this._chartElement, n.clientY);
        a !== null && l !== null && h !== null && e.push({
          x: a,
          index: h,
          y: l
        });
      }
    }
    const i = {
      points: e
    };
    this._touchInteraction.fire(i);
  }
  _touchFinish(t) {
    if (t.preventDefault(), t.targetTouches.length < 1) {
      this._touchLeave.fire();
      return;
    }
  }
  _touchOther(t) {
    t.preventDefault();
  }
}
const U = {
  lineColor: "rgba(0, 0, 0, 0.2)",
  priceExtractor: (s) => s.value !== void 0 ? [s.value, s.value.toFixed(2)] : s.close !== void 0 ? [
    s.close,
    s.close.toFixed(2)
  ] : [0, ""],
  showTime: !1,
  topOffset: 20
};
class q {
  _options;
  _crosshairPaneView;
  _deltaTooltipPaneView;
  _paneViews;
  _crosshairData = [];
  _tooltipData;
  _attachedParams;
  _touchChartEvents = null;
  _activeRange = new L();
  constructor(t) {
    this._options = {
      ...U,
      ...t
    }, this._tooltipData = {
      topSpacing: this._options.topOffset
    }, this._crosshairPaneView = new Y(this._crosshairData), this._deltaTooltipPaneView = new $(this._tooltipData), this._paneViews = [this._crosshairPaneView, this._deltaTooltipPaneView];
  }
  attached(t) {
    this._attachedParams = t, this._setCrosshairMode(), this._touchChartEvents = new I(t.chart, {
      simulateMultiTouchUsingMouseDrag: !0
    }), this._touchChartEvents.leave().subscribe(() => {
      this._activeRange.fire(null), this._hideCrosshair();
    }, this), this._touchChartEvents.move().subscribe((e) => {
      this._showTooltip(e);
    }, this);
  }
  detached() {
    this._touchChartEvents && (this._touchChartEvents.leave().unsubscribeAll(this), this._touchChartEvents.move().unsubscribeAll(this), this._touchChartEvents.destroy()), this._activeRange.destroy();
  }
  paneViews() {
    return this._paneViews;
  }
  updateAllViews() {
    this._crosshairPaneView.update(this._crosshairData), this._deltaTooltipPaneView.update(this._tooltipData);
  }
  setData(t, e) {
    this._crosshairData = t, this._tooltipData = e, this.updateAllViews(), this._attachedParams?.requestUpdate();
  }
  currentColor() {
    return this._options.lineColor;
  }
  chart() {
    return this._attachedParams?.chart;
  }
  series() {
    return this._attachedParams?.series;
  }
  applyOptions(t) {
    this._options = {
      ...this._options,
      ...t
    }, this._tooltipData.topSpacing = this._options.topOffset;
  }
  activeRange() {
    return this._activeRange;
  }
  _setCrosshairMode() {
    const t = this.chart();
    if (!t)
      throw new Error(
        "Unable to change crosshair mode because the chart instance is undefined"
      );
    t.applyOptions({
      crosshair: {
        mode: y.Magnet,
        vertLine: {
          visible: !1,
          labelVisible: !1
        },
        horzLine: {
          visible: !1,
          labelVisible: !1
        }
      }
    });
    const e = this.series();
    e && e.applyOptions({ crosshairMarkerVisible: !1 });
  }
  _hideTooltip() {
    this.setData([], {
      tooltips: []
    });
  }
  _hideCrosshair() {
    this._hideTooltip();
  }
  _chartBackgroundColor() {
    const t = this.chart();
    if (!t)
      return "#FFFFFF";
    const e = t.options().layout.background;
    return e.type === B.Solid ? e.color : e.topColor;
  }
  _seriesLineColor() {
    const t = this.series();
    if (!t)
      return "#888";
    const e = t.options();
    return e.color || e.lineColor || "#888";
  }
  _showTooltip(t) {
    const e = this.series();
    if (t.points.length < 1 || !e) {
      this._hideCrosshair();
      return;
    }
    const i = this._tooltipData.topSpacing ?? 20, o = this._chartBackgroundColor(), n = this._seriesLineColor(), a = [], h = [], l = [];
    let u = t.points[0].index;
    for (let c = 0; c < Math.min(2, t.points.length); c++) {
      const _ = t.points[c], m = e.dataByIndex(_.index);
      if (m) {
        const [f, g] = this._options.priceExtractor(m);
        l.push([f, _.index]);
        const p = e.priceToCoordinate(f) ?? -1e3, [M, x] = O(
          m.time ? F(m.time) : void 0
        ), w = {
          x: _.x,
          lineContent: [g, M]
        };
        this._options.showTime && w.lineContent.push(x), _.index >= u ? a.push(w) : a.unshift(w), h.push({
          x: _.x,
          priceY: p,
          visible: !0,
          color: this.currentColor(),
          topMargin: i,
          markerColor: n,
          markerBorderColor: o
        });
      }
    }
    const d = {
      tooltips: a
    };
    if (l.length > 1) {
      const c = l[1][1] > l[0][1], _ = c ? l[0][0] : l[1][0], f = (c ? l[1][0] : l[0][0]) - _, g = 100 * f / _, p = f >= 0;
      d.deltaTopLine = (p ? "+" : "") + f.toFixed(2), d.deltaBottomLine = (p ? "+" : "") + g.toFixed(2) + "%", d.deltaBackgroundColor = p ? "rgb(4,153,129, 0.2)" : "rgb(239,83,80, 0.2)", d.deltaTextColor = p ? "rgb(4,153,129)" : "rgb(239,83,80)", this._activeRange.fire({
        from: l[c ? 0 : 1][1] + 1,
        to: l[c ? 1 : 0][1] + 1,
        positive: p
      });
    } else
      d.deltaTopLine = "", d.deltaBottomLine = "", this._activeRange.fire(null);
    this.setData(h, d);
  }
}
export {
  q as DeltaTooltipPrimitive
};
