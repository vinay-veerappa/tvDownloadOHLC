"""Every C# bot whose execution defaults differ from the frozen document.

Recorded 2026-09-05 by measurement. Enforced by `test_bot_defaults.py`.

WHAT IS AND IS NOT INVARIANT -- a correction to the first version of this file.
`lastEntryEt` and `flattenByEt` INTERACT WITH THE SESSION A STRATEGY TRADES. A
deliberate NY_PM strategy must be allowed to enter after 14:30, so a global
freeze at 14:30 would forbid a legitimate setup. BBMRReversionBot is exactly that
case and its own source says so: "// Time -- NY_PM only (matches Python v3:
13:30-16:00)". Those three fields are therefore listed as `overridable` in
trading_defaults.json, and this inventory records the spread rather than
condemning it.

ONE RULE HAS NO EXEMPTIONS: ADR-020's 16:00 ET hard exit. A position held past it
can liquidate a prop account, so `test_no_bot_exits_later_than_the_adr_020_hard_limit`
fails whatever is recorded here. It found one violation --
BBMRReversionBot flattened at 16:15 -- which was fixed rather than inventoried.

WHAT THIS INVENTORY IS FOR. Twelve bots carried five different flatten times and
six different daily trade caps, every one hand-set, and nothing compared them to
the Python engine that predicts their trades. The spread is the problem; the
inventory freezes it so it cannot grow while the normalisation (section 11, item
10) proceeds strategy by strategy.

  * a bot NOT here that differs from the frozen defaults FAILS
  * a bot here whose values CHANGE fails, so a value can only move toward frozen
  * a bot here that now AGREES must lose its line

B1 CLOSED 2026-09-05: BBMRReversionBot no longer declares MaxTradesPerDay (the
trade-ordinal report measured every trade at ordinal 1, so there is no sample for
a cap and it refuses to suggest one), and the Python engine runs uncapped too --
the pair is comparable at the trade-set layer again. Its remaining divergence is
the overridable flattenByEt (1600 vs frozen 1545), deliberate for its NY_PM
window and recorded as spread, not condemned.
"""

# path -> (FlattenBy, MaxTradesPerDay, LatestEntry). None = not declared.
KNOWN_DIVERGENCES = {
    # flatten fixed 1615 -> 1600 (ADR-020). The trade cap was removed 2026-09-05
    # (B1 closed): the bot no longer declares one, matching the uncapped engine.
    # FlattenBy=1600 remains the recorded overridable divergence from 1545.
    "scripts/ninjatrader/strategies/bandits_8020/BBMRReversionBot.cs": (1600, None, 1600),
    "scripts/ninjatrader/strategies/bandits_8020/Bandits8020Bot.cs": (1555, 3, 1100),
    "scripts/ninjatrader/strategies/ib_breakout/IBFadeBot.cs": (1555, 2, 1555),
    "scripts/ninjatrader/strategies/ifvg_cisd/ICTFVGCISDBot.cs": (1555, 3, 1530),
    "scripts/ninjatrader/strategies/keltner_channel/KeltnerChannelBot.cs": (1600, 4, 1530),
    "scripts/ninjatrader/strategies/supertrend/STTrendBot.cs": (1555, None, 1555),
    "scripts/ninjatrader/strategies/the_strat/Strat212ContinuationBot.cs": (1555, 6, 1530),
    "scripts/ninjatrader/strategies/the_strat/Strat22RevStratBot.cs": (1555, 6, 1530),
    # EMAPullbackBot left this list 2026-09-05: it differs only in LatestEntry,
    # which stopped being a frozen field when entries became unrestricted. See
    # BOT_FIX_BACKLOG.md B6.
    # IBStrategyBase left this list 2026-09-05 (B4 closed): its 1550 vs
    # IBFadeBot's 1555 -- which one applied depended on construction order --
    # is settled; the base now carries the frozen 1545 and matches, and only
    # IBFadeBot's deliberate PM-window override remains recorded. See
    # BOT_FIX_BACKLOG.md B4 for the one-key-three-bots mapping note.
}

# ONLY `flattenByEt` IS COMPARED. `maxTradesPerDay` and `lastEntryEt` are
# `analysisDerived` in trading_defaults.json -- an entry may happen at any time,
# and a trade cap is an OUTPUT of reporting/trade_ordinal.py rather than a
# frozen input. A bot setting either is therefore not a divergence to be fixed;
# it is a number waiting for the analysis that justifies it. The tuples above
# still record all three, because the SPREAD is what BOT_FIX_BACKLOG.md works
# through, and a value that moves should be noticed even when it is not policed.
COMPARED_FIELD = "FlattenBy"

# Bots that already match the frozen defaults exactly, kept out of the inventory
# on purpose: FailedAuctionBot and VWAPReclaimBot (1545 / 3 / 1430). The
# staleness test above removed them when it found they agreed -- which is the
# inventory working, not a gap.

# ADR-020: an intraday position exits at 16:00 ET at the latest (close of the
# 15:59 bar). Past it is a prop-firm liquidation risk, not a convention.
RTH_HARD_EXIT = 1600
