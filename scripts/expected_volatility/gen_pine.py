"""Generate the EV Session Stack Pine indicator from study artifacts.

The research report (§5.4, §5.5, §2.3b, §4.9) validated five data objects:

  * the RTH percentile ladder (train-fitted, holdout MAE 1.45%)
  * per-weekday per-side width multipliers (§4.9, shrunk 0.5)
  * arrival curves — median arrival and cumulative P(touch by t) per rung/side
  * extension zones — ext p50/p75/p90, die-in-zone, back-to-anchor (§5.5)
  * session-stack verdicts — NY CALIBRATED / London CALIBRATED / Asia NOMINAL

Hand-typing ~200 numbers into Pine is how constants drift from the research,
and how a §7.1 refit silently fails to reach the chart. This generator reads
the JSON artifacts and emits `ev_session_stack.pine` — the same pipeline
pattern as scripts/indicators-pine/profiler/ (PROFILER_ARCHITECTURE §1).

Every constant block in the output carries its artifact + fold provenance in a
comment, so the chart and the report can be audited against each other.

Usage
-----
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.gen_pine
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.gen_pine --ticker ES1 --out custom.pine
"""

from __future__ import annotations

import argparse
import json

from .features import OUT_DIR, TARGET_P, VOL_FOR_TICKER

TICKERS = {"ES1": "ES", "NQ1": "NQ", "YM1": "YM", "RTY1": "RTY", "GC1": "GC"}
PRIORITY = (0.35, 0.25, 0.15, 0.10, 0.05)
MILESTONES = ("10:00", "11:00", "12:00", "13:30", "15:00")
MS_MIN = {"10:00": 30, "11:00": 90, "12:00": 150, "13:30": 240, "15:00": 330}
REGIME = {("up", 0.35): "broad", ("up", 0.25): "broad-close",
          ("up", 0.15): "close", ("up", 0.10): "close", ("up", 0.05): "close",
          ("dn", 0.35): "am", ("dn", 0.25): "am", ("dn", 0.15): "am",
          ("dn", 0.10): "am", ("dn", 0.05): "close"}


def _jload(name):
    p = OUT_DIR / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _arr(vals, nd=4):
    return "array.from(" + ", ".join(f"{v:.{nd}f}" for v in vals) + ")"


def _clock(m):
    m = int(round(m))
    return f"{m // 60:02d}:{m % 60:02d}"


def _blocks(ticker: str) -> dict:
    lad = _jload(f"ladder_{ticker}.json")
    if lad is None:
        # the ladder lives in the sessions frame; fall back to arrival rungs
        arr = _jload(f"arrival_{ticker}_RTH.json")
        up = [g["c"] for g in arr["rungs"] if g["side"] == "up"]
        dn = [g["c"] for g in arr["rungs"] if g["side"] == "dn"]
        lad = {"c_up": up, "c_dn": dn}
    up = [float(v) for v in lad["c_up"]] if "c_up" in lad else \
        [g["c"] for g in _jload(f"arrival_{ticker}_RTH.json")["rungs"]
     if g["side"] == "up"]
    dn = [float(v) for v in lad["c_dn"]] if "c_dn" in lad else \
        [g["c"] for g in _jload(f"arrival_{ticker}_RTH.json")["rungs"]
     if g["side"] == "dn"]

    dow = _jload(f"dow_multipliers_{ticker}_RTH.json")
    arr = _jload(f"arrival_{ticker}_RTH.json")
    rev = _jload(f"reversal_{ticker}_RTH.json")
    stack = _jload(f"sessions_stack_{ticker}.json")
    return {"ladder": (up, dn), "dow": dow, "arr": arr, "rev": rev, "stack": stack}


def generate(ticker: str = "ES1") -> str:
    b = _blocks(ticker)
    up, dn = b["ladder"]
    sym = TICKERS.get(ticker, ticker)
    vol = VOL_FOR_TICKER.get(ticker, "VIX")

    # Per-ticker session verdicts — the footer and the London/Asia input
    # labels must state THIS symbol's status, never a hardcoded string.
    verd = {"RTH": "CAL", "LONDON": "CAL", "ASIA": "CAL"}
    if b["stack"]:
        for kind in ("LONDON", "ASIA"):
            rec = b["stack"]["sessions"].get(kind, {})
            v = rec.get("pooled", {}).get("verdict")
            if v == "calibrated":
                verd[kind] = "CAL"
            elif v == "nominal":
                verd[kind] = "NOMINAL"
            else:
                verd[kind] = "REFIT"
    # a session that is not CALIBRATED must be OFF by default — it must not
    # render calibrated-looking levels the moment the indicator is added.
    show_ldn_default = verd["LONDON"] == "CAL"
    show_asi_default = False  # Asia is nominal everywhere measured

    # ---- arrival + zone blocks (priority rungs, HOLDOUT fold for trader use)
    arr_rows, cum_rows, rev_rows = [], [], []
    for g in b["arr"]["rungs"] if b["arr"] else []:
        if g["target_p"] not in PRIORITY:
            continue
        f = g["train"]  # train fold: full-session counts, stable
        med = f["hit_med_min"] if f["hit_med_min"] is not None else -1
        cum = f["milestones"]
        arr_rows.append({
            "p": g["target_p"], "side": g["side"], "c": g["c"],
            "med": med, "regime": REGIME[(g["side"], g["target_p"])],
            "cum": [cum[m]["cum"] for m in MILESTONES],
        })
    for c in b["rev"]["cells"] if b["rev"] else []:
        if c["fold"] != "train" or c["rung"] not in PRIORITY or c["n_hits"] < 30:
            continue
        if c["rung"] == 0.05:
            # die@zone is undefined for the outermost rung (no next rung to
            # fail to reach); reversal.py records 0.0 — an artifact, not a
            # stat. Bake nothing rather than a false "0%".
            continue
        rev_rows.append(c)

    # ---- Pine assembly
    L: list[str] = []
    A = L.append
    A("// ─────────────────────────────────────────────────────────────────────")
    A("//  EV Session Stack — probability·distance·time map (GENERATED)")
    A("//  Source of truth: scripts/expected_volatility/ + RESEARCH_REPORT.md")
    A("//  DO NOT hand-edit the data blocks — regenerate with gen_pine.py.")
    A("//")
    A(f"//  Validated (holdout): RTH MAE 1.45% | London 1.95% CAL | Asia NOMINAL |")
    A(f"//  arrival 68/80 cells ±5pp | zones/die/back per §5.5 | {ticker} artifacts.")
    A("//  Historical probabilities — a description of past sessions, NOT a")
    A("//  forecast, and NOT an entry signal (§3.1/§3.2).")
    A("// ─────────────────────────────────────────────────────────────────────")
    A("//@version=6")
    A(f'indicator("EV Session Stack — {sym}", "EV-Stack", overlay = true,')
    A("     max_lines_count = 500, max_labels_count = 500, max_boxes_count = 100)")
    A("")
    A('// ── inputs ──────────────────────────────────────────────────────────')
    A('grpS = "Sessions"')
    A('showRTH    = input.bool(true, "NY (RTH) — CALIBRATED",              group = grpS)')
    A(f'showLondon = input.bool({"true" if show_ldn_default else "false"}, '
      f'"London 03:00-09:30 — {verd["LONDON"]}",   group = grpS)')
    A(f'showAsia   = input.bool({"true" if show_asi_default else "false"}, '
      f'"Asia 18:00-03:00 — {verd["ASIA"]}",       group = grpS)')
    A('grpL = "Rungs"')
    A('showInner  = input.bool(false, "Inner rungs 80/65/50 (faint)",      group = grpL)')
    A('showWork   = input.bool(true,  "Work rungs 35/25 (primary)",        group = grpL)')
    A('showTails  = input.bool(true,  "Tail rungs 15/10/5 (dotted)",       group = grpL)')
    A('dowAdjust  = input.bool(true,  "Weekday width adjustment (§4.9)",   group = grpL)')
    A('grpT = "Table"')
    A('showTable  = input.bool(true,  "Show dashboard",                     group = grpT)')
    A('tblPos     = input.string("Top Right", "Position", options = ["Top Right","Top Left","Bottom Right","Bottom Left"], group = grpT)')
    A('tblSizeIn  = input.string("Small", "Size", options = ["Tiny","Small","Normal"], group = grpT)')
    A('grpV = "Vol input"')
    A(f'volSym     = input.symbol("CBOE:{vol}", "Vol index", group = grpV)')
    A('grpZ = "Zones (behind 35% rung)"')
    A('showZones  = input.bool(true, "Extension zones",                     group = grpZ)')
    A('zoneLbls   = input.bool(true, "Zone labels",                         group = grpZ)')
    A("")
    A('// ── DATA — generated blocks; provenance in each header ──────────────')
    A(f"// RTH ladder c_up/c_dn, train-fit on 887 sessions (paths.py parity)")
    A(f"var array<float> cUpRTH = {_arr(up)}")
    A(f"var array<float> cDnRTH = {_arr(dn)}")
    if b["dow"]:
        A("// Weekday multipliers Mon..Fri, shrunk 0.5 (seasonality.py, §4.9)")
        A(f"var array<float> wUpDOW = {_arr([r['w_up'] for r in b['dow']['days']])}")
        A(f"var array<float> wDnDOW = {_arr([r['w_dn'] for r in b['dow']['days']])}")
    else:
        A("var array<float> wUpDOW = array.from(1.0, 1.0, 1.0, 1.0, 1.0)")
        A("var array<float> wDnDOW = array.from(1.0, 1.0, 1.0, 1.0, 1.0)")
    if b["stack"]:
        lon = b["stack"]["sessions"]["LONDON"]["pooled"]
        asi = b["stack"]["sessions"]["ASIA"]["pooled"]
        A(f"// Session-stack ladders (sessions_stack.py: London {verd['LONDON']}, Asia {verd['ASIA']})")
        A(f"var array<float> cUpLDN = {_arr(lon['ladder_up'])}")
        A(f"var array<float> cDnLDN = {_arr(lon['ladder_dn'])}")
        A(f"var array<float> cUpASA = {_arr(asi['ladder_up'])}")
        A(f"var array<float> cDnASA = {_arr(asi['ladder_dn'])}")
    if arr_rows:
        A("// Arrival §5.4: median first-touch min + cum P(touch by t), TRAIN fold.")
        A("// arrCum is flat: row-major [row*5 + milestone], milestones")
        A("// 10:00/11:00/12:00/13:30/15:00. arrMed < 0 = too few hits.")
        A("var array<int>   arrIdx   = array.from(" + ", ".join(
            str(list(TARGET_P).index(r["p"])) for r in arr_rows) + ")")
        A("var array<string> arrSide  = array.from(" + ", ".join(
            '"up"' if r["side"] == "up" else '"dn"' for r in arr_rows) + ")")
        A("var array<int>   arrMed   = array.from(" + ", ".join(
            f"{r['med']:.0f}" for r in arr_rows) + ")")
        A("var array<float> arrCum   = array.from(" + ", ".join(
            f"{c*100:.1f}" for r in arr_rows for c in r["cum"]) + ")")
        A("var array<string> arrRegime = array.from(" + ", ".join(
            f'"{r["regime"]}"' for r in arr_rows) + ")")
    if rev_rows:
        A("// Zones §5.5: ext p50/p75/p90 (EV past rung) + die%/back% — TRAIN fold,")
        A("// n>=30. revExt/revRate flat: [row*3]/[row*2].")
        A("var array<int>    revIdx  = array.from(" + ", ".join(
            str(list(TARGET_P).index(r["rung"])) for r in rev_rows) + ")")
        A("var array<string> revSide = array.from(" + ", ".join(
            '"up"' if r["side"] == "up" else '"dn"' for r in rev_rows) + ")")
        A("var array<float>  revExt  = array.from(" + ", ".join(
            f"{v:.3f}" for r in rev_rows for v in (r["ext_p50"], r["ext_p75"], r["ext_p90"])) + ")")
        A("var array<float>  revRate = array.from(" + ", ".join(
            f"{v:.1f}" for r in rev_rows for v in (r["die_pct"]*100, r["back_pct"]*100)) + ")")
    A("")
    A('// ── helpers ─────────────────────────────────────────────────────────')
    A('NY_TZ = "America/New_York"')
    A('// median first-touch minute from the 09:30 open -> ET wall clock.')
    A('// NOTE: m is an INT here (callers pass arrMed, an array<int>); the')
    A('// int cast keeps timestamp()+m*60000 a series int — str.format_time')
    A('// requires int, and a float here is compile error CE10123.')
    A('f_med2clock(int m) =>')
    A('    m < 0 ? "—" : str.format_time(timestamp(NY_TZ, year(time, NY_TZ), month(time, NY_TZ), dayofmonth(time, NY_TZ), 9, 30) + m * 60000, "HH:mm", NY_TZ)')
    A('')
    A('f_pos(s) =>')
    A('    s == "Top Left" ? position.top_left : s == "Bottom Right" ? position.bottom_right : s == "Bottom Left" ? position.bottom_left : position.top_right')
    A('')
    A('f_tsz(s) => s == "Tiny" ? size.tiny : s == "Normal" ? size.normal : size.small')
    A('')
    A('f_clearLn(arr) =>')
    A('    if array.size(arr) > 0')
    A('        for i = 0 to array.size(arr) - 1')
    A('            line.delete(array.get(arr, i))')
    A('    array.clear(arr)')
    A('')
    A('f_clearLb(arr) =>')
    A('    if array.size(arr) > 0')
    A('        for i = 0 to array.size(arr) - 1')
    A('            label.delete(array.get(arr, i))')
    A('    array.clear(arr)')
    A('')
    A('f_clearBx(arr) =>')
    A('    if array.size(arr) > 0')
    A('        for i = 0 to array.size(arr) - 1')
    A('            box.delete(array.get(arr, i))')
    A('    array.clear(arr)')
    A('')
    A('// ── state ───────────────────────────────────────────────────────────')
    A('var array<line>  lnRTH  = array.new<line>()')
    A('var array<label> lbRTH  = array.new<label>()')
    A('var array<box>   zbxRTH = array.new<box>()')
    A('var array<label> zlbRTH = array.new<label>()')
    A('var array<line>  lnLDN  = array.new<line>()')
    A('var array<label> lbLDN  = array.new<label>()')
    A('var array<line>  lnASA  = array.new<line>()')
    A('var array<label> lbASA  = array.new<label>()')
    A('var float rthOpen = na')
    A('var float ldnOpen = na')
    A('var float asiOpen = na')
    A('var float rthEV   = na')
    A('var float ldnEV   = na')
    A('var float asiEV   = na')
    A('var bool ldnDrawn = false')
    A('var bool asiDrawn = false')
    A('')
    A('// ── runtime reads ───────────────────────────────────────────────────')
    A('vixPrev = request.security(volSym, "1D", close[1], lookahead = barmerge.lookahead_off)')
    A('int nyHour = hour(time, NY_TZ)')
    A('int nyMin  = minute(time, NY_TZ)')
    A('int nyDow  = dayofweek(time, NY_TZ)')
    A('bool inRTH    = (nyHour == 9 and nyMin >= 30) or (nyHour >= 10 and nyHour < 16)')
    A('bool inLondon = nyHour >= 3 and nyHour < 9')
    A('bool inAsia   = nyHour >= 18 or nyHour < 3')
    A('bool rthStart = inRTH and not inRTH[1]')
    A('bool ldnStart = inLondon and not inLondon[1]')
    A('bool asiStart = inAsia and not inAsia[1]')
    A('')
    A('// tEnd for the NY session (today 16:00 ET)')
    A('f_tEndRTH() => timestamp(NY_TZ, year(time, NY_TZ), month(time, NY_TZ), dayofmonth(time, NY_TZ), 16, 0)')
    A('')
    A('// ── drawing primitives ──────────────────────────────────────────────')
    A('// rung probabilities in TARGET_P order (index-matched to cUp/cDn arrays)')
    A('var array<float> PROBS = array.from(0.80, 0.65, 0.50, 0.35, 0.25, 0.15, 0.10, 0.05)')
    A('')
    A('// one rung: line + probability label; returns the level')
    A('f_rung(S, EV, c, pTxt, side, col, sty, wid, tEnd) =>')
    A('    float lvl = side == "up" ? S + EV * c : S - EV * c')
    A('    array.push(lnRTH, line.new(time, lvl, tEnd, lvl, xloc = xloc.bar_time, color = col, style = sty, width = wid))')
    A('    array.push(lbRTH, label.new(tEnd, lvl, pTxt, xloc = xloc.bar_time, style = label.style_label_left, color = color.new(color.white, 100), textcolor = col, size = size.tiny))')
    A('    lvl')
    A('')
    A('// extension zones behind a rung (TYPICAL/DEEP/STRETCH), one side')
    A('f_zone(S, EV, c, e50, e75, e90, isUp, tEnd) =>')
    A('    float sgn  = isUp ? 1.0 : -1.0')
    A('    float base = S + sgn * EV * c')
    A('    float z1 = base + sgn * EV * e50')
    A('    float z2 = base + sgn * EV * e75')
    A('    float z3 = base + sgn * EV * e90')
    A('    array.push(zbxRTH, box.new(time, math.max(base, z1), tEnd, math.min(base, z1), xloc = xloc.bar_time, bgcolor = color.new(#9e9e9e, 88), border_color = color.new(#9e9e9e, 55)))')
    A('    array.push(zbxRTH, box.new(time, math.max(z1, z2), tEnd, math.min(z1, z2), xloc = xloc.bar_time, bgcolor = color.new(#2196f3, 88), border_color = color.new(#2196f3, 55)))')
    A('    array.push(zbxRTH, box.new(time, math.max(z2, z3), tEnd, math.min(z2, z3), xloc = xloc.bar_time, bgcolor = color.new(#ff9800, 88), border_color = color.new(#ff9800, 55)))')
    A('    if zoneLbls')
    A('        array.push(zlbRTH, label.new(tEnd, (base + z1) / 2, "TYPICAL", xloc = xloc.bar_time, style = label.style_label_left, color = color.new(color.white, 100), textcolor = #9e9e9e, size = size.tiny))')
    A('        array.push(zlbRTH, label.new(tEnd, (z1 + z2) / 2, "DEEP",     xloc = xloc.bar_time, style = label.style_label_left, color = color.new(color.white, 100), textcolor = #2196f3, size = size.tiny))')
    A('        array.push(zlbRTH, label.new(tEnd, (z2 + z3) / 2, "STRETCH",  xloc = xloc.bar_time, style = label.style_label_left, color = color.new(color.white, 100), textcolor = #ff9800, size = size.tiny))')
    A('')
    A('// label text: P(touch) · median arrival · cum by 15:00')
    A('f_rungLbl(float p, int med, float cum15) =>')
    A('    str.tostring(p * 100, "#") + "%" + (med >= 0 ? " · med " + f_med2clock(med) : "") + (cum15 >= 0 ? " · " + str.tostring(cum15, "#.#") + "% by 15:00" : "")')
    A('')
    A('// ── NY (RTH) session build ──────────────────────────────────────────')
    A('if rthStart and showRTH')
    A('    f_clearLn(lnRTH)')
    A('    f_clearLb(lbRTH)')
    A('    f_clearBx(zbxRTH)')
    A('    f_clearLb(zlbRTH)')
    A('    rthOpen := open')
    A('    rthEV   := open * vixPrev / math.sqrt(252) / 100.0')
    A('    if not na(rthEV) and rthEV > 0')
    A('        int tEnd = f_tEndRTH()')
    A('        int dIdx = nyDow == dayofweek.monday ? 0 : nyDow == dayofweek.tuesday ? 1 : nyDow == dayofweek.wednesday ? 2 : nyDow == dayofweek.thursday ? 3 : 4')
    A('        float wU = dowAdjust ? array.get(wUpDOW, dIdx) : 1.0')
    A('        float wD = dowAdjust ? array.get(wDnDOW, dIdx) : 1.0')
    A('        // zones behind the 35% rung (j=3), both sides')
    A('        if showZones and showWork')
    A('            float c35u = array.get(cUpRTH, 3) * wU')
    A('            float c35d = array.get(cDnRTH, 3) * wD')
    A('            int zrU = -1')
    A('            int zrD = -1')
    A('            if array.size(revIdx) > 0')
    A('                for ri = 0 to array.size(revIdx) - 1')
    A('                    if array.get(revIdx, ri) == 3 and array.get(revSide, ri) == "up"')
    A('                        zrU := ri')
    A('                    if array.get(revIdx, ri) == 3 and array.get(revSide, ri) == "dn"')
    A('                        zrD := ri')
    A('            if zrU >= 0')
    A('                f_zone(rthOpen, rthEV, c35u, array.get(revExt, zrU * 3), array.get(revExt, zrU * 3 + 1), array.get(revExt, zrU * 3 + 2), true, tEnd)')
    A('            if zrD >= 0')
    A('                f_zone(rthOpen, rthEV, c35d, array.get(revExt, zrD * 3), array.get(revExt, zrD * 3 + 1), array.get(revExt, zrD * 3 + 2), false, tEnd)')
    A('        // rungs')
    A('        for j = 0 to 7')
    A('            bool inner = j <= 2')
    A('            bool work = j == 3 or j == 4')
    A('            bool tail = j >= 5')
    A('            bool want = (inner and showInner) or (work and showWork) or (tail and showTails)')
    A('            if want')
    A('                float p = array.get(PROBS, j)')
    A('                float cu = array.get(cUpRTH, j) * wU')
    A('                float cd_ = array.get(cDnRTH, j) * wD')
    A('                int medU = -1')
    A('                int medD = -1')
    A('                float cumU = -1.0')
    A('                float cumD = -1.0')
    A('                if array.size(arrIdx) > 0')
    A('                    for ai = 0 to array.size(arrIdx) - 1')
    A('                        if array.get(arrIdx, ai) == j and array.get(arrSide, ai) == "up"')
    A('                            medU := array.get(arrMed, ai)')
    A('                            cumU := array.get(arrCum, ai * 5 + 4)')
    A('                        if array.get(arrIdx, ai) == j and array.get(arrSide, ai) == "dn"')
    A('                            medD := array.get(arrMed, ai)')
    A('                            cumD := array.get(arrCum, ai * 5 + 4)')
    A('                color colU = inner ? color.new(#1b7f4b, 55) : work ? #1b7f4b : color.new(#1b7f4b, 30)')
    A('                color colD = inner ? color.new(#b3341f, 55) : work ? #b3341f : color.new(#b3341f, 30)')
    A('                int wid = work ? 2 : 1')
    A('                string sty = inner or tail ? line.style_dotted : line.style_solid')
    A('                f_rung(rthOpen, rthEV, cu, f_rungLbl(p, medU, cumU), "up", colU, sty, wid, tEnd)')
    A('                f_rung(rthOpen, rthEV, cd_, f_rungLbl(p, medD, cumD), "dn", colD, sty, wid, tEnd)')
    A('')
    A('// ── London / Asia anchors ───────────────────────────────────────────')
    A('if ldnStart')
    A('    f_clearLn(lnLDN)')
    A('    f_clearLb(lbLDN)')
    A('    ldnDrawn := false')
    A('    ldnOpen := open')
    A('    ldnEV   := open * vixPrev / math.sqrt(252) / 100.0')
    A('if asiStart')
    A('    f_clearLn(lnASA)')
    A('    f_clearLb(lbASA)')
    A('    asiDrawn := false')
    A('    asiOpen := open')
    A('    asiEV   := open * vixPrev / math.sqrt(252) / 100.0')
    A('')
    A('// draw London 35/25 rungs ONCE per session (at the anchor bar)')
    A('if showLondon and ldnStart and not na(ldnEV) and ldnEV > 0')
    A('    int tEndL = timestamp(NY_TZ, year(time, NY_TZ), month(time, NY_TZ), dayofmonth(time, NY_TZ), 9, 30)')
    A('    for j = 3 to 4')
    A('        float p = array.get(PROBS, j)')
    A('        float lvlU = ldnOpen + ldnEV * array.get(cUpLDN, j)')
    A('        float lvlD = ldnOpen - ldnEV * array.get(cDnLDN, j)')
    A('        array.push(lnLDN, line.new(time, lvlU, tEndL, lvlU, xloc = xloc.bar_time, color = color.new(#5d8aa8, 30), style = line.style_dashed))')
    A('        array.push(lbLDN, label.new(tEndL, lvlU, "LDN " + str.tostring(p * 100, "#") + "%", xloc = xloc.bar_time, style = label.style_label_left, color = color.new(color.white, 100), textcolor = #5d8aa8, size = size.tiny))')
    A('        array.push(lnLDN, line.new(time, lvlD, tEndL, lvlD, xloc = xloc.bar_time, color = color.new(#5d8aa8, 30), style = line.style_dashed))')
    A('        array.push(lbLDN, label.new(tEndL, lvlD, "LDN " + str.tostring(p * 100, "#") + "%", xloc = xloc.bar_time, style = label.style_label_left, color = color.new(color.white, 100), textcolor = #5d8aa8, size = size.tiny))')
    A('    ldnDrawn := true')
    A('')
    A('// draw Asia 35/25 rungs ONCE per session (NOMINAL — distance indicative).')
    A('// Asia opens 18:00 ET and runs to 03:00 the NEXT calendar day; building')
    A('// the end timestamp from (anchor date + 1 day) handles month rollovers.')
    A('if showAsia and asiStart and not na(asiEV) and asiEV > 0')
    A('    int tEndA = timestamp(NY_TZ, year(time, NY_TZ), month(time, NY_TZ), dayofmonth(time, NY_TZ), 18, 0) + 9 * 3600000')
    A('    for j = 3 to 4')
    A('        float p = array.get(PROBS, j)')
    A('        float lvlU = asiOpen + asiEV * array.get(cUpASA, j)')
    A('        float lvlD = asiOpen - asiEV * array.get(cDnASA, j)')
    A('        array.push(lnASA, line.new(time, lvlU, tEndA, lvlU, xloc = xloc.bar_time, color = color.new(#cddc39, 45), style = line.style_dotted))')
    A('        array.push(lbASA, label.new(tEndA, lvlU, "ASIA* " + str.tostring(p * 100, "#") + "%", xloc = xloc.bar_time, style = label.style_label_left, color = color.new(color.white, 100), textcolor = #cddc39, size = size.tiny))')
    A('        array.push(lnASA, line.new(time, lvlD, tEndA, lvlD, xloc = xloc.bar_time, color = color.new(#cddc39, 45), style = line.style_dotted))')
    A('        array.push(lbASA, label.new(tEndA, lvlD, "ASIA* " + str.tostring(p * 100, "#") + "%", xloc = xloc.bar_time, style = label.style_label_left, color = color.new(color.white, 100), textcolor = #cddc39, size = size.tiny))')
    A('    asiDrawn := true')
    A('')
    A('// ── dashboard ────────────────────────────────────────────────────────')
    A('var table tbl = na')
    A('if showTable and barstate.islast')
    A('    if not na(tbl)')
    A('        table.delete(tbl)')
    A('    tbl := table.new(f_pos(tblPos), 7, 20, bgcolor = color.new(color.black, 30), border_color = color.new(color.gray, 70), frame_color = color.new(color.gray, 50), frame_width = 1)')
    A('    int row = 0')
    A('    table.cell(tbl, 0, row, "EV STACK · " + syminfo.ticker + " · " + str.format_time(time, "EEE HH:mm", NY_TZ), text_color = color.white, text_size = f_tsz(tblSizeIn))')
    A('    table.merge_cells(tbl, 0, row, 6, row)')
    A('    row += 1')
    A('    string evS = na(rthEV) or rthEV <= 0 ? "—" : str.tostring(rthEV, format.mintick)')
    A('    table.cell(tbl, 0, row, "VIX " + (na(vixPrev) ? "—" : str.tostring(vixPrev, "#.##")) + " → EV " + evS + " pts" + (dowAdjust ? " · dow-adj" : ""), text_color = color.silver, text_size = f_tsz(tblSizeIn))')
    A('    table.merge_cells(tbl, 0, row, 6, row)')
    A('    row += 1')
    A('    string[] hdr = array.from("rung", "med arr", "by 11", "by 13:30", "by 15", "die@", "back@")')
    A('    for c = 0 to 6')
    A('        table.cell(tbl, c, row, array.get(hdr, c), text_color = color.gray, text_size = f_tsz(tblSizeIn))')
    A('    row += 1')
    A('    if array.size(arrIdx) > 0')
    A('        for ai = 0 to array.size(arrIdx) - 1')
    A('            int j = array.get(arrIdx, ai)')
    A('            float p = array.get(PROBS, j)')
    A('            string side = array.get(arrSide, ai)')
    A('            string medS = f_med2clock(array.get(arrMed, ai))')
    A('            string c11 = str.tostring(array.get(arrCum, ai * 5 + 1), "#.#") + "%"')
    A('            string c1330 = str.tostring(array.get(arrCum, ai * 5 + 3), "#.#") + "%"')
    A('            string c15 = str.tostring(array.get(arrCum, ai * 5 + 4), "#.#") + "%"')
    A('            string dieS = "—"')
    A('            string backS = "—"')
    A('            if array.size(revIdx) > 0')
    A('                for ri = 0 to array.size(revIdx) - 1')
    A('                    if array.get(revIdx, ri) == j and array.get(revSide, ri) == side')
    A('                        dieS := str.tostring(array.get(revRate, ri * 2), "#") + "%"')
    A('                        backS := str.tostring(array.get(revRate, ri * 2 + 1), "#") + "%"')
    A('            color tc = side == "up" ? #26a69a : #ef5350')
    A('            table.cell(tbl, 0, row, str.tostring(p * 100, "#") + "% " + (side == "up" ? "▲" : "▼"), text_color = tc, text_size = f_tsz(tblSizeIn))')
    A('            table.cell(tbl, 1, row, medS,  text_color = color.white, text_size = f_tsz(tblSizeIn))')
    A('            table.cell(tbl, 2, row, c11,   text_color = color.white, text_size = f_tsz(tblSizeIn))')
    A('            table.cell(tbl, 3, row, c1330, text_color = color.white, text_size = f_tsz(tblSizeIn))')
    A('            table.cell(tbl, 4, row, c15,   text_color = color.white, text_size = f_tsz(tblSizeIn))')
    A('            table.cell(tbl, 5, row, dieS, text_color = color.white, text_size = f_tsz(tblSizeIn))')
    A('            table.cell(tbl, 6, row, backS, text_color = color.white, text_size = f_tsz(tblSizeIn))')
    A('            row += 1')
    A(f'    table.cell(tbl, 0, row, "NY CAL · LONDON {verd["LONDON"]} · ASIA {verd["ASIA"]}", text_color = color.silver, text_size = f_tsz(tblSizeIn))')
    A('    table.merge_cells(tbl, 0, row, 6, row)')
    A('    row += 1')
    A('    table.cell(tbl, 0, row, "historical probabilities · not a signal", text_color = color.gray, text_size = f_tsz(tblSizeIn))')
    A('    table.merge_cells(tbl, 0, row, 6, row)')
    A("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ticker", default=None,
                    help="generate one ticker (default: all with artifacts)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    from pathlib import Path
    tickers = [args.ticker] if args.ticker else list(TICKERS)
    for t in tickers:
        try:
            code = generate(t)
        except FileNotFoundError as e:
            print(f"  skip {t}: missing artifact ({e}) — run the studies first")
            continue
        except KeyError as e:
            print(f"  skip {t}: artifact missing key {e} — run the studies first")
            continue
        out = args.out or \
            f"scripts/indicators-pine/expected-volatility/ev_session_stack_{t}.pine"
        p = Path(out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(code, encoding="utf-8")
        print(f"wrote {p}  ({len(code.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())