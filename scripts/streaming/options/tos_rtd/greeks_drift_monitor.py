"""
Greeks Drift Monitor — compares TOS RTD native Greeks vs our BSM-computed Greeks.

Phase 4: Monitors model drift between exchange-quality Greeks from TOS and
our analytical BSM model. High drift (>5%) indicates our model assumptions
(risk-free rate, dividend yield, DTE calculation) need recalibration.

Can run standalone or be called from the pipeline via HybridCoordinator.

Usage::

    python -m scripts.streaming.options.tos_rtd.greeks_drift_monitor --symbol /ES --duration 30
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from .adapter import TOSRTDAdapter, RTDConfig
from .symbol_builder import OptionSymbolBuilder, parse_rtd_option_symbol

log = logging.getLogger(__name__)

# Drift threshold — above this, BSM model needs recalibration
DRIFT_THRESHOLD_PCT = 5.0


@dataclass
class DriftRecord:
    """Single Greeks drift comparison record."""

    rtd_symbol: str
    strike: float
    option_type: str
    rtd_gamma: Optional[float]
    bsm_gamma: Optional[float]
    drift_pct: Optional[float]
    rtd_oi: Optional[int]
    rtd_volume: Optional[int]
    timestamp: float = field(default_factory=time.time)

    @property
    def is_high_drift(self) -> bool:
        return self.drift_pct is not None and self.drift_pct > DRIFT_THRESHOLD_PCT


class GreeksDriftMonitor:
    """
    Monitors Greeks drift between TOS RTD and BSM model.

    In standalone mode, it subscribes to RTD and logs drift.
    In pipeline mode, it receives BSM Greeks from gex_calculator
    and compares against RTD native Greeks.
    """

    def __init__(self, threshold_pct: float = DRIFT_THRESHOLD_PCT):
        self.threshold_pct = threshold_pct
        self._records: list[DriftRecord] = []
        self._high_drift_count = 0

    def compare(
        self,
        rtd_greeks: dict[str, dict[str, float | int | None]],
        bsm_greeks: dict[float, dict[str, float]],
        base_symbol: str = "/ES",
    ) -> list[DriftRecord]:
        """
        Compare RTD native Greeks against BSM-computed Greeks.

        Args:
            rtd_greeks: {rtd_symbol: {GAMMA: ..., OPEN_INT: ..., VOLUME: ...}}
            bsm_greeks: {strike: {GAMMA: ..., DELTA: ...}}

        Returns:
            List of DriftRecord for contracts with both sources.
        """
        records: list[DriftRecord] = []

        for rtd_sym, rtd_data in rtd_greeks.items():
            parsed = parse_rtd_option_symbol(rtd_sym)
            if not parsed or parsed.base_symbol != base_symbol:
                continue

            rtd_gamma = rtd_data.get("GAMMA")
            bsm_data = bsm_greeks.get(parsed.strike, {})
            bsm_gamma = bsm_data.get("GAMMA")

            drift_pct = None
            if rtd_gamma is not None and bsm_gamma is not None and rtd_gamma != 0:
                drift_pct = abs(rtd_gamma - bsm_gamma) / abs(rtd_gamma) * 100.0

            record = DriftRecord(
                rtd_symbol=rtd_sym,
                strike=parsed.strike,
                option_type=parsed.option_type,
                rtd_gamma=rtd_gamma,
                bsm_gamma=bsm_gamma,
                drift_pct=drift_pct,
                rtd_oi=rtd_data.get("OPEN_INT"),
                rtd_volume=rtd_data.get("VOLUME"),
            )
            records.append(record)

            if record.is_high_drift:
                self._high_drift_count += 1
                log.warning(
                    "HIGH GAMMA DRIFT: %s strike=%.0f %s | RTD=%.6f BSM=%.6f drift=%.2f%%",
                    rtd_sym,
                    parsed.strike,
                    parsed.option_type,
                    rtd_gamma or 0,
                    bsm_gamma or 0,
                    drift_pct or 0,
                )

        self._records.extend(records)
        return records

    def get_summary(self) -> dict:
        """Get drift summary statistics."""
        drifts = [r.drift_pct for r in self._records if r.drift_pct is not None]
        if not drifts:
            return {
                "total_compared": len(self._records),
                "high_drift_count": 0,
                "avg_drift_pct": None,
                "max_drift_pct": None,
                "threshold_pct": self.threshold_pct,
            }

        return {
            "total_compared": len(self._records),
            "high_drift_count": sum(1 for d in drifts if d > self.threshold_pct),
            "avg_drift_pct": round(sum(drifts) / len(drifts), 4),
            "max_drift_pct": round(max(drifts), 4),
            "threshold_pct": self.threshold_pct,
        }

    def reset(self) -> None:
        """Clear accumulated records."""
        self._records.clear()
        self._high_drift_count = 0


def run_standalone_monitor(symbol: str, duration: int) -> None:
    """
    Run the drift monitor standalone — subscribes to RTD and logs
    native gamma values (without BSM comparison, just captures TOS Greeks).

    This is useful for validating that RTD is streaming meaningful Greeks
    during RTH.
    """
    print(f"\n=== Greeks Drift Monitor ({duration}s) ===")
    print(f"Symbol: {symbol}")
    print(f"Drift threshold: {DRIFT_THRESHOLD_PCT}%")
    print("Note: Standalone mode captures TOS native Greeks only.")
    print("      BSM comparison requires pipeline integration.\n")

    expiry = date.today() + timedelta(days=(4 - date.today().weekday()) % 7 or 7)
    config = RTDConfig(strike_range=10, strike_spacing=1.0)
    adapter = TOSRTDAdapter(config)

    try:
        # Phase 1: Get futures price
        adapter.start(symbols=[symbol], expiry=expiry)
        time.sleep(3)
        price = adapter.get_futures_price(symbol)
        print(f"{symbol} price: {price}")

        if not price:
            print("No price data — exiting")
            return

        # Phase 2: Restart with option symbols
        adapter.stop()
        time.sleep(1)
        adapter.start(symbols=[symbol], expiry=expiry, current_price={symbol: price})
        time.sleep(5)

        # Monitor loop
        for i in range(duration):
            snapshot = adapter.get_snapshot()
            option_count = sum(1 for k in snapshot if k.startswith("."))
            gamma_count = sum(1 for k in snapshot if k.endswith(":GAMMA") and snapshot[k] is not None and snapshot[k] != 0)
            oi_count = sum(1 for k in snapshot if k.endswith(":OPEN_INT") and snapshot[k] is not None and snapshot[k] != 0)

            print(f"[{i+1}s] {option_count} option keys | {gamma_count} non-zero gamma | {oi_count} non-zero OI")

            # Show sample Greeks
            if i % 5 == 0 and gamma_count > 0:
                print("  Sample Greeks:")
                shown = 0
                for key, val in sorted(snapshot.items()):
                    if key.endswith(":GAMMA") and val is not None and val != 0 and shown < 5:
                        sym_part = key.replace(":GAMMA", "")
                        oi = snapshot.get(f"{sym_part}:OPEN_INT")
                        vol = snapshot.get(f"{sym_part}:VOLUME")
                        print(f"    {sym_part}: gamma={val:.6f} OI={oi} VOL={vol}")
                        shown += 1

            time.sleep(1)

        # Final summary
        print("\n=== Final Summary ===")
        snapshot = adapter.get_snapshot()
        status = adapter.get_status()
        for k, v in status.items():
            print(f"  {k}: {v}")

    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        adapter.stop()
        print("\nDone")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    parser = argparse.ArgumentParser(description="TOS RTD Greeks Drift Monitor")
    parser.add_argument("--symbol", default="/ES", help="Futures symbol (default: /ES)")
    parser.add_argument("--duration", type=int, default=30, help="Monitor duration in seconds")
    parser.add_argument("--threshold", type=float, default=DRIFT_THRESHOLD_PCT, help="Drift threshold %%")
    args = parser.parse_args()

    run_standalone_monitor(args.symbol, args.duration)


if __name__ == "__main__":
    main()