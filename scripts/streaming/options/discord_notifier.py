"""
discord_notifier.py
===================
Formats dealer-positioning summaries into Discord embeds and delivers them
via webhook.  All Discord-specific logic lives in this module.

Public API
----------
send_discord_update(translated_levels, run_label, webhook_url) -> None
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.libs_py.discord import (
    compact_embed as _shared_compact_embed,
    embed_batches as _shared_embed_batches,
    embed_char_count as _shared_embed_char_count,
    embed_to_content as _shared_embed_to_content,
    load_webhook_url as _shared_load_webhook_url,
    send_payload as _shared_send_payload,
    truncate_text as _shared_truncate_text,
    DISCORD_MAX_CONTENT,
    DISCORD_MAX_EMBEDS,
    DISCORD_SAFE_EMBED_BATCH_CHARS,
)

from .config import (
    DISCORD_TARGET_KEY,
    DISCORD_MACRO_KEY,
    DISCORD_COLOR_POSITIVE,
    DISCORD_COLOR_NEGATIVE,
    ENABLE_DISCORD_COPY_ATTACHMENT,
    DISCORD_COPY_ATTACHMENT_FILENAME,
)
from .formatting import (
    build_coaches_note,
    build_plan,
    copy_ready_line,
    fmt,
    fmt_copy,
    futures_tag,
    HasLevels,
    traffic_light,
)
from .futures_translator import TranslatedLevels
from .gex_calculator import DealerLevels
from .file_writer import build_scored_levels_line
from .level_scorer import (
    ScoredLevels,
    TaggedLevel,
    MechanicalWall,
    StructuralAnchor,
    InflectionPoint
)

log = logging.getLogger(__name__)

# Discord webhook limits. The shared `scripts.libs_py.discord`
# sub-package owns the canonical constants; we re-export them
# under their historic module-local names so the public surface
# of `scripts.streaming.options.discord_notifier` is unchanged.
_DISCORD_MAX_EMBEDS = DISCORD_MAX_EMBEDS
_DISCORD_MAX_CONTENT = DISCORD_MAX_CONTENT
_DISCORD_SAFE_EMBED_BATCH_CHARS = DISCORD_SAFE_EMBED_BATCH_CHARS


# ---------------------------------------------------------------------------
# Internal helpers (shims over `scripts.libs_py.discord`)
# ---------------------------------------------------------------------------
# The functions below are intentionally thin shims that delegate to
# the shared sub-package. They exist for two reasons:
#
#   1. The legacy call sites in this module (and downstream tests
#      in tests/streaming/test_options_output_contract.py) reference
#      these names directly. Keeping the names lets us migrate
#      without breaking monkeypatched tests.
#
#   2. The legacy ``_load_webhook_url`` raises on missing key/file;
#      the shared ``load_webhook_url`` returns ``None`` (best-effort,
#      matching the narrative chain's contract). The shim preserves
#      the raise-on-missing behaviour for this pipeline.

def _load_webhook_url(target_key: str = DISCORD_TARGET_KEY) -> str:
    """Read the webhook URL for the specified key from discord_webhooks.json.

    Thin shim over ``scripts.libs_py.discord.load_webhook_url`` that
    preserves the historical raise-on-missing semantics: a missing
    key or file raises the same exception type the previous in-line
    code raised, so callers that relied on that behaviour (and the
    tests that mock it) continue to work.
    """
    from pathlib import Path as _Path

    url = _shared_load_webhook_url(
        target_key,
        webhooks_path=_Path(__file__).resolve().parents[3] / "discord_webhooks.json",
    )
    if url is None:
        # We can't tell "file missing" from "key missing" without
        # re-reading, but the previous code only raised either
        # FileNotFoundError or KeyError. The shim re-raises the
        # more informative of the two based on a quick check.
        webhooks_path = _Path(__file__).resolve().parents[3] / "discord_webhooks.json"
        if not webhooks_path.exists():
            raise FileNotFoundError(
                f"discord_webhooks.json not found at {webhooks_path}"
            )
        raise KeyError(
            f"Webhook key '{target_key}' not found in {webhooks_path}. "
            f"Available keys: {list(__import__('json').loads(webhooks_path.read_text()).keys())}"
        )
    return url


def _regime_line(regime: str) -> str:
    emoji = "🟢" if regime == "POSITIVE" else "🔴"
    return f"{emoji} **{regime} GEX**"


def _plan_lines(tl: TranslatedLevels) -> str:
    """Compact trade-plan narrative for Discord embeds."""
    tag = futures_tag(tl.futures_symbol)
    lines = build_plan(tag, tl, extended=False)
    return "\n".join(lines)


def _copy_block_payloads(
    translated_levels: list[TranslatedLevels],
    run_label: str,
    cash_levels: list[DealerLevels] | None = None,
) -> list[dict[str, Any]]:
    """Build one or more Discord payloads containing raw copy-ready strings."""
    lines = [copy_ready_line(futures_tag(tl.futures_symbol), tl) for tl in translated_levels]
    if cash_levels:
        # Add cash levels that weren't already included as futures translations
        # (or include all if the user explicitly wants indices too)
        lines.extend(copy_ready_line(levels.ticker, levels) for levels in cash_levels)

    return _chunk_copy_lines(lines)


def _chunk_copy_lines(lines: list[str]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    current_lines: list[str] = []
    current_len = 0
    
    for line in lines:
        if current_lines and current_len + len(line) + 1 > _DISCORD_MAX_CONTENT:
            payloads.append({"content": "\n".join(current_lines)})
            current_lines = [line]
            current_len = len(line)
        else:
            current_lines.append(line)
            current_len += len(line) + 1
            
    if current_lines:
        payloads.append({"content": "\n".join(current_lines)})

    return payloads


def _copy_attachment_payload(lines: list[str], run_label: str) -> tuple[dict[str, Any], dict[str, Any]]:
    content = "\n".join(lines)
    payload = {
        "content": f"Dealer Levels raw payload ({run_label}) attached as text file."
    }
    files = {
        "file": (DISCORD_COPY_ATTACHMENT_FILENAME, content.encode("utf-8"), "text/plain")
    }
    return payload, files


def _truncate_text(value: str, max_len: int) -> str:
    """Shim over :func:`scripts.libs_py.discord.truncate_text`."""
    return _shared_truncate_text(value, max_len)


def _embed_char_count(embed: dict[str, Any]) -> int:
    """Shim over :func:`scripts.libs_py.discord.embed_char_count`."""
    return _shared_embed_char_count(embed)


def _compact_embed(embed: dict[str, Any], max_chars: int = _DISCORD_SAFE_EMBED_BATCH_CHARS) -> dict[str, Any]:
    """Shim over :func:`scripts.libs_py.discord.compact_embed`."""
    return _shared_compact_embed(embed, max_chars=max_chars)


def _embed_to_content(embed: dict[str, Any]) -> str:
    """Shim over :func:`scripts.libs_py.discord.embed_to_content`."""
    return _shared_embed_to_content(embed, max_len=_DISCORD_MAX_CONTENT)


def _embed_batches(embeds: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Shim over :func:`scripts.libs_py.discord.embed_batches`."""
    return _shared_embed_batches(embeds)


def _build_scored_fields(scored: ScoredLevels) -> list[dict[str, Any]]:
    """Construct embed fields for the Three-Filter Architecture."""
    fields = []
    
    # 1. Mechanical Walls (Filter 1)
    res_walls = scored.resistance_walls
    sup_walls = scored.support_walls
    if res_walls or sup_walls:
        lines = []
        for w in (res_walls[:2] + sup_walls[:2]):
            book_str = f" ({w.pct_of_book*100:.1f}% book)" if w.pct_of_book > 0 else ""
            lines.append(f"• **{w.strike:g}** {w.side}: {w.label}{book_str}")
        if lines:
            fields.append({"name": "🧱 Gamma Walls (Mechanical)", "value": "\n".join(lines), "inline": False})

    # 2. Structural Anchors (Filter 2)
    anchors = [l for l in scored.tagged_levels if isinstance(l, StructuralAnchor)]
    if anchors:
        lines = []
        for a in anchors[:3]:
            lines.append(f"• **{a.strike:g}**: [{a.matched_program}] — *{a.relevance}* ({a.days_to_expiry}d)")
        fields.append({"name": "⚓ Structural Anchors (Institutional)", "value": "\n".join(lines), "inline": False})
        
    # 3. Transitions & Inflections (Filter 3)
    pts = [l for l in scored.tagged_levels if isinstance(l, InflectionPoint)]
    if pts:
        lines = [f"• **{l.strike:g}**: {l.label}" for l in pts[:3]]
        fields.append({"name": "⚖️ Transitions & Inflections", "value": "\n".join(lines), "inline": False})
        
    return fields


def _build_embed(levels: HasLevels, run_label: str, scored: ScoredLevels | None = None) -> dict[str, Any]:
    """Construct a single Discord embed dict for one levels entry (translated or cash)."""
    color = DISCORD_COLOR_POSITIVE if levels.gex_regime == "POSITIVE" else DISCORD_COLOR_NEGATIVE
    
    # ── Tag / Ticker resolution ─────────────────────────────────────
    # Use hasattr to robustly detect TranslatedLevels regardless of import context
    is_tl = hasattr(levels, "futures_symbol") and hasattr(levels, "cash_ticker")
    if is_tl:
        tag = futures_tag(getattr(levels, "futures_symbol"))
        title = f"{getattr(levels, 'cash_ticker')} -> {tag} Dealer Levels"
        cash_sym = getattr(levels, "cash_ticker")
        spot = getattr(levels, "cash_spot")
    else:
        # DealerLevels (Cash Only)
        tag = getattr(levels, "ticker")
        title = f"{tag} Dealer Levels"
        cash_sym = tag
        spot = getattr(levels, "spot")

    # Regime + traffic light
    regime_emoji = {"PINNED": "📌", "TRENDING": "🚀", "COILED": "🔄", "BATTLE_ZONE": "⚔️"}.get(levels.regime_label, "⚪")
    pin_pct = f"{levels.pin_odds:.0%}" if levels.pin_odds else "N/A"
    light_color, _light_reason = traffic_light(levels)
    light_emoji = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}[light_color]
    bias_arrow = "↓" if levels.directional_bias == "BEARISH" else "↑" if levels.directional_bias == "BULLISH" else "↔"
    bias_color = "🔴" if levels.directional_bias == "BEARISH" else "🟢" if levels.directional_bias == "BULLISH" else "⚪"

    fields: list[dict[str, Any]] = [
        {
            "name": "Regime",
            "value": f"{light_emoji} {light_color}  |  {_regime_line(levels.gex_regime)}  {regime_emoji} **{levels.regime_label} {bias_arrow}** {bias_color} {levels.directional_bias}",
            "inline": False,
        },
        # ── Prices ──────────────────────────────────────────────
        {"name": f"Ticker ({cash_sym})", "value": fmt(spot), "inline": True},
    ]

    if is_tl:
        fields.extend([
            {"name": f"{tag} Futures Price", "value": fmt(getattr(levels, "futures_price")), "inline": True},
            {"name": "Basis" if getattr(levels, "translation_mode") == "additive" else "Scale Ratio",
             "value": f"{getattr(levels, 'basis_spread'):+.2f}" if getattr(levels, "translation_mode") == "additive" else f"{getattr(levels, 'basis_ratio'):.2f}×",
             "inline": True},
        ])

    front_em = None
    ems = getattr(levels, "expected_moves", None) or []
    if ems:
        ems_sorted = sorted(
            [em for em in ems if getattr(em, "dte", None) is not None],
            key=lambda em: em.dte,
        )
        if ems_sorted:
            front_em = ems_sorted[0]

    fields.extend([
        # ── Spacer ───────────────────────────────────────────────
        {"name": "\u200b", "value": "\u200b", "inline": False},
        # ── Market Structure ─────────────────────────────────────
        {"name": "🧲 Gamma Magnet",  "value": fmt(levels.gamma_magnet), "inline": True},
        {"name": f"📌 Pin Strike ({pin_pct})", "value": fmt(levels.pin_strike), "inline": True},
        {"name": "↔️ Wall Separation",         "value": f"{fmt(levels.wall_separation)} pts", "inline": True},
        # ── Spacer ───────────────────────────────────────────────
        {"name": "\u200b", "value": "\u200b", "inline": False},
        # ── Key levels ─────────────────────
        {"name": f"📈 Call Wall ({tag})",    "value": fmt(levels.call_wall),   "inline": True},
        {"name": f"📉 Put Wall ({tag})",     "value": fmt(levels.put_wall),    "inline": True},
        {"name": f"⚡ Zero Gamma ({tag})",   "value": fmt(levels.zero_gamma),  "inline": True},
        {"name": f"⚡ Zero Gamma (DA) ({tag})", "value": fmt(levels.zero_gamma_delta_adj), "inline": True},
        # ── Spacer ───────────────────────────────────────────────
        {"name": "\u200b", "value": "\u200b", "inline": False},
        # ── Expected move ────────────────────────────────────────
        {"name": f"🔼 EM HI ({tag})",        "value": fmt(front_em.em_upper if front_em else levels.em_upper), "inline": True},
        {"name": f"🔽 EM LO ({tag})",        "value": fmt(front_em.em_lower if front_em else levels.em_lower), "inline": True},
        {"name": f"🔼 EM85 HI ({tag})",      "value": fmt(front_em.straddle_85_upper if front_em and getattr(front_em, 'straddle_85_upper', 0) else None), "inline": True},
        {"name": f"🔽 EM85 LO ({tag})",      "value": fmt(front_em.straddle_85_lower if front_em and getattr(front_em, 'straddle_85_lower', 0) else None), "inline": True},
        {"name": "ATM Straddle (market)",    "value": fmt(levels.atm_straddle), "inline": True},
        {"name": "Expected Move (model)",    "value": f"±{fmt(levels.em_value)}", "inline": True},
        # ── Compact execution plan ──────────────────────────────
        {"name": "🧠 Execution Plan",          "value": "\n".join(build_plan(tag, levels, extended=False)), "inline": False},
    ])

    weekly_scope_upper = getattr(levels, "weekly_scope_upper", None)
    weekly_scope_lower = getattr(levels, "weekly_scope_lower", None)
    weekly_scope_expiry = getattr(levels, "weekly_scope_expiry", None)
    if weekly_scope_upper is not None and weekly_scope_lower is not None:
        expiry_suffix = f" → {weekly_scope_expiry}" if weekly_scope_expiry else ""
        fields.append(
            {
                "name": f"🗓️ Weekly Scope ({tag}){expiry_suffix}",
                "value": f"{fmt(weekly_scope_lower)} ↔ {fmt(weekly_scope_upper)}",
                "inline": False,
            }
        )

    if scored:
        fields.append({"name": "\u200b", "value": "── **THREE-FILTER ANALYSIS** ──", "inline": False})
        fields.extend(_build_scored_fields(scored))

    footer_parts = [
        f"Total GEX: {levels.total_gex:,.0f}",
        f"EM ±{fmt(levels.em_value)}",
        f"Vanna: {levels.net_vanna_exposure:,.0f}"
    ]
    if is_tl:
        footer_parts.insert(2, f"{'Basis: ' + f'{getattr(levels, 'basis_spread'):+.2f}' if getattr(levels, 'translation_mode') == 'additive' else 'Ratio: ' + f'{getattr(levels, 'basis_ratio'):.2f}×'}")

    return {
        "title": f"{title}  |  {run_label}",
        "color": color,
        "fields": fields,
        "footer": {
            "text": " • ".join(footer_parts)
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _build_coaches_note_payloads(
    levels_list: list[HasLevels],
    run_label: str,
) -> list[dict[str, Any]]:
    """Build one Discord message per instrument with the full Coach's Note."""
    payloads: list[dict[str, Any]] = []

    for levels in levels_list:
        if hasattr(levels, "futures_symbol") and hasattr(levels, "cash_ticker"):
            tag = futures_tag(getattr(levels, "futures_symbol"))
        else:
            tag = getattr(levels, "ticker")
            
        note = build_coaches_note(tag, levels)
        content = f"**🏋️ Coach's Briefing — {tag}  |  {run_label}**\n\n" + "\n".join(note)

        if len(content) > _DISCORD_MAX_CONTENT:
            content = content[:_DISCORD_MAX_CONTENT - 20] + "\n\n*(truncated)*"

        payloads.append({"content": content})

    return payloads


def _post_payload(
    url: str,
    payload: dict[str, Any],
    files: dict[str, Any] | None = None,
    allow_embed_fallback: bool = True,
) -> bool:
    """POST a Discord webhook payload (JSON or multipart) with error handling.

    Thin shim over :func:`scripts.libs_py.discord.webhooks.send_payload`
    that preserves the historical keyword-only positional contract
    (URL, payload, files, allow_embed_fallback). Existing tests
    monkeypatch this name on the module, so the signature must
    stay stable.
    """
    return _shared_send_payload(
        url,
        payload,
        files=files,
        allow_embed_fallback=allow_embed_fallback,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_macro_update(
    ticker: str,
    spot: float,
    chart_buf: Any,  
    levels: dict[str, float | None],
    anomalies: list[dict[str, Any]],
    dominant_nodes: list[dict[str, Any]], # Explicitly received
    webhook_url: str | None = None,
    scored: ScoredLevels | None = None,
) -> None:
    """
    Delivers the macro HTF chart and formatted institutional brief to Discord.
    """
    url = webhook_url or _load_webhook_url(DISCORD_MACRO_KEY)
    
    # Extract variables safely
    zg = levels.get("zero_gamma")
    zg_da = levels.get("zero_gamma_delta_adj")
    cw = levels.get("macro_call_wall")
    pw = levels.get("macro_put_wall")
    
    # 1. Regime Formatting
    if zg and spot:
        regime = "🟢 POSITIVE GAMMA" if spot >= zg else "🔴 NEGATIVE GAMMA"
        regime_text = f"{regime} (Above {zg:,.2f})" if spot >= zg else f"{regime} (Below {zg:,.2f})"
    else:
        regime_text = "⚪ NEUTRAL"

    # 2. Major Nodes Formatting (using the explicitly passed list)
    nodes_str = ", ".join([f"{n['strike']:g} {'C' if n['type']=='CALL' else 'P'} ({n['dominance_pct']}%)" for n in dominant_nodes[:3]])
    if not nodes_str:
        nodes_str = "N/A"

    # 3. Build the Institutional Markdown
    lines = [
        f"🏦 **INSTITUTIONAL MACRO BRIEF — ${ticker}**",
        f"Spot: **{spot:,.2f}** | Regime: **{regime_text}**",
        "",
        "🏛️ **THE STRUCTURAL MAP (Resting Liquidity)**",
        f"• Ceiling (Call Wall): {cw:,.2f}" if cw else "• Ceiling: N/A",
        f"• Floor (Put Wall): {pw:,.2f}" if pw else "• Floor: N/A",
        f"• Pivot (Zero Gamma): {zg:,.2f}" if zg else "• Pivot: N/A",
        f"• Pivot (Zero Gamma DA): {zg_da:,.2f}" if zg_da else "• Pivot (Zero Gamma DA): N/A",
        f"• Major Nodes: {nodes_str}",
        "",
    ]

    # Add Scored Briefing
    if scored:
        best_anchor = scored.strategic[0] if scored.strategic else None
        res = scored.resistance_walls[0] if scored.resistance_walls else None
        sup = scored.support_walls[0] if scored.support_walls else None

        lines.extend([
            "🪜 **THREE-FILTER SCORECARD**",
            f"• Sentiment: **{scored.bias}** ({scored.regime} GEX)",
            f"• Mech. Resistance: {res.strike:g} ({res.label})" if res else "• Mech. Resistance: N/A",
            f"• Mech. Support: {sup.strike:g} ({sup.label})" if sup else "• Mech. Support: N/A",
            f"• Best Anchor: {best_anchor.strike:g} ({best_anchor.label})" if best_anchor else "• Best Anchor: N/A",
            ""
        ])

    lines.append("🚨 **THE URGENT TAPE (Top Institutional Flow)**")

    # 4. Append the Anomalies (Formatted with Golden Sweeps)
    for w in anomalies[:5]:
        is_gs = w.get("is_golden_sweep", False)
        icon = "🏆" if is_gs else "🌊"
        gs_tag = " — GOLDEN SWEEP" if is_gs else ""
        notional_m = w['notional'] / 1_000_000.0
        
        lines.append(f"{icon} **{w['strike']:g} {w['type']} (Tier {w['tier']}){gs_tag}**")
        lines.append(f"DTE: {w['dte_str']} | Confluence: x{w['confluence']} | Notional: ${notional_m:.1f}M | Vol/OI: {w['avg_vol_oi_ratio']}x\n")

    content = "\n".join(lines)

    # 5. Post to Discord
    files = {"file": ("macro_chart.png", chart_buf, "image/png")}
    _post_payload(url, {"content": content}, files=files)

def send_discord_update(
    translated_levels: list[TranslatedLevels],
    run_label: str = "",
    cash_levels: list[DealerLevels] | None = None,
    scored_levels: list[ScoredLevels] | None = None,
    unified_copy_path: Path | None = None,
    webhook_url: str | None = None,
    webhook_key: str | None = None,
    include_cash_embeds: bool = False,
) -> None:
    """
    Post one Discord embed per entry via webhook.
    """
    if not run_label:
        run_label = datetime.now().strftime("%H:%M ET")

    log.info(
        "Preparing Discord update: %d futures, %d cash. full_discord=%s",
        len(translated_levels),
        len(cash_levels) if cash_levels else 0,
        include_cash_embeds,
    )

    url = webhook_url or _load_webhook_url(webhook_key or DISCORD_TARGET_KEY)

    # 1. Copy Blocks (Always include everything specified)
    if translated_levels or cash_levels:
        lines: list[str] = []

        if unified_copy_path and unified_copy_path.exists():
            file_lines = [ln.strip() for ln in unified_copy_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            if file_lines:
                lines = file_lines

        if not lines:
            scored_lookup = {s.ticker: s for s in (scored_levels or [])}
            if scored_lookup:
                for ticker, scored in scored_lookup.items():
                    line = build_scored_levels_line(ticker, scored)
                    if line:
                        lines.append(line)

        if not lines:
            lines = [copy_ready_line(futures_tag(tl.futures_symbol), tl) for tl in translated_levels]
            if cash_levels:
                lines.extend(copy_ready_line(levels.ticker, levels) for levels in cash_levels)

        if ENABLE_DISCORD_COPY_ATTACHMENT and lines:
            payload, files = _copy_attachment_payload(lines, run_label)
            sent = _post_payload(url, payload, files=files)
            if sent is False:
                log.warning("Attachment send failed, falling back to raw line chunks.")
                for fallback_payload in _chunk_copy_lines(lines):
                    _post_payload(url, fallback_payload)
        else:
            for payload in _chunk_copy_lines(lines):
                _post_payload(url, payload)

    # 2. Detailed Embeds & Notes
    # If include_cash_embeds is False, we only show detailed cards for the indices we translate.
    # Otherwise, we show cards for every stock too.
    targets: list[HasLevels] = list(translated_levels)
    if include_cash_embeds and cash_levels:
        # Avoid showing the cash version of a ticker if we already have the futures version
        futures_indices = {tl.cash_ticker for tl in translated_levels}
        for cl in cash_levels:
            if cl.ticker not in futures_indices:
                targets.append(cl)
    
    log.debug("Sending Discord embeds/briefings for %d targets.", len(targets))

    scored_lookup = {s.ticker: s for s in (scored_levels or [])}
    embeds = [_build_embed(t, run_label, scored=scored_lookup.get(t.cash_ticker if hasattr(t, 'cash_ticker') else t.ticker)) for t in targets]

    # Batch and post embeds using both count and char-size constraints.
    for batch in _embed_batches(embeds):
        _post_payload(url, {"embeds": batch})

    # Coach's briefing
    for payload in _build_coaches_note_payloads(targets, run_label):
        _post_payload(url, payload)


def send_regime_change_alert(
    alert_text: str,
    webhook_url: str | None = None,
) -> None:
    """
    Post a regime-change alert to Discord.

    Parameters
    ----------
    alert_text  : Pre-formatted alert string from state_tracker.format_change_alert().
    webhook_url : Override URL; uses discord_webhooks.json default when None.
    """
    if not alert_text:
        return

    url = webhook_url or _load_webhook_url()

    content = alert_text
    if len(content) > _DISCORD_MAX_CONTENT:
        content = content[:_DISCORD_MAX_CONTENT - 20] + "\n\n*(truncated)*"

    _post_payload(url, {"content": content})


def send_rtd_health_alert(
    rtd_status: dict[str, Any],
    webhook_url: str | None = None,
) -> None:
    """
    Post a TOS RTD health status alert to Discord.

    Called from run_options_levels.py when RTD is enabled, to show
    connection state, topic count, and Greeks drift summary.

    Parameters
    ----------
    rtd_status : Status dict from HybridCoordinator.get_status()
    webhook_url : Override URL; uses default when None.
    """
    if not rtd_status:
        return

    url = webhook_url or _load_webhook_url()

    mode = rtd_status.get("mode", "unknown")
    rtd_active = rtd_status.get("rtd_active", False)

    if rtd_active:
        adapter = rtd_status.get("adapter", {})
        validation = rtd_status.get("greeks_validation", {})

        lines = [
            f"**TOS RTD Status: ACTIVE** (hybrid mode)",
            f"  Symbols: {adapter.get('base_symbols', [])}",
            f"  Option subscriptions: {adapter.get('option_symbol_count', 0)}",
            f"  Data keys: {adapter.get('data_keys', 0)}",
            f"  Expiry: {adapter.get('expiry', 'N/A')}",
        ]

        if validation.get("active"):
            lines.extend([
                f"  Greeks drift: avg={validation.get('avg_drift_pct', 'N/A')}% max={validation.get('max_drift_pct', 'N/A')}%",
                f"  High drift contracts: {validation.get('high_drift_count', 0)} (threshold: {validation.get('threshold_pct', 5)}%)",
            ])
        else:
            lines.append("  Greeks drift: no validation data yet")

        # RTD GEX mode
        gex_mode = rtd_status.get("rtd_gex_mode", "supplementary")
        if gex_mode == "primary":
            lines.append("  GEX source: **RTD PRIMARY** (futures options direct)")
        else:
            lines.append("  GEX source: Schwab-translated (RTD supplementary)")
    else:
        lines = [
            f"**TOS RTD Status: {'ENABLED but INACTIVE' if rtd_status.get('rtd_enabled') else 'DISABLED'}**",
            f"  Mode: {mode}",
        ]
        if rtd_status.get("rtd_enabled"):
            lines.append("  Check: TOS desktop running? COM initialized?")

    content = "\n".join(lines)
    _post_payload(url, {"content": content})