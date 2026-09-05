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

THE MOST CONSEQUENTIAL ENTRY is still BBMRReversionBot: it allows 99 trades a day
where the Python `mean_reversion` engine that predicts it allows 3. That pair
cannot be compared at the trade-set layer until the two agree, and no report says
so today.
"""

# path -> (FlattenBy, MaxTradesPerDay, LatestEntry). None = not declared.
KNOWN_DIVERGENCES = {
    # flatten fixed 1615 -> 1600 (ADR-020). The 99-trade cap remains a real
    # divergence from the Python side's 3 and is why this pair is not comparable.
    "scripts/ninjatrader/strategies/bandits_8020/BBMRReversionBot.cs": (1600, 99, 1600),
    "scripts/ninjatrader/strategies/bandits_8020/Bandits8020Bot.cs": (1555, 3, 1100),
    "scripts/ninjatrader/strategies/ib_breakout/IBFadeBot.cs": (1555, 2, 1555),
    "scripts/ninjatrader/strategies/ib_breakout/IBStrategyBase.cs": (1550, 2, 1430),
    "scripts/ninjatrader/strategies/ifvg_cisd/ICTFVGCISDBot.cs": (1555, 3, 1530),
    "scripts/ninjatrader/strategies/keltner_channel/KeltnerChannelBot.cs": (1600, 4, 1530),
    "scripts/ninjatrader/strategies/supertrend/STTrendBot.cs": (1555, 99, 1555),
    "scripts/ninjatrader/strategies/the_strat/Strat212ContinuationBot.cs": (1555, 6, 1530),
    "scripts/ninjatrader/strategies/the_strat/Strat22RevStratBot.cs": (1555, 6, 1530),
    # EMAPullbackBot left this list 2026-09-05: it differs only in LatestEntry,
    # which stopped being a frozen field when entries became unrestricted. See
    # BOT_FIX_BACKLOG.md B6.
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
