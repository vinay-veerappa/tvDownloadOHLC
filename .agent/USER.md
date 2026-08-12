# USER.md — Compiled Profile

> Auto-rendered from `user_prefs` + select `memories`. Absent key = no info, never the opposite.

## Preferences
- **api_compile_via_mcp**: NT8 compile via nt_compile MCP only; never manual HTTP to localhost:7890
- **api_mcp_first**: Use codebase-memory MCP first for code search; grep only as fallback
- **conventions_parallel**: >=32-arm parameter sweeps use joblib; Numba @njit for bounded loops; CuPy GPU for >1M-element cumulative (ADR-022)
- **conventions_prop_rth_close**: Max intraday exit at 16:00 ET close of 15:59 bar (ADR-020)
- **conventions_prop_sim**: Only PropFirmSimulator for prop firm evaluation; never per-trade % as daily P&L (ADR-021)
- **conventions_stats_pct**: Metrics as price-percentage, not absolute points (ADR-002)
- **conventions_timezone**: UTC naive inputs; ET session windows; UTC epoch storage (ADR-001)
- **conventions_vectorized**: No for-loops in calculation paths — vectorized NumPy/Pandas (ADR-017)
- **conventions_visual**: Indicators bind to VISUAL_SYSTEM.md templates, zero direct draw calls (ADR-018)
- **trading_ael_pattern**: Asia Engulfs London: 81.1% break London High (high-conviction bullish)
- **trading_execution**: Buy in Discount (<50% of dealing range), Sell in Premium (>50%)
- **trading_instruments**: NQ1 (primary), ES1 (secondary)
- **trading_lea_pattern**: London Engulfs Asia: 71.5% break London High, 70.4% break Low
- **trading_rth_inside**: Open inside pRTH: 74% break at least one side; only 8.3% outside day
- **trading_sessions**: Asia 20:00-02:00, London 02:00-08:00, NY 08:00-16:00 ET
- **workflow_sync_keyword**: 'sync' keyword triggers mandatory startup sequence (AGENTS.md + memory.db + skills)
- **lessons_account_change**: NT8 Account.Change() modifies the position in place — validate after call (conf=0.7)
- **lessons_fix_class_not_instance**: When a defect is found, ask what structure generates it before patching the instance (conf=0.7)
- **lessons_git_push_blockers**: data/ and audio files purge from git; run git lfs or .gitignore before push (conf=0.7)
- **lessons_mutation_testing**: Mutation testing is the evidence standard, not green-suite review (conf=0.7)
- **lessons_test_doubles**: A green suite is evidence about the fiction we authored, not the system (conf=0.7)

## Recent user_profile / standard memories
- [standard] nqstats: NQStats Engine: Pandas Compatibility & Performance Fixes  ## NQStats Engine Fixes (2026-03-27)  ### FutureWarning Suppre
- [standard] token: Token Efficiency  Structural Graph (36k nodes) reduces navigation tokens by ~90%.
- [standard] data: Data Access  Indicators and Market Levels are now served via MCP tools to bypass file parsing.
- [standard] midnight: Midnight Open  The midnight open (00:00 EST) is a critical level for daily bias. Most institutional algorithms reset the
- [standard] reporting: Reporting Standard: Every statistical analysis section must include a qualitative 'Day Trader Takeaway' and 'Analysis' b
- [standard] scripting: Scripting Standard: Always ensure analysis and data scripts are ticker-independent. They must accept a ticker as a comma
- [standard] statistics: Market Analysis Standards: 1. Tripartite Rule (Mean, Median, Mode required). 2. US/Eastern Timezone Lock. 3. 8:30 AM US 
- [user_profile] preference: UPDATE: User also prioritizes Average/Mean metrics for price and time data (in addition to Median/Mode/MAE/MFE).
- [user_profile] preference: User is a Futures Day Trader (NQ, ES). Sessions: NY, Asia. Style: ICT + Stats. Key Metrics: MAE, MFE, Median, Mode (Pric
