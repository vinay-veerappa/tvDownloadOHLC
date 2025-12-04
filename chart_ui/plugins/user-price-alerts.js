const m = [
  new Path2D(
    "M5.34004 1.12254C4.7902 0.438104 3.94626 0 3 0C1.34315 0 0 1.34315 0 3C0 3.94626 0.438104 4.7902 1.12254 5.34004C1.04226 5.714 1 6.10206 1 6.5C1 9.36902 3.19675 11.725 6 11.9776V10.9725C3.75002 10.7238 2 8.81628 2 6.5C2 4.01472 4.01472 2 6.5 2C8.81628 2 10.7238 3.75002 10.9725 6H11.9776C11.9574 5.77589 11.9237 5.55565 11.8775 5.34011C12.562 4.79026 13.0001 3.9463 13.0001 3C13.0001 1.34315 11.6569 0 10.0001 0C9.05382 0 8.20988 0.438111 7.66004 1.12256C7.28606 1.04227 6.89797 1 6.5 1C6.10206 1 5.714 1.04226 5.34004 1.12254ZM4.28255 1.46531C3.93534 1.17484 3.48809 1 3 1C1.89543 1 1 1.89543 1 3C1 3.48809 1.17484 3.93534 1.46531 4.28255C2.0188 3.02768 3.02768 2.0188 4.28255 1.46531ZM8.71751 1.46534C9.97237 2.01885 10.9812 3.02774 11.5347 4.28262C11.8252 3.93541 12.0001 3.48812 12.0001 3C12.0001 1.89543 11.1047 1 10.0001 1C9.51199 1 9.06472 1.17485 8.71751 1.46534Z"
  ),
  new Path2D("M7 7V4H8V8H5V7H7Z"),
  new Path2D("M10 8V10H8V11H10V13H11V11H13V10H11V8H10Z")
], w = [
  new Path2D(
    "M5.11068 1.65894C3.38969 2.08227 1.98731 3.31569 1.33103 4.93171C0.938579 4.49019 0.700195 3.90868 0.700195 3.27148C0.700195 1.89077 1.81948 0.771484 3.2002 0.771484C3.9664 0.771484 4.65209 1.11617 5.11068 1.65894Z"
  ),
  new Path2D(
    "M12.5 3.37148C12.5 4.12192 12.1694 4.79514 11.6458 5.25338C11.0902 3.59304 9.76409 2.2857 8.09208 1.7559C8.55066 1.21488 9.23523 0.871484 10 0.871484C11.3807 0.871484 12.5 1.99077 12.5 3.37148Z"
  ),
  new Path2D(
    "M6.42896 11.4999C8.91424 11.4999 10.929 9.48522 10.929 6.99994C10.929 4.51466 8.91424 2.49994 6.42896 2.49994C3.94367 2.49994 1.92896 4.51466 1.92896 6.99994C1.92896 9.48522 3.94367 11.4999 6.42896 11.4999ZM6.00024 3.99994V6.99994H4.00024V7.99994H7.00024V3.99994H6.00024Z"
  ),
  new Path2D(
    "M4.08902 0.934101C4.4888 1.08621 4.83946 1.33793 5.11068 1.65894C5.06565 1.67001 5.02084 1.68164 4.97625 1.69382C4.65623 1.78123 4.34783 1.89682 4.0539 2.03776C3.16224 2.4653 2.40369 3.12609 1.8573 3.94108C1.64985 4.2505 1.47298 4.58216 1.33103 4.93171C1.05414 4.6202 0.853937 4.23899 0.760047 3.81771C0.720863 3.6419 0.700195 3.45911 0.700195 3.27148C0.700195 1.89077 1.81948 0.771484 3.2002 0.771484C3.51324 0.771484 3.81285 0.829023 4.08902 0.934101ZM12.3317 4.27515C12.4404 3.99488 12.5 3.69015 12.5 3.37148C12.5 1.99077 11.3807 0.871484 10 0.871484C9.66727 0.871484 9.34974 0.936485 9.05938 1.05448C8.68236 1.20769 8.35115 1.45027 8.09208 1.7559C8.43923 1.8659 8.77146 2.00942 9.08499 2.18265C9.96762 2.67034 10.702 3.39356 11.2032 4.26753C11.3815 4.57835 11.5303 4.90824 11.6458 5.25338C11.947 4.98973 12.1844 4.65488 12.3317 4.27515ZM9.18112 3.43939C8.42029 2.85044 7.46556 2.49994 6.42896 2.49994C3.94367 2.49994 1.92896 4.51466 1.92896 6.99994C1.92896 9.48522 3.94367 11.4999 6.42896 11.4999C8.91424 11.4999 10.929 9.48522 10.929 6.99994C10.929 5.55126 10.2444 4.26246 9.18112 3.43939ZM6.00024 3.99994H7.00024V7.99994H4.00024V6.99994H6.00024V3.99994Z"
  )
], P = 10, x = new Path2D(
  "M9.35359 1.35359C9.11789 1.11789 8.88219 0.882187 8.64648 0.646484L5.00004 4.29293L1.35359 0.646484C1.11791 0.882212 0.882212 1.11791 0.646484 1.35359L4.29293 5.00004L0.646484 8.64648C0.882336 8.88204 1.11804 9.11774 1.35359 9.35359L5.00004 5.70714L8.64648 9.35359C8.88217 9.11788 9.11788 8.88217 9.35359 8.64649L5.70714 5.00004L9.35359 1.35359Z"
);
class v {
  _listeners = [];
  subscribe(t, e, i) {
    const r = {
      callback: t,
      linkedObject: e,
      singleshot: i === !0
    };
    this._listeners.push(r);
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
class y {
  _chart = void 0;
  _series = void 0;
  _unSubscribers = [];
  _clicked = new v();
  _mouseMoved = new v();
  attached(t, e) {
    this._chart = t, this._series = e;
    const i = this._chart.chartElement();
    this._addMouseEventListener(
      i,
      "mouseleave",
      this._mouseLeave
    ), this._addMouseEventListener(
      i,
      "mousemove",
      this._mouseMove
    ), this._addMouseEventListener(
      i,
      "click",
      this._mouseClick
    );
  }
  detached() {
    this._series = void 0, this._clicked.destroy(), this._mouseMoved.destroy(), this._unSubscribers.forEach((t) => {
      t();
    }), this._unSubscribers = [];
  }
  clicked() {
    return this._clicked;
  }
  mouseMoved() {
    return this._mouseMoved;
  }
  _addMouseEventListener(t, e, i) {
    const r = i.bind(this);
    t.addEventListener(e, r);
    const s = () => {
      t.removeEventListener(e, r);
    };
    this._unSubscribers.push(s);
  }
  _mouseLeave() {
    this._mouseMoved.fire(null);
  }
  _mouseMove(t) {
    this._mouseMoved.fire(this._determineMousePosition(t));
  }
  _mouseClick(t) {
    this._clicked.fire(this._determineMousePosition(t));
  }
  _determineMousePosition(t) {
    if (!this._chart || !this._series) return null;
    const e = this._chart.chartElement(), i = e.getBoundingClientRect(), r = this._series.priceScale().width(), s = this._chart.timeScale().height(), n = t.clientX - i.x, a = t.clientY - i.y, h = a > e.clientHeight - s, l = e.clientWidth - r - n, c = l < 0;
    return {
      x: n,
      y: a,
      xPositionRelativeToPriceScale: l,
      overPriceScale: c,
      overTimeScale: h
    };
  }
}
class f {
  _data = null;
  update(t) {
    this._data = t;
  }
}
function R(o) {
  return Math.floor(o * 0.5);
}
function _(o, t, e = 1, i) {
  const r = Math.round(t * o), s = Math.round(e * t), n = R(s);
  return { position: r - n, length: s };
}
class S extends f {
  draw(t) {
    t.useBitmapCoordinateSpace((e) => {
      if (!this._data) return;
      this._drawAlertLines(e), this._drawAlertIcons(e), this._data.alerts.some(
        (r) => r.showHover && r.hoverRemove
      ) || (this._drawCrosshairLine(e), this._drawCrosshairLabelButton(e)), this._drawAlertLabel(e);
    });
  }
  _drawHorizontalLine(t, e) {
    const i = t.context;
    try {
      const r = _(
        e.y,
        t.verticalPixelRatio,
        e.lineWidth
      ), s = r.position + r.length / 2;
      i.save(), i.beginPath(), i.lineWidth = e.lineWidth, i.strokeStyle = e.color;
      const n = 4 * t.horizontalPixelRatio;
      i.setLineDash([n, n]), i.moveTo(0, s), i.lineTo(
        (e.width - 21) * t.horizontalPixelRatio,
        s
      ), i.stroke();
    } finally {
      i.restore();
    }
  }
  _drawAlertLines(t) {
    if (!this._data?.alerts) return;
    const e = this._data.color;
    this._data.alerts.forEach((i) => {
      this._drawHorizontalLine(t, {
        width: t.mediaSize.width,
        lineWidth: 1,
        color: e,
        y: i.y
      });
    });
  }
  _drawAlertIcons(t) {
    if (!this._data?.alerts) return;
    const e = this._data.color, i = this._data.alertIcon;
    this._data.alerts.forEach((r) => {
      this._drawLabel(t, {
        width: t.mediaSize.width,
        labelHeight: 17,
        y: r.y,
        roundedCorners: 2,
        icon: i,
        iconScaling: 13 / 13,
        padding: {
          left: 4,
          top: 2
        },
        color: e
      });
    });
  }
  _calculateLabelWidth(t) {
    return 9 * 2 + 26 + t * 5.81;
  }
  _drawAlertLabel(t) {
    if (!this._data?.alerts) return;
    const e = t.context, i = this._data.alerts.find((a) => a.showHover);
    if (!i || !i.showHover) return;
    const r = this._calculateLabelWidth(i.text.length), s = _(
      t.mediaSize.width / 2,
      t.horizontalPixelRatio,
      r
    ), n = _(
      i.y,
      t.verticalPixelRatio,
      20
    );
    e.save();
    try {
      const a = 4 * t.horizontalPixelRatio;
      e.beginPath(), e.roundRect(
        s.position,
        n.position,
        s.length,
        n.length,
        a
      ), e.fillStyle = "#FFFFFF", e.fill();
      const h = s.position + s.length - 26 * t.horizontalPixelRatio;
      i.hoverRemove && (e.beginPath(), e.roundRect(
        h,
        n.position,
        26 * t.horizontalPixelRatio,
        n.length,
        [0, a, a, 0]
      ), e.fillStyle = "#F0F3FA", e.fill()), e.beginPath();
      const l = _(
        h / t.horizontalPixelRatio,
        t.horizontalPixelRatio,
        1
      );
      e.fillStyle = "#F1F3FB", e.fillRect(
        l.position,
        n.position,
        l.length,
        n.length
      ), e.beginPath(), e.roundRect(
        s.position,
        n.position,
        s.length,
        n.length,
        a
      ), e.strokeStyle = "#131722", e.lineWidth = 1 * t.horizontalPixelRatio, e.stroke(), e.beginPath(), e.fillStyle = "#131722", e.textBaseline = "middle", e.font = `${Math.round(12 * t.verticalPixelRatio)}px sans-serif`, e.fillText(
        i.text,
        s.position + 9 * t.horizontalPixelRatio,
        i.y * t.verticalPixelRatio
      ), e.beginPath();
      const c = 9;
      e.translate(
        h + t.horizontalPixelRatio * (26 - c) / 2,
        (i.y - 5) * t.verticalPixelRatio
      );
      const d = c / P * t.horizontalPixelRatio;
      e.scale(d, d), e.fillStyle = "#131722", e.fill(x, "evenodd");
    } finally {
      e.restore();
    }
  }
  _drawCrosshairLine(t) {
    this._data?.crosshair && this._drawHorizontalLine(t, {
      width: t.mediaSize.width,
      lineWidth: 1,
      color: this._data.color,
      y: this._data.crosshair.y
    });
  }
  _drawCrosshairLabelButton(t) {
    !this._data?.button || !this._data?.crosshair || this._drawLabel(t, {
      width: t.mediaSize.width,
      labelHeight: 21,
      y: this._data.crosshair.y,
      roundedCorners: [2, 0, 0, 2],
      icon: this._data.button.crosshairLabelIcon,
      iconScaling: 13 / 13,
      padding: {
        left: 4,
        top: 4
      },
      color: this._data.button.hovering ? this._data.button.hoverColor : this._data.color
    });
  }
  _drawLabel(t, e) {
    const i = t.context;
    try {
      i.save(), i.beginPath();
      const r = _(
        e.y,
        t.verticalPixelRatio,
        e.labelHeight
      ), s = (e.width - 22) * t.horizontalPixelRatio;
      i.roundRect(
        s,
        r.position,
        21 * t.horizontalPixelRatio,
        r.length,
        H(e.roundedCorners, t.horizontalPixelRatio)
      ), i.fillStyle = e.color, i.fill(), i.beginPath(), i.translate(
        s + e.padding.left * t.horizontalPixelRatio,
        r.position + e.padding.top * t.verticalPixelRatio
      ), i.scale(
        e.iconScaling * t.horizontalPixelRatio,
        e.iconScaling * t.verticalPixelRatio
      ), i.fillStyle = "#FFFFFF", e.icon.forEach((n) => {
        i.beginPath(), i.fill(n, "evenodd");
      });
    } finally {
      i.restore();
    }
  }
}
function H(o, t) {
  return typeof o == "number" ? o * t : o.map((e) => e * t);
}
class M extends f {
  draw(t) {
    t.useBitmapCoordinateSpace((e) => {
      this._data && this._drawCrosshairLabel(e);
    });
  }
  _drawCrosshairLabel(t) {
    if (!this._data?.crosshair) return;
    const e = t.context;
    try {
      const r = t.bitmapSize.width - 8 * t.horizontalPixelRatio;
      e.save(), e.beginPath(), e.fillStyle = this._data.color;
      const s = _(this._data.crosshair.y, t.verticalPixelRatio, 21), n = 2 * t.horizontalPixelRatio;
      e.roundRect(
        0,
        s.position,
        r,
        s.length,
        [0, n, n, 0]
      ), e.fill(), e.beginPath(), e.fillStyle = "#FFFFFF", e.textBaseline = "middle", e.textAlign = "right", e.font = `${Math.round(12 * t.verticalPixelRatio)}px sans-serif`;
      const a = e.measureText(this._data.crosshair.text);
      e.fillText(
        this._data.crosshair.text,
        a.width + 10 * t.horizontalPixelRatio,
        this._data.crosshair.y * t.verticalPixelRatio
      );
    } finally {
      e.restore();
    }
  }
}
class g {
  _renderer;
  constructor(t) {
    this._renderer = t ? new M() : new S();
  }
  zOrder() {
    return "top";
  }
  renderer() {
    return this._renderer;
  }
  update(t) {
    this._renderer.update(t);
  }
}
class L {
  _alertAdded = new v();
  _alertRemoved = new v();
  _alertChanged = new v();
  _alertsChanged = new v();
  _alerts;
  constructor() {
    this._alerts = /* @__PURE__ */ new Map(), this._alertsChanged.subscribe(() => {
      this._updateAlertsArray();
    }, this);
  }
  destroy() {
    this._alertsChanged.unsubscribeAll(this);
  }
  alertAdded() {
    return this._alertAdded;
  }
  alertRemoved() {
    return this._alertRemoved;
  }
  alertChanged() {
    return this._alertChanged;
  }
  alertsChanged() {
    return this._alertsChanged;
  }
  addAlert(t) {
    const e = this._getNewId(), i = {
      price: t,
      id: e
    };
    return this._alerts.set(e, i), this._alertAdded.fire(i), this._alertsChanged.fire(), e;
  }
  removeAlert(t) {
    this._alerts.has(t) && (this._alerts.delete(t), this._alertRemoved.fire(t), this._alertsChanged.fire());
  }
  alerts() {
    return this._alertsArray;
  }
  _alertsArray = [];
  _updateAlertsArray() {
    this._alertsArray = Array.from(this._alerts.values()).sort((t, e) => e.price - t.price);
  }
  _getNewId() {
    let t = Math.round(Math.random() * 1e6).toString(16);
    for (; this._alerts.has(t); )
      t = Math.round(Math.random() * 1e6).toString(16);
    return t;
  }
}
class z extends L {
  _chart = void 0;
  _series = void 0;
  _mouseHandlers;
  _paneViews = [];
  _pricePaneViews = [];
  _lastMouseUpdate = null;
  _currentCursor = null;
  _symbolName = "";
  constructor() {
    super(), this._mouseHandlers = new y();
  }
  attached({ chart: t, series: e, requestUpdate: i }) {
    this._chart = t, this._series = e, this._paneViews = [new g(!1)], this._pricePaneViews = [new g(!0)], this._mouseHandlers.attached(t, e), this._mouseHandlers.mouseMoved().subscribe((r) => {
      this._lastMouseUpdate = r, i();
    }, this), this._mouseHandlers.clicked().subscribe((r) => {
      if (r && this._series) {
        if (this._isHovering(r)) {
          const s = this._series.coordinateToPrice(r.y);
          s && (this.addAlert(s), i());
        }
        this._hoveringID && (this.removeAlert(this._hoveringID), i());
      }
    }, this);
  }
  detached() {
    this._mouseHandlers.mouseMoved().unsubscribeAll(this), this._mouseHandlers.clicked().unsubscribeAll(this), this._mouseHandlers.detached(), this._series = void 0;
  }
  paneViews() {
    return this._paneViews;
  }
  priceAxisPaneViews() {
    return this._pricePaneViews;
  }
  updateAllViews() {
    const t = this.alerts(), e = this._calculateRendererData(
      t,
      this._lastMouseUpdate
    );
    this._currentCursor = null, (e?.button?.hovering || e?.alerts.some((i) => i.showHover && i.hoverRemove)) && (this._currentCursor = "pointer"), this._paneViews.forEach((i) => i.update(e)), this._pricePaneViews.forEach((i) => i.update(e));
  }
  hitTest() {
    return this._currentCursor ? {
      cursorStyle: this._currentCursor,
      externalId: "user-alerts-primitive",
      zOrder: "top"
    } : null;
  }
  setSymbolName(t) {
    this._symbolName = t;
  }
  _isHovering(t) {
    return !!(t && t.xPositionRelativeToPriceScale >= 1 && t.xPositionRelativeToPriceScale < 21);
  }
  _isHoveringRemoveButton(t, e, i, r) {
    if (!t || !e || Math.abs(t.y - i) > 20 / 2) return !1;
    const n = 9 * 2 + 26 + r * 5.81, a = (e + n - 26) * 0.5;
    return Math.abs(t.x - a) <= 26 / 2;
  }
  _hoveringID = "";
  /**
   * We are calculating this here instead of within a view
   * because the data is identical for both Renderers so lets
   * rather calculate it once here.
   */
  _calculateRendererData(t, e) {
    if (!this._series) return null;
    const i = this._series.priceFormatter(), r = e && !e.overTimeScale, s = r, n = e && this._series.coordinateToPrice(e.y), a = i.format(n ?? -100);
    let h = 1 / 0, l = -1;
    const c = t.map((d, b) => {
      const u = this._series.priceToCoordinate(d.price) ?? -100;
      if (e?.y && u >= 0) {
        const C = Math.abs(e.y - u);
        C < h && (l = b, h = C);
      }
      return {
        y: u,
        showHover: !1,
        price: d.price,
        id: d.id
      };
    });
    if (this._hoveringID = "", l >= 0 && h < 50) {
      const d = this._chart?.timeScale().width() ?? 0, b = c[l], u = `${this._symbolName} crossing ${this._series.priceFormatter().format(b.price)}`, C = this._isHoveringRemoveButton(
        e,
        d,
        b.y,
        u.length
      );
      c[l] = {
        ...c[l],
        showHover: !0,
        text: u,
        hoverRemove: C
      }, C && (this._hoveringID = b.id);
    }
    return {
      alertIcon: w,
      alerts: c,
      button: s ? {
        hovering: this._isHovering(e),
        hoverColor: "#50535E",
        crosshairLabelIcon: m
      } : null,
      color: "#131722",
      crosshair: r ? {
        y: e.y,
        text: a
      } : null
    };
  }
}
export {
  z as UserPriceAlerts
};
