"""
scripts.streaming.options
=========================
Automated Dealer Levels pipeline for the Charles Schwab API.

Modules
-------
config           — All tuneable constants (tickers, paths, schedule times).
options_fetcher  — Authenticated Schwab API data retrieval.
gex_calculator   — GEX, Zero-Gamma, Call/Put Wall, Expected-Move maths.
futures_translator — Cash-index → futures price-level translation.
discord_notifier — Discord webhook output formatting and delivery.
file_writer      — JSON (Pine-ready) and TXT file persistence.
run_options_levels — CLI / scheduler entry point.
"""
