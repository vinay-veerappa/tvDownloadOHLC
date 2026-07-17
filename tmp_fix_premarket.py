"""Add GEX verdict, Herman Pre-NY, FTFC, and Delivery Triad to premarket mode"""

with open('scripts/trader/briefing_core.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace old GEX structure blocks with GEX positioning verdict in premarket
old_premarket_gex = '''    nq_gex = _extract_gex_levels(nq_unified, "NQ" if "NQ" in unified else "QQQ")
    es_gex = _extract_gex_levels(es_unified, "ES" if "ES" in unified else "SPY")

    sections.append(_format_gex_block("NQ", nq_gex, nq_spot))
    sections.append(_format_gex_block("ES", es_gex, es_spot))'''

new_premarket_gex = '''    nq_gex = _extract_gex_levels(nq_unified, "NQ" if "NQ" in unified else "QQQ")
    es_gex = _extract_gex_levels(es_unified, "ES" if "ES" in unified else "SPY")

    # GEX positioning verdict (session-aware — premarket uses prior close reference)
    try:
        from scripts.trader.signals.intraday_blocks import _format_gex_block as _fmt_gex
        sections.append(_fmt_gex(nq_spot, es_spot, nq_ticker, session="PREMARKET", target_date=target_date))
    except Exception as e:
        log.warning("[premarket] GEX positioning failed: %s", e)'''

if old_premarket_gex in content:
    content = content.replace(old_premarket_gex, new_premarket_gex, 1)
    print("✓ GEX positioning replaced old GEX blocks in premarket")
else:
    print("✗ Could not find premarket GEX blocks")

# 2. Add Herman Pre-NY sweep + FTFC + Delivery Triad after the ICT feature blocks in premarket
old_premarket_ict = '''    except Exception as e:
        log.warning("[premarket] ICT feature blocks failed: %s", e)

    return "\\n\\n".join(sections)'''

new_premarket_ict = '''    except Exception as e:
        log.warning("[premarket] ICT feature blocks failed: %s", e)

    # FTFC bias + SMA stance
    try:
        from scripts.trader.signals.intraday_blocks import _format_ftfc_block
        import pytz as _pytz2
        _now = datetime.now(_pytz2.timezone("America/New_York"))
        sections.append(_format_ftfc_block(nq_ticker, nq_spot, _now))
    except Exception as e:
        log.warning("[premarket] FTFC failed: %s", e)

    # Herman Pre-NY sweep — DOMINANT signal
    try:
        from scripts.libs_py.nqstats.classifiers import compute_herman_pre_ny_sweep
        from scripts.trader.signals.session_ranges import compute_all_session_ranges
        from scripts.utils.fused_data_loader import load_fused_data
        _df = load_fused_data(nq_ticker, timeframe="1m", require_historical=False)
        if _df is not None and not _df.empty:
            if _df.index.tz is None:
                _df.index = pd.DatetimeIndex(_df.index).tz_localize("UTC").tz_convert(ET)
            elif _df.index.tz != ET:
                _df.index = _df.index.tz_convert(ET)
            _sr = compute_all_session_ranges(_df, target_date, ET)
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
        log.warning("[premarket] Herman Pre-NY sweep failed: %s", e)

    # Delivery triad 1-liner
    try:
        from scripts.trader.signals.intraday_blocks import _format_delivery_triad_1liner
        _triad = _format_delivery_triad_1liner(nq_ticker, nq_spot, target_date)
        if _triad:
            sections.append(f"== DELIVERY TRIAD ==\\n{_triad}")
    except Exception as e:
        log.warning("[premarket] Delivery triad failed: %s", e)

    return "\\n\\n".join(sections)'''

if old_premarket_ict in content:
    content = content.replace(old_premarket_ict, new_premarket_ict, 1)
    print("✓ FTFC + Herman Pre-NY + Delivery Triad added to premarket")
else:
    print("✗ Could not find premarket ICT blocks ending")

with open('scripts/trader/briefing_core.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")