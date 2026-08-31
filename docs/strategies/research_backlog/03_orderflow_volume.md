# Orderflow / Volume Strategies — Research Backlog F3

> Purpose, validation standard, and status legend as in [01_ict_smc_price_action.md](01_ict_smc_price_action.md).
> Note: repo's 1m OHLCV parquet has volume but NOT bid/ask tick data — delta must be *estimated* (e.g., close-position-in-bar rule or `(close-open)/(high-low)` proxy). Each doc below states the proxy used; treat all delta-based tests as proxy-delta until TOS RTD or NT8 tick feeds are wired into the pipeline.

---

## Repo context already established

| Finding | Source |
|---|---|
| CVD absorption divergence defined as fade signal at IB extremes (bullish abs = price LL + CVD HL) | STRATEGY_CONFLUENCE_PLAYBOOK C5.2 |
| Failed Auction hunter vectorized (tape-reading reversal) | [reversal/README.md](../reversal/README.md) + FailedAuctionIndicator.cs |
| RedTailVolumeProfile (POC/VAH/VAL/nodes), RedTailVolume (cum delta + spikes), RedTailFRVP (footprint-style rel-vol profile) exist as NT8 indicators | STRATEGY_CONFLUENCE_PLAYBOOK §8.4 |
| Bandits 80/20: "Repair" (single-wick imbalance) acts as entry/target magnet; xx20/xx80 liquidity sniping | [prop_firm_bandits_80_20_liquidity_code.md](../prop_firm_bandits_80_20_liquidity_code.md) |
| LVN hunter indicator (liquidity void moves fast through) | STRATEGY_CONFLUENCE_PLAYBOOK §8.5 |

---

## O1. CVD divergence fade at session extremes
**Status**: ⬜

- Published frame ([Bookmap CVD guide](https://bookmap.com/blog/how-cumulative-volume-delta-transform-your-trading-strategy), [LuxAlgo CVD concept](https://www.luxalgo.com/library/concept/cumulative-volume-delta.md), [Inloopo](https://www.inloopo.com/day-trading/cumulative-delta/)):
  - **Distribution divergence**: price new session high, CVD lower high → fade short.
  - **Absorption divergence**: price new session low, CVD higher low → fade long.
  - Both treated by practitioners as *confirmation* signals requiring price action, never standalone.
- **Proxy**: delta = volume × (close − open)/(high − low) per bar (documented limitation: no bid/ask truth).
- **Testable variant**: divergence measured over a rolling N-bar window (N=20/30/60) at session high/low extremes; enter on first structure break (CISD analog) in divergence direction, not on the divergence itself. Arms: standalone divergence vs divergence+CISD vs divergence+CISD+killzone.
- **Learning**: does proxy-CVD divergence add any WR over price-only equivalents (e.g., lower-wick dominance at extremes)? If proxy-delta diverges from true delta materially, kill the whole proxy approach early and route F3 through NT8 tick data instead.
- **Sources**: [zitaplus divergence strategies](https://zitaplus.com/blog/analysis/cumulative-volume-delta-divergence-details--strategies/), [All-in-One CVD script](https://www.tradingview.com/script/UzTtufWl-All-in-One-CVD-Failed-Auction-Trap-Flow-Classifications/)

## O2. Absorption bars (high volume + tight range) at levels
**Status**: ⬜

- Definition ([AMT suite](https://es.tradingview.com/script/A4jmkFCw-AMT-Order-Flow-Suite-v2-2/)): bar with volume > k× rolling average AND range < r× rolling average = iceberg/absorption footprint; diamond-marked.
- **Testable variant**: absorption bar prints *at* a key level (PDH/PDL, IB extreme, VAH/VAL) → next-bar directional bet toward the absorption side. Arms on k (2/3/4) and r (0.5/0.7).
- **Learning**: absorption WR by level type; does absorption+failed-auction combo (the TradingView script's claim: "true failed auctions require absorption") beat plain failed auction hunter already in repo?
- **Related**: effort-vs-result framing in [LuxAlgo absorption & exhaustion concept](https://www.luxalgo.com/library/concept/absorption-and-exhaustion/)

## O3. Failed auction / value-area rejection (acceptance-rejection test)
**Status**: 🟡 hunter exists; the *volume-profile value-area* variant is untested

- Published frame ([ITII acceptance-to-rejection](https://internationaltradinginstitute.com/blog/reading-the-volume-profile-from-acceptance-to-rejection/), [Alchemy Markets](https://alchemymarkets.com/education/indicators/volume-profile/)): price escapes value area, returns and holds inside → failed auction → sharp reversal; unfinished auctions (unfinished business at highs/lows of the profile) get revisited next session.
- **Testable variant**: build rolling value area from session volume profile; FA = excursion beyond VAH/VAL followed by 2×15m close inside; enter toward value midpoint; target = POC.
- **Learning**: does volume-profile-FA beat the existing tape-reading FailedAuction hunter? Is "unfinished auction revisit next day" real on NQ (a cheap overnight-session test)?
- **Related**: TradeZella AMT/LVN playbook ([auction market strategy](https://www.tradezella.com/strategies/auction-market-strategy))

## O4. POC / HVN magnetism and LVN traversal speed
**Status**: ⬜

- Theory: price gravitates to session POC (fair value anchor) and *accelerates through* LVNs (no volume to transact) — the basis of RedTailLVNHunter. Virgin POCs (untouched prior-session POCs) produce the strongest reactions (AMT suite claim).
- **Testable variants**: (a) first-touch-of-day POC reaction WR; (b) LVN traversal — mean time & slippage to cross an LVN vs an HVN of equal height; (c) virgin-POC reaction vs non-virgin.
- **Learning**: magnet or myth? Measures whether profile-based targets (instead of fixed-R) improve exit quality across ALL strategies in F1/F2 — that's the composition payoff.

## O5. Volume spike continuation vs exhaustion
**Status**: ⬜

- RedTailVolume flags volume spikes; classic question — is a 3σ-volume bar continuation (climax of acceptance) or exhaustion (climax of rejection)?
- **Testable variant**: classify spikes by location (inside value / at VA edge / at session extreme) and by next-bar close direction; measure forward 30-min drift.
- **Learning**: a location-conditional spike classifier reusable as a filter on breakout entries in F1/F2.

## O6. Repairs (single-wick imbalance voids) — Bandits 80/20 formalization
**Status**: 🟡 production NT8 bot exists ([Bandits8020Bot](../STRATEGY_CONFLUENCE_PLAYBOOK.md)); the *decay rule* (most recent repairs fill within 2–4 bars) is unpublished folklore worth testing

- **Testable variant**: measure fill-rate of flat-top/flat-bottom bars by: age of repair, body/range ratio, session bucket.
- **Learning**: the repair-decay curve — if it exists, it's a reusable *target model* for every F1 entry technique (ET-1…ET-7).