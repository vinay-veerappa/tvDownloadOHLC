# LuxAlgo Ecosystem Evaluation

Status: research + spike complete, no adoption decided. Captured 2026-09-03 so the
thinking can be picked back up later without re-deriving it. Not abandoning
TradingView Desktop or NT8 — this is about whether/how pieces of LuxAlgo's stack
(github.com/LuxAlgo) fit into an eventual more-unified system.

## Why this started

The original ask was narrower: can Vela (LuxAlgo's charting library) replace
`lightweight-charts` in `web/` so we stop rebuilding chart chrome by hand. That
turned into: LuxAlgo has since shipped a whole ecosystem (journal, options flow,
prop-firm sim, broker connectivity, execution relay, congress/insider data,
Pine-in-Node) — worth knowing what each piece actually is before deciding whether
any of it belongs in the system.

**Standing tension to resolve before going further**: today the system is a
collection of fairly delinked pieces (NT8 execution + riskguard/bridge, Schwab/TOS
RTD options pipeline, the Next.js web app with its own journal, `range_probability`
stats engine, agent-loop tooling, various MCP servers). The appeal of the LuxAlgo
stack is that several of these are *already wired together* as one coherent set
(journal ↔ broker-sync ↔ stats ↔ charting ↔ MCP). Before evaluating fit further,
worth thinking through how to make the *existing* system more fluid/seamless on
its own terms — then it'll be clearer which LuxAlgo pieces actually solve that vs.
just add a second, parallel set of tools.

---

## Part 1 — Vela (charting library)

### Comparison vs. TradingView Lightweight Charts

| | LuxAlgo Vela | TradingView Lightweight Charts |
|---|---|---|
| Maturity | Created Jul 2026, v0.6.16, 93 ★ | Created 2019, v5.2.1, 17,160 ★ |
| npm downloads/wk | ~737 | ~939,000 |
| License | Apache-2.0 + NOTICE-driven watermark requirement | Apache-2.0, lighter attribution |
| Rendering | WebGL2 native, Canvas2D fallback | Canvas2D only |
| Bundle | Not yet on Bundlephobia; pulls in Zag.js UI kit | ~62KB gzip, 1 tiny dep |
| Scope | Batteries-included app: workspace shell, 70+ indicators, plugin SDK, bundled data providers | Headless primitive only — series/scales/markers, no chrome, no data |
| Backing | LuxAlgo (known for TV indicator scripts) | TradingView itself |

**License detail**: Apache-2.0 core. The `NOTICE` file adds an attribution-mark
requirement, but it's explicitly anchored to Apache §4(d), which triggers on
*redistribution* — not private/internal use. For a personal fork not handed to
third parties, the watermark can very likely be removed with no obligation. That
flips back on the moment this becomes something other people install or a hosted
service other people log into.

### Spike outcome (`web/app/tools/vela-spike/`, throwaway, not wired into the real app)

Built a standalone route rendering Vela's `VelaWorkspace` against the *same* real
data your production chart uses (`stream_chart.py` on `:8001`). Confirmed:

- **Feel**: noticeably smoother pan/zoom than the current `lightweight-charts`
  build; a lot of chrome (drawing toolbar, indicators dialog, keyboard shortcuts,
  object tree, alerts, screenshot) works out of the box that currently lives in
  hand-built code (`hooks/chart/use-chart-drag.ts`, `use-chart-sync.ts`,
  `use-chart-trading.ts`, the context-menu, `journal/chart-library.tsx`).
- **Live data requires writing a `DataProvider`** (Vela's port for
  `getBars`/`subscribe`). Built one (`web/lib/vela-spike/stream-chart-provider.ts`,
  ~130 lines) bridging Vela to `stream_chart.py`'s `/history` + `/stream`
  WebSocket — vs. the ~250 hand-rolled lines in
  `web/hooks/chart/use-live-data-loading.ts` today.
- **Real gap surfaced by building it, not just reading docs**: Vela's providers
  must serve whatever timeframe is requested themselves — there's no built-in
  resampling. So the 1m→Nm aggregation logic doesn't disappear with a migration,
  it just relocates from the hook into the provider.
- **Two real bugs hit and fixed during the spike** (both instructive about how
  Vela fails):
  1. Mutating the same bar object across live updates and passing the same
     reference to `onBar()` looked like a no-op to Vela's internal diffing —
     always construct a new object per update.
  2. **Silent failure, not an error**: `chart.data.resolve('/NQ')` (a bare
     symbol) returned `null` because the custom provider didn't implement
     `listSymbols()` (needed to build a bare-symbol index). The *initial history
     load* has a looser fallback that tolerated the unresolved bare symbol
     (misleadingly making it look like everything worked), but the *live
     subscribe* path resolves strictly through the registry and just never calls
     `provider.subscribe()` on failure — no error, no warning. Fix: use the
     explicit `provider:ticker` form (`streamchart:/NQ`). Point for later: a
     misconfigured provider fails quietly on the live path while working fine on
     history — genuinely easy to ship broken and not notice.
- After both fixes: confirmed genuine tick-by-tick live updates (verified via
  direct instrumentation of the provider, not just visual inspection) — the
  server's `quote` messages (~1/sec) build the forming bar; the rarer `candle`
  messages correct it with authoritative OHLC, mirroring what the existing hook
  already does by hand.

---

## Part 2 — Wider LuxAlgo ecosystem (github.com/LuxAlgo)

All are TypeScript (pnpm workspaces), Node-based, created ~2026-08-24/25 (i.e.
brand new) **except PineTS** (created 2025-01-30, the mature flagship) and
**pinets-cli** (2026-02-15, apparently stale ~6 weeks vs. the rest).

### Cross-cutting facts

- **`broker-sdk` is the shared dependency** for `trade-journal`, `edge-stats`,
  `prop-firm-sim`, and `trade-relay`. It has **zero NinjaTrader adapter and no
  direct futures-broker adapter** — confirmed via its adapter file list (Alpaca,
  Alpaca-bars, Binance, Bybit, Coinbase, Crypto.com, E*TRADE, Etrade, Gemini,
  Hyperliquid, IBKR-flex, Kraken, KuCoin, OKX, Public, Questrade, Robinhood-crypto,
  **Schwab**, Tastytrade, Topstep(via ProjectX, prop-eval read-only), TradeStation,
  Tradier(+bars/list), Trading212, Webull). Schwab read access (accounts/trades)
  works; **order placement ("experimental write path") is Alpaca/Tradier/Binance
  Spot Testnet only — not Schwab, not NT8.**
- Since all live execution here is NT8 (via `nt8-riskguard`/`nt8-mcp-bridge`) and
  options are Schwab, that gap reaches into every repo built on `broker-sdk`.
  NT8 only appears anywhere in the ecosystem as a **statement/CSV import format**
  in `trade-journal` and `prop-firm-sim` — batch, not live, no platform API talk.
- **Vela is bundled/referenced across nearly the whole set**
  (`trade-journal`, `edge-stats`, `whale-options`, `trade-relay`,
  `market-trackers`, `PineTS`) as the shared charting layer — always Apache-2.0
  even when the host repo is MIT or AGPL.
- **License split**: 7 of 9 repos MIT. `PineTS` and `pinets-cli` are AGPL-3.0.
  `edge-stats`'s calendar/event data is additionally CC BY 4.0. `market-trackers`'s
  published data dumps are CC0.

### Per-repo findings

**trade-journal** — self-hosted journal on a raw-execution model (fills →
FIFO/LIFO/weighted-avg round trips). P&L calendar, versioned "Edge Score" formula,
win-rate/PF/expectancy/R-multiple analytics, trade pages charted on Vela, daily
journal with voice dictation + autosaving Markdown, playbooks, AI reflection
(bring-your-own Anthropic key), CSV/JSON/PDF export. Statement import covers
TradeZella/Tradervue/TradingView/MT4/MT5/ThinkOrSwim/**NinjaTrader**/Tradovate/
TopstepX/Webull/DAS/generic CSV. Storage: SQLite via Drizzle, single file. Two
IO-free importable packages: `@luxalgo/journal-core` (round trips, metrics, Edge
Score), `@luxalgo/journal-importers`. No CLI/MCP in this repo — broker sync comes
from `broker-sdk`. 7★, 0 issues, MIT, "early release — schema may still move."

**edge-stats** — "P(outcome | conditions)" stats engine. Syncs bars into local
DuckDB, derives session features once, runs composable queries. Every result
carries point estimate + N + **Wilson 95% CI**, min-sample guards (warn <30,
refuse <10), first/second-half stability split, per-year counts, drill-down to
underlying sessions. 42 presets / 121 named variants (gap fills, ORB, initial
balance, seasonality, prior-day levels, streaks, NR7, event-day FOMC/CPI/
NFP/OPEX). Can condition on your own trades (via broker-sdk or CSV import).
Adapters: **csv**, synthetic, Binance, Coinbase, Alpaca, **Databento (paid, CME
futures)**, Massive/Polygon flat files, LSE, Dukascopy, Hyperliquid — the CSV
adapter means your own local 1m parquet (exported to CSV) can feed it without
touching Databento. CLI (`edgestats query/report/serve/init`), local dashboard +
REST API, **MCP server** with 10 read-only tools. 1★, 0 issues, MIT + data files
CC BY 4.0. Explicit non-goals: "No order execution, ever." "No tick streaming."
"No hosted service, no telemetry." 233 tests claimed.

**prop-firm-sim** — Monte Carlo (10,000 paths) against a firm's *exact* ruleset,
not a binomial approximation. Models 4 distinct trailing-drawdown semantics
(static / EOD-trailing / intraday-peak-trailing / lock-at-breakeven), decomposes
"5% daily loss" into 4 independent choices, **block-bootstraps real trade streaks
to preserve autocorrelation** instead of assuming i.i.d., computes optimal-risk
curves (risk-that-maximizes-pass-probability ≠ risk-that-maximizes-EV), models
consistency rules/payout gating/stagnation. Ingests real trade history (TV,
MT4/MT5, ThinkOrSwim, generic CSV, broker-sdk JSON). News-filter replay,
portfolio-overlap audit across up to 5 histories. **Firm rulesets fetched live
from LuxAlgo's public prop-firm directory API** (keyless), 3-tier honesty policy
(structured columns verbatim / free text inferred only if unambiguous, flagged /
ambiguous refused rather than guessed) — any ruleset can also be passed fully
offline. Pure TS compute engine, zero I/O, zero persistence. CLI, MCP server,
importable core library, separate hosted browser simulator. 6★, 0 issues, MIT.
Stated limits: trades modeled as same-day round trips (no overnight holding),
intra-trade excursions not modeled, attempts assumed i.i.d. with no
learning/tilt, scaling plans not simulated.

**whale-options** — options-flow engine that "shows its work." Sweeps (same
contract/side across ≥2 exchanges within a rolling 500ms window, ISO-flag
corroborated), blocks (dynamic threshold = 99.5th percentile of trade-size
distribution per liquidity bucket, floored 50/100/250/500 contracts), splits/
ladders (≥4 same-contract/side clips over minutes). Every event gets a full,
transparent score breakdown (volume/premium-vs-baseline, vol/OI, aggression,
urgency, repetition) with `n/a`/renormalization instead of guessing on missing
data. Cold-start flagging until baselines exist (`whale backfill`). GEX per
strike/expiry with a heatmap, repriced live every ~2s. Market-structure tools
(OI deltas, max-pain, IV rank, net-flow), FINRA short-volume context. Alert rules
as JSON predicates → 5 sinks. **Full flight recorder with byte-identical
deterministic replay** (`whale replay --diff`), plus an audit mode calibrating
recorded scores against actual forward returns. Feeds: **Tradier, ThetaData,
Alpaca, Massive/Polygon, synthetic, replay** — no Schwab/TOS RTD adapter exists;
one would need to be written. CLI, local dashboard+API+WS, MCP server with 16
tools, webhook sink (HMAC-signable). SQLite storage. 3★, 0 issues, MIT (Vela
chart bundle Apache-2.0). Explicit non-goals: no real-time dark-pool prints, no
hosted/multi-tenant mode, no order execution, no "smart money" narrative claims.

**broker-sdk** — normalized read-only-by-default API, 22 brokers/exchanges,
`connect({broker, credentials}).fetchSnapshot()` → `{accounts, positions, trades}`.
Multi-broker portfolio aggregation with per-broker failure isolation.
`fetchBars` only works for **Alpaca and Tradier** — every other broker (including
Schwab) rejects it. Generic CSV importer. Drop-in React `<BrokerConnect>`
component. `broker-sync` daemon polls + diffs + emits HMAC-signed webhook events.
Experimental write layer (`connectTrading`): Alpaca (paper default, live needs
explicit acknowledgement), Tradier (sandbox-only — live "impossible by
construction"), Binance Spot Testnet — **that's the entire write surface**.
Confirmed Schwab adapter is real (OAuth2, published Schwab Trader API,
bring-your-own-app, 30-min access / 7-day refresh tokens) but read-only in
practice (trades ✅, bars ➖, no order placement). Zero runtime deps, Node ≥18.17.
1★, **4 open issues** (highest of the new batch), MIT, v0.5.0 (most mature by
semver of the new repos). Explicit scope limit: "sanctioned APIs only," no
scraping, no aggregator-only brokers (Plaid-style).

**trade-relay** — self-hosted execution relay: webhook/AI-agent alert →
risk-checked broker order. Native JSON payload plus auto-detected TradersPost/
SignalStack formats. **Safety rails on by default, and a config that doesn't
explicitly loosen a rail refuses to boot** — symbol allowlist, max position size,
max daily loss, duplicate-alert protection, trading-hours windows, orders/day
ceiling, persistent kill switch (dashboard/API/webhook/MCP-triggerable, survives
restarts). Full flight-recorder dashboard with per-rule verdict+reason and
one-click paper replay. "Tape" panel charts fills on Vela with FIFO-matched P&L
lines, and is explicit about never fabricating a candle it didn't see. **All
broker connectivity goes through `broker-sdk`** — confirmed via `src/brokers/`
(`sdk-port.ts`, a vendored `broker-sdk` tarball). Built-in simulator with full
order types, zero keys. Live trading: Alpaca (paper full, live needs
acknowledgement), Tradier sandbox (equity market/limit only). **No NinjaTrader,
no futures broker with live order support** — inherits broker-sdk's exact gap.
Single SQLite file. CLI, dashboard+API, MCP server (trading via MCP needs
`mcp.allowTrading: true` explicitly set). 2★, 0 issues, MIT, v0.2.0 (younger than
broker-sdk). Explicit refusals: no hosted version, no custody, no strategy
advice, no unofficial broker APIs (why there's no Robinhood order execution).

**market-trackers** — ingests **18 datasets** from primary government/regulatory
sources: Congress trades (Senate eFD + House Clerk), SEC insider transactions
(Forms 3/4/5), 13F holdings, government contracts/grants (USAspending), lobbying
(Senate LDA), **short-sale volume (FINRA Reg SHO)**, committee assignments,
patents (USPTO, needs a free key), clinical trials, FDA approvals, **futures
positioning/COT (CFTC)**, federal legislation, campaign finance + PAC→candidate
(FEC), congressional hearings, **Fed communications (FOMC statements/minutes/
speeches)**, Wikipedia pageviews. Incremental/idempotent sync, per-source
watermarks, natural-key upserts. Exports daily-delta JSON + per-year snapshots
(JSON.gz + **Parquet**) + per-dataset/per-entity RSS feeds + a manifest, mirrored
to a public data repo and weekly to Hugging Face. `analyze`/`backtest congress`
join disclosed trades against user-supplied price CSVs (ships no market data
itself). **Confirmed wholly new data domain** — no overlap with anything in a
futures/options price-action repo; closest adjacency is COT and FINRA
short-volume, both flow/positioning data rather than price data. SQLite default,
**Postgres via one flag**. CLI, MCP server (23 tools), RSS feeds, free daily
CC0 dumps, and — uniquely in this set — a **first-class Python reader package**
(`market_trackers_data`, zero required deps, optional pandas). 1★, 7 open issues
(second-highest), code MIT / data dumps CC0. Explicit non-goals: no predictions/
scores/conviction ratings, no fabricated precision (disclosed ranges stay
ranges), no social/Reddit sentiment, no scraping of commercial products.

**PineTS** — TypeScript transpiler+runtime executing native Pine Script v5/v6 in
Node/Deno/Bun/browser with the real time-series model (lookbacks, `var`/`let`
persistence, bar state). 60+ TA functions, full data structures, `request.
security()`, live `.stream()`, a `strategy()` broker-emulator namespace. Built-in
providers: Binance, FMP, Alpaca, or raw OHLCV arrays. A **separate** addon repo
(`Vela-pinets`) runs PineTS scripts on Vela through Vela's `ScriptingEngine` port
(in-process or off-main-thread). By far the most mature repo in the whole set:
**522★, 112 forks, 30 open issues, created 2025-01-30** (over a year old vs. ~10
days for most others), actively pushed today. Listed in "Awesome Quant."
**AGPL-3.0 with a commercial-license buyout option** (`LICENSE-COMMERCIAL.md`,
contact business@luxalgo.com) — note this is the *core engine* under AGPL, not
an Apache core with an AGPL addon (a stricter shape than the Vela/Vela-pinets
split). Roadmap still marks full Pine v6 compatibility as in-progress. Explicit
disclaimer: not affiliated with/endorsed by TradingView, Inc. (trademark risk
called out directly).

**pinets-cli** — thin CLI: `pinets run indicator.pine --symbol BTCUSDT
--timeframe 60` → JSON plot series. File or stdin input, live Binance or local
JSON OHLCV. Options for candle count/warmup, output format, `--clean` (drop
null/false/empty — useful for signal-only crossover indicators), `--plots`
filter. Built for agent/programmatic use (stdin-in/stdout-JSON-out, ships a
`SKILL.md` for agent frameworks). No library API, no MCP, CLI only. 25★, 6
forks, 0 issues, AGPL-3.0-or-later (no separate commercial-license file, unlike
PineTS itself), last pushed ~6 weeks before this research (stalest repo in the
set). **Provenance flag**: `package.json`'s `repository`/`bugs`/`author` point
to `QuantForgeOrg` and an individual person, not "LuxAlgo Global, LLC" like
every other repo here — reads as possibly a third-party/community CLI that
LuxAlgo links to rather than one it authored. Worth confirming which repo is
actually upstream before depending on it.

---

## Part 3 — Verdict table

| Repo | Counterpart here | Verdict | Adaptation cost |
|---|---|---|---|
| market-trackers | *(nothing)* | Adopt | **None** — self-contained, own data sources |
| edge-stats | `scripts/range_probability/*` | Bake off | **Low** — CSV-export your own parquet, no new vendor |
| whale-options | `whale_detector.py` + `gex_calculator.py` + `level_scorer.py` | Bake off | **Medium** — needs a TOS RTD/Schwab → whale-options feed adapter (none exists) |
| prop-firm-sim | `prop_firm_simulator.py` (ADR-021) | Mine methodology, don't replace | N/A — stays Python, ADR-021 mandates it exclusively |
| trade-journal | `web/app/journal/*` | Selectively adopt libraries | **Low** for the packages (Edge Score, AI-reflection prompts); broker-sync itself is NT8-blocked |
| trade-relay | *(NT8 bridge is the de facto relay today)* | Watch, don't build on | **Blocked** — no NT8, no Schwab order placement, nothing to adapt around |
| broker-sdk | NT8 bridge, Schwab/TOS RTD auth | Watch | **Blocked** for write; usable today only for read-only Schwab trade history |
| PineTS / pinets-cli | Pine→Python→NT8-C# triple-port problem | Interesting, license-gated | **Low** technically, but AGPL network-clause risk scales with "how many other people touch this over a network" — fine today at personal-use scale |

## Part 4 — Open questions to think through before doing anything

These are the threads flagged as needing more thought before scoping real work,
not answered here on purpose:

1. **Broker integration shape.** If any of this gets adopted, what does "broker
   integration" even mean given NT8 (futures, via the custom bridge) and Schwab
   (options, via TOS RTD) sit outside every adapter LuxAlgo ships? Options:
   (a) write and maintain your own NT8 adapter against `broker-sdk`'s port
   shape, (b) keep NT8/Schwab entirely on the existing bridge/TOS-RTD path and
   only let LuxAlgo pieces touch *derived* data (parquet/CSV exports), never
   live broker state, (c) some hybrid where read-only Schwab flows through
   broker-sdk (it already works) but NT8 never does.
2. **MCP surface area post-move.** Several LuxAlgo repos ship their own MCP
   servers (edge-stats, prop-firm-sim, whale-options, market-trackers,
   broker-sdk via `luxalgo-mcp-server`, trade-relay). Stacked against the
   existing MCP surface (`nq-data-bridge`, `ninjatrader`, `codebase-memory-mcp`,
   `tradingview`, etc.), what's the intended shape — one Claude session with a
   dozen-plus MCP servers, a curated subset, or a broker/gateway layer in
   front of all of them so an agent doesn't have to reason about which of 6
   near-synonymous tools to call?
3. **Sequencing vs. the "delinked system" problem.** Given the standing
   tension noted at the top — is the right move to first tie together what
   already exists (NT8 execution, options pipeline, journal, stats engine,
   agent-loop) into something more seamless on its own, and *then* evaluate
   which LuxAlgo pieces plug into *that* shape — vs. adopting pieces now and
   letting the integration shape emerge from what's adopted?
4. **TradingView/NT8 exit is not decided.** This whole evaluation assumes NT8
   stays the execution venue and TradingView Desktop stays available; nothing
   here should be read as pointing toward dropping either. Any plan that
   *implicitly* requires leaving NT8 (e.g., trade-relay for execution) is
   effectively vetoed until that's an explicit, separate decision.

## Part 5 — If/when this resumes: suggested order

Not a commitment, just where the cheapest signal is if this picks back up:

1. market-trackers — zero conflict, just wire it up
2. edge-stats bake-off — CSV-export parquet, diff a handful of presets against `range_probability/`
3. whale-options bake-off — scope the TOS RTD feed adapter, then compare sweep/GEX output on one real session
4. prop-firm-sim mining — write the block-bootstrap/trailing-DD/optimal-risk ideas up as an ADR-021 amendment proposal
5. trade-relay / broker-sdk — parked until NT8 connectivity exists on either side
6. PineTS — optional, personal-use-only experiment on a non-critical indicator
