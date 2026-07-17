"""Add GEX positioning, Herman Pre-NY sweep, and FTFC to open/premarket modes"""

with open('scripts/trader/briefing_core.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add GEX positioning verdict to open mode (after GEX regime change block)
old_gex = '''    except Exception as e:
        log.warning("[cheat_sheet] GEX regime change failed: %s", ticker, e)

    # Expected Move'''
new_gex = '''    except Exception as e:
        log.warning("[cheat_sheet] GEX regime change failed: %s", ticker, e)

    # GEX positioning verdict (session-aware, pre-computed for LLM)
    try:
        from scripts.trader.signals.intraday_blocks import _format_gex_block
        _es_spot = ticker_spot if ticker == "ES1" else 0
        sections.append(_format_gex_block(ticker_spot, _es_spot, ticker, session="OPEN", target_date=target_date))
    except Exception as e:
        log.warning("[cheat_sheet] GEX positioning failed for %s: %s", ticker, e)

    # Expected Move'''

if old_gex in content:
    content = content.replace(old_gex, new_gex, 1)
    print("✓ GEX positioning added to open mode")
else:
    print("✗ Could not find GEX regime change block in open mode")

# 2. Add Herman Pre-NY sweep to open mode (after the ALN block)
old_herman = '''    sections.append(_format_aln_block(base_label, aln_data, ticker_spot))'''
new_herman = '''    sections.append(_format_aln_block(base_label, aln_data, ticker_spot))

    # Herman Pre-NY sweep — DOMINANT signal at open
    try:
        from scripts.libs_py.nqstats.classifiers import compute_herman_pre_ny_sweep
        _es_spot_h = ticker_spot if ticker == "ES1" else 0
        from scripts.trader.signals.session_ranges import compute_all_session_ranges
        from scripts.utils.fused_data_loader import load_fused_data
        _df_h = load_fused_data(ticker, timeframe="1m", require_historical=False)
        if _df_h is not None and not _df_h.empty:
            if _df_h.index.tz is None:
                _df_h.index = pd.DatetimeIndex(_df_h.index).tz_localize("UTC").tz_convert(ET)
            elif _df_h.index.tz != ET:
                _df_h.index = _df_h.index.tz_convert(ET)
            _sr = compute_all_session_ranges(_df_h, target_date, ET)
            _pre_ny = _sr.get("PRE_NY", {})
            _london = _sr.get("LONDON", {})
            if _pre_ny and _london:
                _sweep = compute_herman_pre_ny_sweep(_pre_ny, _london.get("high"), _london.get("low"))
                _lines = ["== HERMAN PRE-NY SWEEP (05:00-08:30) — DOMINANT =="]
                _lines.append(f"Result: {_sweep['label']}")
                _lines.append(f"Bias: {_sweep['bias']} ({_sweep['probability']:.1f}%)")
                if _sweep["dominant"]:
                    _lines.append("DOMINANT — overrides ALN. Do not fade.")
                else:
                    _lines.append("Not dominant — wait for 09:30 OR break.")
                _lines.append(f"Read: {_sweep['read']}")
                sections.append("\\n".join(_lines))
    except Exception as e:
        log.warning("[cheat_sheet] Herman Pre-NY sweep failed for %s: %s", ticker, e)'''

if old_herman in content:
    content = content.replace(old_herman, new_herman, 1)
    print("✓ Herman Pre-NY sweep added to open mode")
else:
    print("✗ Could not find ALN block in open mode")

# 3. Add FTFC to open mode (after the ICT dealing range block)
old_ftfc = '''    # Candle Science
    try:
        cs = get_candle_science_read(ticker=ticker)
        sections.append(_format_candle_science_block(base_label, cs))'''
new_ftfc = '''    # FTFC bias + SMA stance
    try:
        from scripts.trader.signals.intraday_blocks import _format_ftfc_block
        sections.append(_format_ftfc_block(ticker, ticker_spot, now_et))
    except Exception as e:
        log.warning("[cheat_sheet] FTFC failed for %s: %s", ticker, e)

    # Candle Science
    try:
        cs = get_candle_science_read(ticker=ticker)
        sections.append(_format_candle_science_block(base_label, cs))'''

if old_ftfc in content:
    content = content.replace(old_ftfc, new_ftfc, 1)
    print("✓ FTFC added to open mode")
else:
    print("✗ Could not find Candle Science block in open mode")

with open('scripts/trader/briefing_core.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")