"""Session-adaptive intraday blocks.

Each function builds the cheat-sheet blocks relevant to one session.
build_intraday_context() in briefing_core.py calls the appropriate one
based on the current session detected by session_ranges.detect_session().

This modular design makes it easy to add or modify blocks for a specific
session without touching the others.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.trader.signals.session_ranges import (
    compute_all_session_ranges,
    detect_session,
    detect_sweep,
)

log = logging.getLogger(__name__)
_REPO = Path(__file__).parent.parent.parent.parent

# ET timezone
try:
    import pytz
    ET = pytz.timezone("America/New_York")
except ImportError:
    ET = None


def _format_session_header(session: str, now_et: Any, ticker: str) -> str:
    """Build the == CURRENT SESSION == header block."""
    base_label = ticker.replace("1", "").upper()
    time_str = now_et.strftime("%H:%M ET") if hasattr(now_et, "strftime") else "?"
    return f"== CURRENT SESSION ==\n{session} | {time_str} | {base_label}"


def _format_gex_block(ticker_current: float, es_current: float, ticker: str) -> str:
    """GEX level interactions — relevant in all sessions."""
    from scripts.trader.briefing_core import _extract_gex_levels, load_macro_levels
    try:
        unified = load_macro_levels(session="live")
        nq_unified = unified.get("NQ") or unified.get("QQQ") or {}
        es_unified = unified.get("ES") or unified.get("SPY") or {}
        nq_gex = _extract_gex_levels(nq_unified, "NQ" if "NQ" in unified else "QQQ")
        es_gex = _extract_gex_levels(es_unified, "ES" if "ES" in unified else "SPY")
        lines = ["== LEVEL INTERACTIONS =="]
        if nq_gex:
            cw = nq_gex.get("call_wall")
            pw = nq_gex.get("put_wall")
            flip = nq_gex.get("flip") or nq_gex.get("zero_gamma")
            if cw and ticker_current > cw:
                lines.append(f"NQ Call Wall ({cw:,.2f}) BROKEN — bullish")
            elif cw:
                lines.append(f"NQ Call Wall ({cw:,.2f}) overhead — untested")
            if pw and ticker_current < pw:
                lines.append(f"NQ Put Wall ({pw:,.2f}) BROKEN — bearish")
            elif pw:
                lines.append(f"NQ Put Wall ({pw:,.2f}) below — holding")
            if flip:
                lines.append(f"NQ Gamma Flip: {flip:,.2f} — {'above' if ticker_current > flip else 'below'} ({'negative' if ticker_current > flip else 'positive'} gamma)")
        if es_gex:
            cw = es_gex.get("call_wall")
            pw = es_gex.get("put_wall")
            flip = es_gex.get("flip") or es_gex.get("zero_gamma")
            if cw and es_current > cw:
                lines.append(f"ES Call Wall ({cw:,.2f}) BROKEN — bullish")
            elif cw:
                lines.append(f"ES Call Wall ({cw:,.2f}) overhead — untested")
            if pw and es_current < pw:
                lines.append(f"ES Put Wall ({pw:,.2f}) BROKEN — bearish")
            elif pw:
                lines.append(f"ES Put Wall ({pw:,.2f}) below — holding")
            if flip:
                lines.append(f"ES Gamma Flip: {flip:,.2f} — {'above' if es_current > flip else 'below'} ({'negative' if es_current > flip else 'positive'} gamma)")
        return "\n".join(lines)
    except Exception as e:
        log.warning("[intraday:gex] Failed: %s", e)
        return "== LEVEL INTERACTIONS ==\nGEX data unavailable"


def _format_ict_block(ticker: str, ticker_current: float) -> str:
    """ICT dealing range — relevant in all sessions.

    TODO (ICT expansion — tackle next):
      - ICT Killzone pivots: AS.H/AS.L, LO.H/LO.L, NYAM.H/NYAM.L after each KZ ends.
      - ICT Silver Bullet windows: 10:00-11:00 (NY AM), 14:00-15:00 (NY PM), 03:00-04:00 (London).
      - ICT Macros: 09:50-10:10, 10:50-11:10, 13:10-13:40, 15:15-15:45, 02:33-03:00, 04:03-04:30.
      - ICT FVG (Fair Value Gap) detection from 1m/5m data.
      - ICT Order Block detection.
      - ICT Judas Swing detection (sweep of Midnight Open during London/Pre-Market).
      - ICT Market Structure Shift (MSS) / Break of Structure (BOS) on daily/weekly.
      - ICT Draw on Liquidity (DOL): proximity to BSL/SSL pools (PWH, PWL, old D1 highs/lows).
      - ICT Market Delivery Triad: I2E (fill FVG → seek external liquidity) vs E2I (sweep → revert to FVG).
      - ICT IPDA 20/40/60 ranges (rolling daily high/low/equilibrium).
      - SMT Divergence (NQ vs ES, or ES vs RTY) at key levels.
    """
    from scripts.trader.briefing_core import _format_ict_block as _fmt
    from scripts.trader.signals.ict_context import compute_ict_from_htf
    try:
        ict = compute_ict_from_htf(ticker=ticker, current_price=ticker_current)
        base_label = ticker.replace("1", "").upper()
        return _fmt(base_label, ict, ticker_current)
    except Exception as e:
        log.warning("[intraday:ict] Failed: %s", e)
        return "== ICT DEALING RANGE ==\nICT data unavailable"


def _format_liquidity_map_block(
    ticker: str,
    ticker_current: float,
    intraday_bias: str,
    aln_data: dict,
    session_ranges: dict,
    am_high: float | None = None,
    am_low: float | None = None,
    events: list | None = None,
) -> str:
    """ICT liquidity map with raid-swept detection."""
    from scripts.trader.briefing_core import _format_liquidity_map_block as _fmt
    from scripts.trader.signals.ict_context import compute_ict_from_htf
    from scripts.trader.signals.liquidity_map import build_liquidity_map
    try:
        ict = compute_ict_from_htf(ticker=ticker, current_price=ticker_current)
        news_tier = "NONE"
        if events:
            if any(e.get("impact") == "HIGH" for e in events):
                news_tier = "HIGH"
            elif any(e.get("impact") == "MEDIUM" for e in events):
                news_tier = "MEDIUM"

        overnight = {}
        if session_ranges.get("ASIA"):
            overnight = {"high": session_ranges["ASIA"].get("high"), "low": session_ranges["ASIA"].get("low")}

        lm = build_liquidity_map(
            bias=intraday_bias,
            nq_status=aln_data,
            overnight=overnight,
            ict=ict,
            news_tier=news_tier,
        )
        # Raid-swept detection
        raid_target_level = lm.get("raid_target_level")
        raid_swept_note = ""
        if raid_target_level and am_high is not None and am_low is not None:
            if intraday_bias == "BEARISH" and am_high >= raid_target_level:
                raid_swept_note = f" (ALREADY SWEPT — today's AM high {am_high:,.2f} exceeded target)"
            elif intraday_bias == "BULLISH" and am_low <= raid_target_level:
                raid_swept_note = f" (ALREADY SWEPT — today's AM low {am_low:,.2f} pierced target)"
        formatted_lm = _fmt(lm)
        if raid_swept_note:
            formatted_lm = formatted_lm.replace(
                f"Target level: {raid_target_level:,.2f}",
                f"Target level: {raid_target_level:,.2f}{raid_swept_note}",
            )
        return formatted_lm
    except Exception as e:
        log.warning("[intraday:liquidity_map] Failed: %s", e)
        return "== ICT LIQUIDITY MAP ==\nLiquidity map unavailable"


def _format_calendar_block(target_date: date) -> tuple[str, list]:
    """Calendar update — returns (formatted_block, raw_events)."""
    from scripts.trader.briefing_core import fetch_week_events, run_async_safely
    try:
        events = run_async_safely(fetch_week_events(target_date, target_date))
        upcoming = [e for e in events if not e.get("passed", False)]
        passed = [e for e in events if e.get("passed", False)]
        lines = ["== CALENDAR =="]
        if passed:
            lines.append("Passed: " + ", ".join(f"{e.get('time_et','?')} {e.get('name','?')}" for e in passed))
        if upcoming:
            lines.append("Upcoming: " + ", ".join(f"{e.get('time_et','?')} {e.get('name','?')} [{e.get('impact','?')}]" for e in upcoming))
        else:
            lines.append("No more events today.")
        return "\n".join(lines), events
    except Exception as e:
        log.warning("[intraday:calendar] Failed: %s", e)
        return "== CALENDAR ==\nCalendar unavailable", []


def _format_prior_eod_block(ticker: str) -> str:
    """Prior EOD narrative — relevant for Asia session."""
    from scripts.trader.briefing_core import OPTIONS_DATA_DIR
    try:
        eod_path = OPTIONS_DATA_DIR / "daily" / f"latest_trader_narrative_close_{ticker}.md"
        if not eod_path.exists():
            eod_path = OPTIONS_DATA_DIR / "daily" / "latest_trader_narrative_close.md"
        if eod_path.exists():
            text = eod_path.read_text(encoding="utf-8")
            summary = text[:400] + "..." if len(text) > 400 else text
            return "== PRIOR EOD NARRATIVE ==\n" + summary
        return "== PRIOR EOD NARRATIVE ==\nNo EOD narrative available."
    except Exception as e:
        log.warning("[intraday:eod] Failed: %s", e)
        return "== PRIOR EOD NARRATIVE ==\nEOD narrative unavailable"


def _format_range_stack_block(
    df_t: pd.DataFrame,
    ticker: str,
    ticker_current: float,
    session_ranges: dict,
    tf_levels: list[str] | None = None,
) -> str:
    """Multi-timeframe range detection block.

    Computes ranges at multiple timeframes and presents as a stack.
    Also includes compression detection and adaptive tightest-range scan.

    Args:
        df_t: 1m DataFrame (ET-localized).
        ticker: Ticker symbol.
        ticker_current: Current price.
        session_ranges: Output from compute_all_session_ranges().
        tf_levels: Which timeframes to include. Defaults to day-trading set.
    """
    from scripts.trader.signals.range_detection import (
        compute_range_stack,
        detect_compression,
        find_tightest_range,
        format_adaptive_range_block,
        format_range_block,
    )
    try:
        # Default TF set for day trading: micro + short + session + daily
        if tf_levels is None:
            tf_levels = [
                "MICRO_5", "MICRO_15", "MICRO_30",
                "SHORT_60", "SHORT_120",
                "SESSION", "RTH", "DAILY_1",
            ]

        # Load daily parquet for DAILY_1 if needed
        df_1d = None
        if any(tf in _DAILY_TFS_NEEDED for tf in tf_levels):
            try:
                df_1d = pd.read_parquet(_REPO / "data" / f"{ticker}_1d.parquet")
            except Exception:
                pass

        stack = compute_range_stack(
            df_1m=df_t,
            df_1d=df_1d,
            df_1w=None,
            current_price=ticker_current,
            session_ranges=session_ranges,
            tf_levels=tf_levels,
        )

        compression = detect_compression(df_t) if df_t is not None and not df_t.empty else {}

        block = format_range_block(stack, compression)

        # Add adaptive tightest range
        adaptive = find_tightest_range(df_t) if df_t is not None and not df_t.empty else {}
        if adaptive:
            block += "\n\n" + format_adaptive_range_block(adaptive)

        return block
    except Exception as e:
        log.warning("[intraday:range_stack] Failed: %s", e)
        return "== RANGE STACK ==\nRange detection unavailable"


# Which TFs need daily parquet
_DAILY_TFS_NEEDED = {"DAILY_1", "DAILY_3", "DAILY_5"}


# ══════════════════════════════════════════════════════════════════════
# ICT FEATURE BLOCK BUILDERS (from derived parquets via ict_data_loader)
# ══════════════════════════════════════════════════════════════════════

def _format_kz_pivots_block(ticker: str, ticker_current: float, session: str) -> str:
    """Today's ICT killzone pivots (AS.H/AS.L, LO.H/LO.L, NYAM.H/NYAM.L)."""
    try:
        from scripts.trader.signals.ict_data_loader import load_kz_pivots
        kz = load_kz_pivots(ticker, auto_refresh=True)
        if kz.empty:
            return "== ICT KILLZONE PIVOTS ==\nNo pivot data available"

        # Get today's row (or most recent)
        import pytz
        today = datetime.now(pytz.timezone("America/New_York")).date()
        kz["trading_date"] = pd.to_datetime(kz["trading_date"]).dt.date
        today_row = kz[kz["trading_date"] == today]
        if today_row.empty:
            today_row = kz.tail(1)
        if today_row.empty:
            return "== ICT KILLZONE PIVOTS ==\nNo pivot data for today"

        row = today_row.iloc[0]
        lines = ["== ICT KILLZONE PIVOTS =="]

        has_any = False
        for prefix, label in [("asia", "Asia (20:00-00:00)"), ("london", "London (02:00-05:00)"), ("nyam", "NY AM (08:30-11:00)")]:
            high = row.get(f"{prefix}_high")
            low = row.get(f"{prefix}_low")
            if pd.notna(high) and pd.notna(low):
                has_any = True
                mid = row.get(f"{prefix}_mid", (high + low) / 2)
                rng = row.get(f"{prefix}_range", high - low)
                # Position relative to current price
                if ticker_current > 0 and rng > 0:
                    if ticker_current > high:
                        pos_str = f" | Price ABOVE range (+{(ticker_current - high):,.2f})"
                    elif ticker_current < low:
                        pos_str = f" | Price BELOW range (-{(low - ticker_current):,.2f})"
                    else:
                        pos = (ticker_current - low) / rng * 100
                        pos_str = f" | Price at {pos:.0f}% of range"
                else:
                    pos_str = ""
                lines.append(f"{label}: H {high:,.2f} | L {low:,.2f} | Mid {mid:,.2f} | Range {rng:,.2f}{pos_str}")

        if not has_any:
            return "== ICT KILLZONE PIVOTS ==\nNo pivots computed yet (sessions not complete)"

        return "\n".join(lines)
    except Exception as e:
        log.warning("[kz_pivots] Failed: %s", e)
        return "== ICT KILLZONE PIVOTS ==\nPivot data unavailable"


def _format_ipda_block(ticker: str, ticker_current: float) -> str:
    """IPDA 20/40/60 rolling dealing ranges and current position.

    These are *multi-day* rolling ranges (20/40/60 daily candles),
    distinct from the single-day PDH/PDL dealing range shown in the
    ICT Dealing Range block.
    """
    try:
        from scripts.trader.signals.ict_data_loader import load_ipda
        ipda = load_ipda(ticker, auto_refresh=True)
        if ipda.empty:
            return "== IPDA 20/40/60 (multi-day) ==\nNo IPDA data available"

        import pytz
        today = datetime.now(pytz.timezone("America/New_York")).date()
        ipda["trading_date"] = pd.to_datetime(ipda["trading_date"]).dt.date
        today_row = ipda[ipda["trading_date"] == today]
        if today_row.empty:
            today_row = ipda.tail(1)
        if today_row.empty:
            return "== IPDA 20/40/60 (multi-day) ==\nNo IPDA data for today"

        row = today_row.iloc[0]
        lines = ["== IPDA 20/40/60 (multi-day rolling) =="]
        lines.append("Note: These are 20/40/60-day rolling ranges, not the daily PDH/PDL dealing range.")

        for n, label in [(20, "IPDA-20"), (40, "IPDA-40"), (60, "IPDA-60")]:
            hi = row.get(f"ipda{n}_high")
            lo = row.get(f"ipda{n}_low")
            eq = row.get(f"ipda{n}_eq")
            pct = row.get(f"ipda{n}_pct")
            if pd.notna(hi) and pd.notna(lo):
                pos = "PREMIUM" if pd.notna(pct) and pct > 50 else ("DISCOUNT" if pd.notna(pct) else "")
                pct_str = f" ({pct:.1f}% — {pos})" if pd.notna(pct) else ""
                lines.append(f"{label}: H {hi:,.2f} | L {lo:,.2f} | Eq {eq:,.2f}{pct_str}")

        return "\n".join(lines)
    except Exception as e:
        log.warning("[ipda] Failed: %s", e)
        return "== IPDA 20/40/60 (multi-day) ==\nIPDA data unavailable"


def _format_silver_bullet_block(now_et: Any) -> str:
    """Silver Bullet window status (active or next upcoming)."""
    try:
        from scripts.trader.signals.ict_data_loader import load_active_silver_bullet
        sb = load_active_silver_bullet(now_et)
        lines = ["== ICT SILVER BULLET =="]
        if sb["active"]:
            lines.append(f"IN WINDOW: {sb['name']} ({sb['window']})")
            lines.append("Rules: HTF bias -> liquidity sweep -> displacement -> FVG entry")
            lines.append("One trade per window. Wait for sweep + FVG confirmation.")
        elif sb["next_window"]:
            lines.append(f"Next: {sb['next_window']} at {sb['next_time']}")
            lines.append("No active Silver Bullet window.")
        else:
            lines.append("No Silver Bullet windows remaining today.")
        return "\n".join(lines)
    except Exception as e:
        log.warning("[silver_bullet] Failed: %s", e)
        return "== ICT SILVER BULLET ==\nData unavailable"


def _format_macro_block(now_et: Any) -> str:
    """ICT Macro window status (active or next upcoming)."""
    try:
        from scripts.trader.signals.ict_data_loader import load_active_macro
        macro = load_active_macro(now_et)
        lines = ["== ICT MACROS =="]
        if macro["active"]:
            lines.append(f"IN MACRO: {macro['name']} ({macro['window']})")
            lines.append("High probability for liquidity sweeps, FVG formations, displacement.")
        elif macro["next_macro"]:
            lines.append(f"Next macro: {macro['next_macro']} at {macro['next_time']}")
            lines.append("No active macro window.")
        else:
            lines.append("No macro windows remaining today.")
        return "\n".join(lines)
    except Exception as e:
        log.warning("[macro] Failed: %s", e)
        return "== ICT MACROS ==\nData unavailable"


def _format_imbalance_block(ticker: str, ticker_current: float, session_date: date | None = None, now_et: Any = None) -> str:
    """Today's unfilled FVGs and Volume Imbalances near current price.

    Only shows imbalances up to the current time (no future bars).
    Proximity threshold: 0.25% of current price (not 1%).
    """
    try:
        from scripts.trader.signals.ict_data_loader import load_imbalances
        # Load 5m imbalances for today
        imb = load_imbalances(ticker, "5m", auto_refresh=True, session_date=session_date)
        if imb.empty:
            return "== ICT IMBALANCES (5m) ==\nNo imbalances detected today"

        # Filter to bars up to now_et (no future bars)
        if now_et is not None:
            now_naive = now_et.replace(tzinfo=None) if hasattr(now_et, 'tzinfo') and now_et.tzinfo else now_et
            imb = imb[imb.index <= now_naive]
        if imb.empty:
            return "== ICT IMBALANCES (5m) ==\nNo imbalances yet in current session"

        lines = ["== ICT IMBALANCES (5m) =="]

        # Proximity threshold: 0.25% of current price
        proximity_pct = 0.25
        threshold = ticker_current * proximity_pct / 100 if ticker_current > 0 else 100

        fvgs = imb[imb["fvg_type"] != 0].copy()
        vis = imb[imb["vi_type"] != 0].copy()

        if not fvgs.empty:
            # Most recent 5 FVGs
            recent_fvgs = fvgs.tail(5)
            lines.append("Fair Value Gaps:")
            for _, row in recent_fvgs.iterrows():
                ftype = "Bullish" if row["fvg_type"] == 1 else "Bearish"
                top = row["fvg_top"]
                bot = row["fvg_bottom"]
                dist = abs(ticker_current - (top + bot) / 2) if ticker_current > 0 else 0
                near = " (NEAR)" if dist < threshold else ""
                lines.append(f"  {ftype} FVG {bot:,.2f}-{top:,.2f} @ {row.name.strftime('%H:%M')}{near}")

        if not vis.empty:
            recent_vis = vis.tail(5)
            lines.append("Volume Imbalances:")
            for _, row in recent_vis.iterrows():
                vtype = "Bullish" if row["vi_type"] == 1 else "Bearish"
                top = row["vi_top"]
                bot = row["vi_bottom"]
                dist = abs(ticker_current - (top + bot) / 2) if ticker_current > 0 else 0
                near = " (NEAR)" if dist < threshold else ""
                lines.append(f"  {vtype} VI {bot:,.2f}-{top:,.2f} @ {row.name.strftime('%H:%M')}{near}")

        if fvgs.empty and vis.empty:
            lines.append("No FVGs or VIs detected in current session")

        return "\n".join(lines)
    except Exception as e:
        log.warning("[imbalance] Failed: %s", e)
        return "== ICT IMBALANCES (5m) ==\nImbalance data unavailable"


def _format_gaps_block(ticker: str, ticker_current: float) -> str:
    """Active NWOG/NDOG/RTH gaps with fill status.

    Shows today's gaps + recent unfilled gaps (last 30 days only).
    Filters out NaN entries.
    """
    try:
        from scripts.trader.signals.ict_data_loader import load_gaps
        gaps = load_gaps(ticker, auto_refresh=True)
        if gaps.empty:
            return "== ICT GAPS ==\nNo gap data available"

        import pytz
        from datetime import timedelta
        today = datetime.now(pytz.timezone("America/New_York")).date()

        gaps["session_date"] = pd.to_datetime(gaps["session_date"]).dt.date
        # Filter out NaN gap sizes
        gaps = gaps.dropna(subset=["gap_high", "gap_low", "gap_size"])
        # Filter to last 30 days for unfilled gaps
        cutoff = today - timedelta(days=30)

        today_gaps = gaps[gaps["session_date"] == today]
        unfilled = gaps[(~gaps["filled"].astype(bool)) & (gaps["session_date"] >= cutoff)].tail(5)

        lines = ["== ICT GAPS =="]

        if not today_gaps.empty:
            lines.append("Today's gaps:")
            for _, row in today_gaps.iterrows():
                filled_str = "FILLED" if row["filled"] else "UNFILLED"
                lines.append(
                    f"  {row['gap_type']}: {row['gap_low']:,.2f}-{row['gap_high']:,.2f} "
                    f"(size {row['gap_size']:,.2f}, CE {row['gap_ce']:,.2f}) [{filled_str}]"
                )

        if not unfilled.empty:
            lines.append("Recent unfilled gaps (magnet levels):")
            for _, row in unfilled.iterrows():
                lines.append(
                    f"  {row['gap_type']} ({row['session_date']}): "
                    f"{row['gap_low']:,.2f}-{row['gap_high']:,.2f} CE {row['gap_ce']:,.2f}"
                )

        if today_gaps.empty and unfilled.empty:
            lines.append("No active gaps")

        return "\n".join(lines)
    except Exception as e:
        log.warning("[gaps] Failed: %s", e)
        return "== ICT GAPS ==\nGap data unavailable"


def _format_structure_block(ticker: str, ticker_current: float, session_date: date | None = None, now_et: Any = None) -> str:
    """Recent BOS/MSS/CISD events and current trend direction from swings."""
    try:
        from scripts.trader.signals.ict_data_loader import load_structure
        # Use 1h for structural overview (less noise than 5m)
        struct = load_structure(ticker, "1h", auto_refresh=True, session_date=session_date)
        if struct.empty:
            return "== ICT STRUCTURE (1h) ==\nNo structure data available"

        # Filter to bars up to now_et
        if now_et is not None:
            now_naive = now_et.replace(tzinfo=None) if hasattr(now_et, 'tzinfo') and now_et.tzinfo else now_et
            struct = struct[struct.index <= now_naive]
        if struct.empty:
            return "== ICT STRUCTURE (1h) ==\nNo structure events yet in current session"

        lines = ["== ICT STRUCTURE (1h) =="]

        # Recent break events
        breaks = struct[(struct["break_high"] != 0) | (struct["break_low"] != 0)]
        if not breaks.empty:
            recent_breaks = breaks.tail(3)
            lines.append("Recent structure breaks:")
            for _, row in recent_breaks.iterrows():
                level = row.get("swing_level", 0)
                level_str = f"{level:,.2f}" if pd.notna(level) and level != 0 else "prior swing"
                if row["break_high"]:
                    lines.append(f"  BOS HIGH @ {row.name.strftime('%H:%M')} — broke {level_str} (bullish continuation)")
                if row["break_low"]:
                    lines.append(f"  BOS LOW @ {row.name.strftime('%H:%M')} — broke {level_str} (bearish continuation)")

        # Recent CISD events
        cisds = struct[struct["cisd_type"] != 0]
        if not cisds.empty:
            recent_cisds = cisds.tail(3)
            lines.append("Recent CISD (state changes):")
            for _, row in recent_cisds.iterrows():
                direction = "bullish" if row["cisd_type"] == 1 else "bearish"
                lines.append(f"  {direction.upper()} CISD @ {row.name.strftime('%H:%M')}")

        # Latest swing
        swings = struct[struct["swing_type"] != 0]
        if not swings.empty:
            last_swing = swings.iloc[-1]
            swing_type = "High" if last_swing["swing_type"] == 1 else "Low"
            lines.append(f"Latest swing: {swing_type} at {last_swing['swing_level']:,.2f} @ {last_swing.name.strftime('%H:%M')}")

        if breaks.empty and cisds.empty and swings.empty:
            lines.append("No structure events detected in current session")

        return "\n".join(lines)
    except Exception as e:
        log.warning("[structure] Failed: %s", e)
        return "== ICT STRUCTURE (1h) ==\nStructure data unavailable"


def _format_ob_block(ticker: str, ticker_current: float, session_date: date | None = None, now_et: Any = None) -> str:
    """Today's active Order Blocks near current price."""
    try:
        from scripts.trader.signals.ict_data_loader import load_orderblocks
        obs = load_orderblocks(ticker, "5m", auto_refresh=True, session_date=session_date)
        if obs.empty:
            return "== ICT ORDER BLOCKS (5m) ==\nNo order blocks detected today"

        if now_et is not None:
            now_naive = now_et.replace(tzinfo=None) if hasattr(now_et, 'tzinfo') and now_et.tzinfo else now_et
            obs = obs[obs.index <= now_naive]
        if obs.empty:
            return "== ICT ORDER BLOCKS (5m) ==\nNo order blocks yet in current session"

        lines = ["== ICT ORDER BLOCKS (5m) =="]

        # Proximity threshold: 0.5% of current price
        threshold = ticker_current * 0.5 / 100 if ticker_current > 0 else 100

        recent_obs = obs.tail(5)
        for _, row in recent_obs.iterrows():
            ob_type = "Bullish" if row["ob_type"] == 1 else "Bearish"
            top = row["ob_top"]
            bot = row["ob_bottom"]
            mid = (top + bot) / 2
            dist = abs(ticker_current - mid) if ticker_current > 0 else 0
            near = " (NEAR)" if dist < threshold else ""
            lines.append(f"  {ob_type} OB {bot:,.2f}-{top:,.2f} @ {row.name.strftime('%H:%M')}{near}")

        return "\n".join(lines)
    except Exception as e:
        log.warning("[ob] Failed: %s", e)
        return "== ICT ORDER BLOCKS (5m) ==\nOrder block data unavailable"


def _format_liquidity_block(ticker: str, ticker_current: float, session_date: date | None = None, now_et: Any = None) -> str:
    """Today's liquidity pools (BSL/SSL/EQH/EQL) near current price."""
    try:
        from scripts.trader.signals.ict_data_loader import load_liquidity
        liq = load_liquidity(ticker, "1h", auto_refresh=True, session_date=session_date)
        if liq.empty:
            return "== ICT LIQUIDITY (1h) ==\nNo liquidity data available"

        if now_et is not None:
            now_naive = now_et.replace(tzinfo=None) if hasattr(now_et, 'tzinfo') and now_et.tzinfo else now_et
            liq = liq[liq.index <= now_naive]
        if liq.empty:
            return "== ICT LIQUIDITY (1h) ==\nNo liquidity pools yet in current session"

        lines = ["== ICT LIQUIDITY POOLS (1h) =="]

        # Show most recent BSL and SSL
        bsls = liq[liq["liq_kind"] == "BSL"]
        ssls = liq[liq["liq_kind"] == "SSL"]
        eqhs = liq[liq["liq_kind"] == "EQH"]
        eqls = liq[liq["liq_kind"] == "EQL"]

        if not bsls.empty:
            last_bsl = bsls.iloc[-1]
            dist = abs(ticker_current - last_bsl["liq_level"]) if ticker_current > 0 else 0
            lines.append(f"  BSL (buy stops): {last_bsl['liq_level']:,.2f} @ {last_bsl.name.strftime('%H:%M')} ({dist:,.2f} above)")
        if not ssls.empty:
            last_ssl = ssls.iloc[-1]
            dist = abs(ticker_current - last_ssl["liq_level"]) if ticker_current > 0 else 0
            lines.append(f"  SSL (sell stops): {last_ssl['liq_level']:,.2f} @ {last_ssl.name.strftime('%H:%M')} ({dist:,.2f} below)")
        if not eqhs.empty:
            last_eqh = eqhs.iloc[-1]
            lines.append(f"  EQH (equal highs): {last_eqh['liq_level']:,.2f} @ {last_eqh.name.strftime('%H:%M')}")
        if not eqls.empty:
            last_eql = eqls.iloc[-1]
            lines.append(f"  EQL (equal lows): {last_eql['liq_level']:,.2f} @ {last_eql.name.strftime('%H:%M')}")

        if bsls.empty and ssls.empty and eqhs.empty and eqls.empty:
            lines.append("No liquidity pools detected in current session")

        return "\n".join(lines)
    except Exception as e:
        log.warning("[liquidity] Failed: %s", e)
        return "== ICT LIQUIDITY (1h) ==\nLiquidity data unavailable"


def _format_smt_block(ticker: str, session_date: date | None = None, now_et: Any = None) -> str:
    """SMT Divergence status (NQ vs ES)."""
    try:
        from scripts.trader.signals.ict_data_loader import load_smt
        # SMT is only for NQ1 (NQ vs ES)
        if ticker != "NQ1":
            return ""  # Skip SMT for non-NQ tickers
        smt = load_smt("NQ1", auto_refresh=True, session_date=session_date)
        if smt.empty:
            return "== SMT DIVERGENCE (NQ vs ES) ==\nNo SMT data available"

        if now_et is not None:
            now_naive = now_et.replace(tzinfo=None) if hasattr(now_et, 'tzinfo') and now_et.tzinfo else now_et
            smt = smt[smt.index <= now_naive]
        if smt.empty:
            return "== SMT DIVERGENCE (NQ vs ES) ==\nNo SMT events yet today"

        lines = ["== SMT DIVERGENCE (NQ vs ES) =="]

        # Show most recent SMT events
        recent = smt.tail(3)
        for _, row in recent.iterrows():
            direction = "bullish" if row["smt_type"] == 1 else "bearish"
            lines.append(f"  {direction.upper()} SMT @ {row.name.strftime('%H:%M')}")

        if len(smt) == 0:
            lines.append("No SMT divergence detected today")

        return "\n".join(lines)
    except Exception as e:
        log.warning("[smt] Failed: %s", e)
        return "== SMT DIVERGENCE (NQ vs ES) ==\nSMT data unavailable"


def _format_delivery_triad_block(ticker: str, ticker_current: float, session_date: date | None = None, now_et: Any = None) -> str:
    """Market Delivery Triad — determines if market is in I2E or E2I mode.

    I2E (Internal to External): price just filled/mitigated an FVG -> next draw is external liquidity (BSL/SSL).
    E2I (External to Internal): price just swept external liquidity -> next draw is internal imbalance (FVG).

    Uses the imbalance parquet (FVGs) and liquidity parquet (BSL/SSL) to determine the most recent event type.
    """
    try:
        from scripts.trader.signals.ict_data_loader import load_imbalances, load_liquidity

        # Load today's data
        imb = load_imbalances(ticker, "5m", auto_refresh=True, session_date=session_date)
        liq = load_liquidity(ticker, "1h", auto_refresh=True, session_date=session_date)

        if now_et is not None:
            now_naive = now_et.replace(tzinfo=None) if hasattr(now_et, 'tzinfo') and now_et.tzinfo else now_et
            if not imb.empty:
                imb = imb[imb.index <= now_naive]
            if not liq.empty:
                liq = liq[liq.index <= now_naive]

        lines = ["== ICT DELIVERY TRIAD (I2E / E2I) =="]

        # Find the most recent FVG event
        recent_fvg_time = None
        recent_fvg_type = None
        if not imb.empty:
            fvgs = imb[imb["fvg_type"] != 0]
            if not fvgs.empty:
                last_fvg = fvgs.iloc[-1]
                recent_fvg_time = last_fvg.name
                recent_fvg_type = "bullish" if last_fvg["fvg_type"] == 1 else "bearish"

        # Find the most recent liquidity sweep (a BSL/SSL where price pierced then reversed)
        # For simplicity, we check if the latest liquidity pool is near current price (suggesting a sweep)
        recent_liq_time = None
        recent_liq_kind = None
        recent_liq_level = None
        if not liq.empty:
            last_liq = liq.iloc[-1]
            recent_liq_time = last_liq.name
            recent_liq_kind = last_liq["liq_kind"]
            recent_liq_level = last_liq["liq_level"]

        # Determine mode: whichever happened more recently
        if recent_fvg_time is None and recent_liq_time is None:
            lines.append("No FVG or liquidity events detected yet — no delivery triad signal.")
            return "\n".join(lines)

        fvg_ts = recent_fvg_time.to_pydatetime() if hasattr(recent_fvg_time, 'to_pydatetime') else recent_fvg_time
        liq_ts = recent_liq_time.to_pydatetime() if hasattr(recent_liq_time, 'to_pydatetime') else recent_liq_time

        # Strip timezone for comparison
        if hasattr(fvg_ts, 'replace'):
            fvg_ts = fvg_ts.replace(tzinfo=None)
        if hasattr(liq_ts, 'replace'):
            liq_ts = liq_ts.replace(tzinfo=None)

        if recent_fvg_time and (recent_liq_time is None or fvg_ts > liq_ts):
            # FVG happened more recently -> I2E mode (price filled an FVG, now seeking liquidity)
            lines.append(f"Mode: I2E (Internal -> External)")
            lines.append(f"  Most recent: {recent_fvg_type} FVG @ {recent_fvg_time.strftime('%H:%M')}")
            lines.append(f"  Price just rebalanced an imbalance -> next draw is external liquidity")
            if recent_liq_level and ticker_current > 0:
                if recent_liq_kind in ("BSL", "EQH") and recent_liq_level > ticker_current:
                    lines.append(f"  Target: BSL at {recent_liq_level:,.2f} ({abs(recent_liq_level - ticker_current):,.2f} above)")
                elif recent_liq_kind in ("SSL", "EQL") and recent_liq_level < ticker_current:
                    lines.append(f"  Target: SSL at {recent_liq_level:,.2f} ({abs(ticker_current - recent_liq_level):,.2f} below)")
        elif recent_liq_time:
            # Liquidity happened more recently -> E2I mode (price swept liquidity, now seeking FVG)
            lines.append(f"Mode: E2I (External -> Internal)")
            lines.append(f"  Most recent: {recent_liq_kind} at {recent_liq_level:,.2f} @ {recent_liq_time.strftime('%H:%M')}")
            lines.append(f"  Price just swept external liquidity -> next draw is an internal imbalance (FVG)")
            if not imb.empty:
                fvgs = imb[imb["fvg_type"] != 0]
                if not fvgs.empty:
                    last_fvg = fvgs.iloc[-1]
                    fvg_mid = (last_fvg["fvg_top"] + last_fvg["fvg_bottom"]) / 2
                    fvg_dir = "bullish" if last_fvg["fvg_type"] == 1 else "bearish"
                    dist = abs(ticker_current - fvg_mid) if ticker_current > 0 else 0
                    lines.append(f"  Target: {fvg_dir} FVG at {last_fvg['fvg_bottom']:,.2f}-{last_fvg['fvg_top']:,.2f} ({dist:,.2f} away)")

        return "\n".join(lines)
    except Exception as e:
        log.warning("[delivery_triad] Failed: %s", e)
        return "== ICT DELIVERY TRIAD ==\nDelivery triad data unavailable"


def _format_ftfc_block(ticker: str, ticker_current: float, now_et: Any) -> str:
    """Full Timeframe Continuity bias — 3 separate views + session-adaptive bias.

    View 1: Candle FTFC — all timeframes have close > open (green candle)
    View 2: MS FTFC — all timeframes have HH/HL (market structure bullish)
    View 3: 200 SMA — price above/below 200-day SMA on daily

    Plus session-adaptive combined bias that picks the best model for the
    current session time.
    """
    try:
        from scripts.trader.signals.ict_data_loader import compute_ftfc
        ftfc = compute_ftfc(ticker, ticker_current, now_et)

        lines = ["== FTFC BIAS (Full Timeframe Continuity) =="]

        # View 1: Candle FTFC
        candle = ftfc.get("candle_ftfc", {})
        lines.append(f"Candle FTFC: {candle.get('bias', 'N/A')} [{candle.get('alignment', 'N/A')}]")
        per_tf_candle = candle.get("per_tf", {})
        tf_str = " | ".join(f"{tf}:{d[0]}" for tf, d in per_tf_candle.items() if d and d != "N/A")
        lines.append(f"  {tf_str}")

        # View 2: MS FTFC
        ms = ftfc.get("ms_ftfc", {})
        lines.append(f"MS FTFC: {ms.get('bias', 'N/A')} [{ms.get('alignment', 'N/A')}]")
        per_tf_ms = ms.get("per_tf", {})
        tf_str_ms = " | ".join(f"{tf}:{d[0]}" for tf, d in per_tf_ms.items() if d and d != "N/A")
        lines.append(f"  {tf_str_ms}")

        # View 3: 200 SMA (multi-TF)
        sma = ftfc.get("sma_200", {})
        sma_dir = sma.get("direction", "N/A")
        sma_val = sma.get("daily_value", "N/A")
        lines.append(f"200 SMA (daily): {sma_dir} (price {'above' if sma_dir == 'BULLISH' else 'below' if sma_dir == 'BEARISH' else 'at'} {sma_val})")
        # Per-TF 200 SMA
        per_tf_sma_dirs = sma.get("per_tf_dirs", {})
        if per_tf_sma_dirs:
            sma_tf_str = " | ".join(f"{tf}:{d[0]}" for tf, d in per_tf_sma_dirs.items() if d)
            sma_bull = sum(1 for d in per_tf_sma_dirs.values() if d == "BULLISH")
            sma_bear = sum(1 for d in per_tf_sma_dirs.values() if d == "BEARISH")
            lines.append(f"  200 SMA intraday: {sma_tf_str} [{sma_bull}B/{sma_bear}R]")

        # Combined
        combined = ftfc.get("combined", {})
        lines.append(f"Combined: {combined.get('bias', 'NONE')}")

        # Session-adaptive bias
        sess = ftfc.get("session_bias", {})
        sess_bias = sess.get("bias", "N/A")
        sess_model = sess.get("model", "N/A")
        sess_conf = sess.get("confidence", 0)
        lines.append(f"Session Bias: {sess_bias} via {sess_model} ({sess_conf}% confidence)")

        lines.append(f"Summary: {ftfc.get('summary', 'N/A')}")

        # Guidance
        if sess_bias == "BULLISH" or sess_bias == "BEARISH":
            lines.append(f"Direction: {sess_bias} — use ICT levels (FVG, OB, KZ pivots) for entries in this direction")
        elif "NEUTRAL" in str(sess_bias):
            lines.append("Direction: NEUTRAL — no FTFC aligned bias. Use ICT levels for entry timing only.")

        return "\n".join(lines)
    except Exception as e:
        log.warning("[ftfc] Failed: %s", e)
        return "== FTFC BIAS ==\nFTFC data unavailable"


def _format_ict_features_block(
    ticker: str,
    ticker_current: float,
    session: str,
    now_et: Any,
    target_date: date,
) -> list[str]:
    """Build all ICT feature blocks for a session.

    Returns a list of formatted block strings. This is the one-stop
    function that all session builders call to get the full ICT feature
    stack: FTFC bias + KZ pivots + IPDA + Silver Bullet + Macros +
    Structure + OB + Imbalances + Liquidity + Delivery Triad + SMT + Gaps.

    FTFC provides the DIRECTIONAL BIAS.
    ICT concepts provide ENTRY TARGETS and LEVELS.
    """
    blocks: list[str] = []
    # FTFC bias — the directional bias (replaces ICT Daily Bias)
    blocks.append(_format_ftfc_block(ticker, ticker_current, now_et))
    # ICT features — entry targets and levels (not directional bias)
    blocks.append(_format_kz_pivots_block(ticker, ticker_current, session))
    blocks.append(_format_ipda_block(ticker, ticker_current))
    blocks.append(_format_silver_bullet_block(now_et))
    blocks.append(_format_macro_block(now_et))
    blocks.append(_format_structure_block(ticker, ticker_current, target_date, now_et))
    blocks.append(_format_ob_block(ticker, ticker_current, target_date, now_et))
    blocks.append(_format_imbalance_block(ticker, ticker_current, target_date, now_et))
    blocks.append(_format_liquidity_block(ticker, ticker_current, target_date, now_et))
    blocks.append(_format_delivery_triad_block(ticker, ticker_current, target_date, now_et))
    blocks.append(_format_smt_block(ticker, target_date, now_et))
    blocks.append(_format_gaps_block(ticker, ticker_current))
    return [b for b in blocks if b]


# ══════════════════════════════════════════════════════════════════════
# SESSION-SPECIFIC BLOCK BUILDERS
# Each returns a list of formatted strings (cheat-sheet blocks).
# ══════════════════════════════════════════════════════════════════════

def build_asia_blocks(
    df_t: pd.DataFrame,
    ticker: str,
    ticker_current: float,
    es_current: float,
    target_date: date,
    session_ranges: dict,
    now_et: Any = None,
) -> list[str]:
    """ASIA session (18:00-02:00 ET): Overnight globex, prior EOD, levels for tomorrow."""
    base_label = ticker.replace("1", "").upper()
    sections: list[str] = []

    # Prior EOD narrative
    sections.append(_format_prior_eod_block(ticker))

    # Globex overnight trajectory
    try:
        if df_t is not None and not df_t.empty:
            globex_start = pd.Timestamp(target_date).tz_localize(ET) + pd.Timedelta(hours=18)
            globex = df_t[df_t.index >= globex_start]
            if not globex.empty:
                g_open = float(globex["open"].iloc[0])
                g_high = float(globex["high"].max())
                g_low = float(globex["low"].min())
                g_current = float(globex["close"].iloc[-1])
                chg = (g_current / g_open - 1) * 100
                lines = [f"== GLOBEX OVERNIGHT ({base_label}) =="]
                lines.append(f"Open {g_open:,.2f} → Current {g_current:,.2f} ({chg:+.2f}%)")
                lines.append(f"High {g_high:,.2f} | Low {g_low:,.2f}")
                if g_current > g_open:
                    lines.append("Trajectory: drift higher")
                elif g_current < g_open:
                    lines.append("Trajectory: drift lower")
                else:
                    lines.append("Trajectory: flat")
                sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[asia:globex] Failed: %s", e)

    # GEX levels
    sections.append(_format_gex_block(ticker_current, es_current, ticker))

    # ICT dealing range
    sections.append(_format_ict_block(ticker, ticker_current))

    # Calendar
    cal_block, _ = _format_calendar_block(target_date)
    sections.append(cal_block)

    # Asia range size (Herman filter)
    try:
        if session_ranges.get("ASIA") and session_ranges["ASIA"].get("range") and ticker_current:
            asia_range_pct = (session_ranges["ASIA"]["range"] / ticker_current) * 100
            if asia_range_pct < 0.48:
                regime = "SMALL — trend continuation regime"
            else:
                regime = "LARGE — mean reversion regime"
            lines = ["== HERMAN ASIA RANGE =="]
            lines.append(f"Range: {session_ranges['ASIA']['range']:,.2f} ({asia_range_pct:.2f}%)")
            lines.append(f"Regime: {regime}")
            sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[asia:herman] Failed: %s", e)

    # ICT feature blocks (KZ pivots, IPDA, Silver Bullet, Macros, Imbalances, Gaps)
    sections.extend(_format_ict_features_block(ticker, ticker_current, "ASIA", now_et, target_date))

    # Daily Profiler (session outcomes, predictions, levels)
    try:
        from scripts.trader.signals.profiler import build_dual_profiler_block
        sections.append(build_dual_profiler_block(
            ticker, "ES1", ticker_current, es_current, target_date, now_et,
        ))
    except Exception as e:
        log.warning("[asia:profiler] Failed: %s", e)

    # Quarters Theory (overnight combo + hourly candle structure)
    try:
        from scripts.trader.signals.quarters_theory import build_quarters_block
        asia_status = session_ranges.get("ASIA", {}).get("status", "") if session_ranges else ""
        london_status = session_ranges.get("LONDON", {}).get("status", "") if session_ranges else ""
        sections.append(build_quarters_block(
            ticker, df_t, now_et, asia_status, london_status,
        ))
    except Exception as e:
        log.warning("[asia:quarters] Failed: %s", e)

    # Multi-timeframe range stack
    sections.append(_format_range_stack_block(
        df_t, ticker, ticker_current, session_ranges,
        tf_levels=["MICRO_5", "MICRO_15", "MICRO_30", "SHORT_60", "SHORT_120", "SESSION", "DAILY_1"],
    ))

    return sections


def build_london_blocks(
    df_t: pd.DataFrame,
    ticker: str,
    ticker_current: float,
    es_current: float,
    target_date: date,
    session_ranges: dict,
    now_et: Any = None,
) -> list[str]:
    """LONDON session (02:00-08:30 ET): Asia complete, London forming, Herman OR/sweep logic."""
    base_label = ticker.replace("1", "").upper()
    sections: list[str] = []

    # Asia box (complete)
    asia = session_ranges.get("ASIA", {})
    if asia:
        lines = [f"== ASIA BOX ({base_label}) — COMPLETE =="]
        lines.append(f"High {asia.get('high', 0):,.2f} | Low {asia.get('low', 0):,.2f} | Range {asia.get('range', 0):,.2f}")
        sections.append("\n".join(lines))

    # Pre-London box (00:00-02:00)
    pl = session_ranges.get("PL", {})
    if pl:
        lines = ["== PRE-LONDON (00:00-02:00) =="]
        lines.append(f"High {pl.get('high', 0):,.2f} | Low {pl.get('low', 0):,.2f}")
        # PL sweep of Asia
        sweep = detect_sweep(pl, asia.get("high"), asia.get("low"))
        if sweep["swept_high"]:
            lines.append("PL swept Asia HIGH → 77.2% London sweeps high again (continuation)")
        if sweep["swept_low"]:
            lines.append("PL swept Asia LOW → 69.6% London sweeps low again (continuation)")
        if not sweep["swept_high"] and not sweep["swept_low"]:
            lines.append("PL inside Asia — watch London OR (02:00-03:00) for direction")
        sections.append("\n".join(lines))

    # London box (forming)
    london = session_ranges.get("LONDON", {})
    if london:
        lines = ["== LONDON BOX (02:00-05:00) — FORMING =="]
        lines.append(f"High {london.get('high', 0):,.2f} | Low {london.get('low', 0):,.2f}")
        # London sweep of Asia
        sweep = detect_sweep(london, asia.get("high"), asia.get("low"))
        if sweep["swept_high"]:
            lines.append("London swept Asia HIGH (60% historical probability)")
        if sweep["swept_low"]:
            lines.append("London swept Asia LOW (50% historical probability)")
        sections.append("\n".join(lines))

    # London OR (02:00-03:00)
    try:
        if df_t is not None and not df_t.empty:
            or_start = pd.Timestamp(target_date).tz_localize(ET) + pd.Timedelta(hours=2)
            or_end = pd.Timestamp(target_date).tz_localize(ET) + pd.Timedelta(hours=3)
            or_df = df_t[(df_t.index >= or_start) & (df_t.index <= or_end)]
            if not or_df.empty:
                or_high = float(or_df["high"].max())
                or_low = float(or_df["low"].min())
                lines = ["== LONDON OPENING RANGE (02:00-03:00) =="]
                lines.append(f"OR High {or_high:,.2f} | OR Low {or_low:,.2f}")
                if ticker_current > or_high:
                    lines.append("OR broken HIGH → 76.5% bullish continuation")
                elif ticker_current < or_low:
                    lines.append("OR broken LOW → 73.8% bearish continuation")
                else:
                    lines.append("OR not yet broken — waiting for direction")
                # Sweep-return: 02:00-03:00 sweep → 72.4% return to open
                lines.append("Sweep-return: 02:00-03:00 sweep → 72.4% return to open (fade)")
                sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[london:or] Failed: %s", e)

    # ALN pattern (partial)
    try:
        from scripts.libs_py.nqstats.engine import NQStatsEngine
        if df_t is not None and not df_t.empty:
            engine = NQStatsEngine(df_t.tail(5000), ticker=ticker)
            engine.process()
            latest = engine.get_latest_status()
            lines = [f"== ALN PATTERN ({base_label}) — PARTIAL =="]
            lines.append(f"Pattern: {latest.get('aln', 'N/A')} | Broken: {latest.get('broken', 'N/A')}")
            lh = latest.get("london_high")
            ll = latest.get("london_low")
            if lh and ll:
                lines.append(f"London High {lh:,.2f} | London Low {ll:,.2f}")
            sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[london:aln] Failed: %s", e)

    # GEX levels
    sections.append(_format_gex_block(ticker_current, es_current, ticker))

    # ICT dealing range
    sections.append(_format_ict_block(ticker, ticker_current))

    # ICT feature blocks (KZ pivots, IPDA, Silver Bullet, Macros, Imbalances, Gaps)
    sections.extend(_format_ict_features_block(ticker, ticker_current, "LONDON", now_et, target_date))

    # Calendar
    cal_block, events = _format_calendar_block(target_date)
    sections.append(cal_block)

    # ICT liquidity map (bias from overnight direction)
    aln_data = {}
    aln_status = {}
    try:
        from scripts.libs_py.nqstats.engine import NQStatsEngine
        if df_t is not None and not df_t.empty:
            engine = NQStatsEngine(df_t.tail(5000), ticker=ticker)
            engine.process()
            latest = engine.get_latest_status()
            aln_data = {
                "london_high": latest.get("london_high"),
                "london_low": latest.get("london_low"),
                "asia_high": latest.get("asia_high"),
                "asia_low": latest.get("asia_low"),
            }
            aln_status = {
                "asia": latest.get("asiabox_status", ""),
                "london": latest.get("londonbox_status", ""),
            }
    except Exception:
        pass

    # Bias from overnight direction
    overnight_bias = "NEUTRAL"
    if ticker_current > 0 and asia:
        if ticker_current > asia.get("high", 0):
            overnight_bias = "BULLISH"
        elif ticker_current < asia.get("low", 0):
            overnight_bias = "BEARISH"

    sections.append(_format_liquidity_map_block(
        ticker, ticker_current, overnight_bias, aln_data, session_ranges, events=events,
    ))

    # Daily Profiler (session outcomes, predictions, levels)
    try:
        from scripts.trader.signals.profiler import build_dual_profiler_block
        sections.append(build_dual_profiler_block(
            ticker, "ES1", ticker_current, es_current, target_date,
        ))
    except Exception as e:
        log.warning("[london:profiler] Failed: %s", e)

    # Quarters Theory (overnight combo + hourly candle structure)
    try:
        from scripts.trader.signals.quarters_theory import build_quarters_block
        asia_status = session_ranges.get("ASIA", {}).get("status", "") if session_ranges else ""
        london_status = session_ranges.get("LONDON", {}).get("status", "") if session_ranges else ""
        sections.append(build_quarters_block(
            ticker, df_t, now_et, asia_status, london_status,
        ))
    except Exception as e:
        log.warning("[london:quarters] Failed: %s", e)

    # Multi-timeframe range stack
    sections.append(_format_range_stack_block(
        df_t, ticker, ticker_current, session_ranges,
        tf_levels=["MICRO_5", "MICRO_15", "MICRO_30", "SHORT_60", "SHORT_120", "SESSION", "DAILY_1"],
    ))

    return sections


def build_ny_am_blocks(
    df_t: pd.DataFrame,
    ticker: str,
    ticker_current: float,
    es_current: float,
    target_date: date,
    session_ranges: dict,
    now_et: Any = None,
) -> list[str]:
    """NY AM session (09:30-11:30 ET): RTH open, IB forming, Herman Pre-NY sweep."""
    base_label = ticker.replace("1", "").upper()
    sections: list[str] = []

    # RTH session so far
    rth = session_ranges.get("RTH", {})
    ny_am = session_ranges.get("NY_AM", {})
    if rth:
        rth_open = rth.get("open", 0)
        rth_high = rth.get("high", 0)
        rth_low = rth.get("low", 0)
        chg = (ticker_current / rth_open - 1) * 100 if rth_open else 0
        session_dir = "BULLISH" if ticker_current > rth_open else ("BEARISH" if ticker_current < rth_open else "FLAT")
        lines = [f"== INTRADAY BIAS ({base_label}) =="]
        lines.append(f"RTH Open {rth_open:,.2f} → Current {ticker_current:,.2f} ({chg:+.2f}%)")
        lines.append(f"High {rth_high:,.2f} | Low {rth_low:,.2f}")
        lines.append(f"Session direction: {session_dir}")
        sections.append("\n".join(lines))

    # Herman Pre-NY sweep (05:00-08:30) — DOMINANT signal
    pre_ny = session_ranges.get("PRE_NY", {})
    london = session_ranges.get("LONDON", {})
    if pre_ny and london:
        lines = ["== HERMAN PRE-NY SWEEP (05:00-08:30) — DOMINANT =="]
        sweep = detect_sweep(pre_ny, london.get("high"), london.get("low"))
        if sweep["swept_high"]:
            lines.append("Pre-NY broke London HIGH → 86.4% bullish (do not fade)")
        elif sweep["swept_low"]:
            lines.append("Pre-NY broke London LOW → 77.9% bearish (do not fade)")
        else:
            lines.append("Pre-NY inside London → 50/50 coin flip. Wait for 09:30 OR break.")
        sections.append("\n".join(lines))

    # IB status
    try:
        from scripts.libs_py.nqstats.engine import NQStatsEngine
        if df_t is not None and not df_t.empty:
            engine = NQStatsEngine(df_t.tail(5000), ticker=ticker)
            engine.process()
            status = engine.get_latest_status()
            ib_high = status.get("ib_high")
            ib_low = status.get("ib_low")
            ib_mid = (ib_high + ib_low) / 2 if ib_high and ib_low else None
            lines = ["== INITIAL BALANCE (IB) STATUS =="]
            lines.append(f"IB High {ib_high:,.2f} | IB Low {ib_low:,.2f} | IB Mid {ib_mid:,.2f}" if ib_mid else "IB: forming")
            if ib_high and ticker_current > ib_high:
                lines.append("IB Broken: HIGH (bullish tell)")
            elif ib_low and ticker_current < ib_low:
                lines.append("IB Broken: LOW (bearish tell)")
            else:
                lines.append("IB: not yet broken")
            sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[ny_am:ib] Failed: %s", e)

    # ALN pattern (resolved)
    try:
        from scripts.libs_py.nqstats.engine import NQStatsEngine
        if df_t is not None and not df_t.empty:
            engine = NQStatsEngine(df_t.tail(5000), ticker=ticker)
            engine.process()
            latest = engine.get_latest_status()
            lines = [f"== ALN PATTERN ({base_label}) =="]
            lines.append(f"Pattern: {latest.get('aln', 'N/A')} | Broken: {latest.get('broken', 'N/A')}")
            lh = latest.get("london_high")
            ll = latest.get("london_low")
            if lh and ll:
                lines.append(f"London High {lh:,.2f} | London Low {ll:,.2f}")
                if ticker_current > lh:
                    lines.append("London High BROKEN — bullish resolution")
                elif ticker_current < ll:
                    lines.append("London Low BROKEN — bearish resolution")
            sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[ny_am:aln] Failed: %s", e)

    # GEX levels
    sections.append(_format_gex_block(ticker_current, es_current, ticker))

    # ICT dealing range
    sections.append(_format_ict_block(ticker, ticker_current))

    # ICT feature blocks (KZ pivots, IPDA, Silver Bullet, Macros, Imbalances, Gaps)
    sections.extend(_format_ict_features_block(ticker, ticker_current, "NY_AM", now_et, target_date))

    # Calendar
    cal_block, events = _format_calendar_block(target_date)
    sections.append(cal_block)

    # ICT liquidity map
    aln_data = {}
    aln_status = {}
    intraday_bias = "NEUTRAL"
    try:
        from scripts.libs_py.nqstats.engine import NQStatsEngine
        if df_t is not None and not df_t.empty:
            engine = NQStatsEngine(df_t.tail(5000), ticker=ticker)
            engine.process()
            latest = engine.get_latest_status()
            aln_data = {
                "london_high": latest.get("london_high"),
                "london_low": latest.get("london_low"),
                "asia_high": latest.get("asia_high"),
                "asia_low": latest.get("asia_low"),
            }
            aln_status = {
                "asia": latest.get("asiabox_status", ""),
                "london": latest.get("londonbox_status", ""),
            }
            # Bias from Pre-NY sweep + IB break
            if pre_ny and london:
                sweep = detect_sweep(pre_ny, london.get("high"), london.get("low"))
                if sweep["swept_high"]:
                    intraday_bias = "BULLISH"
                elif sweep["swept_low"]:
                    intraday_bias = "BEARISH"
    except Exception:
        pass

    sections.append(_format_liquidity_map_block(
        ticker, ticker_current, intraday_bias, aln_data, session_ranges,
        am_high=rth.get("high") if rth else None,
        am_low=rth.get("low") if rth else None,
        events=events,
    ))

    # Daily Profiler (session outcomes, predictions, levels)
    try:
        from scripts.trader.signals.profiler import build_dual_profiler_block
        sections.append(build_dual_profiler_block(
            ticker, "ES1", ticker_current, es_current, target_date,
        ))
    except Exception as e:
        log.warning("[ny_am:profiler] Failed: %s", e)

    # Quarters Theory (overnight combo + hourly candle structure)
    try:
        from scripts.trader.signals.quarters_theory import build_quarters_block
        sections.append(build_quarters_block(
            ticker, df_t, now_et,
            asia_status=aln_status.get("asia", ""),
            london_status=aln_status.get("london", ""),
        ))
    except Exception as e:
        log.warning("[ny_am:quarters] Failed: %s", e)

    # Multi-timeframe range stack
    sections.append(_format_range_stack_block(
        df_t, ticker, ticker_current, session_ranges,
        tf_levels=["MICRO_5", "MICRO_15", "MICRO_30", "SHORT_60", "SHORT_120", "SESSION", "RTH", "DAILY_1"],
    ))

    return sections


def build_ny_lunch_blocks(
    df_t: pd.DataFrame,
    ticker: str,
    ticker_current: float,
    es_current: float,
    target_date: date,
    session_ranges: dict,
    now_et: Any = None,
) -> list[str]:
    """NY LUNCH session (11:30-13:30 ET): Low volume, manipulation, lunch range forming."""
    base_label = ticker.replace("1", "").upper()
    sections: list[str] = []

    # RTH session so far
    rth = session_ranges.get("RTH", {})
    if rth:
        rth_open = rth.get("open", 0)
        chg = (ticker_current / rth_open - 1) * 100 if rth_open else 0
        session_dir = "BULLISH" if ticker_current > rth_open else ("BEARISH" if ticker_current < rth_open else "FLAT")
        lines = [f"== INTRADAY BIAS ({base_label}) =="]
        lines.append(f"RTH Open {rth_open:,.2f} → Current {ticker_current:,.2f} ({chg:+.2f}%)")
        lines.append(f"AM High {rth.get('high', 0):,.2f} | AM Low {rth.get('low', 0):,.2f}")
        lines.append(f"Session direction: {session_dir}")
        sections.append("\n".join(lines))

    aln_status = {}
    # IB status
    try:
        from scripts.libs_py.nqstats.engine import NQStatsEngine
        if df_t is not None and not df_t.empty:
            engine = NQStatsEngine(df_t.tail(5000), ticker=ticker)
            engine.process()
            status = engine.get_latest_status()
            aln_status = {
                "asia": status.get("asiabox_status", ""),
                "london": status.get("londonbox_status", ""),
            }
            ib_high = status.get("ib_high")
            ib_low = status.get("ib_low")
            lines = ["== IB STATUS =="]
            lines.append(f"IB High {ib_high:,.2f} | IB Low {ib_low:,.2f}")
            if ib_high and ticker_current > ib_high:
                lines.append("IB Broken: HIGH (bullish)")
            elif ib_low and ticker_current < ib_low:
                lines.append("IB Broken: LOW (bearish)")
            else:
                lines.append("IB: not broken (inside)")
            sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[lunch:ib] Failed: %s", e)

    # Lunch range (12:00-13:00) — forming
    ny_lunch = session_ranges.get("NY_LUNCH", {})
    if ny_lunch:
        lines = ["== LUNCH RANGE (12:00-13:00) — FORMING =="]
        lines.append(f"High {ny_lunch.get('high', 0):,.2f} | Low {ny_lunch.get('low', 0):,.2f}")
        lines.append("Herman: Lunch range breakout → PM direction (53.5% high-first)")
        lines.append("Herman: Lunch fade reversals ~40% (low probability — don't fade)")
        sections.append("\n".join(lines))
    else:
        sections.append("== LUNCH RANGE (12:00-13:00) ==\nLunch range not yet formed.")

    # GEX levels
    sections.append(_format_gex_block(ticker_current, es_current, ticker))

    # ICT dealing range
    sections.append(_format_ict_block(ticker, ticker_current))

    # ICT feature blocks (KZ pivots, IPDA, Silver Bullet, Macros, Imbalances, Gaps)
    sections.extend(_format_ict_features_block(ticker, ticker_current, "NY_LUNCH", now_et, target_date))

    # Calendar
    cal_block, _ = _format_calendar_block(target_date)
    sections.append(cal_block)

    # Daily Profiler (session outcomes, predictions, levels)
    try:
        from scripts.trader.signals.profiler import build_dual_profiler_block
        sections.append(build_dual_profiler_block(
            ticker, "ES1", ticker_current, es_current, target_date,
        ))
    except Exception as e:
        log.warning("[ny_lunch:profiler] Failed: %s", e)

    # Quarters Theory (overnight combo + hourly candle structure)
    try:
        from scripts.trader.signals.quarters_theory import build_quarters_block
        sections.append(build_quarters_block(
            ticker, df_t, now_et,
            asia_status=aln_status.get("asia", ""),
            london_status=aln_status.get("london", ""),
        ))
    except Exception as e:
        log.warning("[ny_lunch:quarters] Failed: %s", e)

    # Multi-timeframe range stack
    sections.append(_format_range_stack_block(
        df_t, ticker, ticker_current, session_ranges,
        tf_levels=["MICRO_5", "MICRO_15", "MICRO_30", "SHORT_60", "SHORT_120", "SESSION", "RTH", "DAILY_1"],
    ))

    return sections


def build_ny_pm_blocks(
    df_t: pd.DataFrame,
    ticker: str,
    ticker_current: float,
    es_current: float,
    target_date: date,
    session_ranges: dict,
    now_et: Any = None,
) -> list[str]:
    """NY PM session (13:30-16:00 ET): PM expansion, lunch breakout, noon curve, trend close."""
    base_label = ticker.replace("1", "").upper()
    sections: list[str] = []

    # RTH session so far
    rth = session_ranges.get("RTH", {})
    if rth:
        rth_open = rth.get("open", 0)
        chg = (ticker_current / rth_open - 1) * 100 if rth_open else 0
        session_dir = "BULLISH" if ticker_current > rth_open else ("BEARISH" if ticker_current < rth_open else "FLAT")
        lines = [f"== INTRADAY BIAS ({base_label}) =="]
        lines.append(f"RTH Open {rth_open:,.2f} → Current {ticker_current:,.2f} ({chg:+.2f}%)")
        lines.append(f"AM High {rth.get('high', 0):,.2f} | AM Low {rth.get('low', 0):,.2f}")
        lines.append(f"Session direction: {session_dir}")
        sections.append("\n".join(lines))

    aln_status = {}
    # IB status
    try:
        from scripts.libs_py.nqstats.engine import NQStatsEngine
        if df_t is not None and not df_t.empty:
            engine = NQStatsEngine(df_t.tail(5000), ticker=ticker)
            engine.process()
            status = engine.get_latest_status()
            aln_status = {
                "asia": status.get("asiabox_status", ""),
                "london": status.get("londonbox_status", ""),
            }
            ib_high = status.get("ib_high")
            ib_low = status.get("ib_low")
            lines = ["== IB STATUS =="]
            lines.append(f"IB High {ib_high:,.2f} | IB Low {ib_low:,.2f}")
            if ib_high and ticker_current > ib_high:
                lines.append("IB Broken: HIGH (bullish)")
            elif ib_low and ticker_current < ib_low:
                lines.append("IB Broken: LOW (bearish)")
            else:
                lines.append("IB: not broken (inside)")
            sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[pm:ib] Failed: %s", e)

    # Noon curve
    try:
        from scripts.libs_py.nqstats.engine import NQStatsEngine
        if df_t is not None and not df_t.empty:
            engine = NQStatsEngine(df_t.tail(5000), ticker=ticker)
            engine.process()
            latest = engine.get_latest_status()
            lines = ["== NOON CURVE =="]
            ny_am = session_ranges.get("NY_AM", {})
            if ny_am:
                lines.append(f"AM High {ny_am.get('high', 0):,.2f} at {ny_am.get('high_time', '?')}")
                lines.append(f"AM Low {ny_am.get('low', 0):,.2f} at {ny_am.get('low_time', '?')}")
            lines.append("72.8% chance opposite side taken in PM")
            lines.append("Hourly personality: 15:00 ET trend-close hour — late PM highs more likely to hold (41.5% break rate)")
            sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[pm:noon] Failed: %s", e)

    # Lunch range breakout
    ny_lunch = session_ranges.get("NY_LUNCH", {})
    if ny_lunch:
        lines = ["== LUNCH RANGE BREAKOUT =="]
        lh = ny_lunch.get("high", 0)
        ll = ny_lunch.get("low", 0)
        lines.append(f"Lunch High {lh:,.2f} | Lunch Low {ll:,.2f}")
        if ticker_current > lh:
            lines.append("Lunch HIGH broken → PM direction bullish (53.5% high-first, median 12-14 pts)")
        elif ticker_current < ll:
            lines.append("Lunch LOW broken → PM direction bearish")
        else:
            lines.append("Lunch range not yet broken — PM expansion pending")
        sections.append("\n".join(lines))

    # GEX levels
    sections.append(_format_gex_block(ticker_current, es_current, ticker))

    # ICT dealing range
    sections.append(_format_ict_block(ticker, ticker_current))

    # ICT feature blocks (KZ pivots, IPDA, Silver Bullet, Macros, Imbalances, Gaps)
    sections.extend(_format_ict_features_block(ticker, ticker_current, "NY_PM", now_et, target_date))

    # Calendar
    cal_block, events = _format_calendar_block(target_date)
    sections.append(cal_block)

    # ICT liquidity map
    aln_data = {}
    intraday_bias = "NEUTRAL"
    try:
        from scripts.libs_py.nqstats.engine import NQStatsEngine
        if df_t is not None and not df_t.empty:
            engine = NQStatsEngine(df_t.tail(5000), ticker=ticker)
            engine.process()
            latest = engine.get_latest_status()
            aln_data = {
                "london_high": latest.get("london_high"),
                "london_low": latest.get("london_low"),
                "asia_high": latest.get("asia_high"),
                "asia_low": latest.get("asia_low"),
            }
            # Bias from session direction
            if rth:
                rth_open = rth.get("open", 0)
                if ticker_current > rth_open:
                    intraday_bias = "BULLISH"
                elif ticker_current < rth_open:
                    intraday_bias = "BEARISH"
    except Exception:
        pass

    sections.append(_format_liquidity_map_block(
        ticker, ticker_current, intraday_bias, aln_data, session_ranges,
        am_high=rth.get("high") if rth else None,
        am_low=rth.get("low") if rth else None,
        events=events,
    ))

    # Daily Profiler (session outcomes, predictions, levels)
    try:
        from scripts.trader.signals.profiler import build_dual_profiler_block
        sections.append(build_dual_profiler_block(
            ticker, "ES1", ticker_current, es_current, target_date,
        ))
    except Exception as e:
        log.warning("[ny_pm:profiler] Failed: %s", e)

    # Quarters Theory (overnight combo + hourly candle structure)
    try:
        from scripts.trader.signals.quarters_theory import build_quarters_block
        sections.append(build_quarters_block(
            ticker, df_t, now_et,
            asia_status=aln_status.get("asia", ""),
            london_status=aln_status.get("london", ""),
        ))
    except Exception as e:
        log.warning("[ny_pm:quarters] Failed: %s", e)

    # Multi-timeframe range stack
    sections.append(_format_range_stack_block(
        df_t, ticker, ticker_current, session_ranges,
        tf_levels=["MICRO_5", "MICRO_15", "MICRO_30", "SHORT_60", "SHORT_120", "SESSION", "RTH", "DAILY_1"],
    ))

    return sections


# ══════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════

def build_intraday_cheat_sheet(
    df_t: pd.DataFrame,
    ticker: str,
    target_date: date,
    now_et: Any | None = None,
) -> str:
    """Build the session-adaptive intraday cheat sheet.

    Detects the current session and assembles only the blocks relevant
    to that session. This replaces the old fixed NY-PM-only approach.

    Args:
        df_t: 1-minute DataFrame with ET-localized tz-aware index.
        ticker: Ticker symbol (e.g. ES1, NQ1).
        target_date: The trading date.
        now_et: Current ET datetime (for session detection). Defaults to now.

    Returns:
        Formatted cheat sheet string.
    """
    import pytz
    if now_et is None:
        now_et = datetime.now(pytz.timezone("America/New_York"))

    session = detect_session(now_et)

    # Weekend graceful exit
    if session == "WEEKEND":
        return "== MARKETS CLOSED ==\nMarkets are closed (weekend). Run the weekly narrative for a full week review."

    # After close — defer to EOD narrative
    if session == "AFTER_CLOSE":
        return "== SESSION COMPLETE ==\nRTH session has ended. Run the EOD narrative for the full close review."

    # Compute all session ranges
    session_ranges = compute_all_session_ranges(df_t, target_date, ET)

    # Get current price
    ticker_current = float(df_t["close"].iloc[-1]) if df_t is not None and not df_t.empty else 0.0

    # Get ES current (for GEX cross-reference)
    es_current = 0.0
    if ticker != "ES1":
        try:
            from scripts.utils.fused_data_loader import load_fused_data
            df_es = load_fused_data("ES1", timeframe="1m", require_historical=False)
            if df_es is not None and not df_es.empty:
                es_current = float(df_es["close"].iloc[-1])
        except Exception:
            pass

    # Session header
    sections: list[str] = [_format_session_header(session, now_et, ticker)]

    # Dispatch to session-specific builder
    if session == "ASIA":
        sections.extend(build_asia_blocks(df_t, ticker, ticker_current, es_current, target_date, session_ranges, now_et))
    elif session == "LONDON":
        sections.extend(build_london_blocks(df_t, ticker, ticker_current, es_current, target_date, session_ranges, now_et))
    elif session == "NY_AM":
        sections.extend(build_ny_am_blocks(df_t, ticker, ticker_current, es_current, target_date, session_ranges, now_et))
    elif session == "NY_LUNCH":
        sections.extend(build_ny_lunch_blocks(df_t, ticker, ticker_current, es_current, target_date, session_ranges, now_et))
    elif session == "NY_PM":
        sections.extend(build_ny_pm_blocks(df_t, ticker, ticker_current, es_current, target_date, session_ranges, now_et))
    else:
        sections.append(f"== UNKNOWN SESSION ==\nCould not determine session for {now_et}.")

    return "\n\n".join(sections)