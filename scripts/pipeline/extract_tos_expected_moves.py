"""
Daily Analysis Pipeline Integration: ThinkorSwim Expected Moves Fetcher
========================================================================
Extracts exact ThinkorSwim platform Expected Moves from Desktop or Web, and
saves them to the project data directories.

Usage:
  python -m scripts.pipeline.extract_tos_expected_moves --tickers SPX /NQ AAPL
  python -m scripts.pipeline.extract_tos_expected_moves --tickers SPY --maximize
  python -m scripts.pipeline.extract_tos_expected_moves --tickers SPY --log-feature nav=trace
  python -m scripts.pipeline.extract_tos_expected_moves --source web --tickers SPX

Desktop-only options (--maximize, --account-mode, --isolated, --capture,
--password-mode, and the --log-* family) are ignored for --source web.

Exit codes:
  0  every requested ticker produced expiration data
  1  the run failed outright
  2  the run completed but one or more tickers produced no data
"""

__build__ = "2026-08-02.11"

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

PACKAGE_ROOT = WORKSPACE_ROOT / "tos-ui-mcp"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

_DATA_DIR_DEFAULT = "data/expected_moves"

# Every default below comes from tos_config.json. Edit that file rather than
# passing flags; flags still win when given.
try:
    from tos_ui_mcp.tos_config import config
except ImportError:
    try:
        from tos_config import config
    except ImportError:
        config = None


def _cfg(dotted: str, fallback):
    return config.get(dotted, fallback) if config else fallback


DEFAULT_TICKERS = (config.tickers() if config else ["SPX", "/NQ", "AAPL", "NVDA"])

DATA_OUTPUT_DIR = (config.resolve_path("output.data_dir", _DATA_DIR_DEFAULT,
                                       WORKSPACE_ROOT)
                   if config else WORKSPACE_ROOT / _DATA_DIR_DEFAULT)
DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Logging is configured here so it covers the whole pipeline run, not just the
# extractor's __main__ block.
# ---------------------------------------------------------------------------
def configure_logging(args) -> Path | None:
    try:
        from tos_ui_mcp import tos_logging as TL
    except ImportError:
        try:
            import tos_logging as TL
        except ImportError:
            return None

    cfg_log = config.logging_kwargs(WORKSPACE_ROOT) if config else {}
    log_path = TL.configure(
        console_level=args.log_level or cfg_log.get("console_level"),
        file_level=args.log_file_level or cfg_log.get("file_level"),
        features=(",".join(args.log_feature) if args.log_feature
                  else cfg_log.get("features")),
        log_file=(False if args.no_log_file
                  else (args.log_file or cfg_log.get("log_file"))),
        log_dir=args.log_dir or cfg_log.get("log_dir"),
        header={
            "pipeline": Path(__file__).name,
            "source": args.source,
            "tickers": " ".join(args.tickers or DEFAULT_TICKERS),
            "argv": " ".join(sys.argv[1:]),
        })
    TL.install_excepthook()
    return log_path


# Symbols whose absence means desktop_extractor.py is a stale copy. Failing here
# with a clear message beats a NameError from deep inside a live TOS session.
_REQUIRED_EXTRACTOR_SYMBOLS = (
    "extract_desktop_expected_moves", "tos_windows", "log_tos_windows",
    "classify_tos_window", "find_tos_main_dashboard_window",
    "intelligent_ocr_launch_and_login", "navigate_to_symbol", "ensure_trade_tab",
    "_run_tickers",
)


def _check_extractor(mod) -> list:
    return [s for s in _REQUIRED_EXTRACTOR_SYMBOLS if not hasattr(mod, s)]


def _print_builds():
    """Print every module build so a mismatch is obvious in the log."""
    mods = {}
    for name in ("tos_logging", "tos_config", "tos_hotkeys", "tos_winput",
                 "tos_desktop_session", "desktop_extractor"):
        try:
            m = __import__(f"tos_ui_mcp.{name}", fromlist=[name])
            mods[name] = getattr(m, "__build__", "<no stamp>")
        except Exception as e:
            mods[name] = f"<not importable: {type(e).__name__}>"
    mods["pipeline"] = __build__
    distinct = {v for v in mods.values() if not v.startswith("<")}
    print("[PIPELINE] module builds: "
          + ", ".join(f"{k}={v}" for k, v in mods.items()))
    if len(distinct) > 1:
        print("[PIPELINE] !! BUILD MISMATCH — at least one file is a stale copy.")
        print("[PIPELINE] !! Run: python tos_verify.py   (in tos-ui-mcp/tos_ui_mcp)")
    return mods


def fetch_pipeline_expected_moves(source: str = "desktop",
                                  tickers: list[str] | None = None,
                                  *,
                                  maximize: bool = False,
                                  account_mode: str = "paper",
                                  password_mode: str = "type",
                                  capture: str = "screen",
                                  isolated: str | None = None,
                                  headless: bool = True,
                                  save: bool = True):
    if tickers is None:
        tickers = list(DEFAULT_TICKERS)

    print(f"[PIPELINE] ThinkorSwim Expected Move Fetcher "
          f"(source={source.upper()}, tickers={' '.join(tickers)})")

    if source.lower() == "desktop":
        _print_builds()
        from tos_ui_mcp import desktop_extractor as _EX
        missing = _check_extractor(_EX)
        if missing:
            msg = ("desktop_extractor.py is a STALE copy — missing: "
                   + ", ".join(missing)
                   + ". Re-copy it, delete __pycache__, then run tos_verify.py.")
            print(f"[PIPELINE-ERROR] {msg}")
            return {"status": "error", "message": msg}
        extract_desktop_expected_moves = _EX.extract_desktop_expected_moves
        try:
            from tos_ui_mcp import tos_winput as W
            W.CAPTURE_MODE = capture
        except Exception:
            pass
        results = extract_desktop_expected_moves(
            tickers=tickers,
            save_json=False,
            maximize=maximize,
            account_mode=account_mode,
            password_mode=password_mode,
            isolated_desktop=isolated,
        )
    else:
        import asyncio
        from tos_ui_mcp.extractor import extract_tos_ui_expected_moves
        results = asyncio.run(extract_tos_ui_expected_moves(
            tickers=tickers, headless=headless, save_json=False))

    if results.get("status") == "error":
        print(f"[PIPELINE-ERROR] Extraction failed: {results.get('message')}")
        return results

    if save:
        today_str = datetime.now().strftime("%Y-%m-%d")
        out_file = DATA_OUTPUT_DIR / f"tos_expected_moves_{today_str}.json"
        latest_file = DATA_OUTPUT_DIR / "latest_tos_expected_moves.json"
        for path in (out_file, latest_file):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)
        print(f"\n[PIPELINE-SUCCESS] Saved to:\n  - {out_file}\n  - {latest_file}")

    print_briefing(results)
    return results


def print_briefing(results: dict):
    today_str = datetime.now().strftime("%Y-%m-%d")
    tickers = results.get("tickers", {}) or {}

    print("\n" + "=" * 74)
    print(f" THINKORSWIM EXPECTED MOVES BRIEFING ({today_str})")
    mode = results.get("detected_account_mode") or results.get("account_mode")
    if mode:
        print(f" account mode: {mode}"
              + (f"   (requested: {results['requested_account_mode']})"
                 if results.get("requested_account_mode") not in (None, mode) else ""))
    print("=" * 74)

    ok, failed = [], []
    for symbol, data in tickers.items():
        expirations = data.get("expirations") or []
        price = data.get("last_price")
        error = data.get("error")

        if not expirations:
            failed.append(symbol)
            reason = error or "no expiration rows parsed"
            print(f" [{symbol}] NO DATA — {reason}")
            continue

        ok.append(symbol)
        front = expirations[0]
        em = front.get("expected_move")
        iv = front.get("iv_pct")
        dte = front.get("dte")
        expiry = front.get("expiry")

        price_txt = f"${price:,.2f}" if isinstance(price, (int, float)) else "unknown"
        print(f" [{symbol}] Price: {price_txt} | Front Expiry: {expiry} ({dte} DTE)"
              f" | IV: {iv}%")

        if isinstance(price, (int, float)) and isinstance(em, (int, float)):
            print(f"      Expected Move: ±{em}  ==> Range: "
                  f"[ ${price - em:,.2f}  to  ${price + em:,.2f} ]")
        elif isinstance(em, (int, float)):
            print(f"      Expected Move: ±{em}  (no price, cannot compute range)")

    print("=" * 74)
    print(f" {len(ok)} of {len(tickers)} ticker(s) returned data"
          + (f" | missing: {', '.join(failed)}" if failed else ""))

    try:
        from tos_ui_mcp import tos_logging as TL
        if TL.log_path():
            print(f" full trace log: {TL.log_path()}")
    except Exception:
        pass
    print("=" * 74)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Pipeline Expected Moves Fetcher",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--config", default=None,
                   help="path to a tos_config.json to use instead of the default")
    p.add_argument("--show-config", action="store_true",
                   help="print the resolved configuration and exit")
    p.add_argument("--source", choices=["desktop", "web"],
                   default=_cfg("source", "desktop"))
    p.add_argument("--tickers", nargs="+", default=None,
                   help=f"default from config: {' '.join(DEFAULT_TICKERS)}")
    p.add_argument("--ticker-set", default=None, metavar="NAME",
                   help="use a named set from config.ticker_sets: "
                        + ", ".join(sorted((config.ticker_sets() if config else {}))))
    p.add_argument("--no-save", action="store_true",
                   help="run and print the briefing without writing data files")

    d = p.add_argument_group("desktop options")
    d.add_argument("--maximize", action=argparse.BooleanOptionalAction,
                   default=_cfg("desktop.maximize", True),
                   help="maximise the TOS window first; prevents the option-chain "
                        "IV/expected-move column being clipped on a narrow window")
    d.add_argument("--account-mode", choices=["paper", "live"],
                   default=_cfg("desktop.account_mode", "paper"))
    d.add_argument("--password-mode", choices=["type", "paste", "both"],
                   default=_cfg("desktop.password_mode", "type"))
    d.add_argument("--capture", choices=["screen", "printwindow"],
                   default=_cfg("desktop.capture", "screen"),
                   help="printwindow renders the window offscreen, so it does not "
                        "need to be raised over what you are doing")
    d.add_argument("--isolated", nargs="?",
                   const=_cfg("desktop.isolated_desktop_name", "tos_bg"),
                   default=_cfg("desktop.isolated", None),
                   metavar="DESKTOP_NAME",
                   help="run TOS on a separate Windows desktop so automation does "
                        "not take over your mouse and keyboard (experimental)")

    w = p.add_argument_group("web options")
    w.add_argument("--no-headless", action="store_true",
                   default=not _cfg("web.headless", True))

    l = p.add_argument_group("logging")
    l.add_argument("--log-level", default=None,
                   help="console level: trace|debug|info|warn|error|off")
    l.add_argument("--log-file-level", default=None, help="log-file level")
    l.add_argument("--log-feature", action="append", default=[], metavar="NAME=LEVEL",
                   help="per-feature level, repeatable (e.g. nav=trace, capture=off)")
    l.add_argument("--log-file", default=None)
    l.add_argument("--log-dir", default=None)
    l.add_argument("--no-log-file", action="store_true")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.config and config:
        config.load(Path(args.config))

    configure_logging(args)

    if args.show_config:
        if config:
            print(config.describe())
        else:
            print("tos_config module unavailable")
        return 0

    tickers = args.tickers
    if tickers is None:
        tickers = (config.tickers(args.ticker_set) if config
                   else list(DEFAULT_TICKERS))
    print(f"[PIPELINE] tickers: {' '.join(tickers)}"
          + (f"  (set: {args.ticker_set})" if args.ticker_set else "")
          + (f"  (config: {config.path.name})" if config and config.path else ""))

    results = fetch_pipeline_expected_moves(
        source=args.source,
        tickers=tickers,
        maximize=args.maximize,
        account_mode=args.account_mode,
        password_mode=args.password_mode,
        capture=args.capture,
        isolated=args.isolated,
        headless=not args.no_headless,
        save=not args.no_save,
    )

    if results.get("status") == "error":
        return 1
    tickers = results.get("tickers", {}) or {}
    if not tickers:
        return 1
    if any(not (d.get("expirations") or []) for d in tickers.values()):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
