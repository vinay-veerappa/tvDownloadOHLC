class Y {
  numbers;
  cache;
  constructor(e) {
    this.numbers = e, this.cache = /* @__PURE__ */ new Map();
  }
  findClosestIndex(e, i) {
    const n = `${e}:${i}`;
    if (this.cache.has(n))
      return this.cache.get(n);
    const r = this._performSearch(e, i);
    return this.cache.set(n, r), r;
  }
  _performSearch(e, i) {
    let n = 0, r = this.numbers.length - 1;
    if (e <= this.numbers[0].time) return 0;
    if (e >= this.numbers[r].time) return r;
    for (; n <= r; ) {
      const a = Math.floor((n + r) / 2), h = this.numbers[a].time;
      if (h === e)
        return a;
      h > e ? r = a - 1 : n = a + 1;
    }
    return i === "left" ? n : r;
  }
}
function x(c) {
  for (const e of c)
    if (typeof e.time != "number")
      throw new Error('All items must have a numeric "time" property.');
  return c;
}
function b(c) {
  for (const e of c) {
    if (typeof e.close == "number")
      return "close";
    if (typeof e.value == "number")
      return "value";
  }
  return null;
}
function F(c, e, i) {
  const n = i.primarySource ?? b(c);
  if (!n)
    throw new Error(
      "Please provide a `primarySource` for the primary data of the correlation indicator."
    );
  const r = i.secondarySource ?? b(e);
  if (!r)
    throw new Error(
      "Please provide a `secondarySource` for the secondary data of the correlation indicator."
    );
  x(c);
  const a = new Y(
    x(e)
  ), h = i.length, t = [], o = [];
  return c.map((m) => {
    const f = {
      time: m.time
    }, N = m[n];
    if (N === void 0)
      return t.push(NaN), o.push(NaN), t.length > h && (t.shift(), o.shift()), f;
    const I = a.findClosestIndex(
      m.time,
      "left"
    ), y = e[I], S = y?.[r], M = y?.time === m.time;
    if (S === void 0 || !i.allowMismatchedDates && !M)
      return t.push(NaN), o.push(NaN), t.length > h && (t.shift(), o.shift()), f;
    if (t.push(N), o.push(S), t.length > h && (t.shift(), o.shift()), t.length < h || t.some(isNaN) || o.some(isNaN))
      return f;
    const d = h, p = t.reduce((u, s) => u + s, 0), w = o.reduce((u, s) => u + s, 0), g = t.reduce(
      (u, s, X) => u + s * o[X],
      0
    ), C = t.reduce((u, s) => u + s * s, 0), E = o.reduce((u, s) => u + s * s, 0), V = d * g - p * w, v = Math.sqrt(
      (d * C - p * p) * (d * E - w * w)
    );
    let l;
    return v === 0 ? l = 0 : (l = V / v, l = Math.max(-1, Math.min(1, l))), {
      time: m.time,
      value: l
    };
  });
}
export {
  F as calculateCorrelationIndicatorValues
};
