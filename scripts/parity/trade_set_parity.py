r"""Trade-set parity: does Python take THE SAME TRADES as NT8?

WHY A NEW ONE. `scripts/validation/ib_parity_harness.py` is 960 lines welded to
one IB play, and its join is structurally unable to fail in the way that matters.
It matches each Python trade to the closest NT8 trade within +/-60s on the same
side, then reports agreement over the matched pairs. Consequences, measured on
its own corpus: it reported **97.9% agreement** while Python had actually found
only **47 of 73** NT8 trades, because 26 surplus NT8 re-entries had no Python
counterpart to be matched to and therefore never entered the denominator. A
tolerance join silently absorbs a surplus on either side.

97.9% was not wrong arithmetic. It was the answer to a different question:
*given the trades both engines took, do they agree?* The question that decides
whether a C# bot will behave like its Python screen is: *did they take the same
trades at all?*

WHAT THIS DOES DIFFERENTLY

1. The join key is `(entry bar, direction, occurrence)`. Not nearest-neighbour,
   not a tolerance window. Trades are bucketed by the BAR their entry falls in;
   within a bucket, occurrences are zipped in time order. A surplus on either
   side is therefore left unmatched BY CONSTRUCTION and lands in the report.

2. Three numbers are always reported together and none can be quoted alone:
     recall    = matched / len(nt8)     did Python FIND NT8's trades?
     precision = matched / len(python)  did Python INVENT trades?
     jaccard   = matched / (union)      the one number that penalises both
   `summary()` refuses to emit a single headline agreement figure. The old
   harness's 97.9% was precisely such a figure.

3. Matched pairs are then compared on entry price, exit price, exit reason and
   P&L, against tolerances the CALLER declares. A matched-pair agreement rate is
   meaningful only next to recall, so it is never returned without it.

4. Timezones are refused rather than guessed. NT8 Strategy Analyzer exports
   ET-naive timestamps; reading them as UTC shifts every trade by 4-5 hours,
   which a tolerance join partially hides and a bar join turns into total
   mismatch. Naive input requires an explicit `assume_tz`.

Run:
  .venv\Scripts\python.exe -m scripts.parity.trade_set_parity \
      --python trades_py.csv --nt8 trades_nt8.csv --bar-seconds 60
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

CANONICAL = ("entry_time", "exit_time", "direction", "entry_price",
             "exit_price", "pnl", "exit_reason")

# Column aliases seen in the wild. NT8 exports PascalCase or camelCase depending
# on the path (SA grid export vs the bridge's ExtractBacktest); the Python engines
# use snake_case and disagree with each other.
ALIASES: Dict[str, Sequence[str]] = {
    "entry_time": ("entry_time", "entryTime", "EntryTime", "Entry time",
                   "signal_time", "entry_dt"),
    "exit_time": ("exit_time", "exitTime", "ExitTime", "Exit time", "exit_dt"),
    "direction": ("direction", "side", "Side", "marketPosition",
                  "MarketPosition", "Market position"),
    "entry_price": ("entry_price", "entryPrice", "EntryPrice", "Entry price"),
    "exit_price": ("exit_price", "exitPrice", "ExitPrice", "Exit price"),
    "pnl": ("pnl", "PnL", "total_pnl_usd", "profitCurrency", "ProfitCurrency",
            "profit", "Profit"),
    "exit_reason": ("exit_reason", "exitName", "ExitName", "reason",
                    "Exit name", "exit_type"),
}

LONG_TOKENS = ("LONG", "BUY")
SHORT_TOKENS = ("SHORT", "SELL")


class ParityInputError(ValueError):
    """Raised when input cannot be interpreted without guessing."""


def _pick(df: pd.DataFrame, field: str) -> Optional[str]:
    for name in ALIASES[field]:
        if name in df.columns:
            return name
    return None


def normalise_direction(values: Iterable[Any]) -> pd.Series:
    """Map any of the many spellings onto 'long'/'short', refusing the rest.

    A direction that cannot be read must not silently become one of the two --
    getting it wrong makes every trade look like a mismatch on the other side,
    which reads as a parity failure rather than a parsing failure.
    """
    out = []
    for v in values:
        s = str(v).strip().upper()
        if any(t in s for t in LONG_TOKENS):
            out.append("long")
        elif any(t in s for t in SHORT_TOKENS):
            out.append("short")
        elif s in ("1", "1.0", "+1"):
            out.append("long")
        elif s in ("-1", "-1.0"):
            out.append("short")
        else:
            out.append(None)
    if any(o is None for o in out):
        bad = sorted({str(v) for v, o in zip(values, out) if o is None})[:8]
        raise ParityInputError(
            "unreadable direction value(s): {}. Recognised: long/buy/1, "
            "short/sell/-1 (case-insensitive, substring). Refusing to guess -- a "
            "wrong direction makes every trade mismatch and reads as a parity "
            "failure rather than a parsing one.".format(bad))
    return pd.Series(out, dtype="object")


def normalise_trades(df: pd.DataFrame, *, label: str,
                     assume_tz: Optional[str] = None) -> pd.DataFrame:
    """Map an arbitrary trade export onto the canonical schema.

    `assume_tz` is REQUIRED when entry timestamps are naive. NT8 Strategy
    Analyzer writes ET-naive timestamps and this repo's Python engines write
    tz-aware ET; reading the former as UTC shifts every trade 4-5 hours. That is
    a mistake a tolerance join half-absorbs and a bar join turns into a total
    mismatch, so it is refused here instead.
    """
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=list(CANONICAL) + ["entry_bar", "_src"])

    resolved: Dict[str, Any] = {}
    missing = []
    for field in CANONICAL:
        col = _pick(df, field)
        if col is None:
            if field in ("entry_time", "direction"):
                missing.append(field)
            resolved[field] = None
        else:
            resolved[field] = df[col]
    if missing:
        raise ParityInputError(
            "{}: cannot find {} in columns {}. These two are the JOIN KEY and "
            "have no substitute.".format(label, missing, list(df.columns)[:20]))

    out = pd.DataFrame(index=range(len(df)))
    et = pd.to_datetime(resolved["entry_time"].to_numpy(), errors="coerce")
    et = pd.DatetimeIndex(et)
    if et.isna().any():
        raise ParityInputError(
            "{}: {} entry timestamp(s) could not be parsed".format(
                label, int(et.isna().sum())))

    if et.tz is None:
        if not assume_tz:
            raise ParityInputError(
                "{}: entry timestamps are TIMEZONE-NAIVE and no --assume-tz was "
                "given. NT8 Strategy Analyzer exports ET-naive; interpreting "
                "them as UTC shifts every trade by 4-5 hours. State the zone "
                "rather than letting pandas pick one.".format(label))
        et = et.tz_localize(assume_tz, ambiguous="NaT", nonexistent="shift_forward")
        if et.isna().any():
            raise ParityInputError(
                "{}: {} entry timestamp(s) are ambiguous or nonexistent in {} "
                "(a DST transition)".format(label, int(et.isna().sum()), assume_tz))
    out["entry_time"] = et.tz_convert("UTC")

    xt = resolved["exit_time"]
    if xt is not None:
        xt_i = pd.DatetimeIndex(pd.to_datetime(xt.to_numpy(), errors="coerce"))
        if xt_i.tz is None and assume_tz:
            xt_i = xt_i.tz_localize(assume_tz, ambiguous="NaT",
                                    nonexistent="shift_forward")
        out["exit_time"] = (xt_i.tz_convert("UTC") if xt_i.tz is not None
                            else pd.NaT)
    else:
        out["exit_time"] = pd.NaT

    out["direction"] = normalise_direction(resolved["direction"].to_numpy()).values
    for f in ("entry_price", "exit_price", "pnl"):
        out[f] = (pd.to_numeric(resolved[f], errors="coerce").to_numpy()
                  if resolved[f] is not None else np.nan)
    out["exit_reason"] = (resolved["exit_reason"].astype(str).to_numpy()
                          if resolved["exit_reason"] is not None else "")
    out["_src"] = label
    return out.sort_values("entry_time").reset_index(drop=True)


def assign_bars(trades: pd.DataFrame, bar_seconds: int) -> pd.DataFrame:
    """Bucket each entry into the bar that contains it.

    Floor, not round: a trade at 09:31:59 belongs to the 09:31 bar, and rounding
    would push it into 09:32 and manufacture a mismatch against an engine that
    floors. `bar_seconds` must be DECLARED -- it cannot be inferred from a trade
    list, and inferring it from inter-trade gaps would be wrong on any strategy
    that trades less often than once a bar.
    """
    if bar_seconds <= 0:
        raise ParityInputError("bar_seconds must be positive")
    out = trades.copy()
    if out.empty:
        out["entry_bar"] = pd.Series(dtype="datetime64[ns, UTC]")
        return out
    out["entry_bar"] = out["entry_time"].dt.floor(f"{int(bar_seconds)}s")
    return out


def match_trade_sets(py: pd.DataFrame, nt8: pd.DataFrame,
                     bar_seconds: int) -> Dict[str, Any]:
    """Join on (entry_bar, direction, occurrence). Surplus stays unmatched.

    Within a (bar, direction) bucket both engines may legitimately have more than
    one trade -- NT8 re-entry inside a bar is real. Occurrences are zipped in
    time order and any excess on either side is reported. This is the property
    the tolerance join lacked: there is no way for an extra NT8 trade to be
    quietly paired with a Python trade that already has a partner.
    """
    p = assign_bars(py, bar_seconds)
    n = assign_bars(nt8, bar_seconds)

    pairs: List[Dict[str, Any]] = []
    py_matched = set()
    nt8_matched = set()

    p_groups = p.groupby(["entry_bar", "direction"], sort=True).groups
    n_groups = n.groupby(["entry_bar", "direction"], sort=True).groups

    for key, p_idx in p_groups.items():
        if key not in n_groups:
            continue
        p_list = list(p_idx)
        n_list = list(n_groups[key])
        for pi, ni in zip(p_list, n_list):
            py_matched.add(pi)
            nt8_matched.add(ni)
            pairs.append({"py_i": pi, "nt8_i": ni,
                          "entry_bar": key[0], "direction": key[1]})

    py_only = [i for i in range(len(p)) if i not in py_matched]
    nt8_only = [i for i in range(len(n)) if i not in nt8_matched]

    return {"pairs": pairs, "py_only": py_only, "nt8_only": nt8_only,
            "py": p, "nt8": n, "bar_seconds": int(bar_seconds)}


def compare_matched(m: Dict[str, Any], *, price_tol: float = 0.25,
                    pnl_tol: float = 1.0) -> pd.DataFrame:
    """Per-pair agreement on prices, exit reason and P&L, at declared tolerances."""
    p, n = m["py"], m["nt8"]
    rows = []
    for pair in m["pairs"]:
        pi, ni = pair["py_i"], pair["nt8_i"]
        pr, nr = p.iloc[pi], n.iloc[ni]
        d_entry = float(pr["entry_price"]) - float(nr["entry_price"])
        d_exit = float(pr["exit_price"]) - float(nr["exit_price"])
        d_pnl = float(pr["pnl"]) - float(nr["pnl"])
        rows.append({
            "entry_bar": pair["entry_bar"],
            "direction": pair["direction"],
            "py_entry": pr["entry_price"], "nt8_entry": nr["entry_price"],
            "d_entry": d_entry,
            "py_exit": pr["exit_price"], "nt8_exit": nr["exit_price"],
            "d_exit": d_exit,
            "py_pnl": pr["pnl"], "nt8_pnl": nr["pnl"], "d_pnl": d_pnl,
            "py_reason": pr["exit_reason"], "nt8_reason": nr["exit_reason"],
            "entry_ok": bool(abs(d_entry) <= price_tol) if np.isfinite(d_entry) else False,
            "exit_ok": bool(abs(d_exit) <= price_tol) if np.isfinite(d_exit) else False,
            "pnl_ok": bool(abs(d_pnl) <= pnl_tol) if np.isfinite(d_pnl) else False,
            # Sign agreement is reported separately from magnitude: two engines
            # can disagree on P&L by a tick and still agree on win/loss, and a
            # sign flip is a different kind of problem from a rounding gap.
            "sign_ok": bool(np.sign(pr["pnl"]) == np.sign(nr["pnl"]))
                       if np.isfinite(d_pnl) else False,
        })
    return pd.DataFrame(rows)


def summary(m: Dict[str, Any], matched: pd.DataFrame) -> Dict[str, Any]:
    """Parity metrics. Deliberately returns NO single headline figure.

    There is no `agreement_pct` key. The old harness's 97.9% coexisted with a
    real trade-set recall of 47/73, and any consumer able to quote one number
    will quote the flattering one. `jaccard` is the closest thing to a scalar
    here and it penalises a surplus on either side.
    """
    n_py = int(len(m["py"]))
    n_nt8 = int(len(m["nt8"]))
    n_matched = int(len(m["pairs"]))
    union = n_py + n_nt8 - n_matched

    out = {
        "bar_seconds": m["bar_seconds"],
        "python_trades": n_py,
        "nt8_trades": n_nt8,
        "matched": n_matched,
        "python_only": int(len(m["py_only"])),
        "nt8_only": int(len(m["nt8_only"])),
        "recall": (n_matched / n_nt8) if n_nt8 else None,
        "precision": (n_matched / n_py) if n_py else None,
        "jaccard": (n_matched / union) if union else None,
    }
    if not matched.empty:
        out.update({
            "matched_entry_price_ok": float(matched["entry_ok"].mean()),
            "matched_exit_price_ok": float(matched["exit_ok"].mean()),
            "matched_pnl_ok": float(matched["pnl_ok"].mean()),
            "matched_pnl_sign_ok": float(matched["sign_ok"].mean()),
            "max_abs_entry_delta": float(matched["d_entry"].abs().max()),
            "max_abs_exit_delta": float(matched["d_exit"].abs().max()),
            "max_abs_pnl_delta": float(matched["d_pnl"].abs().max()),
        })
    else:
        out.update({"matched_entry_price_ok": None, "matched_exit_price_ok": None,
                    "matched_pnl_ok": None, "matched_pnl_sign_ok": None,
                    "max_abs_entry_delta": None, "max_abs_exit_delta": None,
                    "max_abs_pnl_delta": None})
    return out


def verdict(s: Dict[str, Any], *, min_recall: float, min_precision: float,
            min_matched_pnl_sign: float = 1.0) -> Dict[str, Any]:
    """PASS/FAIL against thresholds the CALLER states. No default thresholds.

    `min_recall` and `min_precision` are required arguments on purpose. A default
    would become the standard by accident, and the acceptable trade-set gap is a
    judgement about what the screen is FOR -- not something this module knows.
    """
    reasons = []
    if s["nt8_trades"] == 0 and s["python_trades"] == 0:
        return {"verdict": "VACUOUS", "reasons": [
            "both engines produced ZERO trades; parity is UNTESTED, not proven. "
            "An empty set matches an empty set."]}
    if s["nt8_trades"] == 0:
        reasons.append("NT8 produced no trades; there is nothing to be in parity with")
    if s["python_trades"] == 0:
        reasons.append("Python produced no trades while NT8 produced {}".format(
            s["nt8_trades"]))

    if s["recall"] is not None and s["recall"] < min_recall:
        reasons.append("recall {:.3f} < {:.3f}: Python missed {} of NT8's {} trades"
                       .format(s["recall"], min_recall, s["nt8_only"], s["nt8_trades"]))
    if s["precision"] is not None and s["precision"] < min_precision:
        reasons.append("precision {:.3f} < {:.3f}: Python took {} trades NT8 did not"
                       .format(s["precision"], min_precision, s["python_only"]))
    if (s["matched_pnl_sign_ok"] is not None
            and s["matched_pnl_sign_ok"] < min_matched_pnl_sign):
        reasons.append("{:.1%} of matched trades agree on win/loss SIGN (< {:.1%})"
                       .format(s["matched_pnl_sign_ok"], min_matched_pnl_sign))

    return {"verdict": "FAIL" if reasons else "PASS", "reasons": reasons,
            "thresholds": {"min_recall": min_recall,
                           "min_precision": min_precision,
                           "min_matched_pnl_sign": min_matched_pnl_sign}}


def run_parity(py_trades: pd.DataFrame, nt8_trades: pd.DataFrame, *,
               bar_seconds: int, min_recall: float, min_precision: float,
               price_tol: float = 0.25, pnl_tol: float = 1.0,
               assume_tz_python: Optional[str] = None,
               assume_tz_nt8: Optional[str] = None) -> Dict[str, Any]:
    """End-to-end: normalise, join, compare, judge. Returns a run-record-ready dict."""
    p = normalise_trades(py_trades, label="python", assume_tz=assume_tz_python)
    n = normalise_trades(nt8_trades, label="nt8", assume_tz=assume_tz_nt8)
    m = match_trade_sets(p, n, bar_seconds)
    matched = compare_matched(m, price_tol=price_tol, pnl_tol=pnl_tol)
    s = summary(m, matched)
    v = verdict(s, min_recall=min_recall, min_precision=min_precision)
    return {"summary": s, "verdict": v, "tolerances":
            {"price_tol": price_tol, "pnl_tol": pnl_tol},
            "matched_detail": matched, "match": m}


def format_report(result: Dict[str, Any], max_rows: int = 15) -> str:
    s, v = result["summary"], result["verdict"]
    L = []
    L.append("=" * 74)
    L.append("TRADE-SET PARITY  (join = entry bar + direction + occurrence)")
    L.append("=" * 74)
    L.append(f"{'python trades':<26} {s['python_trades']}")
    L.append(f"{'nt8 trades':<26} {s['nt8_trades']}")
    L.append(f"{'matched':<26} {s['matched']}")
    L.append(f"{'python only (invented)':<26} {s['python_only']}")
    L.append(f"{'nt8 only (missed)':<26} {s['nt8_only']}")
    L.append("")
    for k in ("recall", "precision", "jaccard"):
        val = s[k]
        L.append(f"{k:<26} {'n/a' if val is None else format(val, '.4f')}")
    L.append("")
    L.append("-- agreement WITHIN matched pairs (meaningless without recall above) --")
    for k in ("matched_entry_price_ok", "matched_exit_price_ok",
              "matched_pnl_ok", "matched_pnl_sign_ok"):
        val = s[k]
        L.append(f"{k:<26} {'n/a' if val is None else format(val, '.4f')}")
    for k in ("max_abs_entry_delta", "max_abs_exit_delta", "max_abs_pnl_delta"):
        val = s[k]
        L.append(f"{k:<26} {'n/a' if val is None else format(val, '.4f')}")
    L.append("")
    L.append(f"VERDICT: {v['verdict']}")
    for r in v["reasons"]:
        L.append(f"  - {r}")

    md = result["matched_detail"]
    if not md.empty:
        bad = md[~(md["entry_ok"] & md["exit_ok"] & md["sign_ok"])]
        if not bad.empty:
            L.append("")
            L.append(f"-- worst matched disagreements ({len(bad)} of {len(md)}) --")
            cols = ["entry_bar", "direction", "d_entry", "d_exit", "d_pnl",
                    "py_reason", "nt8_reason"]
            L.append(bad.reindex(columns=cols)
                        .sort_values("d_pnl", key=lambda c: c.abs(), ascending=False)
                        .head(max_rows).to_string(index=False))
    return "\n".join(L)


def _read(path: str) -> pd.DataFrame:
    if path.endswith(".json"):
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        if isinstance(payload, dict):
            for k in ("trades", "Trades", "data"):
                if k in payload:
                    payload = payload[k]
                    break
        return pd.DataFrame(payload)
    if path.endswith(".parquet"):
        return pd.read_parquet(path)
    return pd.read_csv(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", required=True, help="Python trade export (csv/json/parquet)")
    ap.add_argument("--nt8", required=True, help="NT8 trade export (csv/json/parquet)")
    ap.add_argument("--bar-seconds", type=int, required=True,
                    help="Primary series bar length. Cannot be inferred from a "
                         "trade list; state it.")
    ap.add_argument("--min-recall", type=float, required=True,
                    help="Minimum fraction of NT8 trades Python must find.")
    ap.add_argument("--min-precision", type=float, required=True,
                    help="Minimum fraction of Python trades NT8 also took.")
    ap.add_argument("--price-tol", type=float, default=0.25)
    ap.add_argument("--pnl-tol", type=float, default=1.0)
    ap.add_argument("--assume-tz-python", default=None)
    ap.add_argument("--assume-tz-nt8", default="America/New_York",
                    help="NT8 SA exports ET-naive timestamps.")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    result = run_parity(
        _read(args.python), _read(args.nt8),
        bar_seconds=args.bar_seconds, min_recall=args.min_recall,
        min_precision=args.min_precision, price_tol=args.price_tol,
        pnl_tol=args.pnl_tol, assume_tz_python=args.assume_tz_python,
        assume_tz_nt8=args.assume_tz_nt8)

    print(format_report(result))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"summary": result["summary"], "verdict": result["verdict"],
                       "tolerances": result["tolerances"]}, fh, indent=2, default=str)
    return 0 if result["verdict"]["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
