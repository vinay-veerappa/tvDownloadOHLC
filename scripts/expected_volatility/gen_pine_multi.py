"""Generate ONE multi-symbol EV Session Stack Pine indicator.

`gen_pine.py` emits one file per ticker. This module packs all tickers into a
single `ev_session_stack.pine`: every per-symbol data object becomes a flat
array with a fixed stride, and the chart symbol is resolved at runtime to a
slot (ES->0, NQ->1, YM->2, RTY->3, GC->4) that indexes those arrays. One file
covers every supported symbol; adding one = run its studies, add it to
TICKERS, regenerate.

Slot order in TICKERS is the contract between this generator and the emitted
Pine: SYM prefixes, VOLS, VERDICTS and every packed block use it.

Packing layout (documented identically in the emitted header comments):

    cUpRTH/cDnRTH/cUpLDN/...   [slot*8 + rung]              5x8 floats
    wUpDOW/wDnDOW              [slot*5 + dow]               5x5 floats
    arrMed                      [slot*10 + row]              5x10 ints
    arrCum                      [slot*50 + row*5 + ms]       5x10x5 floats
    revExt                      [slot*24 + row*3 + k]        5x8x3 floats
    revRate                     [slot*16 + row*2 + k]         5x8x2 floats

arrival rows (both folds' priority rungs, TARGET_P order): 35up,35dn,25up,
25dn,15up,15dn,10up,10dn,5up,5dn. Zone rows: same minus the 5% rung (die@zone
is undefined there — its artifact 0.0 is a measurement artifact, not a stat).

Pine hazards this emit deliberately avoids (all bit us before):
comma-declarations; `array.from(...)[i]` indexing; untyped `line` style vars;
float minutes reaching str.format_time (CE10123); per-bar redraw loops;
calendar-date+1 month overflow; `table.delete(na)`; and non-short-circuit
ternaries indexing with slot=-1 — resolved via slotSafe = math.max(slot, 0).

Usage
-----
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.gen_pine_multi
"""

from __future__ import annotations

import argparse
import json

from .features import OUT_DIR, TARGET_P, VOL_FOR_TICKER

# slot order is the contract: SYM prefixes, VOLS, VERDICTS, all packed blocks
TICKERS = ("ES1", "NQ1", "YM1", "RTY1", "GC1")
SYM_PREFIX = {"ES1": "ES", "NQ1": "NQ", "YM1": "YM", "RTY1": "RTY", "GC1": "GC"}
# Every chart symbol that maps to a family slot: big futures, micros, cash
# indexes and unlevered ETFs. EV-unit constants are scale-invariant (EV is
# recomputed from the chart symbol's own open), so mapping is all that is
# needed. LEVERAGED ETFs (SPXL/UPRO/TQQQ/SQQQ/UDOW...) are deliberately NOT
# mapped: their 2-3x daily-reset amplification breaks the EV structure and
# would misstate probabilities — they render as unsupported instead.
FAMILY = {
    "ES1":  ("ES", "MES", "SPX", "SPY", "XSP", "VOO"),
    "NQ1":  ("NQ", "MNQ", "NDX", "QQQ"),
    "YM1":  ("YM", "MYM", "DJI", "DIA", "DJ"),
    "RTY1": ("RTY", "RUT", "M2K", "IWM"),
    "GC1":  ("GC", "MGC", "XAU", "GLD"),
}
PRIORITY = (0.35, 0.25, 0.15, 0.10, 0.05)
MILESTONES = ("10:00", "11:00", "12:00", "13:30", "15:00")
# arrival rows per symbol: ALL 8 rungs x 2 sides = 16 (inner rungs included —
# the trader's question 'where does price tend to stay' needs their timing);
# zone rows per symbol: priority rungs only (35..10), 8 rows (5% die@ undefined)
NAROW, NREV = 16, 8


def _jload(name):
    p = OUT_DIR / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _arr(vals, nd=4):
    return "array.from(" + ", ".join(f"{v:.{nd}f}" for v in vals) + ")"


def _arr_rows(arr) -> list:
    """ALL 8 rungs x 2 sides in fixed index order (see constants docstring).

    Inner rungs (80/65/50) carry the timing a trader needs most — the 80%
    rung's median arrival is ~09:45, the open drive. Order: for each rung,
    up then dn, matching TARGET_P.
    """
    rows = []
    by_key = {(g["target_p"], g["side"]): g for g in (arr["rungs"] if arr else [])}
    for p in TARGET_P:
        for side in ("up", "dn"):
            g = by_key.get((p, side))
            f = g["train"] if g else None
            rows.append({"p": p, "side": side,
                         "med": (f["hit_med_min"] if f and f["hit_med_min"] is not None else -1),
                         "cum": ([f["milestones"][m]["cum"] for m in MILESTONES]
                                 if f else [0.0] * len(MILESTONES))})
    return rows


def _sess_arr_rows(rec) -> list:
    """Per-session arrival rows from session_timing: same rung-major layout
    returned by `_arr_rows`, uniform dict shape regardless of source."""
    return [{"p": r["p"], "side": r["side"], "med": int(r["med"]),
             "cum": r["cum"]} for r in rec]


def _rev_rows(rev) -> list:
    rows = []
    for c in (rev["cells"] if rev else []):
        if c["fold"] != "train" or c["rung"] not in PRIORITY or c["n_hits"] < 30:
            continue
        if c["rung"] == 0.05:
            continue  # die@zone undefined for the outermost rung
        rows.append(c)
    return rows


def _sess_rev_rows(rec) -> list:
    """Per-session reversal rows from session_timing: same fixed order as
    `_rev_rows` (35up,35dn,25up,25dn,15up,15dn,10up,10dn), gated to n>=30,
    padded with sentinels so the flat pack keeps its stride."""
    rows = []
    for r in rec:
        ok = r["n_hits"] >= 30 and r["rung"] in PRIORITY
        rows.append(r if ok else {"ext_p50": None, "ext_p75": None,
                                  "ext_p90": None, "die_pct": None,
                                  "back_pct": None})
    while len(rows) < NREV:
        rows.append({"ext_p50": None, "ext_p75": None, "ext_p90": None,
                     "die_pct": None, "back_pct": None})
    return rows[:NREV]


def generate() -> str:
    ladders, wups, wdns, med, cum, ext, rate = [], [], [], [], [], [], []
    lonU, lonD, asiU, asiD = [], [], [], []
    ldnM, asiM, lonC, asiC = [], [], [], []   # per-session arrival blocks
    ldnE, asiE, ldnR, asiR = [], [], [], []   # per-session reversal blocks
    ldn_verd, asi_verd, vols = [], [], []
    PAD = {"ext_p50": None, "ext_p75": None, "ext_p90": None,
           "die_pct": None, "back_pct": None}
    for t in TICKERS:
        arr = _jload(f"arrival_{t}_RTH.json")
        rev = _jload(f"reversal_{t}_RTH.json")
        dow = _jload(f"dow_multipliers_{t}_RTH.json")
        stk = _jload(f"sessions_stack_{t}.json")
        st = _jload(f"session_timing_{t}.json")
        if arr is None or dow is None or stk is None or st is None:
            raise FileNotFoundError(
                f"{t}: missing artifacts — run the studies first "
                "(incl. session_timing)")
        ladders.append(([g["c"] for g in arr["rungs"] if g["side"] == "up"],
                        [g["c"] for g in arr["rungs"] if g["side"] == "dn"]))
        wups += [r["w_up"] for r in dow["days"]]
        wdns += [r["w_dn"] for r in dow["days"]]
        arows = _arr_rows(arr)
        assert len(arows) == NAROW, f"{t}: {len(arows)} arrival rows"
        med += [int(r["med"]) for r in arows]
        cum += [c * 100 for r in arows for c in r["cum"]]
        # per-session arrival: same 16-row rung-major layout; minutes are
        # session-local (from each session's own open, clock rendered in Pine)
        for kind, medl, cuml in (("LONDON", ldnM, lonC), ("ASIA", asiM, asiC)):
            rows = _sess_arr_rows(st["sessions"][kind]["arrival"])
            assert len(rows) == NAROW, f"{t} {kind}: {len(rows)} arrival rows"
            medl += [int(r["med"]) for r in rows]
            cuml += [c * 100 for r in rows for c in r["cum"]]
        # per-session reversal/extension zones: same fixed row order as RTH,
        # n>=30 gated, padded — so the pack stride stays NREV for every session
        for kind, eL, rL in (("LONDON", ldnE, ldnR), ("ASIA", asiE, asiR)):
            rrows = _sess_rev_rows(st["sessions"][kind]["reversal"])
            eL += [v if v is not None else float("nan")
                   for r in rrows for v in (r["ext_p50"], r["ext_p75"], r["ext_p90"])]
            rL += [(v * 100 if v is not None else -1.0)
                   for r in rrows for v in (r["die_pct"], r["back_pct"])]
        rrows = _rev_rows(rev) if rev else []
        # fixed-stride packing needs identical row counts; pad short lists
        # with sentinels (ext NaN, rate -1) that the Pine renders as "—".
        while len(rrows) < NREV:
            rrows.append({"ext_p50": None, "ext_p75": None, "ext_p90": None,
                          "die_pct": None, "back_pct": None})
        rrows = rrows[:NREV]
        ext += [v if v is not None else float("nan")
                for r in rrows for v in (r["ext_p50"], r["ext_p75"], r["ext_p90"])]
        rate += [(v * 100 if v is not None else -1.0)
                 for r in rrows for v in (r["die_pct"], r["back_pct"])]
        lon = stk["sessions"]["LONDON"]["pooled"]
        asi = stk["sessions"]["ASIA"]["pooled"]
        lonU += lon["ladder_up"]; lonD += lon["ladder_dn"]
        asiU += asi["ladder_up"]; asiD += asi["ladder_dn"]
        ldn_verd.append({"calibrated": "CAL", "nominal": "NOMINAL"}.get(
            lon.get("verdict"), "REFIT"))
        asi_verd.append({"calibrated": "CAL", "nominal": "NOMINAL"}.get(
            asi.get("verdict"), "REFIT"))
        vols.append(f"CBOE:{VOL_FOR_TICKER[t]}")
    cUp = [v for pair in ladders for v in pair[0]]
    cDn = [v for pair in ladders for v in pair[1]]

    L: list[str] = []
    A = L.append
    A("// ─────────────────────────────────────────────────────────────────────")
    A("//  EV Session Stack — probability·distance·time map (GENERATED)")
    A("//  ONE indicator, multi-symbol: ES / NQ / YM / RTY / GC.")
    A("//  Source of truth: scripts/expected_volatility/ + RESEARCH_REPORT.md")
    A("//  DO NOT hand-edit the data blocks — regenerate with gen_pine_multi.py.")
    A("//")
    A("//  Per-symbol holdout verdicts (rendered in the dashboard footer):")
    A(f"//  " + " | ".join(
        f"{SYM_PREFIX[t]}: London {ldn_verd[i]}, Asia {asi_verd[i]}"
        for i, t in enumerate(TICKERS)))
    A("//  London draws ONLY where CAL (ES/NQ); REFIT sessions stay blank rather")
    A("//  than render drifted levels. Historical probabilities — a description")
    A("//  of past sessions, NOT a forecast, and NOT an entry signal (§3.1/§3.2).")
    A("// ─────────────────────────────────────────────────────────────────────")
    A("//@version=6")
    A('indicator("EV Session Stack", "EV-Stack", overlay = true,')
    A("     max_lines_count = 500, max_labels_count = 500, max_boxes_count = 100)")
    A("")
    A("// ── inputs ──────────────────────────────────────────────────────────")
    A('grpS = "Sessions"')
    A('showRTH    = input.bool(true, "NY (RTH) — CALIBRATED",              group = grpS)')
    A('showLondon = input.bool(true, "London 03:00-09:30 (draws only where CAL)", group = grpS)')
    A('showAsia   = input.bool(true, "Asia 18:00-03:00 — NOMINAL (indicative)", group = grpS)')
    A('grpL = "Rungs"')
    A('showInner  = input.bool(true,  "Inner rungs 80/65/50 (session frame)", group = grpL)')
    A('showWork   = input.bool(true,  "Work rungs 35/25 (primary)",        group = grpL)')
    A('showTails  = input.bool(true,  "Tail rungs 15/10/5 (dotted)",       group = grpL)')
    A('dowAdjust  = input.bool(true,  "Weekday width adjustment (§4.9)",   group = grpL)')
    A('grpT = "Table"')
    A('showTable  = input.bool(true,  "Show dashboard",                     group = grpT)')
    A('tblPos     = input.string("Top Right", "Position", options = ["Top Right","Top Left","Bottom Right","Bottom Left"], group = grpT)')
    A('tblSizeIn  = input.string("Small", "Size", options = ["Tiny","Small","Normal"], group = grpT)')
    A('grpZ = "Zones (behind 35% rung)"')
    A('showZones  = input.bool(true, "Extension zones",                     group = grpZ)')
    A('zoneLbls   = input.bool(true, "Zone labels",                         group = grpZ)')
    A("")
    A("// ── DATA — per-symbol packed blocks; slot order is the contract ─────")
    A(f"// slots: " + ", ".join(f"{i}={SYM_PREFIX[t]}" for i, t in enumerate(TICKERS)))
    A("// rung probabilities in TARGET_P order (index-matched to the ladders)")
    A("var array<float> PROBS = array.from(0.80, 0.65, 0.50, 0.35, 0.25, 0.15, 0.10, 0.05)")
    A("// RTH ladders: [slot*8 + rung] (paths.py train fit, holdout-validated)")
    A(f"var array<float> cUpRTH = {_arr(cUp)}")
    A(f"var array<float> cDnRTH = {_arr(cDn)}")
    A("// weekday multipliers Mon..Fri: [slot*5 + dow] (seasonality.py §4.9)")
    A(f"var array<float> wUpDOW = {_arr(wups)}")
    A(f"var array<float> wDnDOW = {_arr(wdns)}")
    A("// London/Asia ladders: [slot*8 + rung] (sessions_stack.py)")
    A(f"var array<float> cUpLDN = {_arr(lonU)}")
    A(f"var array<float> cDnLDN = {_arr(lonD)}")
    A(f"var array<float> cUpASA = {_arr(asiU)}")
    A(f"var array<float> cDnASA = {_arr(asiD)}")
    A("// arrival §5.4 TRAIN fold, RTH: 16 rows/symbol; med [slot*16 + row];")
    A(f"// arrCum [slot*{NAROW*5} + row*5 + ms], ms = 10:00/11:00/12:00/13:30/15:00.")
    A("var array<int>   arrMed = array.from(" + ", ".join(str(v) for v in med) + ")")
    A("var array<float> arrCum = array.from(" + ", ".join(f"{v:.1f}" for v in cum) + ")")
    A(f"// per-session arrival (session_timing.py, TRAIN fold): LONDON 16 rows")
    A(f"// med [slot*{NAROW} + row], cum [slot*{NAROW*5} + row*5 + ms]; milestones")
    A("// London 04:00/05:30/07:00/08:30/09:30 — Asia 20:00/22:00/00:00/02:00/03:00.")
    A("// Minutes are SESSION-LOCAL (from each session's own open). Asia = NOMINAL,")
    A("// indicative only.")
    A(f"var array<int>   ldnMed = array.from(" + ", ".join(str(v) for v in ldnM) + ")")
    A(f"var array<float> ldnCum = array.from(" + ", ".join(f"{v:.1f}" for v in lonC) + ")")
    A(f"var array<int>   asiMed = array.from(" + ", ".join(str(v) for v in asiM) + ")")
    A(f"var array<float> asiCum = array.from(" + ", ".join(f"{v:.1f}" for v in asiC) + ")")
    A(f"// per-session reversal/extension zones (session_timing.py, TRAIN, n>=30):")
    A(f"// same row order as RTH zones (35up,35dn,25up,...,10dn). ldnExt/asiExt")
    A(f"// [slot*{NREV*3} + row*3 + k]; ldnRate/asiRate [slot*{NREV*2} + row*2 + k]")
    A("// = die%, back%. Sentinel -1 renders as dash. Gates: LDN zones draw only")
    A("// where the session verdict is CAL (same rule as its ladder).")
    A(f"var array<float> ldnExt  = array.from(" + ", ".join(f"{v:.3f}" for v in ldnE) + ")")
    A(f"var array<float> ldnRate = array.from(" + ", ".join(f"{v:.1f}" for v in ldnR) + ")")
    A(f"var array<float> asiExt  = array.from(" + ", ".join(f"{v:.3f}" for v in asiE) + ")")
    A(f"var array<float> asiRate = array.from(" + ", ".join(f"{v:.1f}" for v in asiR) + ")")
    A(f"// zones §5.5 TRAIN fold n>=30: {NREV} rows/symbol (35..10, 5% excluded)")
    A(f"// die@zone undefined there. revExt [slot*{NREV*3} + row*3 + k];")
    A(f"// revRate [slot*{NREV*2} + row*2 + k] = die%, back%.")
    A("var array<float> revExt  = array.from(" + ", ".join(f"{v:.3f}" for v in ext) + ")")
    A("var array<float> revRate = array.from(" + ", ".join(f"{v:.1f}" for v in rate) + ")")
    A("// per-slot vol index (auto-selected by chart symbol) + session verdicts")
    A("var array<string> VOLS    = array.from(" + ", ".join(f'"{v}"' for v in vols) + ")")
    A("var array<string> LDNVERD = array.from(" + ", ".join(f'"{v}"' for v in ldn_verd) + ")")
    A("var array<string> ASIVERD = array.from(" + ", ".join(f'"{v}"' for v in asi_verd) + ")")
    A("")
    A("// ── symbol slot resolution ─────────────────────────────────────────")
    A("// Matches big futures, micros, CME codes, cash indexes and unlevered")
    A("// ETFs to their family slot (MES->ES, SPY/QQQ/DIA/IWM->index slots,")

    A("// XAU/GLD->GC). Leveraged ETFs are deliberately unsupported: a 3x")
    A("// daily-reset product changes the EV structure, and the family")
    A("// probabilities would be wrong on it. slotSafe keeps every array.get")
    A("// in bounds even on an unmatched symbol.")
    A("f_slot() =>")
    A("    string t = syminfo.ticker")
    A("    int s = -1")
    for i, t in enumerate(TICKERS):
        kw = "if" if i == 0 else "else if"
        prefixes = FAMILY[t]
        conds = " or ".join(f'str.startswith(t, "{p}")' for p in prefixes)
        A(f"    {kw} {conds}")
        A(f"        s := {i}")
    A("    s")
    A("")
    A("int slot = f_slot()")
    A("bool supported = slot >= 0")
    A("int slotSafe = math.max(slot, 0)")
    A('string volSym = array.get(VOLS, slotSafe)')
    A("string ldnVerd = array.get(LDNVERD, slotSafe)")
    A("string asiVerd = array.get(ASIVERD, slotSafe)")
    A('bool ldnOn = showLondon and supported and ldnVerd == "CAL"')
    A("bool asiOn = showAsia and supported")
    A("")
    A("// ── helpers ─────────────────────────────────────────────────────────")
    A('NY_TZ = "America/New_York"')
    A("// median first-touch minute from the 09:30 open -> ET wall clock.")
    A("// m is INT (arrMed is array<int>): keeps timestamp()+m*60000 a series")
    A("// int — str.format_time requires int (CE10123 otherwise).")
    A("f_med2clock(int m) =>")
    A('    m < 0 ? "—" : str.format_time(timestamp(NY_TZ, year(time, NY_TZ), month(time, NY_TZ), dayofmonth(time, NY_TZ), 9, 30) + m * 60000, "HH:mm", NY_TZ)')
    A("")
    A("// session-local clock: LONDON anchored 03:00, ASIA anchored 18:00")
    A("f_med2clockS(string kind, int m) =>")
    A('    int hh = kind == "LONDON" ? 3 : 18')
    A('    m < 0 ? "—" : str.format_time(timestamp(NY_TZ, year(time, NY_TZ), month(time, NY_TZ), dayofmonth(time, NY_TZ), hh, 0) + m * 60000, "HH:mm", NY_TZ)')
    A("")
    A('f_pos(s) =>')
    A('    s == "Top Left" ? position.top_left : s == "Bottom Right" ? position.bottom_right : s == "Bottom Left" ? position.bottom_left : position.top_right')
    A("")
    A('f_tsz(s) => s == "Tiny" ? size.tiny : s == "Normal" ? size.normal : size.small')
    A("")
    A("f_clearLn(arr) =>")
    A("    if array.size(arr) > 0")
    A("        for i = 0 to array.size(arr) - 1")
    A("            line.delete(array.get(arr, i))")
    A("    array.clear(arr)")
    A("")
    A("f_clearLb(arr) =>")
    A("    if array.size(arr) > 0")
    A("        for i = 0 to array.size(arr) - 1")
    A("            label.delete(array.get(arr, i))")
    A("    array.clear(arr)")
    A("")
    A("f_clearBx(arr) =>")
    A("    if array.size(arr) > 0")
    A("        for i = 0 to array.size(arr) - 1")
    A("            box.delete(array.get(arr, i))")
    A("    array.clear(arr)")
    A("")
    A("// label text: P(touch) · median arrival · cum (clock anchored per session)")
    A("// NOTE: composed from locals — expression continuations at 4-space indent")
    A("// parse as new statements in Pine v6 (server CE: 'Syntax error at input').")
    A("f_rungLbl(float p, int med, float cum15) =>")
    A('    string sP = str.tostring(p * 100, "#") + "%"')
    A('    string sM = med >= 0 ? " · med " + f_med2clock(med) : ""')
    A('    string sC = cum15 >= 0 ? " · " + str.tostring(cum15, "#.#") + "%" : ""')
    A("    sP + sM + sC")
    A("")
    A("// session-anchored variant: anchorHH 3 (London), 18 (Asia)")
    A("f_rungLblT(float p, int med, float cum15, int anchorHH) =>")
    A('    string sP = str.tostring(p * 100, "#") + "%"')
    A('    string medTxt = str.format_time(timestamp(NY_TZ, year(time, NY_TZ), month(time, NY_TZ), dayofmonth(time, NY_TZ), anchorHH, 0) + med * 60000, "HH:mm", NY_TZ)')
    A('    string sM = med >= 0 ? " · med " + medTxt : ""')
    A('    string sC = cum15 >= 0 ? " · " + str.tostring(cum15, "#.#") + "%" : ""')
    A("    sP + sM + sC")
    A("")
    A("// ── state ───────────────────────────────────────────────────────────")
    A("var array<line>  lnRTH  = array.new<line>()")
    A("var array<label> lbRTH  = array.new<label>()")
    A("var array<box>   zbxRTH = array.new<box>()")
    A("var array<label> zlbRTH = array.new<label>()")
    A("var array<line>  lnLDN  = array.new<line>()")
    A("var array<label> lbLDN  = array.new<label>()")
    A("var array<box>   zbxLDN = array.new<box>()")
    A("var array<label> zlbLDN = array.new<label>()")
    A("var array<line>  lnASA  = array.new<line>()")
    A("var array<label> lbASA  = array.new<label>()")
    A("var array<box>   zbxASA = array.new<box>()")
    A("var array<label> zlbASA = array.new<label>()")
    A("var float rthOpen = na")
    A("var float ldnOpen = na")
    A("var float asiOpen = na")
    A("var float rthEV   = na")
    A("var float ldnEV   = na")
    A("var float asiEV   = na")
    A("")
    A("// ── runtime reads ───────────────────────────────────────────────────")
    A('vixPrev = request.security(volSym, "1D", close[1], lookahead = barmerge.lookahead_off)')
    A("int nyHour = hour(time, NY_TZ)")
    A("int nyMin  = minute(time, NY_TZ)")
    A("int nyDow  = dayofweek(time, NY_TZ)")
    A("bool inRTH    = (nyHour == 9 and nyMin >= 30) or (nyHour >= 10 and nyHour < 16)")
    A("bool inLondon = nyHour >= 3 and nyHour < 9")
    A("bool inAsia   = nyHour >= 18 or nyHour < 3")
    A("bool rthStart = inRTH and not inRTH[1]")
    A("bool ldnStart = inLondon and not inLondon[1]")
    A("bool asiStart = inAsia and not inAsia[1]")
    A("")
    A("// tEnd for the NY session (today 16:00 ET)")
    A("f_tEndRTH() => timestamp(NY_TZ, year(time, NY_TZ), month(time, NY_TZ), dayofmonth(time, NY_TZ), 16, 0)")
    A("")
    A("// ── drawing primitives ──────────────────────────────────────────────")
    A("// one rung: line + probability label; returns the level")
    A("f_rung(S, EV, c, pTxt, side, col, sty, wid, tEnd) =>")
    A('    float lvl = side == "up" ? S + EV * c : S - EV * c')
    A("    array.push(lnRTH, line.new(time, lvl, tEnd, lvl, xloc = xloc.bar_time, color = col, style = sty, width = wid))")
    A("    array.push(lbRTH, label.new(tEnd, lvl, pTxt, xloc = xloc.bar_time, style = label.style_label_left, color = color.new(color.white, 100), textcolor = col, size = size.tiny))")
    A("    lvl")
    A("")
    A("// the session anchor: THE reference every rung of that session is")
    A("// measured from. Solid bright line, session-colored, price in label.")
    A("f_anchor(pArr, pLbl, S, col, tEnd, tag) =>")
    A("    array.push(pArr, line.new(time, S, tEnd, S, xloc = xloc.bar_time, color = col, style = line.style_solid, width = 3))")
    A('    array.push(pLbl, label.new(tEnd, S, tag + " OPEN " + str.tostring(S, format.mintick), xloc = xloc.bar_time, style = label.style_label_left, color = color.new(col, 25), textcolor = color.white, size = size.tiny))')
    A("")
    A("// extension zones behind a rung (TYPICAL/DEEP/STRETCH), one side.")
    A("// Zone boxes go to the caller's array so every session shares this.")
    A("f_zone(bxArr, lbArr, S, EV, c, e50, e75, e90, isUp, tEnd) =>")
    A("    float sgn  = isUp ? 1.0 : -1.0")
    A("    float base = S + sgn * EV * c")
    A("    float z1 = base + sgn * EV * e50")
    A("    float z2 = base + sgn * EV * e75")
    A("    float z3 = base + sgn * EV * e90")
    A("    array.push(bxArr, box.new(time, math.max(base, z1), tEnd, math.min(base, z1), xloc = xloc.bar_time, bgcolor = color.new(#9e9e9e, 78), border_color = color.new(#9e9e9e, 45)))")
    A("    array.push(bxArr, box.new(time, math.max(z1, z2), tEnd, math.min(z1, z2), xloc = xloc.bar_time, bgcolor = color.new(#2196f3, 78), border_color = color.new(#2196f3, 45)))")
    A("    array.push(bxArr, box.new(time, math.max(z2, z3), tEnd, math.min(z2, z3), xloc = xloc.bar_time, bgcolor = color.new(#ff9800, 78), border_color = color.new(#ff9800, 45)))")
    A("    if zoneLbls")
    A('        array.push(lbArr, label.new(tEnd, (base + z1) / 2, "TYPICAL", xloc = xloc.bar_time, style = label.style_label_left, color = color.new(color.white, 100), textcolor = #9e9e9e, size = size.tiny))')
    A('        array.push(lbArr, label.new(tEnd, (z1 + z2) / 2, "DEEP",     xloc = xloc.bar_time, style = label.style_label_left, color = color.new(color.white, 100), textcolor = #2196f3, size = size.tiny))')
    A('        array.push(lbArr, label.new(tEnd, (z2 + z3) / 2, "STRETCH",  xloc = xloc.bar_time, style = label.style_label_left, color = color.new(color.white, 100), textcolor = #ff9800, size = size.tiny))')
    A("")
    A("// ── NY (RTH) session build ──────────────────────────────────────────")
    A("if rthStart and showRTH and supported")
    A("    f_clearLn(lnRTH)")
    A("    f_clearLb(lbRTH)")
    A("    f_clearBx(zbxRTH)")
    A("    f_clearLb(zlbRTH)")
    A("    rthOpen := open")
    A("    rthEV   := open * vixPrev / math.sqrt(252) / 100.0")
    A("    if not na(rthEV) and rthEV > 0")
    A("        int tEnd = f_tEndRTH()")
    A("        int dIdx = nyDow == dayofweek.monday ? 0 : nyDow == dayofweek.tuesday ? 1 : nyDow == dayofweek.wednesday ? 2 : nyDow == dayofweek.thursday ? 3 : 4")
    A("        int base8 = slot * 8")
    A("        int base5 = slot * 5")
    A(f"        int aBase = slot * {NAROW}")
    A(f"        int cBase = slot * {NAROW * 5}")
    A(f"        int eBase = slot * {NREV * 3}")
    A("        float wU = dowAdjust ? array.get(wUpDOW, base5 + dIdx) : 1.0")
    A("        float wD = dowAdjust ? array.get(wDnDOW, base5 + dIdx) : 1.0")
    A("        // zones behind the 35% rung: zone rows 0 (up) and 1 (dn)")
    A("        if showZones and showWork")
    A("            float c35u = array.get(cUpRTH, base8 + 3) * wU")
    A("            float c35d = array.get(cDnRTH, base8 + 3) * wD")
    A("            f_zone(zbxRTH, zlbRTH, rthOpen, rthEV, c35u, array.get(revExt, eBase + 0), array.get(revExt, eBase + 1), array.get(revExt, eBase + 2), true, tEnd)")
    A("            f_zone(zbxRTH, zlbRTH, rthOpen, rthEV, c35d, array.get(revExt, eBase + 3), array.get(revExt, eBase + 4), array.get(revExt, eBase + 5), false, tEnd)")
    A("        // rungs — EVERY rung now has an arrival row (16 rows = 8 rungs x 2),")
    A("        // so all labels carry median arrival + by-15:00 cumulative")
    A("        for j = 0 to 7")
    A("            bool inner = j <= 2")
    A("            bool work = j == 3 or j == 4")
    A("            bool tail = j >= 5")
    A("            bool want = (inner and showInner) or (work and showWork) or (tail and showTails)")
    A("            if want")
    A("                float p = array.get(PROBS, j)")
    A("                float cu = array.get(cUpRTH, base8 + j) * wU")
    A("                float cd_ = array.get(cDnRTH, base8 + j) * wD")
    A("                int aRow = j * 2")
    A("                int medU = array.get(arrMed, aBase + aRow)")
    A("                int medD = array.get(arrMed, aBase + aRow + 1)")
    A("                float cumU = array.get(arrCum, cBase + aRow * 5 + 4)")
    A("                float cumD = array.get(arrCum, cBase + (aRow + 1) * 5 + 4)")
    A("                color colU = inner ? #1b7f4b : work ? #0d5c33 : color.new(#0d5c33, 25)")
    A("                color colD = inner ? #b3341f : work ? #8f1f14 : color.new(#8f1f14, 25)")
    A("                int wid = work ? 2 : 1")
    A("                string sty = inner or tail ? line.style_dotted : line.style_solid")
    A('                f_rung(rthOpen, rthEV, cu, f_rungLbl(p, medU, cumU), "up", colU, sty, wid, tEnd)')
    A('                f_rung(rthOpen, rthEV, cd_, f_rungLbl(p, medD, cumD), "dn", colD, sty, wid, tEnd)')
    A("        // the anchor: where the whole ladder is measured from")
    A("        f_anchor(lnRTH, lbRTH, rthOpen, #1565c0, tEnd, \"RTH 09:30\")")
    A("        // the session frame: shade between the 80% rungs (up vs dn) —")
    A("        // the band ~80% of days live inside. This is the 'typical day'")
    A("        // zone a trader reads first; extension zones (35%+) are the tail.")
    A("        if showZones")
    A("            float p80u = array.get(cUpRTH, base8) * wU")
    A("            float p80d = array.get(cDnRTH, base8) * wD")
    A("            float frU = rthOpen + rthEV * p80u")
    A("            float frD = rthOpen - rthEV * p80d")
    A("            array.push(zbxRTH, box.new(time, frU, tEnd, frD, xloc = xloc.bar_time, bgcolor = color.new(#1565c0, 92), border_color = color.new(#1565c0, 30)))")
    A("")
    A("// ── London / Asia anchors ───────────────────────────────────────────")
    A("if ldnStart")
    A("    f_clearLn(lnLDN)")
    A("    f_clearLb(lbLDN)")
    A("    f_clearBx(zbxLDN)")
    A("    f_clearLb(zlbLDN)")
    A("    ldnOpen := open")
    A("    ldnEV   := open * vixPrev / math.sqrt(252) / 100.0")
    A("if asiStart")
    A("    f_clearLn(lnASA)")
    A("    f_clearLb(lbASA)")
    A("    f_clearBx(zbxASA)")
    A("    f_clearLb(zlbASA)")
    A("    asiOpen := open")
    A("    asiEV   := open * vixPrev / math.sqrt(252) / 100.0")
    A("")
    A("// draw London FULL ladder — only where CALIBRATED, with per-session timing")
    A("if ldnOn and ldnStart and not na(ldnEV) and ldnEV > 0")
    A("    int tEndL = timestamp(NY_TZ, year(time, NY_TZ), month(time, NY_TZ), dayofmonth(time, NY_TZ), 9, 30)")
    A("    int aBaseL = slot * 16")
    A("    int cBaseL = slot * 80")
    A(f"    int eBaseL = slot * {NREV * 3}")
    A("    f_anchor(lnLDN, lbLDN, ldnOpen, #5d8aa8, tEndL, \"LDN 03:00\")")
    A("    if showZones")
    A("        float p80uL = array.get(cUpLDN, slot * 8)")
    A("        float p80dL = array.get(cDnLDN, slot * 8)")
    A("        array.push(zbxLDN, box.new(time, ldnOpen + ldnEV * p80uL, tEndL, ldnOpen - ldnEV * p80dL, xloc = xloc.bar_time, bgcolor = color.new(#5d8aa8, 92), border_color = color.new(#5d8aa8, 30)))")
    A("    // extension zones behind the 35% rung (rows 0 up / 1 dn)")
    A("    if showZones and showWork")
    A("        float c35uL = array.get(cUpLDN, slot * 8 + 3)")
    A("        float c35dL = array.get(cDnLDN, slot * 8 + 3)")
    A("        f_zone(zbxLDN, zlbLDN, ldnOpen, ldnEV, c35uL, array.get(ldnExt, eBaseL + 0), array.get(ldnExt, eBaseL + 1), array.get(ldnExt, eBaseL + 2), true, tEndL)")
    A("        f_zone(zbxLDN, zlbLDN, ldnOpen, ldnEV, c35dL, array.get(ldnExt, eBaseL + 3), array.get(ldnExt, eBaseL + 4), array.get(ldnExt, eBaseL + 5), false, tEndL)")
    A("    for j = 0 to 7")
    A("        bool inner = j <= 2")
    A("        bool work = j == 3 or j == 4")
    A("        bool tail = j >= 5")
    A("        bool want = (inner and showInner) or (work and showWork) or (tail and showTails)")
    A("        if want")
    A("            float p = array.get(PROBS, j)")
    A("            int aRowL = j * 2")
    A("            int medU_L = array.get(ldnMed, aBaseL + aRowL)")
    A("            int medD_L = array.get(ldnMed, aBaseL + aRowL + 1)")
    A("            float cumU_L = array.get(ldnCum, cBaseL + aRowL * 5 + 4)")
    A("            float cumD_L = array.get(ldnCum, cBaseL + (aRowL + 1) * 5 + 4)")
    A("            float lvlU = ldnOpen + ldnEV * array.get(cUpLDN, slot * 8 + j)")
    A("            float lvlD = ldnOpen - ldnEV * array.get(cDnLDN, slot * 8 + j)")
    A("            color colU = inner ? #2e6da4 : work ? #2e6da4 : color.new(#2e6da4, 20)")
    A("            color colD = inner ? #a85643 : work ? #a85643 : color.new(#a85643, 25)")
    A("            int widL = work ? 2 : 1")
    A("            string styL = inner or tail ? line.style_dotted : line.style_dashed")
    A('            array.push(lnLDN, line.new(time, lvlU, tEndL, lvlU, xloc = xloc.bar_time, color = colU, style = styL, width = widL))')
    A('            array.push(lbLDN, label.new(tEndL, lvlU, "LDN " + f_rungLblT(p, medU_L, cumU_L, 3), xloc = xloc.bar_time, style = label.style_label_left, color = color.new(color.white, 100), textcolor = colU, size = size.tiny))')
    A('            array.push(lnLDN, line.new(time, lvlD, tEndL, lvlD, xloc = xloc.bar_time, color = colD, style = styL, width = widL))')
    A('            array.push(lbLDN, label.new(tEndL, lvlD, "LDN " + f_rungLblT(p, medD_L, cumD_L, 3), xloc = xloc.bar_time, style = label.style_label_left, color = color.new(color.white, 100), textcolor = colD, size = size.tiny))')
    A("")
    A("// draw Asia FULL ladder (NOMINAL — indicative), with per-session timing.")
    A("// Asia opens 18:00 ET, runs to 03:00 next day; anchor-18:00 + 9h avoids")
    A("// a calendar-date+1 that can overflow the month.")
    A("if asiOn and asiStart and not na(asiEV) and asiEV > 0")
    A("    int tEndA = timestamp(NY_TZ, year(time, NY_TZ), month(time, NY_TZ), dayofmonth(time, NY_TZ), 18, 0) + 9 * 3600000")
    A("    int aBaseA = slot * 16")
    A("    int cBaseA = slot * 80")
    A(f"    int eBaseA = slot * {NREV * 3}")
    A("    f_anchor(lnASA, lbASA, asiOpen, #7c7c1e, tEndA, \"ASIA 18:00\")")
    A("    if showZones")
    A("        float p80uA = array.get(cUpASA, slot * 8)")
    A("        float p80dA = array.get(cDnASA, slot * 8)")
    A("        array.push(zbxASA, box.new(time, asiOpen + asiEV * p80uA, tEndA, asiOpen - asiEV * p80dA, xloc = xloc.bar_time, bgcolor = color.new(#7c7c1e, 92), border_color = color.new(#7c7c1e, 30)))")
    A("    // extension zones behind the 35% rung (rows 0 up / 1 dn) — NOMINAL,")
    A("    // indicative only, per the Asia verdict")
    A("    if showZones and showWork")
    A("        float c35uA = array.get(cUpASA, slot * 8 + 3)")
    A("        float c35dA = array.get(cDnASA, slot * 8 + 3)")
    A("        f_zone(zbxASA, zlbASA, asiOpen, asiEV, c35uA, array.get(asiExt, eBaseA + 0), array.get(asiExt, eBaseA + 1), array.get(asiExt, eBaseA + 2), true, tEndA)")
    A("        f_zone(zbxASA, zlbASA, asiOpen, asiEV, c35dA, array.get(asiExt, eBaseA + 3), array.get(asiExt, eBaseA + 4), array.get(asiExt, eBaseA + 5), false, tEndA)")
    A("    for j = 0 to 7")
    A("        bool inner = j <= 2")
    A("        bool work = j == 3 or j == 4")
    A("        bool tail = j >= 5")
    A("        bool want = (inner and showInner) or (work and showWork) or (tail and showTails)")
    A("        if want")
    A("            float p = array.get(PROBS, j)")
    A("            int aRowA = j * 2")
    A("            int medU_A = array.get(asiMed, aBaseA + aRowA)")
    A("            int medD_A = array.get(asiMed, aBaseA + aRowA + 1)")
    A("            float cumU_A = array.get(asiCum, cBaseA + aRowA * 5 + 4)")
    A("            float cumD_A = array.get(asiCum, cBaseA + (aRowA + 1) * 5 + 4)")
    A("            color colU = inner ? #8d8a1e : work ? #6e6c14 : color.new(#6e6c1e, 20)")
    A("            color colD = inner ? #8d8a1e : work ? #6e6c1e : color.new(#6e6c1e, 20)")
    A("            int widA = work ? 2 : 1")
    A("            float lvlU = asiOpen + asiEV * array.get(cUpASA, slot * 8 + j)")
    A("            float lvlD = asiOpen - asiEV * array.get(cDnASA, slot * 8 + j)")
    A('            array.push(lnASA, line.new(time, lvlU, tEndA, lvlU, xloc = xloc.bar_time, color = colU, style = line.style_dotted, width = widA))')
    A('            array.push(lbASA, label.new(tEndA, lvlU, "ASIA* " + f_rungLblT(p, medU_A, cumU_A, 18), xloc = xloc.bar_time, style = label.style_label_left, color = color.new(color.white, 100), textcolor = colU, size = size.tiny))')
    A('            array.push(lnASA, line.new(time, lvlD, tEndA, lvlD, xloc = xloc.bar_time, color = colD, style = line.style_dotted, width = widA))')
    A('            array.push(lbASA, label.new(tEndA, lvlD, "ASIA* " + f_rungLblT(p, medD_A, cumD_A, 18), xloc = xloc.bar_time, style = label.style_label_left, color = color.new(color.white, 100), textcolor = colD, size = size.tiny))')
    A("")
    A("// ── dashboard ────────────────────────────────────────────────────────")
    A("var table tbl = na")
    A("if showTable and barstate.islast")
    A("    if not na(tbl)")
    A("        table.delete(tbl)")
    A(f'    // rows: 3 (title+VIX+header) + {NAROW} arrival rows + 2 (verdict+disclaimer)')
    A(f'    tbl := table.new(f_pos(tblPos), 7, {NAROW + 5}, bgcolor = color.new(color.black, 30), border_color = color.new(color.gray, 70), frame_color = color.new(color.gray, 50), frame_width = 1)')
    A("    if supported")
    A("        int row = 0")
    A('        table.cell(tbl, 0, row, "EV STACK · " + syminfo.ticker + " · " + str.format_time(time, "EEE HH:mm", NY_TZ), text_color = color.white, text_size = f_tsz(tblSizeIn))')
    A("        table.merge_cells(tbl, 0, row, 6, row)")
    A("        row += 1")
    A('        string evS = na(rthEV) or rthEV <= 0 ? "—" : str.tostring(rthEV, format.mintick)')
    A('        table.cell(tbl, 0, row, "VIX " + (na(vixPrev) ? "—" : str.tostring(vixPrev, "#.##")) + " → EV " + evS + " pts" + (dowAdjust ? " · dow-adj" : ""), text_color = color.silver, text_size = f_tsz(tblSizeIn))')
    A("        table.merge_cells(tbl, 0, row, 6, row)")
    A("        row += 1")
    A('        string[] hdr = array.from("rung", "med arr", "by 11", "by 13:30", "by 15", "die@", "back@")')
    A("        for c = 0 to 6")
    A("            table.cell(tbl, c, row, array.get(hdr, c), text_color = color.gray, text_size = f_tsz(tblSizeIn))")
    A("        row += 1")
    A(f"        // arrival rows: {NAROW} per symbol, rung-major (80up,80dn,65up,65dn,...,5dn)")
    A(f"        int aBase = slot * {NAROW}")
    A(f"        int cBase = slot * {NAROW * 5}")
    A(f"        int rBase = slot * {NREV * 2}")
    A(f"        for ai = 0 to {NAROW} - 1")
    A("            int j = ai / 2   // rung index 0..7, up then dn per rung")
    A('            string side = ai % 2 == 0 ? "up" : "dn"')
    A("            float p = array.get(PROBS, j)")
    A("            string medS = f_med2clock(array.get(arrMed, aBase + ai))")
    A('            string c11 = str.tostring(array.get(arrCum, cBase + ai * 5 + 1), "#.#") + "%"')
    A('            string c1330 = str.tostring(array.get(arrCum, cBase + ai * 5 + 3), "#.#") + "%"')
    A('            string c15 = str.tostring(array.get(arrCum, cBase + ai * 5 + 4), "#.#") + "%"')
    A('            // die/back: zone rows are priority rungs only (j 3..6); inner')
    A('            // (j<3) and the 5% tail (j==7) have no zone row — show dash.')
    A('            string dieS = "—"')
    A('            string backS = "—"')
    A("            if j >= 3 and j < 7")
    A("                int rr = (j - 3) * 2 + ai % 2")
    A('                float dv = array.get(revRate, rBase + rr * 2)')
    A('                float bv = array.get(revRate, rBase + rr * 2 + 1)')
    A('                if dv >= 0')
    A('                    dieS := str.tostring(dv, "#") + "%"')
    A('                if bv >= 0')
    A('                    backS := str.tostring(bv, "#") + "%"')
    A('            color tc = side == "up" ? #26a69a : #ef5350')
    A('            table.cell(tbl, 0, row, str.tostring(p * 100, "#") + "% " + (side == "up" ? "▲" : "▼"), text_color = tc, text_size = f_tsz(tblSizeIn))')
    A("            table.cell(tbl, 1, row, medS,  text_color = color.white, text_size = f_tsz(tblSizeIn))")
    A("            table.cell(tbl, 2, row, c11,   text_color = color.white, text_size = f_tsz(tblSizeIn))")
    A("            table.cell(tbl, 3, row, c1330, text_color = color.white, text_size = f_tsz(tblSizeIn))")
    A("            table.cell(tbl, 4, row, c15,   text_color = color.white, text_size = f_tsz(tblSizeIn))")
    A("            table.cell(tbl, 5, row, dieS, text_color = color.white, text_size = f_tsz(tblSizeIn))")
    A("            table.cell(tbl, 6, row, backS, text_color = color.white, text_size = f_tsz(tblSizeIn))")
    A("            row += 1")
    A('        table.cell(tbl, 0, row, "NY CAL · LONDON " + ldnVerd + " · ASIA " + asiVerd, text_color = color.silver, text_size = f_tsz(tblSizeIn))')
    A("        table.merge_cells(tbl, 0, row, 6, row)")
    A("        row += 1")
    A('        table.cell(tbl, 0, row, "historical probabilities · not a signal", text_color = color.gray, text_size = f_tsz(tblSizeIn))')
    A("        table.merge_cells(tbl, 0, row, 6, row)")
    A("    else")
    A('        table.cell(tbl, 0, 0, "EV Stack: unsupported symbol (ES/NQ/YM/RTY/GC)", text_color = color.orange, text_size = f_tsz(tblSizeIn))')
    A("        table.merge_cells(tbl, 0, 0, 6, 0)")
    A("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out",
                    default="scripts/indicators-pine/expected-volatility/ev_session_stack.pine")
    args = ap.parse_args(argv)

    from pathlib import Path
    code = generate()
    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(code, encoding="utf-8")
    print(f"wrote {p}  ({len(code.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())