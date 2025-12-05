function h(t, s) {
  if (t.length === 0)
    return [];
  const o = s.offset ?? 0, r = s.weight ?? 2, i = new Array(t.length), c = o > 0 ? o : 0, f = o < 0 ? t.length - 1 + o : t.length - 1;
  let n = 0;
  for (let e = 0; e < c; e++)
    i[n] = { time: t[e].time }, n += 1;
  for (let e = c; e < f; e++) {
    const l = t[e];
    "close" in l ? i[n] = { time: l.time, value: (l.close * r + l.high + l.low) / (2 + r) } : i[n] = { time: l.time }, n += 1;
  }
  for (let e = f; e < t.length; e++)
    i[n] = { time: t[e].time }, n += 1;
  return i;
}
export {
  h as calculateWeightedCloseIndicatorValues
};
