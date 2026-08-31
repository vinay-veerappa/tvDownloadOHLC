"""Tiny read-only HTTP feed for TradingView DOM overlays (test T2.1).

Serves session levels for a futures ticker from data/live parquet storage:
PDH/PDL, session OHLC, last price. Bars are UTC-naive 1m OHLCV from
data/live/live_storage_-{ROOT}.parquet; session math is ET-based via
market_calendar.get_futures_session_bounds (18:00 ET roll, DST-aware).

Run (Windows): ..\\.venv\\Scripts\\python.exe -m scripts.streamer.tv_levels_api --port 8630
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from scripts.utils.market_calendar import get_futures_session_bounds
from scripts.utils.live_storage_resolver import get_live_storage_path

app = FastAPI(title="TV Levels Feed", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.tradingview.com"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_CACHE: dict[str, tuple[pd.Timestamp, pd.DataFrame]] = {}


def _root(ticker: str) -> str:
    """MYM1! -> YM (mirror micros onto minis)."""
    t = ticker.upper().lstrip("/")
    for suf in ("1!", "1", "!"):
        if t.endswith(suf):
            t = t[: -len(suf)]
    if t.startswith("M") and len(t) > 2 and t[1:] in {"NQ", "ES", "RTY", "YM", "CL", "GC"}:
        t = t[1:]
    return t


def _load(root: str) -> pd.DataFrame:
    """Load 1m bars (UTC-naive) for root, cached 30 s."""
    path = get_live_storage_path(root)
    if not Path(path).exists():
        raise FileNotFoundError(f"no live storage parquet for {root}: {path}")
    now = pd.Timestamp.utcnow().tz_localize(None)
    hit = _CACHE.get(root)
    if hit and (now - hit[0]).total_seconds() < 30:
        return hit[1]
    df = pd.read_parquet(path)
    if "timestamp" in df.columns:
        df["dt"] = pd.to_datetime(df["timestamp"])
    elif "dt" in df.columns:
        df["dt"] = pd.to_datetime(df["dt"])
    elif "time" in df.columns:
        df["dt"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    if df["dt"].dt.tz is None:
        df["dt"] = df["dt"].dt.tz_localize("UTC")
    else:
        df["dt"] = df["dt"].dt.tz_convert("UTC")
    df = df.sort_values("dt").drop_duplicates("dt").reset_index(drop=True)
    df["dt"] = df["dt"].dt.tz_localize(None)  # strip tz: compare against naive UTC
    _CACHE[root] = (now, df)
    return df


def _et_bounds(df: pd.DataFrame, now_utc: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    """Current + previous logical session bounds, naive UTC out.

    Weekend handling: Globex closed Sat (and Sun before 18:00 ET) -> most recent
    session is Friday's logical session. Sunday evening (>=18:00 ET) belongs to
    Monday's logical session (roll 18:00 ET).
    """
    et = "America/New_York"
    now_et = now_utc.tz_localize("UTC").tz_convert(et)
    wd = now_et.weekday()
    if wd == 5 or wd == 6 and now_et.hour < 18:  # Saturday, or Sunday pre-Globex → Friday's session
        d = _prev_business_day(now_et.date())
    elif wd == 6:  # Sunday evening ≥18:00 ET → Monday's logical session (Globex reopen)
        d = _next_business_day(now_et.date())
    else:
        d = (now_et - timedelta(hours=7)).date() if now_et.hour < 18 else now_et.date()
    s, e = get_futures_session_bounds(d)
    ps, pe = get_futures_session_bounds(_prev_business_day(d))
    n = lambda t: t.astimezone(timezone.utc).replace(tzinfo=None)  # noqa: E731
    return n(s), n(e), n(ps), n(pe)


def _prev_business_day(d):
    prev = d - timedelta(days=1)
    while prev.weekday() >= 5:
        prev -= timedelta(days=1)
    return prev


def _next_business_day(d):
    nxt = d + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return nxt


@app.get("/levels")
def levels(ticker: str = Query("YM1")) -> dict:
    now_utc = pd.Timestamp.utcnow().tz_localize(None)
    root = _root(ticker)
    try:
        df = _load(root)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"storage-unavailable: {exc!s}"[:120]}
    if df.empty:
        return {"error": f"no bars for {root}", "ticker": ticker}
    s, e, ps, pe = _et_bounds(df, now_utc)
    cur = df[(df["dt"] >= s) & (df["dt"] <= min(e, now_utc))]
    prev = df[(df["dt"] >= ps) & (df["dt"] <= pe)]
    if cur.empty:
        return {"error": "no bars in current session", "session_start_utc": str(s), "ticker": ticker}
    last_row = cur.iloc[-1]
    out = {
        "ticker": ticker,
        "root": root,
        "ts_utc": now_utc.isoformat(timespec="seconds"),
        "last": float(last_row.get("close", last_row.get("c"))),
        "bar_ts": str(last_row["dt"]),
        "session_open": float(cur.iloc[0]["open"]),
        "session_high": float(cur["high"].max()),
        "session_low": float(cur["low"].min()),
        "prev_session_high": float(prev["high"].max()) if not prev.empty else None,
        "prev_session_low": float(prev["low"].min()) if not prev.empty else None,
    }
    out["session_range_pct"] = round((out["session_high"] - out["session_low"]) / out["last"] * 100, 3) if out["last"] else None
    return out


@app.get("/health")
def health() -> dict:
    return {"ok": True, "ts": pd.Timestamp.utcnow().isoformat()}


# ---------------------------------------------------------------------------
# NT8 positions feed (T2.2): reads a JSON snapshot written by the agent from
# the NT8 MCP bridge (ninjatrader_nt_positions). The bridge is not callable
# from FastAPI directly (MCP stdio), so the agent pumps the snapshot file.
# ---------------------------------------------------------------------------

NT8_SNAPSHOT = Path(__file__).parent / "nt8_positions_snapshot.json"


@app.get("/positions")
def positions() -> dict:
    """Live NT8 positions from the snapshot file (agent-pumped)."""
    snap = NT8_SNAPSHOT
    if not snap.exists():
        return {"error": "no nt8 snapshot yet", "positions": []}
    try:
        data = json.loads(snap.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"error": f"snapshot-parse: {exc!s}"[:120], "positions": []}
    # freshness: stale > 60s means the bridge/agent stopped pumping
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(data["ts_utc"])).total_seconds()
    return {"ts_utc": data["ts_utc"], "stale": age > 60, "age_s": round(age, 1),
            "positions": data["positions"]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8630)
    args = ap.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()