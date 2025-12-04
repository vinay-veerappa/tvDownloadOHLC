function i(e) {
  for (const o of e)
    if (typeof o.time != "number")
      throw new Error('All items must have a numeric "time" property.');
  return e;
}
function s(e) {
  for (const o of e) {
    if (typeof o.close == "number")
      return "close";
    if (typeof o.value == "number")
      return "value";
  }
  return null;
}
function p(e, o) {
  const t = o.source ?? s(e);
  if (!t)
    throw new Error(
      "Please provide a `source` property for the momentum indicator."
    );
  i(e);
  const r = e.map(
    (n) => n[t]
  ), m = e.map((n) => n.time), u = f(
    r,
    o.length
  );
  return m.map(
    (n, c) => typeof u[c] == "number" ? { time: n, value: u[c] } : { time: n }
  );
}
function f(e, o) {
  const t = [];
  for (let r = 0; r < e.length; ++r) {
    const m = e[r];
    if (typeof m != "number") {
      t.push(void 0);
      continue;
    }
    if (r < o)
      t.push(void 0);
    else {
      const u = e[r - o];
      if (typeof u != "number") {
        t.push(void 0);
        continue;
      }
      const n = m - u;
      t.push(n);
    }
  }
  return t;
}
export {
  p as calculateMomentumIndicatorValues
};
