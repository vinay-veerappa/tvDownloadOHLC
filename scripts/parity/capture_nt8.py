"""Capture an NT8 Strategy Analyzer run from Python. No hand-made CSV.

Until now `--nt8` READ a fixture someone produced by hand with `nt_backtest` +
`nt_extract_trades`, which made the NT8 half of the workflow a manual step in a
procedure whose whole point is that there is one command. The bridge has an HTTP
endpoint and a token on disk, so there was never a reason for the handholding.

    from scripts.parity.capture_nt8 import capture
    res = capture("BBMRReversionBot", "MNQ 12-26", "2025-01-01", "2025-06-30",
                  period_value=5, out_dir=run_dir)
    res.csv_path      # the trade list, NT8's own field names
    res.meta_path     # what it ran under -- globals, profile hash, bar size

THREE REFUSALS, each for a failure that has actually happened:

1. TRUNCATION. `nt_backtest` caps its trade list at `maxTrades`. The MCP tool
   defaults to **50**; a 300-trade backtest returns 50 and looks like a complete
   result. Parity recall measured against a truncated ground truth is a
   guaranteed false red that reads as a strategy defect. `len(trades) ==
   maxTrades` is indistinguishable from "exactly that many", so it REFUSES
   rather than guessing which it was.

2. ATTRIBUTION. The Strategy Analyzer window is REUSED between calls. A name the
   bridge could not resolve used to leave whatever was already loaded and return
   its trades. The response echoes `effectiveStrategy`; if it is not what was
   asked for, the run is not evidence about the strategy requested.

3. THE PROFILE. `requireGlobals` are asserted, never written --
   `GlobalMergePolicy` is machine-global, and `MergeBackAdjusted` silently
   rescales every price. A run whose globals do not match the frozen profile is
   refused by the bridge; this surfaces that reason instead of an empty result.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import os
import pathlib
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from scripts.parity.nt8_profile import (
    ORDER_FILL_KEYS, build_request, load_profile, profile_hash)

BRIDGE_URL = os.getenv("NT8_BRIDGE_URL", "http://localhost:7890/api/backtest")
TOKEN_FILE = pathlib.Path(
    os.getenv("NT8_BRIDGE_TOKEN_FILE",
              str(pathlib.Path.home() / "Documents" / "NinjaTrader 8" / "mcp_token.txt")))

# The bridge default is 2000; the MCP tool default is 50. Ask for a lot and
# refuse on equality rather than choosing a number and hoping.
DEFAULT_MAX_TRADES = 5000

# NT8's own field names, in the order the committed fixture uses. Written
# UNCHANGED so `trade_set_parity.normalise_trades` keeps being exercised against
# the real payload rather than a schema we tidied up.
#: NT8's OWN field names, so `normalise_trades` keeps being exercised against
#: the real payload rather than against a shape this file invented.
#:
#: The second group was added 2026-09-05 with the matching bridge change. Every
#: one of them is needed by a report that could not be written without it:
#:
#:   entryName    the JOIN KEY to the strategy's decision log, which is the only
#:                possible source of WHY a trade was taken -- the criteria live
#:                in the strategy and never reach the platform
#:   entryGroup   which rows are legs of ONE bracket. The bridge already grouped
#:                by this key to report entry-level win rate and never emitted
#:                it, so the aggregate could not be reproduced or checked
#:   entry/exitQuantity  per-LEG size. Trade.Quantity is the trade's; on a
#:                scale-out the executions differ from it and from each other,
#:                which is the entire content of the leg convention
#:   mae/mfe      separates a bad ENTRY (the loser never went your way) from a
#:                bad EXIT (it did, and was given back). No P&L column can
#:                distinguish those two
#:
#: A field the bridge does not send arrives EMPTY rather than absent, so an old
#: bridge produces a readable file with blank columns -- and the reports refuse
#: an all-blank excursion column rather than reporting a median of zero.
TRADE_FIELDS = ("instrument", "marketPosition", "quantity", "entryPrice",
                "exitPrice", "entryTime", "exitTime", "profitCurrency",
                "profitPoints", "exitName",
                "entryName", "entryGroup", "tradeNumber",
                "entryQuantity", "exitQuantity",
                "maeCurrency", "maePoints", "mfeCurrency", "mfePoints",
                "commission")


class Nt8CaptureError(RuntimeError):
    """The capture did not produce attributable evidence. Never a warning."""


@dataclass
class Capture:
    csv_path: str
    meta_path: str
    trades: List[Dict[str, Any]]
    response: Dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def n_trades(self) -> int:
        return len(self.trades)


def _token() -> str:
    if not TOKEN_FILE.is_file():
        raise Nt8CaptureError(
            "no bridge token at {}. The NT8 MCP bridge writes it on start; "
            "without it the capture cannot authenticate. Set "
            "NT8_BRIDGE_TOKEN_FILE if it lives elsewhere.".format(TOKEN_FILE))
    tok = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not tok:
        raise Nt8CaptureError("bridge token file {} is empty".format(TOKEN_FILE))
    return tok


def post(body: Dict[str, Any], *, timeout: int = 600) -> Dict[str, Any]:
    req = urllib.request.Request(
        BRIDGE_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer {}".format(_token())})
    try:
        raw = urllib.request.urlopen(req, timeout=timeout).read()
    except urllib.error.HTTPError as exc:
        raise Nt8CaptureError("bridge HTTP {}: {!r}".format(
            exc.code, exc.read()[:500])) from exc
    except urllib.error.URLError as exc:
        raise Nt8CaptureError(
            "cannot reach the NT8 bridge at {}: {}. Is NinjaTrader running with "
            "the MCP bridge addon loaded?".format(BRIDGE_URL, exc.reason)) from exc
    return json.loads(raw)


def _check(resp: Dict[str, Any], strategy: str, max_trades: int) -> List[Dict[str, Any]]:
    if resp.get("error"):
        detail = [resp["error"]]
        for key in ("globalMismatches", "paramErrors"):
            for m in resp.get(key) or []:
                detail.append("{}: {}".format(key, m))
        raise Nt8CaptureError("the bridge refused the run -- " + " | ".join(detail))

    effective = resp.get("effectiveStrategy")
    if effective and effective != strategy:
        raise Nt8CaptureError(
            "asked for {!r} and the Strategy Analyzer ran {!r}. The SA window is "
            "REUSED between calls, so an unresolved name leaves whatever was "
            "already loaded -- these trades are not evidence about {!r}."
            .format(strategy, effective, strategy))

    trades = resp.get("trades") or []
    if len(trades) >= max_trades:
        raise Nt8CaptureError(
            "got exactly maxTrades={} trades, which is indistinguishable from a "
            "TRUNCATED list. Parity recall against a truncated ground truth is a "
            "false red that reads as a strategy defect. Re-run with a higher "
            "--nt8-max-trades.".format(max_trades))
    return trades


def _write_csv(trades: List[Dict[str, Any]], path: pathlib.Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(TRADE_FIELDS), extrasaction="ignore")
        w.writeheader()
        for t in trades:
            w.writerow({k: t.get(k, "") for k in TRADE_FIELDS})


def capture(strategy: str, symbol: str, date_from: str, date_to: str, *,
            period: str = "Minute", period_value: int = 1,
            out_dir: str | pathlib.Path = ".",
            max_trades: int = DEFAULT_MAX_TRADES,
            extra_params: Optional[Dict[str, Any]] = None,
            timeout_sec: int = 420,
            strategy_source: Optional[str] = None,
            strategy_source_path: Optional[str] = None) -> Capture:
    """Run the strategy in the Analyzer under the frozen profile and store it.

    `strategy_source` (or its path) lets a strategy that programs its own
    series (B9: AddDataSeries in ConfigureStrategy) receive the profile MINUS
    the analyzer's OrderFillResolution keys -- NT8 refuses those on a
    multi-series strategy and aborts the run, which surfaced as a silent
    0-trade capture. The meta records which fill resolution the run had.
    """
    prof = load_profile()
    body = build_request(strategy, symbol, date_from, date_to,
                         period=period, period_value=period_value,
                         max_trades=max_trades, timeout_sec=timeout_sec,
                         extra_params=extra_params, profile=prof,
                         strategy_source=strategy_source,
                         strategy_source_path=strategy_source_path)
    multi_series = any(k not in body["params"] for k in ORDER_FILL_KEYS)
    resp = post(body, timeout=timeout_sec + 180)
    trades = _check(resp, strategy, max_trades)

    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = "nt8_trades_{}_{}_{}_{}".format(
        strategy, symbol.replace(" ", ""), date_from, date_to)
    csv_path = out / (stem + ".csv")
    meta_path = out / (stem + ".meta.json")

    _write_csv(trades, csv_path)

    bar_seconds = {"Minute": 60, "Second": 1, "Day": 86400}.get(period, 0) * period_value
    meta = {
        "_comment": [
            "CAPTURED AUTOMATICALLY by scripts/parity/capture_nt8.py. Not hand-made.",
            "",
            "Field names and timestamps are NT8's OWN, unchanged, so that",
            "trade_set_parity.normalise_trades is exercised against the real",
            "payload rather than a schema we tidied up.",
            "",
            "READ effectiveGlobals BEFORE USING THIS FOR ANYTHING NUMERIC.",
        ],
        "capturedAt": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "source": "capture_nt8.py -> {}".format(BRIDGE_URL),
        "strategy": strategy,
        "effectiveStrategy": resp.get("effectiveStrategy"),
        "instrument": resp.get("instrument") or symbol,
        "symbolRequested": symbol,
        "period": period,
        "periodValue": period_value,
        "barSeconds": bar_seconds,
        "from": date_from,
        "to": date_to,
        # The bridge returns ET-NAIVE timestamps. Recorded explicitly because
        # reading them as UTC shifts every trade 4-5 hours onto a different
        # entry bar and destroys the join silently.
        "timestampZone": "America/New_York",
        "timestampsAreNaive": True,
        "maxTradesRequested": max_trades,
        "tradesReturned": len(trades),
        "effectiveGlobals": resp.get("effectiveGlobals"),
        "appliedParams": resp.get("appliedParams"),
        # Which fill resolution the run actually had. "High" + the three keys
        # means the analyzer series; "strategy-programmed" means the strategy
        # owns one (B9) and the keys were suppressed -- the two are NOT the
        # same configuration and a future reader must not assume they were.
        "fillResolution": "strategy-programmed" if multi_series else "High",
        "profileHash": resp.get("profileHash") or profile_hash(prof),
        "reportedMetrics": {k: resp.get(k) for k in (
            "totalTrades", "winners", "losers", "tradeWinRatePct", "profitFactor",
            "grossProfit", "grossLoss", "netProfit", "maxDrawdown",
            "totalCommission") if k in resp},
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return Capture(str(csv_path), str(meta_path), trades, resp)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--strategy", required=True, help="C# CLASS name, compiled")
    ap.add_argument("--symbol", required=True, help='e.g. "MNQ 12-26"')
    ap.add_argument("--from", dest="date_from", required=True)
    ap.add_argument("--to", dest="date_to", required=True)
    ap.add_argument("--period", default="Minute")
    ap.add_argument("--period-value", type=int, default=1)
    ap.add_argument("--max-trades", type=int, default=DEFAULT_MAX_TRADES)
    ap.add_argument("--out-dir", default="scripts/parity/fixtures")
    ap.add_argument("--bot-source", default=None,
                    help="path to the strategy's .cs source. Passing it lets a "
                         "multi-series strategy (AddDataSeries in "
                         "ConfigureStrategy) receive the profile minus the "
                         "analyzer's OrderFillResolution keys, which NT8 "
                         "refuses there.")
    a = ap.parse_args()
    try:
        res = capture(a.strategy, a.symbol, a.date_from, a.date_to,
                      period=a.period, period_value=a.period_value,
                      out_dir=a.out_dir, max_trades=a.max_trades,
                      strategy_source_path=a.bot_source)
    except Nt8CaptureError as exc:
        print("REFUSED: {}".format(exc))
        return 1
    print("captured {} trades\n  {}\n  {}".format(
        res.n_trades, res.csv_path, res.meta_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
