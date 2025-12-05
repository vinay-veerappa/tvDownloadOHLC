function l(n, t, e) {
  const s = Math.round(e * n), i = Math.round(e * t);
  return {
    position: Math.min(s, i),
    length: Math.abs(i - s) + 1
  };
}
class c {
  _data;
  constructor(t) {
    this._data = t;
  }
  draw(t) {
    t.useBitmapCoordinateSpace((e) => {
      if (this._data.x === null || this._data.top === null) return;
      const s = e.context, i = l(
        this._data.x,
        this._data.x + this._data.width,
        e.horizontalPixelRatio
      ), r = l(
        this._data.top,
        this._data.top - this._data.columnHeight * this._data.items.length,
        e.verticalPixelRatio
      );
      s.fillStyle = "rgba(0, 0, 255, 0.2)", s.fillRect(
        i.position,
        r.position,
        i.length,
        r.length
      ), s.fillStyle = "rgba(80, 80, 255, 0.8)", this._data.items.forEach((a) => {
        if (a.y === null) return;
        const o = l(
          a.y,
          a.y - this._data.columnHeight,
          e.verticalPixelRatio
        ), h = l(
          this._data.x,
          this._data.x + a.width,
          e.horizontalPixelRatio
        );
        s.fillRect(
          h.position,
          o.position,
          h.length,
          o.length - 2
          // 1 to close gaps
        );
      });
    });
  }
}
class _ {
  _source;
  _x = null;
  _width = 6;
  _columnHeight = 0;
  _top = null;
  _items = [];
  constructor(t) {
    this._source = t;
  }
  update() {
    const t = this._source._vpData, e = this._source._series, s = this._source._chart.timeScale();
    this._x = s.timeToCoordinate(t.time), this._width = s.options().barSpacing * t.width;
    const i = e.priceToCoordinate(t.profile[0].price) ?? 0, r = e.priceToCoordinate(t.profile[1].price) ?? s.height();
    this._columnHeight = Math.max(1, i - r);
    const a = t.profile.reduce(
      (o, h) => Math.max(o, h.vol),
      0
    );
    this._top = i, this._items = t.profile.map((o) => ({
      y: e.priceToCoordinate(o.price),
      width: this._width * o.vol / a
    }));
  }
  renderer() {
    return new c({
      x: this._x,
      top: this._top,
      columnHeight: this._columnHeight,
      width: this._width,
      items: this._items
    });
  }
}
class u {
  _chart;
  _series;
  _vpData;
  _minPrice;
  _maxPrice;
  _paneViews;
  _vpIndex = null;
  constructor(t, e, s) {
    this._chart = t, this._series = e, this._vpData = s, this._minPrice = 1 / 0, this._maxPrice = -1 / 0, this._vpData.profile.forEach((i) => {
      i.price < this._minPrice && (this._minPrice = i.price), i.price > this._maxPrice && (this._maxPrice = i.price);
    }), this._paneViews = [new _(this)];
  }
  updateAllViews() {
    this._paneViews.forEach((t) => t.update());
  }
  // Ensures that the VP is within autoScale
  autoscaleInfo(t, e) {
    const s = this._chart.timeScale().timeToCoordinate(this._vpData.time);
    if (s === null) return null;
    const i = this._chart.timeScale().coordinateToLogical(s);
    return i === null || e < i || t > i + this._vpData.width ? null : {
      priceRange: {
        minValue: this._minPrice,
        maxValue: this._maxPrice
      }
    };
  }
  paneViews() {
    return this._paneViews;
  }
}
export {
  u as VolumeProfile
};
