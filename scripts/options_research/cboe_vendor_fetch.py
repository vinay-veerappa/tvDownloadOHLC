"""
cboe_vendor_fetch.py — independent CBOE dealer-levels vendor feed.

Purpose: vendor-comparison source for our own GEX walls (RTD-native + Schwab
translation). Free CBOE delayed-quotes full option chains provide per-contract
OI + IV + gamma for ~3,000 US option roots. Disposable experiment: disable via
`schtasks /Change /TN <task> /DISABLE` when not adding value.

Subcommands:
  core     one cycle for CORE_ROOTS (chains -> wall metrics; full chain
           archived only on anchor cycles 09:33/11:33/13:33/15:48 ET)
  weekly   refresh root universe from CBOE symbol CSV, fetch EVERY root,
           write per-root wall summary (no chains), then prune old chains
  prune    delete chain archives older than --retention-days

Outputs (all under data/options/vendors/):
  cboe_walls.csv                     appended per root per cycle (core)
  cboe_weekly_roots_YYYY-MM-DD.csv   per-root summary once a week
  chains/YYYYMMDD/HHMM_<root>.json.gz  raw chains on anchor cycles
  cboe_roots_YYYYMMDD.txt            root universe refreshed weekly

Scheduled cadence (Windows tasks, Pacific-clock box, times in ET):
  core   every 15 min across 09:33-15:48 ET, Mon-Fri (self-skips when the
         CBOE chain timestamp is stale => closed market / holiday)
  weekly Saturday 11:00 ET (Friday EOD chain, OI fully settled)

GEX convention (gex-tracker / SqueezeMetrics): notional dealer gamma per
contract = gamma * OI * 100 * spot^2 * 0.01; calls positive, puts negative
(dealer long calls / short puts). Walls = max |strike GEX| per side.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import gzip
import io
import json
import logging
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR_DIR = REPO_ROOT / "data" / "options" / "vendors"
CHAIN_DIR = VENDOR_DIR / "chains"
WALLS_CSV = VENDOR_DIR / "cboe_walls.csv"
ROOTS_FILE_PREFIX = "cboe_roots_"

CORE_ROOTS = ["_SPX", "SPY", "_NDX", "QQQ", "_VIX"]
CHAIN_ANCHOR_TIMES_ET = {"09:33", "11:33", "13:33", "15:48"}
WEEKLY_DAY_ET = 5  # Saturday (Mon=0 .. Sun=6)
WEEKLY_WINDOW_ET = ("10:55", "12:10")   # Saturday ET window the weekly pass may run in
CORE_WINDOW_ET = ("09:33", "15:48")     # Mon-Fri cycles
CBOE_OPTIONS_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/{root}.json"
CBOE_SYMBOL_CSV = "https://www.cboe.com/us/options/market_statistics/symbol_data/csv/?mkt=cone"
STALE_SKIP_MIN = 45
HTTP_TIMEOUT = 25
MAX_WORKERS = 8
MAX_REQUESTS_PER_SEC = 3.0
MAX_REQUESTS_PER_SEC = 3.0
ABORT_FAIL_RATE = 0.25
ABORT_MIN_ATTEMPTS = 200

WALL_FIELDS = [
    "fetch_utc", "cboe_ts", "et_date", "et_time", "root", "spot", "n_contracts",
    "call_wall", "put_wall", "gamma_flip", "net_gex_mm", "call_gex_mm",
    "put_gex_mm", "max_pain", "total_call_oi", "total_put_oi", "oi_pcr",
    "data_age_min", "stale",
]

WEEKLY_FIELDS = [
    "fetch_utc", "cboe_ts", "root", "spot", "n_contracts", "front_expiry",
    "call_wall", "put_wall", "gamma_flip", "net_gex_mm", "total_call_oi",
    "total_put_oi", "oi_pcr", "max_pain",
]

log = logging.getLogger("cboe_vendor_fetch")


def now_et() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        log.warning("zoneinfo unavailable, assuming UTC-4 (EDT)")
        return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=-4)))


class _Throttle:
    """Process-wide pacing shared by all worker threads (CBOE 429s bursts)."""

    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            now = time.monotonic()
            t = max(self._next, now)
            self._next = t + self.min_interval
        time.sleep(max(0.0, t - now))


throttle = _Throttle(1.0 / MAX_REQUESTS_PER_SEC)


def http_get_json(url: str, retries: int = 4) -> dict | None:
    for attempt in range(retries + 1):
        throttle.wait()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                ra = e.headers.get("Retry-After") if e.headers else None
                delay = float(ra) + 0.5 if ra else 3.0 * (attempt + 1)
                log.debug("429 on %s — backing off %.1fs", url, delay)
                time.sleep(delay)
                continue
            log.debug("fetch fail %s: %s", url, e)
            return None
        except Exception as e:
            if attempt == retries:
                log.debug("fetch fail %s: %s", url, e)
                return None
            time.sleep(1.0 + attempt)
    return None


_OPT_RE = re.compile(r"^_?([A-Z0-9]+?)(\d{6})([CP])(\d{8})$")


def parse_option_symbol(sym: str):
    m = _OPT_RE.match(sym or "")
    if not m:
        return None
    root, exp, cp, strike = m.groups()
    return root, exp, cp, int(strike) / 1000.0


# alias used by chain_metrics
parse_option = parse_option_symbol


def chain_metrics(data: dict) -> dict | None:
    data = (data or {}).get("data") or {}
    opts = data.get("options") or []
    spot = float(data.get("current_price") or 0)
    if not opts or not spot:
        return None

    call_oi: dict[float, float] = defaultdict(float)
    put_oi: dict[float, float] = defaultdict(float)
    call_gex: dict[float, float] = defaultdict(float)
    put_gex: dict[float, float] = defaultdict(float)
    total_call_oi = total_put_oi = 0.0
    expiries_seen: set[str] = set()

    for o in opts:
        parsed = parse_option(o.get("option", ""))
        if not parsed:
            continue
        _, exp, cp, strike = parsed
        oi = float(o.get("open_interest") or 0)
        if oi <= 0:
            continue
        gamma = float(o.get("gamma") or 0)
        k = round(strike, 4)
        notional = gamma * oi * 100.0 * spot * spot * 0.01
        if cp == "C":
            call_oi[k] += oi
            call_gex[k] += notional
            total_call_oi += oi
        else:
            put_oi[k] += oi
            put_gex[k] += notional
            total_put_oi += oi
        expiries_seen.add(exp)

    if not call_gex and not put_gex:
        return None

    call_wall = max(call_gex, key=call_gex.get) if call_gex else None
    put_wall = max(put_gex, key=put_gex.get) if put_gex else None

    net = sorted({k: call_gex.get(k, 0) - put_gex.get(k, 0) for k in set(call_gex) | set(put_gex)}.items())
    running = 0.0
    gamma_flip = None
    prev = None
    for k, g in net:
        running += g
        if prev and ((prev[1] > 0 > running) or (prev[1] < 0 < running)):
            g0, k0 = prev[1], prev[0]
            denom = abs(g0) + abs(running)
            frac = abs(g0) / denom if denom else 1.0
            gamma_flip = k0 + (k - k0) * frac
            break
        prev = (k, running)

    strikes = sorted(set(call_oi) | set(put_oi))
    max_pain = None
    if strikes:
        best_pain = None
        for K in strikes:
            pain = 0.0
            for kc, oi in call_oi.items():
                if kc > K:
                    pain += (kc - K) * oi
            for kp, oi in put_oi.items():
                if kp < K:
                    pain += (K - kp) * oi
            if best_pain is None or pain < best_pain:
                best_pain = pain
                max_pain = K

    pcr = round(total_put_oi / total_call_oi, 3) if total_call_oi else None
    front_expiry = min(expiries_seen) if expiries_seen else None
    return {
        "spot": round(spot, 2),
        "n_contracts": len(opts),
        "call_wall": round(call_wall, 2) if call_wall is not None else None,
        "put_wall": round(put_wall, 2) if put_wall is not None else None,
        "gamma_flip": round(gamma_flip, 2) if gamma_flip is not None else None,
        "net_gex_mm": round((sum(call_gex.values()) - sum(put_gex.values())) / 1e6, 2),
        "call_gex_mm": round(sum(call_gex.values()) / 1e6, 2),
        "put_gex_mm": round(sum(put_gex.values()) / 1e6, 2),
        "max_pain": round(max_pain, 2) if max_pain is not None else None,
        "total_call_oi": int(total_call_oi),
        "total_put_oi": int(total_put_oi),
        "oi_pcr": pcr,
        "front_expiry": front_expiry,
    }


def append_csv(path: Path, row: dict, fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)


def save_chain(payload: dict, root: str, et: datetime) -> Path | None:
    try:
        d = CHAIN_DIR / et.strftime("%Y%m%d")
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{et.strftime('%H%M')}_{root}.json.gz"
        with gzip.open(p, "wb", compresslevel=6) as f:
            f.write(json.dumps(payload, separators=(",", ":")).encode())
        return p
    except Exception as e:
        log.warning("chain save failed %s: %s", root, e)
        return None


def chain_age_min(cboe_ts: str, et: datetime) -> float | None:
    try:
        ts = datetime.strptime(cboe_ts, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None
    # cboe_ts is ET wall-clock from the exchange
    age = et - ts.replace(tzinfo=et.tzinfo)
    return age.total_seconds() / 60.0


def fetch_core(force: bool, roots: list[str] | None = None) -> int:
    et = now_et()
    roots = roots or CORE_ROOTS
    written = 0
    for root in roots:
        payload = http_get_json(CBOE_OPTIONS_URL.format(root=root))
        if not payload:
            log.warning("core %s: fetch failed", root)
            continue
        data = payload.get("data") or {}
        cboe_ts = payload.get("timestamp") or ""
        metrics = chain_metrics(payload)
        if metrics is None:
            log.warning("core %s: no metrics (empty chain?)", root)
            continue
        age = chain_age_min(cboe_ts, et)
        stale = 1 if (age is None or (age > STALE_SKIP_MIN and not _forced)) else 0
        if stale and not _forced:
            log.info("core %s: skipped stale/closed data (%.0f min old, ts=%s)",
                     root, age if age is not None else -1, cboe_ts)
            continue
        row = {
            "fetch_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "cboe_ts": cboe_ts,
            "et_date": et.strftime("%Y-%m-%d"),
            "et_time": et.strftime("%H:%M"),
            "root": root,
            **metrics,
            "data_age_min": round(age, 1) if age is not None else "",
            "stale": stale,
        }
        append_csv(WALLS_CSV, row, WALL_FIELDS)
        if et.strftime("%H:%M") in CHAIN_ANCHOR_TIMES_ET or _forced:
            p = save_chain(payload, root, et)
            log.info("core %s: walls ok, chain %s", root, p.name if p else "-")
        else:
            log.info("core %s: walls ok (no anchor, chain not archived)", root)
        written += 1
    return written


_forced = False


def cmd_core(args) -> int:
    global _forced
    _forced = args.force
    return fetch_core(_forced, getattr(args, "roots", None))


def refresh_roots(et: datetime) -> Path | None:
    req = urllib.request.Request(CBOE_SYMBOL_CSV, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        txt = r.read().decode("utf-8", "replace")
    rows = list(csv.reader(io.StringIO(txt)))
    roots = sorted({row[0].split()[0] for row in rows[1:] if row})
    out = VENDOR_DIR / f"roots_{et.strftime('%Y%m%d')}.txt"
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(roots))
    log.info("root universe: %d roots -> %s", len(roots), out.name)
    return out and roots or None


def cmd_weekly(args) -> int:
    global _forced
    _forced = True
    et = now_et()
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    if getattr(args, "roots_file", None):
        roots = [r.strip() for r in open(args.roots_file).read().split() if r.strip()]
        log.info("resume mode: %d roots from %s", len(roots), args.roots_file)
    else:
        if getattr(args, "roots_file", None):
        roots = [r.strip() for r in open(args.roots_file).read().split() if r.strip()]
        log.info("resume mode: %d roots from %s", len(roots), args.roots_file)
    else:
        roots = refresh_roots(et)
    out = VENDOR_DIR / f"cboe_weekly_roots_{et.strftime('%Y-%m-%d')}.csv"
    failures: list[str] = []
    attempts = 0
    rows_written = 0
    skipped_empty = 0

    def work(root: str):
        time.sleep(random.uniform(0.02, 0.15))
        return root, http_get_json(CBOE_OPTIONS_URL.format(root=root))

    write_header = not getattr(args, "roots_file", None)
    with out.open("a" if getattr(args, "roots_file", None) else "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=WEEKLY_FIELDS, extrasaction="ignore")
        if write_header:
            w.writeheader()
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as ex:
            futs = {ex.submit(work, root): root for root in roots or []}
            done = 0
            for fut in concurrent.futures.as_completed(futs):
                root = futs[fut]
                done += 1
                attempts += 1
                if attempts == ABORT_MIN_ATTEMPTS and failures and len(failures) / attempts > ABORT_FAIL_RATE:
                    log.error("aborting: fail rate %.0f%% too high", 100 * len(failures) / attempts)
                    for f in futs:
                        f.cancel()
                    break
                try:
                    root, payload = fut.result()
                except Exception:
                    failures.append(root)
                    continue
                if not payload:
                    failures.append(root)
                    if done % 250 == 0:
                        log.info("progress: %d/%d done, %d fails", done, len(futs), len(failures))
                    continue
                m = chain_metrics(payload)
                if m is None:
                    skipped_empty += 1
                    continue
                w.writerow({
                    "fetch_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "cboe_ts": payload.get("timestamp", ""),
                    "root": root,
                    **m,
                })
                rows_written += 1
                if done % 250 == 0:
                    log.info("progress: %d/%d done, %d fails", done, len(futs), len(failures))

    log.info("weekly done: %d roots attempted, %d rows written, %d empty, %d fails",
             attempts, rows_written, skipped_empty, len(failures))
    if failures:
        fail_log = VENDOR_DIR / f"weekly_fails_{et.strftime('%Y-%m-%d')}.txt"
        fail_log.write_text("\n".join(sorted(set(failures))))
    prune_chains(args.retention_days)
    return rows_written


def prune_chains(retention_days: int) -> None:
    if not CHAIN_DIR.exists() or retention_days <= 0:
        return
    cutoff = datetime.now().timestamp() - retention_days * 86400
    removed = 0
    for d in CHAIN_DIR.iterdir():
        try:
            if d.is_dir() and d.stat().st_mtime < cutoff:
                import shutil
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
        except Exception:
            pass
    if removed:
        log.info("pruned %d chain day-dirs older than %dd", removed, retention_days)


def cmd_prune(args) -> None:
    prune_chains(args.retention_days)


def setup_logging() -> None:
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    fh = logging.FileHandler(VENDOR_DIR / "cboe_fetch.log")
    fh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    log.addHandler(h)
    log.addHandler(fh)
    log.setLevel(logging.INFO)


def main() -> int:
    setup = argparse.ArgumentParser(description=__doc__.split("\n")[1] if __doc__ else "cboe fetcher")
    sub = setup.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("core", help="one core-roots cycle")
    p.add_argument("--force", action="store_true", help="bypass stale/weekend guard + archive chains")
    p.add_argument("--roots", nargs="*", default=None)

    w = sub.add_parser("weekly", help="fetch all traded roots, weekly summary")
    w.add_argument("--force", action="store_true", help="bypass Sat-window guard")
    w.add_argument("--max-workers", type=int, default=MAX_WORKERS)
    w.add_argument("--retention-days", type=int, default=30)
    w.add_argument("--roots-file", default=None, help="subset roots to fetch (one per line)")
    w.add_argument("--roots-file", default=None, help="subset roots to fetch (one per line)")

    pr = sub.add_parser("prune", help="delete old chain archives")
    pr.add_argument("--retention-days", type=int, default=30)

    args = setup.parse_args()
    setup_logging()

    et_now = now_et()
    h = et_now.strftime("%H:%M")

    if args.cmd == "core":
        outside = et_now.weekday() >= WEEKLY_DAY_ET or not (CORE_WINDOW_ET[0] <= h <= CORE_WINDOW_ET[1])
        if outside and not args.force:
            log.info("core: outside Mon-Fri %s-%s ET (now %s %s) — skipping",
                     CORE_WINDOW_ET[0], CORE_WINDOW_ET[1], et_now.strftime("%a"), h)
            return 0
        n = cmd_core(args)
        print(f"core cycle: {n} roots written")
        return 0 if n else 1
    if args.cmd == "weekly":
        outside = et_now.weekday() != WEEKLY_DAY_ET or not (WEEKLY_WINDOW_ET[0] <= h <= WEEKLY_WINDOW_ET[1])
        if outside and not args.force:
            log.info("weekly: outside Sat %s-%s ET (now %s %s) — skipping",
                     WEEKLY_WINDOW_ET[0], WEEKLY_WINDOW_ET[1], et_now.strftime("%a"), h)
            return 0
        n = cmd_weekly(args)
        print(f"weekly run: {n} root summaries")
        return 0
    if args.cmd == "prune":
        cmd_prune(args)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())