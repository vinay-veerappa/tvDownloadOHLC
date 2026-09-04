#!/usr/bin/env python3
"""
Generator: configs/strategies/ifvg_cisd.yaml -> IfvgCisdConfig.cs

The manifest is the SINGLE SOURCE OF TRUTH for every default shared between
the Python engine and the C# NT8 bot/indicator. This tool regenerates the
C# projection (a static class both NinjaScript types read at SetDefaults /
State.Configure time) and refuses to let the projection drift from the
manifest.

Usage:
    python scripts/utils/gen_ifvg_cisd_config.py            # regenerate
    python scripts/utils/gen_ifvg_cisd_config.py --verify  # drift gate (CI)

Exit codes: 0 ok, 1 drift (verify), 2 error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "configs" / "strategies" / "ifvg_cisd.yaml"
TARGET = REPO_ROOT / "scripts" / "ninjatrader" / "indicators" / "ifvg_cisd" / "IfvgCisdConfig.cs"

# Field name -> manifest path
_FIELDS = [
    ("EarliestEntryHHMM", ("session", "earliest_entry_hhmm"), "int"),
    ("LatestEntryHHMM", ("session", "latest_entry_hhmm"), "int"),
    ("FlattenByHHMM", ("session", "flatten_by_hhmm"), "int"),
    ("LunchFilterEnabled", ("session", "lunch_filter_enabled"), "bool"),
    ("LunchStartHHMM", ("session", "lunch_start_hhmm"), "int"),
    ("LunchEndHHMM", ("session", "lunch_end_hhmm"), "int"),
    ("MinRiskBps", ("risk", "min_risk_bps"), "double"),
    ("MaxRiskBps", ("risk", "max_risk_bps"), "double"),
    ("StopLossType", ("risk", "stop_loss_type"), "string"),
    ("StopLossBps", ("risk", "stop_loss_bps"), "double"),
    ("QueenTargetBps", ("risk", "queen_target_bps"), "double"),
    ("RunnerTargetBps", ("risk", "runner_target_bps"), "double"),
    ("HtfResampleMinutes", ("structure", "_htf_resample_minutes",), "int"),
    ("Variant", ("structure", "variant"), "string"),
    ("EntryMechanism", ("structure", "entry_mechanism"), "string"),
    ("RequireDirectionalCandle", ("structure", "require_directional_candle"), "bool"),
    ("IncludeVi", ("structure", "include_vi"), "bool"),
    ("StrictIfvgOnly", ("structure", "strict_ifvg_only"), "bool"),
    ("AtrRiskMult", ("structure", "atr_risk_mult"), "double"),
    ("CisdScanMaxBars", ("structure", "cisd_scan_max_bars"), "int"),
    ("MaxTradesPerDay", ("gates", "max_trades_per_day"), "int"),
    ("UseHtfFilter", ("gates", "use_htf_filter"), "bool"),
    ("HtfEmaPeriod", ("gates", "htf_ema_period"), "int"),
    ("RequireExternalSweep", ("gates", "require_external_sweep"), "bool"),
    ("EnableMidlineReclaims", ("gates", "enable_midline_reclaims"), "bool"),
    ("EnableConfirmedReentry", ("gates", "enable_confirmed_reentry"), "bool"),
    ("ReentryWindowBars", ("gates", "reentry_window_bars"), "int"),
    ("EodFlattenHHMM", ("sim", "eod_flatten_hhmm"), "int"),
    ("CommissionPerContract", ("sim", "commission_per_contract"), "double"),
    ("SlippageTicks", ("sim", "slippage_ticks"), "int"),
]

_VARIANT_TO_INT = {"baseline": 0, "variant1": 1, "variant2": 2}
_ENTRY_TO_INT = {"market": 0, "cisd_limit": 1}
_STOP_TYPE_TO_ENUM = {
    "bps_stat": "BpsStat",
    "structural": "Structural",
    "structural_capped_bps": "StructuralCappedBps",
    "skip_if_out_of_band": "SkipIfOutOfBand",
}


def _fmt_literal(kind: str, value) -> str:
    if kind == "bool":
        return "true" if value else "false"
    if kind == "int":
        return str(int(value))
    if kind == "double":
        return f"{float(value):G}d"
    return f'"{value}"'


def _resolve(manifest: dict, path: tuple):
    """Resolve a manifest field, allowing synthetic derived fields (_ prefix)."""
    if path[1].startswith("_"):
        # synthetic derived value
        if path[1] == "_htf_resample_minutes":
            raw = manifest["structure"]["htf_resample"]  # e.g. "5min"
            return int("".join(ch for ch in raw if ch.isdigit()))
        raise KeyError(path)
    node = manifest
    for seg in path:
        node = node[seg]
    return node


def render(manifest: dict) -> str:
    lines = [
        "// =============================================================================",
        "// IfvgCisdConfig.cs — AUTO-GENERATED. DO NOT EDIT BY HAND.",
        "// Source of truth: configs/strategies/ifvg_cisd.yaml",
        "// Regenerate:  python scripts/utils/gen_ifvg_cisd_config.py",
        "// Verify:      python scripts/utils/gen_ifvg_cisd_config.py --verify",
        "// A hand-edited value here that disagrees with the manifest is a defect.",
        "// =============================================================================",
        "namespace NinjaTrader.NinjaScript.Indicators.Vinay",
        "{",
        "    public static class IfvgCisdConfig",
        "    {",
    ]
    for name, path, kind in _FIELDS:
        val = _resolve(manifest, path)
        if name == "Variant":
            lines.append(f"        public const int Variant = {_VARIANT_TO_INT[val]};  // {val}")
        elif name == "EntryMechanism":
            lines.append(f"        public const int EntryMode = {_ENTRY_TO_INT[val]};  // {val}")
        elif name == "StopLossType":
            lines.append(
                f"        public const string StopLossTypeName = \"{_STOP_TYPE_TO_ENUM[val]}\";  // manifest: {val}"
            )
        else:
            lines.append(f"        public const {kind} {name} = {_fmt_literal(kind, val)};")
    lines += [
        "",
        "        // int projection of the stop-loss type for strategy params",
        "        public const int StopLossTypeId = "
        + str(
            ["bps_stat", "structural", "structural_capped_bps", "skip_if_out_of_band"].index(
                manifest["risk"]["stop_loss_type"]
            )
        )
        + ";  // 0=BpsStat 1=Structural 2=StructuralCappedBps 3=SkipIfOutOfBand",
        "    }",
        "}",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Fail (exit 1) if target has drifted.")
    args = parser.parse_args()

    if not MANIFEST.exists():
        print(f"[ERROR] manifest missing: {MANIFEST}", file=sys.stderr)
        return 2
    with open(MANIFEST, "r", encoding="utf-8") as fh:
        manifest = yaml.safe_load(fh)

    content = render(manifest)

    if args.verify:
        if not TARGET.exists():
            print(f"[DRIFT] target missing: {TARGET}")
            return 1
        current = TARGET.read_text(encoding="utf-8")
        if current.replace("\r\n", "\n").strip() != content.strip():
            print("[DRIFT] IfvgCisdConfig.cs disagrees with the manifest.")
            print("        Run: python scripts/utils/gen_ifvg_cisd_config.py")
            return 1
        print("[OK] IfvgCisdConfig.cs matches manifest.")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with open(TARGET, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(content)
    print(f"[GEN] wrote {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())