class a {
  numbers;
  cache;
  constructor(e) {
    this.numbers = e, this.cache = /* @__PURE__ */ new Map();
  }
  findClosestIndex(e, o) {
    const t = `${e}:${o}`;
    if (this.cache.has(t))
      return this.cache.get(t);
    const r = this._performSearch(e, o);
    return this.cache.set(t, r), r;
  }
  _performSearch(e, o) {
    let t = 0, r = this.numbers.length - 1;
    if (e <= this.numbers[0].time) return 0;
    if (e >= this.numbers[r].time) return r;
    for (; t <= r; ) {
      const i = Math.floor((t + r) / 2), s = this.numbers[i].time;
      if (s === e)
        return i;
      s > e ? r = i - 1 : t = i + 1;
    }
    return o === "left" ? t : r;
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
function d(n, e, o) {
  const t = o.primarySource ?? f(n);
  if (!t)
    throw new Error(
      "Please provide a `primarySource` for the primary data of the ratio indicator."
    );
  const r = o.secondarySource ?? f(e);
  if (!r)
    throw new Error(
      "Please provide a `secondarySource` for the secondary data of the ratio indicator."
    );
  l(n);
  const i = new a(
    l(e)
  );
  return n.map((s) => {
    const c = {
      time: s.time
    }, u = s[t];
    if (u === void 0)
      return c;
    const m = i.findClosestIndex(
      s.time,
      "left"
    ), h = e[m][r];
    return h === void 0 || !o.allowMismatchedDates && e[m].time !== s.time ? c : {
      time: s.time,
      value: u / h
    };
  });
}
export {
  d as calculateRatioIndicatorValues
};
