function h(e) {
  return Math.floor(e * 0.5);
}
function l(e, t, i = 1, o) {
  const s = Math.round(t * e), n = Math.round(i * t), r = h(n);
  return { position: s - r, length: n };
}
class a {
  _x = null;
  _options;
  constructor(t, i) {
    this._x = t, this._options = i;
  }
  draw(t) {
    t.useBitmapCoordinateSpace((i) => {
      if (this._x === null) return;
      const o = i.context, s = l(
        this._x,
        i.horizontalPixelRatio,
        this._options.width
      );
      o.fillStyle = this._options.color, o.fillRect(
        s.position,
        0,
        s.length,
        i.bitmapSize.height
      );
    });
  }
}
class c {
  _source;
  _x = null;
  _options;
  constructor(t, i) {
    this._source = t, this._options = i;
  }
  update() {
    const t = this._source._chart.timeScale();
    this._x = t.timeToCoordinate(this._source._time);
  }
  renderer() {
    return new a(this._x, this._options);
  }
}
class _ {
  _source;
  _x = null;
  _options;
  constructor(t, i) {
    this._source = t, this._options = i;
  }
  update() {
    const t = this._source._chart.timeScale();
    this._x = t.timeToCoordinate(this._source._time);
  }
  visible() {
    return this._options.showLabel;
  }
  tickVisible() {
    return this._options.showLabel;
  }
  coordinate() {
    return this._x ?? 0;
  }
  text() {
    return this._options.labelText;
  }
  textColor() {
    return this._options.labelTextColor;
  }
  backColor() {
    return this._options.labelBackgroundColor;
  }
}
const u = {
  color: "green",
  labelText: "",
  width: 3,
  labelBackgroundColor: "green",
  labelTextColor: "white",
  showLabel: !1
};
class x {
  _chart;
  _series;
  _time;
  _paneViews;
  _timeAxisViews;
  constructor(t, i, o, s) {
    const n = {
      ...u,
      ...s
    };
    this._chart = t, this._series = i, this._time = o, this._paneViews = [new c(this, n)], this._timeAxisViews = [new _(this, n)];
  }
  updateAllViews() {
    this._paneViews.forEach((t) => t.update()), this._timeAxisViews.forEach((t) => t.update());
  }
  timeAxisViews() {
    return this._timeAxisViews;
  }
  paneViews() {
    return this._paneViews;
  }
}
export {
  x as VertLine
};
