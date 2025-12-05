class w {
  _source;
  _view;
  constructor(e, t) {
    this._source = e, this._view = t;
  }
  draw(e) {
    e.useMediaCoordinateSpace((t) => {
      const s = t.context, i = this._view._placement;
      if (i) {
        if (!this._source._imgElement) throw new Error("Image element missing.");
        s.globalAlpha = this._source._options.alpha ?? 1, s.drawImage(
          this._source._imgElement,
          i.x,
          i.y,
          i.width,
          i.height
        );
      }
    });
  }
}
class E {
  _source;
  _placement = null;
  constructor(e) {
    this._source = e;
  }
  zOrder() {
    return "bottom";
  }
  update() {
    this._placement = this._determinePlacement();
  }
  renderer() {
    return new w(this._source, this);
  }
  _determinePlacement() {
    if (!this._source._chart) return null;
    const e = this._source._chart.priceScale("left").width(), t = this._source._chart.timeScale().width(), s = e, i = this._source._chart.chartElement().clientHeight - this._source._chart.timeScale().height(), l = Math.round(t / 2) + s, m = Math.round(i / 2) + 0, n = this._source._options.padding ?? 0;
    let a = t - 2 * n, h = i - 2 * n;
    this._source._options.maxHeight && (h = Math.min(
      h,
      this._source._options.maxHeight
    )), this._source._options.maxWidth && (a = Math.min(a, this._source._options.maxWidth));
    const u = a / this._source._imageWidth, d = h / this._source._imageHeight, o = Math.min(u, d), c = this._source._imageWidth * o, _ = this._source._imageHeight * o, g = l - 0.5 * c, p = m - 0.5 * _;
    return {
      x: g,
      y: p,
      height: _,
      width: c
    };
  }
}
class W {
  _paneViews;
  _imgElement = null;
  _imageUrl;
  _options;
  _imageHeight = 0;
  // don't draw until loaded fully
  _imageWidth = 0;
  _chart = null;
  _containerElement = null;
  _requestUpdate;
  constructor(e, t) {
    this._imageUrl = e, this._options = t, this._paneViews = [new E(this)];
  }
  attached({ chart: e, requestUpdate: t }) {
    this._chart = e, this._requestUpdate = t, this._containerElement = e.chartElement(), this._imgElement = new Image(), this._imgElement.onload = () => {
      this._imageHeight = this._imgElement?.naturalHeight ?? 1, this._imageWidth = this._imgElement?.naturalWidth ?? 1, this._paneViews.forEach((s) => s.update()), this.requestUpdate();
    }, this._imgElement.src = this._imageUrl;
  }
  detached() {
    this._imgElement = null;
  }
  requestUpdate() {
    this._requestUpdate && this._requestUpdate();
  }
  updateAllViews() {
    this._paneViews.forEach((e) => e.update());
  }
  paneViews() {
    return this._paneViews;
  }
}
export {
  W as ImageWatermark
};
