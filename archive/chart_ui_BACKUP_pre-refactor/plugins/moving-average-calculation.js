function m(n) {
  for (const e of n)
    if (typeof e.time != "number")
      throw new Error('All items must have a numeric "time" property.');
  return n;
}
function a(n) {
  for (const e of n) {
    if (typeof e.close == "number")
      return "close";
    if (typeof e.value == "number")
      return "value";
  }
  return null;
}
function p(n, e) {
  const r = e.source ?? a(n);
  if (!r)
    throw new Error(
      "Please provide a `source` property for the moving average indicator."
    );
  m(n);
  const i = n.map(
    (f) => f[r]
  ), u = n.map((f) => f.time), t = l(
    i,
    e.length
  );
  let o = t;
  e.smoothingLine && e.smoothingLength && e.smoothingLength > 1 && (o = h(t, e.smoothingLine, e.smoothingLength));
  let s = e.offset ?? 0;
  return s !== 0 && (s > 0 ? o = Array(s).fill(void 0).concat(o.slice(0, o.length - s)) : s < 0 && (o = o.slice(-s).concat(Array(-s).fill(void 0)))), u.map(
    (f, c) => typeof o[c] == "number" ? { time: f, value: o[c] } : { time: f }
  );
}
function h(n, e, r) {
  switch (e) {
    case "SMA":
      return l(n, r);
    case "EMA":
      return v(n, r);
    case "WMA":
      return g(n, r);
    default:
      throw new Error("Unknown smoothing method: " + e);
  }
}
function l(n, e) {
  const r = [];
  let i = 0;
  const u = [];
  for (let t = 0; t < n.length; ++t) {
    const o = n[t];
    if (typeof o != "number") {
      r.push(void 0);
      continue;
    }
    if (u.push(o), i += o, u.length > e) {
      const s = u.shift();
      i -= s;
    }
    u.length === e && u.every((s) => !isNaN(s)) ? r.push(i / e) : r.push(void 0);
  }
  return r;
}
function v(n, e) {
  const r = [];
  let i;
  const u = 2 / (e + 1);
  for (let t = 0; t < n.length; ++t) {
    const o = n[t];
    if (typeof o != "number") {
      r.push(void 0);
      continue;
    }
    i === void 0 ? i = o : i = o * u + i * (1 - u), r.push(i);
  }
  for (let t = 0; t < e - 1 && t < r.length; ++t)
    r[t] = void 0;
  return r;
}
function g(n, e) {
  const r = [], i = Array.from({ length: e }, (t, o) => o + 1), u = i.reduce((t, o) => t + o, 0);
  for (let t = 0; t < n.length; ++t) {
    if (t < e - 1) {
      r.push(void 0);
      continue;
    }
    let o = 0, s = !0;
    for (let f = 0; f < e; ++f) {
      const c = n[t - e + 1 + f];
      if (typeof c != "number") {
        s = !1;
        break;
      }
      o += c * i[f];
    }
    r.push(s ? o / u : void 0);
  }
  return r;
}
export {
  p as calculateMovingAverageIndicatorValues
};
