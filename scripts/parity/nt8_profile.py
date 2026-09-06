r"""Load the frozen NT8 backtest profile, hash it, and build a bridge request.

See docs/architecture/STRATEGY_WORKFLOW.md section 5.2 (the frozen profile).

The contract with the bridge is declare -> echo -> refuse:

  * `params`         are APPLIED to StrategyTemplate and read back. A field that does
                     not take refuses the run rather than substituting a value.
  * `requireGlobals` are ASSERTED against NinjaTrader.Core.Globals.MarketDataOptions.
                     They are GLOBAL to the machine (NT8 Settings -> Market data), so
                     the bridge will not write them; a mismatch refuses and says what
                     to change.
  * `profileHash`    is echoed into the result so a stored artifact names the profile
                     it actually ran under.

The hash covers ONLY the fields that change behaviour. Comment keys (`_comment`,
`_fieldNotes`) are excluded, so editing the prose does not invalidate historical
results - and conversely, changing any real field DOES, which is the point.

Run standalone to print the profile and its hash:
  .venv\Scripts\python.exe -m scripts.parity.nt8_profile
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

PROFILE_PATH = Path(__file__).resolve().parent / "backtest_profile.json"

# Keys that carry prose rather than configuration. Excluded from the hash so a comment
# edit does not orphan every result recorded before it.
_NON_BEHAVIOURAL = ("_comment", "_fieldNotes")

#: NT8 refuses OrderFillResolution=High on a MULTI-series strategy ("program
#: directly into your strategy the more granular resolution"). The three keys
#: describe the ANALYZER's fill series, so they are meaningless the moment the
#: strategy adds its own -- the SA dialog aborts and the capture returns 0
#: trades that reads as "the strategy does not trade". A bot that calls
#: AddDataSeries anywhere in its real source (comments stripped, so a
#: docstring mentioning the method is not a false positive) gets these keys
#: dropped, and the recorded profileHash describes the profile AS SENT.
ORDER_FILL_KEYS = (
    "OrderFillResolution",
    "OrderFillResolutionType",
    "OrderFillResolutionValue",
)
#: Matches a real call, not a mention: `AddDataSeries(` at the start of an
#: expression. `BarsPeriodType` in the same statement is how every live call
#: writes it; keeping the type qualifier in the pattern is what stops
#: `// AddDataSeries(...) explained in prose` from matching once comments are
#: gone -- a bare method name still can, which is why the qualifier rides along.
_ADD_SERIES = re.compile(r"AddDataSeries\s*\(\s*BarsPeriodType")


def strategy_adds_series(source: str) -> bool:
    """Does this C# source call AddDataSeries(BarsPeriodType...) for real?

    Line and block comments are stripped first: the B9 comments in
    BBMRReversionBot and ICTFVGCISDBot say `AddDataSeries` in prose twice per
    bot, and a substring check would call a single-series bot multi-series,
    silently dropping the profile's fill-resolution keys.
    """
    code = re.sub(r"//[^\n]*", "", source)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    return bool(_ADD_SERIES.search(code))


def effective_profile(profile: Dict[str, Any], strategy_source: Optional[str] = None,
                      strategy_source_path: Optional[str] = None) -> Dict[str, Any]:
    """The profile AS IT WILL BE SENT for one strategy.

    A strategy that programs its own series cannot also take the analyzer's
    OrderFillResolution keys, so they are dropped and the result is what
    `profile_hash` should describe -- recording the unsuppressed hash against a
    run that ran without those keys would attribute evidence to a profile it
    did not run under.
    """
    if strategy_source is None and strategy_source_path:
        with open(strategy_source_path, encoding="utf-8") as fh:
            strategy_source = fh.read()
    if strategy_source is None or not strategy_adds_series(strategy_source):
        return profile
    out = dict(profile)
    template = dict(out.get("strategyTemplate") or {})
    dropped = [k for k in ORDER_FILL_KEYS if k in template]
    for k in dropped:
        del template[k]
    if dropped:
        notes = list(out.get("_nonBehaviouralNotes") or [])
        notes.append(
            "OrderFillResolution/Type/Value suppressed for this strategy: it "
            "calls AddDataSeries(BarsPeriodType...), and NT8 refuses the "
            "analyzer's fill series on a multi-series strategy. The strategy "
            "programs its own resolution (B9).")
        out["_nonBehaviouralNotes"] = notes
        out["strategyTemplate"] = template
    return out


def load_profile(path: Path | str | None = None) -> Dict[str, Any]:
    p = Path(path) if path else PROFILE_PATH
    if not p.exists():
        raise FileNotFoundError(f"NT8 backtest profile not found: {p}")
    with p.open(encoding="utf-8") as fh:
        profile = json.load(fh)

    for required in ("strategyTemplate", "requireGlobals"):
        if required not in profile:
            raise ValueError(f"{p} is missing required key '{required}'")
    return profile


def behavioural_subset(profile: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in profile.items() if k not in _NON_BEHAVIOURAL}


def profile_hash(profile: Dict[str, Any]) -> str:
    """Stable hash of the behavioural fields.

    `sort_keys` and a fixed separator make this independent of key order and
    whitespace, so a reformat does not change the hash while a value change does.
    """
    canonical = json.dumps(
        behavioural_subset(profile), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def build_request(
    strategy: str,
    symbol: str,
    date_from: str,
    date_to: str,
    *,
    period: str = "Minute",
    period_value: int = 1,
    max_trades: int = 2000,
    timeout_sec: int = 420,
    extra_params: Dict[str, Any] | None = None,
    profile: Dict[str, Any] | None = None,
    strategy_source: Optional[str] = None,
    strategy_source_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble a /api/backtest body with the profile applied and pinned.

    `extra_params` are strategy-specific inputs. They are merged AFTER the profile, but
    a collision raises instead of silently winning: a strategy input that shadows a
    profile field would mean the run used a configuration the hash claims it did not.

    `strategy_source` (or its path) is the C# source of the strategy being run.
    When it calls AddDataSeries(BarsPeriodType...) the analyzer's
    OrderFillResolution keys are dropped -- NT8 refuses them on a multi-series
    strategy -- and the request's profileHash describes the profile AS SENT.
    """
    prof = profile if profile is not None else load_profile()
    prof = effective_profile(prof, strategy_source=strategy_source,
                             strategy_source_path=strategy_source_path)
    params: Dict[str, Any] = dict(prof["strategyTemplate"])

    if extra_params:
        clash = sorted(set(extra_params) & set(params))
        if clash:
            raise ValueError(
                "strategy params collide with frozen profile fields: "
                + ", ".join(clash)
                + ". The profile hash would no longer describe the run. Rename the "
                "strategy input, or change the profile deliberately."
            )
        params.update(extra_params)

    return {
        "strategy": strategy,
        "symbol": symbol,
        "period": period,
        "periodValue": period_value,
        "from": date_from,
        "to": date_to,
        "maxTrades": max_trades,
        "timeoutSec": timeout_sec,
        "params": params,
        "requireGlobals": prof["requireGlobals"],
        "profileHash": profile_hash(prof),
    }


def main() -> int:
    prof = load_profile()
    print(f"profile: {PROFILE_PATH}")
    print(f"version: {prof.get('profileVersion')}")
    print(f"hash:    {profile_hash(prof)}\n")
    print("strategyTemplate (applied + read back):")
    for k, v in sorted(prof["strategyTemplate"].items()):
        print(f"  {k:<32} = {v}")
    print("\nrequireGlobals (asserted only, NOT written):")
    for k, v in sorted(prof["requireGlobals"].items()):
        print(f"  {k:<32} = {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
