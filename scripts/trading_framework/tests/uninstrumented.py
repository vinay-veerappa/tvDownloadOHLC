"""Strategies and bots that do not yet report the criteria they evaluate.

Recorded 2026-09-05 by measurement. Enforced by `test_instrumentation.py`.

WHY AN INVENTORY AND NOT A BLANKET RULE. Fifteen strategies are registered and
one is instrumented, so a rule that simply required instrumentation would fail
fourteen times and be switched off within a day. The pattern that has worked here
(`known_bot_divergences.py`) is a frozen population that can only SHRINK:

  * a strategy NOT on this list that emits no decision log FAILS
  * a strategy on this list that now emits one must lose its line
  * so the list is a debt register, and a NEW strategy is instrumented from the
    first commit because there is nowhere to add it

THAT LAST CLAUSE IS THE WHOLE POINT. "Built in by default" cannot mean a
convention, because the twelve bots that all inherit `RiskManagerBase` and then
hardcode their own flatten times are what a convention produces (tickets B1-B6).
It has to mean: the default path is the instrumented one, and the uninstrumented
path is a named, shrinking exception.

WHAT INSTRUMENTED MEANS, per side:

  Python  the hunter sets `self.last_decisions` (a `GateRecorder` frame).
          `HunterStrategyAdapter` forwards it, so the check is behavioural --
          call `hunt()` and look -- not a source scan for the class name.

  C#      the bot derives from `GovernedStrategy`, which SEALS
          `CheckForSignal()` and computes the verdict from the declared gates.
          Deriving is therefore sufficient: there is no path by which a
          `GovernedStrategy` subclass can act on an unlogged criterion.
"""

# ---------------------------------------------------------------------------- #
# Python hunters
# ---------------------------------------------------------------------------- #

#: Registry keys whose hunter does not set `last_decisions` yet.
#: `mean_reversion` is deliberately absent -- it is the reference implementation
#: (STRATEGY_WORKFLOW.md section 5.5) and instrumenting it is what revealed that
#: `first_signal_of_day` blocks 99.2% of its setups.
#: MEASURED from the registry, not hand-listed -- the first version of this set
#: named `nine_thirty_breakout`, `measured_move`, `the_strat` and
#: `initial_balance_break`, none of which are registry keys, and
#: `vwap_institutional` (which is) was missing. Four exemptions for nothing plus
#: one strategy silently un-exempted. `test_every_inventoried_hunter_is_a_real_
#: registry_key` is what caught it.
UNINSTRUMENTED_HUNTERS = {
    "box_reversion",
    "ema_pullback",
    "failed_auction",
    "ib_pullback",
    "ict_asia_volatility",
    "ict_displacement",
    "ict_fvg_cisd_rejection",
    "ict_fvg_rejection",
    "ict_liquidity_sweep",
    "ict_ny_session",
    "ifvg_cisd",
    "six_am_reversal",
    "vwap_institutional",
    "vwap_reclaim",
}

# ---------------------------------------------------------------------------- #
# C# bots
# ---------------------------------------------------------------------------- #

#: Bot source files that do not derive from `GovernedStrategy` yet.
#:
#: Ten of these derive from `RiskManagerBase` directly, three from
#: `IBStrategyBase` (which derives from `IntradayStrategyBase`, owned by
#: nt8-riskguard). Migration is ticket B8 and needs a recompile, which is the
#: user's call -- so this list starts as the full population by design, and
#: shrinking it is the work rather than a precondition for it.
UNINSTRUMENTED_BOTS = {
    "scripts/ninjatrader/strategies/bandits_8020/Bandits8020Bot.cs",
    "scripts/ninjatrader/strategies/ib_breakout/IBBreakoutBot.cs",
    "scripts/ninjatrader/strategies/ib_breakout/IBFadeBot.cs",
    "scripts/ninjatrader/strategies/ib_breakout/IBRetestBot.cs",
    "scripts/ninjatrader/strategies/ib_breakout/IBStrategyBase.cs",
    "scripts/ninjatrader/strategies/ifvg_cisd/ICTFVGCISDBot.cs",
    "scripts/ninjatrader/strategies/the_strat/Strat212ContinuationBot.cs",
    "scripts/ninjatrader/strategies/the_strat/Strat22RevStratBot.cs",
}

#: The base classes a bot may derive from while still counting as uninstrumented.
#: Named so the test can tell "not yet migrated" from "derives from something
#: nobody has heard of", which is a different problem needing a different answer.
LEGACY_BOT_BASES = {"RiskManagerBase", "IBStrategyBase", "IntradayStrategyBase"}
