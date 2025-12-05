class a {
  numbers;
  cache;
  constructor(e) {
    this.numbers = e, this.cache = /* @__PURE__ */ new Map();
  }
  findClosestIndex(e, s) {
    const t = `${e}:${s}`;
    if (this.cache.has(t))
      return this.cache.get(t);
    const r = this._performSearch(e, s);
    return this.cache.set(t, r), r;
  }
  _performSearch(e, s) {
    let t = 0, r = this.numbers.length - 1;
    if (e <= this.numbers[0].time) return 0;
    if (e >= this.numbers[r].time) return r;
    for (; t <= r; ) {
      const c = Math.floor((t + r) / 2), o = this.numbers[c].time;
      if (o === e)
        return c;
      o > e ? r = c - 1 : t = c + 1;
    }
    return s === "left" ? t : r;
  }
}
function l(n) {
  for (const e of n)
    if (typeof e.time != "number")
      throw new Error('All items must have a numeric "time" property.');
  return n;
}
function f(n) {
  for (const e of n) {
    if (typeof e.close == "number")
      return "close";
    if (typeof e.value == "number")
      return "value";
  }
  return null;
}
function d(n, e, s) {
  const t = s.primarySource ?? f(n);
  if (!t)
    throw new Error(
      "Please provide a `primarySource` for the primary data of the spread indicator."
    );
  const r = s.secondarySource ?? f(e);
  if (!r)
    throw new Error(
      "Please provide a `secondarySource` for the secondary data of the spread indicator."
    );
  l(n);
  const c = new a(
    l(e)
  );
  return n.map((o) => {
    const i = {
      time: o.time
    }, u = o[t];
    if (u === void 0)
      return i;
    const m = c.findClosestIndex(
      o.time,
      "left"
    ), h = e[m][r];
    return h === void 0 || !s.allowMismatchedDates && e[m].time !== o.time ? i : {
      time: o.time,
      value: u - h
    };
  });
}
export {
  d as calculateSpreadIndicatorValues
};
