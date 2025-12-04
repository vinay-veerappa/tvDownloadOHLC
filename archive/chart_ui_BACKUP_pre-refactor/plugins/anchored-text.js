class l {
  _data;
  constructor(t) {
    this._data = t;
  }
  draw(t) {
    t.useMediaCoordinateSpace((a) => {
      const e = a.context;
      e.font = this._data.font;
      const r = e.measureText(this._data.text).width, h = 20;
      let i = h;
      const n = a.mediaSize.width, c = a.mediaSize.height;
      switch (this._data.horzAlign) {
        case "right": {
          i = n - h - r;
          break;
        }
        case "middle": {
          i = n / 2 - r / 2;
          break;
        }
      }
      const o = 10, _ = this._data.lineHeight;
      let s = o + _;
      switch (this._data.vertAlign) {
        case "middle": {
          s = c / 2 + _ / 2;
          break;
        }
        case "bottom": {
          s = c - o;
          break;
        }
      }
      e.fillStyle = this._data.color, e.fillText(this._data.text, i, s);
    });
  }
}
class u {
  _source;
  constructor(t) {
    this._source = t;
  }
  update() {
  }
  renderer() {
    return new l(this._source._data);
  }
}
class p {
  _paneViews;
  _data;
  constructor(t) {
    this._data = t, this._paneViews = [new u(this)];
  }
  updateAllViews() {
    this._paneViews.forEach((t) => t.update());
  }
  paneViews() {
    return this._paneViews;
  }
  requestUpdate;
  attached({ requestUpdate: t }) {
    this.requestUpdate = t;
  }
  detached() {
    this.requestUpdate = void 0;
  }
  applyOptions(t) {
    this._data = { ...this._data, ...t }, this.requestUpdate && this.requestUpdate();
  }
}
export {
  p as AnchoredText
};
