import { isUTCTimestamp as u, isBusinessDay as m, CrosshairMode as f } from "lightweight-charts";
const v = {
  title: "",
  followMode: "tracking",
  horizontalDeadzoneWidth: 45,
  verticalDeadzoneHeight: 100,
  verticalSpacing: 20,
  topOffset: 20
};
class g {
  _chart;
  _element;
  _titleElement;
  _priceElement;
  _dateElement;
  _timeElement;
  _options;
  _lastTooltipWidth = null;
  constructor(t, i) {
    this._options = {
      ...v,
      ...i
    }, this._chart = t;
    const o = document.createElement("div");
    p(o, {
      display: "flex",
      "flex-direction": "column",
      "align-items": "center",
      position: "absolute",
      transform: "translate(calc(0px - 50%), 0px)",
      opacity: "0",
      left: "0%",
      top: "0",
      "z-index": "100",
      "background-color": "white",
      "border-radius": "4px",
      padding: "5px 10px",
      "font-family": "-apple-system, BlinkMacSystemFont, 'Trebuchet MS', Roboto, Ubuntu, sans-serif",
      "font-size": "12px",
      "font-weight": "400",
      "box-shadow": "0px 2px 4px rgba(0, 0, 0, 0.2)",
      "line-height": "16px",
      "pointer-events": "none",
      color: "#131722"
    });
    const s = document.createElement("div");
    p(s, {
      "font-size": "16px",
      "line-height": "24px",
      "font-weight": "590"
    }), l(s, this._options.title), o.appendChild(s);
    const n = document.createElement("div");
    p(n, {
      "font-size": "14px",
      "line-height": "18px",
      "font-weight": "590"
    }), l(n, ""), o.appendChild(n);
    const a = document.createElement("div");
    p(a, {
      color: "#787B86"
    }), l(a, ""), o.appendChild(a);
    const r = document.createElement("div");
    p(r, {
      color: "#787B86"
    }), l(r, ""), o.appendChild(r), this._element = o, this._titleElement = s, this._priceElement = n, this._dateElement = a, this._timeElement = r;
    const h = this._chart.chartElement();
    h.appendChild(this._element);
    const d = h.parentElement;
    if (!d) {
      console.error("Chart Element is not attached to the page.");
      return;
    }
    const c = getComputedStyle(d).position;
    c !== "relative" && c !== "absolute" && console.error("Chart Element position is expected be `relative` or `absolute`.");
  }
  destroy() {
    this._chart && this._element && this._chart.chartElement().removeChild(this._element);
  }
  applyOptions(t) {
    this._options = {
      ...this._options,
      ...t
    };
  }
  options() {
    return this._options;
  }
  updateTooltipContent(t) {
    if (!this._element) return;
    const i = this._element.getBoundingClientRect();
    this._lastTooltipWidth = i.width, t.title !== void 0 && this._titleElement && l(this._titleElement, t.title), l(this._priceElement, t.price), l(this._dateElement, t.date), l(this._timeElement, t.time);
  }
  updatePosition(t) {
    if (!this._chart || !this._element || (this._element.style.opacity = t.visible ? "1" : "0", !t.visible))
      return;
    const i = this._calculateXPosition(t, this._chart), o = this._calculateYPosition(t);
    this._element.style.transform = `translate(${i}, ${o})`;
  }
  _calculateXPosition(t, i) {
    const o = t.paneX + i.priceScale("left").width(), s = this._lastTooltipWidth ? Math.ceil(this._lastTooltipWidth / 2) : this._options.horizontalDeadzoneWidth;
    return `calc(${Math.min(
      Math.max(s, o),
      i.timeScale().width() - s
    )}px - 50%)`;
  }
  _calculateYPosition(t) {
    if (this._options.followMode == "top")
      return `${this._options.topOffset}px`;
    const i = t.paneY, o = i <= this._options.verticalSpacing + this._options.verticalDeadzoneHeight;
    return `calc(${i + (o ? 1 : -1) * this._options.verticalSpacing}px${o ? "" : " - 100%"})`;
  }
}
function l(e, t) {
  !e || t === e.innerText || (e.innerText = t, e.style.display = t ? "block" : "none");
}
function p(e, t) {
  for (const [i, o] of Object.entries(t))
    e.style.setProperty(i, o);
}
function x(e) {
  if (u(e)) return e * 1e3;
  if (m(e)) return new Date(e.year, e.month, e.day).valueOf();
  const [t, i, o] = e.split("-").map(parseInt);
  return new Date(t, i, o).valueOf();
}
function b(e) {
  if (!e) return ["", ""];
  const t = new Date(e), i = t.getFullYear(), o = t.toLocaleString("default", { month: "short" }), n = `${t.getDate().toString().padStart(2, "0")} ${o} ${i}`, a = t.getHours().toString().padStart(2, "0"), r = t.getMinutes().toString().padStart(2, "0"), h = `${a}:${r}`;
  return [n, h];
}
function E(e) {
  return Math.floor(e * 0.5);
}
function y(e, t, i = 1, o) {
  const s = Math.round(t * e), n = Math.round(i * t), a = E(n);
  return { position: s - a, length: n };
}
class w {
  _data;
  constructor(t) {
    this._data = t;
  }
  draw(t) {
    this._data.visible && t.useBitmapCoordinateSpace((i) => {
      const o = i.context, s = y(
        this._data.x,
        i.horizontalPixelRatio,
        1
      );
      o.fillStyle = this._data.color, o.fillRect(
        s.position,
        this._data.topMargin * i.verticalPixelRatio,
        s.length,
        i.bitmapSize.height
      );
    });
  }
}
class C {
  _data;
  constructor(t) {
    this._data = t;
  }
  update(t) {
    this._data = t;
  }
  renderer() {
    return new w(this._data);
  }
  zOrder() {
    return "bottom";
  }
}
const M = {
  lineColor: "rgba(0, 0, 0, 0.2)",
  priceExtractor: (e) => e.value !== void 0 ? e.value.toFixed(2) : e.close !== void 0 ? e.close.toFixed(2) : ""
};
class P {
  _options;
  _tooltip = void 0;
  _paneViews;
  _data = {
    x: 0,
    visible: !1,
    color: "rgba(0, 0, 0, 0.2)",
    topMargin: 0
  };
  _attachedParams;
  constructor(t) {
    this._options = {
      ...M,
      ...t
    }, this._paneViews = [new C(this._data)];
  }
  attached(t) {
    this._attachedParams = t, this._setCrosshairMode(), t.chart.subscribeCrosshairMove(this._moveHandler), this._createTooltipElement();
  }
  detached() {
    const t = this.chart();
    t && t.unsubscribeCrosshairMove(this._moveHandler);
  }
  paneViews() {
    return this._paneViews;
  }
  updateAllViews() {
    this._paneViews.forEach((t) => t.update(this._data));
  }
  setData(t) {
    this._data = t, this.updateAllViews(), this._attachedParams?.requestUpdate();
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
    }, this._tooltip && this._tooltip.applyOptions({ ...this._options.tooltip });
  }
  _setCrosshairMode() {
    const t = this.chart();
    if (!t)
      throw new Error(
        "Unable to change crosshair mode because the chart instance is undefined"
      );
    t.applyOptions({
      crosshair: {
        mode: f.Magnet,
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
  }
  _moveHandler = (t) => this._onMouseMove(t);
  _hideTooltip() {
    this._tooltip && (this._tooltip.updateTooltipContent({
      title: "",
      price: "",
      date: "",
      time: ""
    }), this._tooltip.updatePosition({
      paneX: 0,
      paneY: 0,
      visible: !1
    }));
  }
  _hideCrosshair() {
    this._hideTooltip(), this.setData({
      x: 0,
      visible: !1,
      color: this.currentColor(),
      topMargin: 0
    });
  }
  _onMouseMove(t) {
    const i = this.chart(), o = this.series(), s = t.logical;
    if (!s || !i || !o) {
      this._hideCrosshair();
      return;
    }
    const n = t.seriesData.get(o);
    if (!n) {
      this._hideCrosshair();
      return;
    }
    const a = this._options.priceExtractor(n), r = i.timeScale().logicalToCoordinate(s), [h, d] = b(t.time ? x(t.time) : void 0);
    if (this._tooltip) {
      const c = this._tooltip.options(), _ = c.followMode == "top" ? c.topOffset + 10 : 0;
      this.setData({
        x: r ?? 0,
        visible: r !== null,
        color: this.currentColor(),
        topMargin: _
      }), this._tooltip.updateTooltipContent({
        price: a,
        date: h,
        time: d
      }), this._tooltip.updatePosition({
        paneX: t.point?.x ?? 0,
        paneY: t.point?.y ?? 0,
        visible: !0
      });
    }
  }
  _createTooltipElement() {
    const t = this.chart();
    if (!t)
      throw new Error("Unable to create Tooltip element. Chart not attached");
    this._tooltip = new g(t, {
      ...this._options.tooltip
    });
  }
}
export {
  P as TooltipPrimitive
};
