r"""The run record: what a result must carry to be attributable and falsifiable.

WHY THIS EXISTS. Before this, a completed research run produced an equity JSON,
an HTML summary and a Prisma row holding `metricsJson` + `configJson`. Nothing
recorded the code that produced it, the exact bars it read, the engine costs it
assumed, how many signals actually reached the frame they were scored on, or the
fold geometry the objective was averaged over. Two runs on different days could
return materially different numbers and no stored artifact could say why.

Concretely, the things that had already gone wrong and were invisible in the
stored output:

  * signals scored against a frame they were not generated on, half of them
    collapsed onto a single bar (fixed 2026-09-04, `signal_alignment`);
  * a Sharpe that scales with frame length, so fold scores and OOS scores are
    not the same unit (`engine.sharpeIsFrameLengthDependent`);
  * NT8 Strategy Analyzer runs inheriting whatever a human last clicked
    (`nt8Profile.hash`);
  * `ResearchRun.gitHash` present in the Prisma schema since day one and never
    once written.

DESIGN. Declare -> echo -> refuse, the same shape as the NT8 backtest profile:

  declare  the caller states what it is about to do, and load-bearing facts have
           NO default -- an undeclared price-adjustment basis records as
           "undeclared", never as "unadjusted", because a default and an
           erasure are indistinguishable once written to a file;
  echo     the record stores what was actually resolved (the data content hash,
           the resolved engine config, the fold boundaries), not what was asked
           for;
  refuse   `finalize()` returns a record whose `attributable` flag is FALSE when
           a load-bearing field is missing, and lists which. Reporting is
           expected to refuse a non-attributable record rather than render it.

`attributable` is a status boolean, so the test suite asks the question that
matters for any status boolean: what input makes it false? See
tests/test_run_record.py -- every load-bearing field has a test that removes it
and asserts the flag flips.

CRASH SAFETY. The ledger is append-only JSONL and a run appends TWICE: once as
`running` at open, once as `complete`/`failed` at close. Readers take the last
line per runId. A run that dies mid-way therefore leaves a `running` line
forever, which is the point -- an abandoned arm that vanishes from the ledger is
how selection bias gets laundered (plan phase 2.5).

Usage:
    rec = RunRecord.open(run_id, strategy_key="mean_reversion", ticker="NQ1")
    rec.declare_data(df, ticker="NQ1", adjustment="undeclared",
                     loader="DataLoader.load_enriched")
    rec.declare_engine(engine)
    with rec.stage("optimize") as st:
        ...
        st.detail(trials=30, folds=folds)
    rec.record_alignment("oos", metrics["signal_alignment"])
    rec.set_metrics(oos_metrics)
    rec.finalize(run_dir)
"""
from __future__ import annotations

import getpass
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

SCHEMA_VERSION = 1

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LEDGER = PROJECT_ROOT / "results" / "RESEARCH" / "_run_ledger.jsonl"

# Columns fingerprinted for the data content hash. Deliberately the price/volume
# columns only, not every derived feature: a feature added to the loader must not
# silently invalidate every prior run's data identity, but a changed BAR must.
HASH_COLUMNS = ("open", "high", "low", "close", "volume")

# Fields without which a stored result cannot be attributed to anything. Each
# one has a test that removes it and asserts `attributable` flips to False.
REQUIRED_PATHS = (
    "runId",
    "code.commit",
    "strategy.key",
    "data.contentHash",
    "data.rows",
    "data.firstBar",
    "data.lastBar",
    "engine.configHash",
    "metrics",
    "stages",
)

# Values that mean "the caller did not say", as opposed to a real answer. Kept as
# a named set so a refusal can distinguish silence from a declaration.
UNDECLARED = "undeclared"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_json(obj: Any) -> str:
    """Stable hash of a JSON-able object. Sorted keys, no whitespace drift."""
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _git(*args: str) -> Optional[str]:
    try:
        out = subprocess.run(
            ("git",) + args, cwd=str(PROJECT_ROOT), capture_output=True,
            text=True, timeout=20, encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def collect_code_provenance() -> Dict[str, Any]:
    """Identify the code that produced a result.

    A DIRTY tree is recorded, not refused. Pre-live this repo is edited
    continuously and refusing every dirty run would make the record unusable --
    but the commit hash does not identify dirty code, so the flag and the file
    list are what a reader needs to know it is looking at something
    unreproducible.
    """
    commit = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain")
    dirty_files: List[str] = []
    if status:
        for line in status.splitlines():
            if len(line) > 3:
                dirty_files.append(line[3:].strip())

    info: Dict[str, Any] = {
        "commit": commit,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(dirty_files),
        "dirtyFileCount": len(dirty_files),
        # Truncated: a 200-file dirty tree should not dominate the record. The
        # count above is the honest measure; the list is a hint.
        "dirtyFiles": sorted(dirty_files)[:40],
        "pythonVersion": sys.version.split()[0],
        "platform": sys.platform,
        "machine": platform.node(),
        "user": _safe_user(),
        "cwd": os.getcwd(),
    }

    pkgs = {}
    for mod in ("pandas", "numpy", "optuna", "scikit-learn", "scipy"):
        try:
            from importlib.metadata import version

            pkgs[mod] = version(mod)
        except Exception:
            pkgs[mod] = None
    info["packages"] = pkgs
    return info


def _safe_user() -> Optional[str]:
    for fn in (getpass.getuser, socket.gethostname):
        try:
            return fn()
        except Exception:
            continue
    return None


def fingerprint_frame(df: pd.DataFrame) -> Dict[str, Any]:
    """Exact content fingerprint of the bars a run actually read.

    Measured on the real 3.6M-row NQ1 enriched frame: hashing the index plus five
    price/volume columns is 173 MB and 0.11s, so this is exact rather than
    sampled. A sampled fingerprint would agree on frames that differ.
    """
    if df is None or len(df) == 0:
        raise ValueError("cannot fingerprint an empty frame; a run with no bars "
                         "has no data identity to record")

    present = [c for c in HASH_COLUMNS if c in df.columns]
    if not present:
        raise ValueError(
            "frame has none of the price columns {}; refusing to record a data "
            "hash computed over nothing. Columns present: {}".format(
                list(HASH_COLUMNS), list(df.columns)[:20])
        )

    h = hashlib.sha256()
    # Index is hashed as UTC nanoseconds so an identical series carrying a
    # different tzinfo object still fingerprints identically -- the bars are the
    # same bars. The tz itself is recorded separately.
    idx = df.index
    if isinstance(idx, pd.DatetimeIndex) and idx.tz is not None:
        idx_vals = idx.tz_convert("UTC").tz_localize(None).values
    else:
        idx_vals = idx.values
    h.update(np.ascontiguousarray(idx_vals).tobytes())
    for c in present:
        h.update(np.ascontiguousarray(df[c].to_numpy(dtype="float64")).tobytes())

    tz = getattr(getattr(df, "index", None), "tz", None)
    return {
        "contentHash": "sha256:" + h.hexdigest(),
        "hashedColumns": present,
        "unhashedColumns": [c for c in df.columns if c not in present],
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "firstBar": str(df.index[0]),
        "lastBar": str(df.index[-1]),
        "tz": str(tz) if tz is not None else None,
        "barSecondsModal": _modal_bar_seconds(df),
        "hasDuplicateIndex": bool(df.index.duplicated().any()),
        "isMonotonic": bool(df.index.is_monotonic_increasing),
    }


def _modal_bar_seconds(df: pd.DataFrame) -> Optional[float]:
    if len(df.index) < 3 or not isinstance(df.index, pd.DatetimeIndex):
        return None
    diffs = np.diff(df.index.values[:5000]).astype("timedelta64[s]").astype(float)
    diffs = diffs[diffs > 0]
    if diffs.size == 0:
        return None
    return float(np.median(diffs))


def describe_engine(engine: Any) -> Dict[str, Any]:
    """Echo the execution assumptions actually resolved on the engine object.

    Read off the instance rather than restated by the caller, because a caller
    that restates the rule can restate it wrongly -- and the whole point of the
    record is that it reports what happened.
    """
    cfg = {
        "class": type(engine).__name__,
        "commission": getattr(engine, "commission", None),
        "slippagePct": getattr(engine, "slippage_pct", None),
        "accountSize": getattr(engine, "account_size", None),
        "maxSearchBars": 1440,
        # Recorded because it is a real comparability trap, not a curiosity:
        # VectorizedBacktester builds Sharpe from a per-BAR series that is zero
        # except at exit bars, so the number scales with frame length. A fold
        # Sharpe and an OOS Sharpe are not the same unit.
        "sharpeIsFrameLengthDependent": True,
    }
    cfg["configHash"] = _sha256_json({k: v for k, v in cfg.items() if k != "configHash"})
    return cfg


class _Stage:
    """One ordered step of a run. Records that it ran, how long, and its verdict."""

    def __init__(self, name: str):
        self.name = name
        self.started = _utcnow()
        self._t0 = time.time()
        self.status = "running"
        self.details: Dict[str, Any] = {}
        self.error: Optional[str] = None
        # Stopped when the stage EXITS, not when it is serialized. This read
        # `time.time() - self._t0` inside to_dict(), and since every stage is
        # serialized together at finalize, each one reported "my start until the
        # end of the whole run" -- measured once as load_data 181s / split 175s /
        # optimize 174s on a run whose split was instant. A duration field that
        # measures the wrong interval is worse than no duration field, because it
        # is the number someone optimises against.
        self._elapsed: Optional[float] = None

    def detail(self, **kw: Any) -> None:
        self.details.update(kw)

    def stop(self) -> None:
        if self._elapsed is None:
            self._elapsed = time.time() - self._t0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "startedAt": self.started,
            "durationSec": (round(self._elapsed, 3) if self._elapsed is not None
                            else None),
            "detail": self.details,
            "error": self.error,
        }


class RunRecord:
    """Accumulates provenance for one research run and writes it once, atomically."""

    def __init__(self, run_id: str, strategy_key: str, ticker: str,
                 ledger_path: Optional[Path] = None):
        if not run_id:
            raise ValueError("run_id is required")
        self.run_id = run_id
        self.started = _utcnow()
        self._t0 = time.time()
        self.ledger_path = Path(ledger_path) if ledger_path else DEFAULT_LEDGER

        self._doc: Dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "runId": run_id,
            "status": "running",
            "startedAt": self.started,
            "finishedAt": None,
            "durationSec": None,
            "code": collect_code_provenance(),
            "strategy": {"key": strategy_key, "name": None, "class": None,
                         "params": None, "paramGrid": None, "paramsHash": None},
            "data": None,
            "engine": None,
            "nt8Profile": None,
            "folds": None,
            "alignment": {},
            "metrics": {},
            "stages": [],
            "warnings": [],
            "refusals": [],
        }
        self._doc["ticker"] = ticker
        self._stages: List[_Stage] = []

        if self._doc["code"]["commit"] is None:
            self.warn("git provenance unavailable; `code.commit` is null and this "
                      "run cannot be attributed to any code state")
        elif self._doc["code"]["dirty"]:
            self.warn("working tree DIRTY at run time ({} files); `code.commit` "
                      "does not identify the code that ran".format(
                          self._doc["code"]["dirtyFileCount"]))

    # -- construction ---------------------------------------------------
    @classmethod
    def open(cls, run_id: str, strategy_key: str, ticker: str,
             ledger_path: Optional[Path] = None) -> "RunRecord":
        rec = cls(run_id, strategy_key, ticker, ledger_path)
        rec._append_ledger()  # a run that dies mid-way still leaves a trace
        return rec

    @staticmethod
    def new_run_id(ticker: str, strategy_key: str) -> str:
        """Unique per run, not per second.

        This was `%Y%m%d_%H%M%S` only, so two runs started inside the same second
        -- a sweep loop, or two shells -- received the SAME id, wrote to the same
        directory and overwrote each other's record. That is the exact failure
        the run-id'd output path was introduced to prevent, one granularity down.
        Caught by an acceptance test that launched two runs back to back.

        Milliseconds alone are not enough either: a tight loop can issue two ids
        inside one millisecond, so a random suffix carries the guarantee and the
        timestamp is there to keep directory listings sortable and readable.
        """
        now = datetime.now()
        return "RUN_{}_{:03d}_{}_{}_{}".format(
            now.strftime("%Y%m%d_%H%M%S"), now.microsecond // 1000,
            ticker, strategy_key.upper(), os.urandom(2).hex())

    # -- declarations ---------------------------------------------------
    def declare_strategy(self, *, name: Optional[str] = None,
                         cls_name: Optional[str] = None,
                         params: Optional[Dict[str, Any]] = None,
                         param_grid: Optional[Dict[str, Any]] = None) -> None:
        s = self._doc["strategy"]
        if name is not None:
            s["name"] = name
        if cls_name is not None:
            s["class"] = cls_name
        if params is not None:
            s["params"] = params
            s["paramsHash"] = _sha256_json(params)
        if param_grid is not None:
            s["paramGrid"] = {k: str(v) for k, v in param_grid.items()}
            s["paramGridHash"] = _sha256_json(s["paramGrid"])

    def declare_data(self, df: pd.DataFrame, *, ticker: str, loader: str,
                     adjustment: str = UNDECLARED,
                     source_files: Optional[List[str]] = None) -> None:
        """Fingerprint the bars, and require the price basis to be STATED.

        `adjustment` has no sensible default. Back-adjusted continuous futures
        and per-contract unadjusted prices are different price series, and the
        NT8 side inherited `MergeBackAdjusted` from a machine-wide global for an
        unknown length of time. Recording `undeclared` is honest; defaulting to
        `unadjusted` would manufacture a fact.
        """
        fp = fingerprint_frame(df)
        fp["ticker"] = ticker
        fp["loader"] = loader
        fp["adjustment"] = adjustment
        fp["sourceFiles"] = self._describe_sources(source_files or [])
        self._doc["data"] = fp

        if adjustment == UNDECLARED:
            self.warn("price adjustment basis UNDECLARED; this result cannot be "
                      "compared to an NT8 run whose GlobalMergePolicy is known")
        if fp["hasDuplicateIndex"]:
            self.warn("data index contains DUPLICATE timestamps ({} rows)".format(fp["rows"]))
        if not fp["isMonotonic"]:
            self.warn("data index is NOT monotonically increasing")

    @staticmethod
    def _describe_sources(paths: List[str]) -> List[Dict[str, Any]]:
        out = []
        for p in paths:
            try:
                st = os.stat(p)
                out.append({"path": str(p), "bytes": st.st_size,
                            "mtime": datetime.fromtimestamp(
                                st.st_mtime, timezone.utc).isoformat(timespec="seconds")})
            except OSError as exc:
                out.append({"path": str(p), "error": str(exc)})
        return out

    def declare_engine(self, engine: Any) -> None:
        self._doc["engine"] = describe_engine(engine)

    def declare_nt8_profile(self, profile_hash: Optional[str],
                            profile_path: Optional[str] = None) -> None:
        """Bind an NT8 Strategy Analyzer profile to this run.

        Legitimately absent for a Python-only run. An absent profile is NOT a
        refusal -- an inapplicable state is not an unreadable one -- but a
        run that CLAIMS NT8 parity without one is, and that is the caller's
        assertion to make via `require_nt8_profile()`.
        """
        self._doc["nt8Profile"] = ({"hash": profile_hash, "path": profile_path}
                                   if profile_hash else None)

    def require_nt8_profile(self) -> None:
        if not self._doc.get("nt8Profile"):
            self.refuse("run declares NT8 comparability but carries no profile hash")

    def declare_folds(self, folds: Any) -> None:
        """Record the exact evaluation geometry the objective was averaged over."""
        self._doc["folds"] = json.loads(json.dumps(folds, default=str))

    def record_alignment(self, stage: str, alignment: Optional[Dict[str, Any]]) -> None:
        """Store a `signal_alignment` report from VectorizedBacktester.

        This is the single most load-bearing thing here. Without it, a result
        computed from signals that never reached the frame they were scored on
        is indistinguishable from a real one -- which is exactly what happened.
        """
        if not alignment:
            self.warn("stage '{}' reported no signal_alignment; engine predates the "
                      "bounded aligner or returned a legacy metrics dict".format(stage))
            return
        self._doc["alignment"][stage] = alignment
        dropped = (int(alignment.get("dropped_before_frame_start", 0))
                   + int(alignment.get("dropped_snap_too_far", 0)))
        if alignment.get("dropped_before_frame_start"):
            self.refuse(
                "stage '{}': {} signal(s) predate the scored frame. Signals and "
                "frame are mismatched; the metrics are not measuring the strategy."
                .format(stage, alignment["dropped_before_frame_start"]))
        elif dropped:
            self.warn("stage '{}': {} signal(s) dropped in alignment".format(stage, dropped))

    def set_metrics(self, metrics: Dict[str, Any]) -> None:
        """Store scalar metrics only. Curves and trade frames are separate artifacts."""
        out: Dict[str, Any] = {}
        for k, v in (metrics or {}).items():
            if isinstance(v, (pd.Series, pd.DataFrame, dict, list)):
                continue
            # Integers stay integers: a trade COUNT rendered as 0.0 invites a
            # reader to treat a count as a rate.
            if isinstance(v, (bool, str)) or v is None:
                out[k] = v
            elif isinstance(v, (int, np.integer)):
                out[k] = int(v)
            elif isinstance(v, (float, np.floating)):
                out[k] = float(v)
            else:
                out[k] = str(v)
        self._doc["metrics"] = out

    def add_artifact(self, name: str, path: str) -> None:
        self._doc.setdefault("artifacts", {})[name] = str(path)

    # -- diagnostics ----------------------------------------------------
    def warn(self, msg: str) -> None:
        """Something a reader must know. Does not block attribution."""
        self._doc["warnings"].append(msg)

    def refuse(self, msg: str) -> None:
        """Something that makes the numbers not mean what they appear to mean."""
        self._doc["refusals"].append(msg)

    # -- stages ---------------------------------------------------------
    @contextmanager
    def stage(self, name: str):
        st = _Stage(name)
        self._stages.append(st)
        try:
            yield st
        except BaseException as exc:
            st.stop()
            st.status = "failed"
            st.error = "{}: {}".format(type(exc).__name__, exc)
            raise
        else:
            st.stop()
            st.status = "ok"

    # -- close ----------------------------------------------------------
    def _missing_required(self) -> List[str]:
        missing = []
        for path in REQUIRED_PATHS:
            node: Any = self._doc
            ok = True
            for part in path.split("."):
                if isinstance(node, dict) and part in node:
                    node = node[part]
                else:
                    ok = False
                    break
            # An empty dict/list is as unattributable as an absent key: `metrics`
            # present but {} tells a reader nothing.
            if not ok or node is None or node == {} or node == []:
                missing.append(path)
        return missing

    def attribution(self) -> Dict[str, Any]:
        """Would this record be attributable if closed now? Does NOT mutate.

        Exists so a caller can gate REPORTING on attribution before the record is
        closed -- otherwise the only orders available are "report then discover
        it was unreportable" or "close the record before it can name the report
        as one of its artifacts". Shares its logic with `finalize`, so the answer
        here and the answer there cannot drift apart.
        """
        # `stages` is rebuilt at finalize from the live stage list, so ask the
        # live list rather than the (still-empty) key.
        missing = [p for p in self._missing_required() if p != "stages"]
        if not self._stages:
            missing.append("stages")
        return {
            "attributable": (not missing) and not self._doc["refusals"],
            "missingRequired": missing,
            "refusals": list(self._doc["refusals"]),
        }

    def finalize(self, run_dir: Optional[str] = None, *,
                 status: str = "complete") -> Dict[str, Any]:
        for st in self._stages:
            if st.status == "running":
                st.status = "abandoned"
        self._doc["stages"] = [s.to_dict() for s in self._stages]
        self._doc["finishedAt"] = _utcnow()
        self._doc["durationSec"] = round(time.time() - self._t0, 3)

        missing = self._missing_required()
        for path in missing:
            self.refuse("required field missing or empty: {}".format(path))

        self._doc["missingRequired"] = missing
        self._doc["attributable"] = (not missing) and not self._doc["refusals"]
        self._doc["status"] = status

        if run_dir:
            self.write(Path(run_dir) / "run_record.json")
        self._append_ledger()
        return dict(self._doc)

    def fail(self, exc: BaseException, run_dir: Optional[str] = None) -> Dict[str, Any]:
        self.refuse("run raised {}: {}".format(type(exc).__name__, exc))
        return self.finalize(run_dir, status="failed")

    def write(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        # utf-8 explicitly: this repo's default console codec is cp1252 and a
        # non-ASCII value in a param or a path silently corrupts the record.
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(self._doc, fh, indent=2, sort_keys=False, default=str)
        os.replace(tmp, path)  # atomic: a half-written record must never be readable
        self.add_artifact("runRecord", str(path))
        return path

    def _append_ledger(self) -> None:
        """Append one line. Runs appear twice (open + close); readers take the last.

        Deliberately append-only. An arm that is abandoned or crashes must remain
        in the ledger, because a search whose failed candidates disappear cannot
        be corrected for multiple testing (plan phase 2.5 / 6.2).
        """
        d = self._doc
        data = d.get("data") or {}
        row = {
            "ts": _utcnow(),
            "runId": d["runId"],
            "status": d["status"],
            "attributable": d.get("attributable"),
            "ticker": d.get("ticker"),
            "strategyKey": (d.get("strategy") or {}).get("key"),
            "paramsHash": (d.get("strategy") or {}).get("paramsHash"),
            "commit": (d.get("code") or {}).get("commit"),
            "dirty": (d.get("code") or {}).get("dirty"),
            "dataHash": data.get("contentHash"),
            "dataRows": data.get("rows"),
            "adjustment": data.get("adjustment"),
            "engineHash": (d.get("engine") or {}).get("configHash"),
            "nt8ProfileHash": (d.get("nt8Profile") or {}).get("hash"),
            "sharpe": (d.get("metrics") or {}).get("sharpe_ratio"),
            "winRate": (d.get("metrics") or {}).get("win_rate_%"),
            "trades": (d.get("metrics") or {}).get("num_trades"),
            "nWarnings": len(d.get("warnings") or []),
            "nRefusals": len(d.get("refusals") or []),
            "durationSec": d.get("durationSec"),
        }
        try:
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.ledger_path, "a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(row, default=str) + "\n")
        except OSError as exc:
            # Never let bookkeeping kill a run, but never let it fail silently.
            self.warn("could not append to run ledger {}: {}".format(self.ledger_path, exc))

    # -- read side ------------------------------------------------------
    @property
    def doc(self) -> Dict[str, Any]:
        return dict(self._doc)


# The two engines disagree on what to call the trade count: VectorizedBacktester
# returns `num_trades`, NT8ParityBacktester returns `total_trades`. A caller
# asking "how many trades" therefore has to know which engine ran.
#
# This bit immediately. A zero-trade gate written as `metrics.get('num_trades',
# 0)` read 0 from an NT8ParityBacktester result and refused a run that had
# actually taken 38 trades at a 71% win rate. The default was the bug: absent
# and zero are different facts, and a gate that cannot tell them apart is a gate
# that fires on the wrong runs.
TRADE_COUNT_KEYS = ("num_trades", "total_trades", "trades")


def trade_count(metrics: Dict[str, Any]) -> int:
    """The trade count under whichever name the engine used.

    Raises when no known key is present, rather than returning 0. A caller that
    genuinely cannot find the count must not silently conclude there were none.
    """
    for k in TRADE_COUNT_KEYS:
        if k in (metrics or {}):
            return int(metrics[k])
    raise KeyError(
        "no trade-count key in metrics; looked for {}. Present keys: {}. "
        "Returning 0 here would make an unmeasurable run indistinguishable "
        "from a run that took no trades.".format(
            list(TRADE_COUNT_KEYS), sorted((metrics or {}).keys())[:20]))


def load_run_record(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def assert_attributable(record: Dict[str, Any]) -> None:
    """Gate for anything that reports a result. Refuses rather than rendering.

    A report built from a non-attributable record looks exactly like one built
    from a good record, which is how a broken run becomes a decision.
    """
    if record.get("attributable"):
        return
    lines = ["run {} is NOT attributable and must not be reported.".format(
        record.get("runId", "<unknown>"))]
    for r in record.get("refusals") or []:
        lines.append("  refusal: " + str(r))
    for m in record.get("missingRequired") or []:
        lines.append("  missing: " + str(m))
    raise ValueError("\n".join(lines))


def read_ledger(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Latest line per runId, in first-seen order.

    Earlier lines are kept on disk (a `running` line proves an arm existed) but
    collapsed here, because the current state of each arm is what a caller wants.
    """
    p = Path(path) if path else DEFAULT_LEDGER
    if not p.exists():
        return []
    latest: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            rid = row.get("runId")
            if rid is None:
                continue
            if rid not in latest:
                order.append(rid)
            latest[rid] = row
    return [latest[r] for r in order]
