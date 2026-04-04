# Strategy Notebooks

One notebook per strategy (vectorized inventory):

1. `01_initial_balance_breakout.ipynb`
2. `02_nine_thirty_breakout.ipynb`
3. `03_ib_pullback.ipynb`
4. `04_box_reversion.ipynb`
5. `05_mean_reversion.ipynb`
6. `06_ema_pullback.ipynb`
7. `07_vwap_reclaim.ipynb`
8. `08_failed_auction.ipynb`
9. `09_six_am_reversal.ipynb`

Notes:
- The Initial Balance Breakout notebook uses the strategy runner script entrypoint.
- The others are structured around `DataLoader` + strategy `hunt()` workflow.
