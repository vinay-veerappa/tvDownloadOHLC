"""gen_charts.py — batch chart image generator for the chart agent.

Productizes scripts/analysis/generate_ict_chart*.py into a configurable
batch renderer that produces high-DPI chart images with ICT overlays for:
  1. Vision verification (the user eyeballs the chart vs the reasoner's verdict)
  2. Annotation dataset collection (Phase 0a thin slice)

Ruses:
  - detect_order_blocks, detect_fvgs, filter_mitigated_* from generate_ict_chart
  - load_fused_data from scripts/utils/fused_data_loader
  - load_ict_context from scripts/trader/signals/ict_data_loader

Usage:
    # Single chart
    python -m scripts.trader.chart_agent.gen_charts --ticker ES1 --date 2026-08-01

    # Batch: last N trading days
    python -m scripts.trader.chart_agent.gen_charts --ticker ES1 --last-n 10

    # Multiple tickers
    python -m scripts.trader.chart_agent.gen_charts --ticker ES1 NQ1 --last-n 5

Output: data/vision/charts/{ticker}_{date}_{view}.png
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import pandas as pd

log = logging.getLogger(__name__)

_REPO = Path(__file__).parent.parent.parent.parent
_OUTPUT_DIR = _REPO / "data" / "vision" / "charts"
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Import existing detection functions (reuse, don't reinvent)
sys.path.insert(0, str(_REPO / "scripts" / "analysis"))
from generate_ict_chart import (
    detect_order_blocks,
    detect_fvgs,
    filter_mitigated_obs,
    filter_mitigated_fvgs,
)
sys.path.insert(0, str(_REPO / "scripts" / "utils"))
from fused_data_loader import load_fused_data

# Import ICT levels from the data loader
sys.path.insert(0, str(_REPO))
from scripts.trader.signals.ict_data_loader import load_ict_context


# ═══════════════════════════════════════════════════════════════════════
#  Chart rendering
# ═══════════════════════════════════════════════════════════════════════

_DARK_BG = "#131722"
_DARK_FG = "#d1d4dc"
_GRID_COLOR = "#2a2e39"
_UP_COLOR = "#26a69a"
_DOWN_COLOR = "#ef5350"


def _resample_1m_to_1h(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Resample 1-minute OHLCV to 1-hour bars."""
    df = df_1m.copy()
    if df.index.tz is None:
        df.index = pd.DatetimeIndex(df.index).tz_localize("UTC")
    df_1h = df.resample("1h").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna(subset=["open"])
    return df_1h


def _style_dark(ax):
    """Apply TradingView-dark styling to an axis."""
    ax.set_facecolor(_DARK_BG)
    ax.tick_params(colors=_DARK_FG, labelsize=8)
    ax.spines["top"].set_color(_GRID_COLOR)
    ax.spines["right"].set_color(_GRID_COLOR)
    ax.spines["bottom"].set_color(_GRID_COLOR)
    ax.spines["left"].set_color(_GRID_COLOR)
    ax.grid(True, color=_GRID_COLOR, alpha=0.3, linewidth=0.5)
    ax.title.set_color(_DARK_FG)
    ax.xaxis.label.set_color(_DARK_FG)
    ax.yaxis.label.set_color(_DARK_FG)


def render_daily_context_chart(
    ticker: str,
    target_date: datetime,
    df_1m: pd.DataFrame,
    ict_ctx: dict,
    save_path: Path,
    dpi: int = 150,
) -> Path:
    """Render a 5-minute daily-context chart with ICT overlays.

    Uses 5m bars (resampled from 1m) for dense, readable candles.
    Shows: overnight + day session, session shading (Asia/London/NY),
    PDH/PDL/PWH/PWL levels, OBs, FVGs, session markers.

    This is the chart the user eyeball-verifies against the reasoner's verdict.
    """
    # Resample 1m -> 5m for dense readable candles
    df_5m = df_1m.resample("5min").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna(subset=["open"])

    # View: target day 00:00 ET -> 23:59 ET (full trading day)
    # For futures with overnight, use prev 18:00 -> target 16:00 when data supports it
    start_view = pd.Timestamp.combine(target_date.date(), time(0, 0))
    end_view = pd.Timestamp.combine(target_date.date(), time(23, 59))

    if df_5m.index.tz:
        start_view = start_view.tz_localize("US/Eastern")
        end_view = end_view.tz_localize("US/Eastern")

    df_view = df_5m[(df_5m.index >= start_view) & (df_5m.index <= end_view)]
    if df_view.empty:
        log.warning("No data in view range for %s %s", ticker, target_date.date())
        return None

    price_min = df_view["low"].min()
    price_max = df_view["high"].max()
    price_range = price_max - price_min
    right_edge = mdates.date2num(df_view.index.max())

    fig, ax = plt.subplots(figsize=(24, 12), dpi=dpi, facecolor=_DARK_BG)
    _style_dark(ax)

    # 1. Candles (5m)
    width = 0.003  # 5min bar width in date units
    up = df_view[df_view["close"] >= df_view["open"]]
    down = df_view[df_view["close"] < df_view["open"]]
    ax.bar(up.index, up["close"] - up["open"], width, bottom=up["open"], color=_UP_COLOR, edgecolor=_UP_COLOR, linewidth=0.5)
    ax.vlines(up.index, up["low"], up["high"], color=_UP_COLOR, linewidth=0.4)
    ax.bar(down.index, down["close"] - down["open"], width, bottom=down["open"], color=_DOWN_COLOR, edgecolor=_DOWN_COLOR, linewidth=0.5)
    ax.vlines(down.index, down["low"], down["high"], color=_DOWN_COLOR, linewidth=0.4)

    # 3. ICT levels (PDH/PDL/PWH/PWL/midnight open) — thicker, right-justified labels
    level_specs = [
        ("PDH", ict_ctx.get("pdh"), "#e91e63", True),
        ("PDL", ict_ctx.get("pdl"), "#e91e63", True),
        ("PWH", ict_ctx.get("pwh"), "#ab47bc", False),
        ("PWL", ict_ctx.get("pwl"), "#ab47bc", False),
        ("Mid", ict_ctx.get("midnight_open"), "#42a5f5", False),
    ]
    for label, price, color, bold in level_specs:
        if price and price_min - price_range * 0.05 < price < price_max + price_range * 0.05:
            lw = 1.5 if bold else 1.0
            ax.axhline(price, color=color, linewidth=lw, linestyle="--", alpha=0.7)
            ax.annotate(f"  {label} {price:,.2f}", xy=(right_edge, price),
                        fontsize=8, color=color, fontweight="bold" if bold else "normal",
                        va="center", ha="left", xytext=(3, 0), textcoords="offset points")

    # 4. Equilibrium
    pdh = ict_ctx.get("pdh")
    pdl = ict_ctx.get("pdl")
    if pdh and pdl:
        eq = (pdh + pdl) / 2
        ax.axhline(eq, color="#787b86", linewidth=0.8, linestyle=":", alpha=0.4)
        ax.annotate(f"  EQ {eq:,.2f}", xy=(right_edge, eq),
                    fontsize=7, color="#787b86", va="center", ha="left",
                    xytext=(3, 0), textcoords="offset points")

    # 5. Order Blocks (detect on 5m view)
    obs = detect_order_blocks(df_view, lookback=50)
    obs = filter_mitigated_obs(obs, df_view)
    for ob in obs:
        if ob["datetime"] < df_view.index.min() or ob["datetime"] > df_view.index.max():
            continue
        color = "#4caf50" if ob["type"] == "BULLISH_OB" else "#f44336"
        label = "+OB" if ob["type"] == "BULLISH_OB" else "-OB"
        ob_start = mdates.date2num(ob["datetime"])
        rect = mpatches.Rectangle(
            (ob_start, ob["low"]), right_edge - ob_start, ob["high"] - ob["low"],
            linewidth=1, edgecolor=color, facecolor=color, alpha=0.2,
        )
        ax.add_patch(rect)

    # 6. Fair Value Gaps (detect on 5m view)
    fvgs = detect_fvgs(df_view, min_gap_ticks=1.0, timeframe="5M")
    fvgs = filter_mitigated_fvgs(fvgs, df_view)
    for fvg in fvgs:
        if fvg["datetime"] < df_view.index.min() or fvg["datetime"] > df_view.index.max():
            continue
        color = "#81d4fa" if "BULLISH" in fvg["type"] else "#ffab91"
        rect = mpatches.Rectangle(
            (mdates.date2num(fvg["datetime"]), fvg["bottom"]),
            right_edge - mdates.date2num(fvg["datetime"]),
            fvg["top"] - fvg["bottom"],
            linewidth=0, facecolor=color, alpha=0.3,
        )
        ax.add_patch(rect)

    # 7. Session markers (vertical lines + labels)
    target_d = target_date.date()
    session_markers = [
        (time(0, 0), "00:00", "#607d8b"),
        (time(8, 30), "08:30", "#ff9800"),
        (time(9, 30), "09:30 NY Open", "#ff9800"),
        (time(11, 30), "11:30 Lunch", "#607d8b"),
        (time(13, 30), "13:30 PM", "#607d8b"),
        (time(16, 0), "16:00 Close", "#607d8b"),
    ]
    for sess_time, sess_label, sess_color in session_markers:
        sess_dt = pd.Timestamp.combine(target_d, sess_time)
        if df_5m.index.tz:
            sess_dt = sess_dt.tz_localize("US/Eastern")
        if df_view.index.min() <= sess_dt <= df_view.index.max():
            ax.axvline(sess_dt, color=sess_color, linewidth=0.8, linestyle=":", alpha=0.4)

    # 8. Current price line
    current_price = df_view["close"].iloc[-1]
    ax.axhline(current_price, color="#ffd700", linewidth=0.8, linestyle="-", alpha=0.5)
    ax.annotate(f"  NOW {current_price:,.2f}", xy=(right_edge, current_price),
                fontsize=8, color="#ffd700", fontweight="bold", va="center", ha="left",
                xytext=(3, 0), textcoords="offset points")

    # 9. Title + formatting
    title = f"{ticker} | {target_d} | 5m Daily Context (ICT)"
    ax.set_title(title, fontsize=14, fontweight="bold", color=_DARK_FG, pad=15)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    ax.xaxis.set_minor_locator(mdates.MinuteLocator(byminute=[0, 30]))
    fig.autofmt_xdate(rotation=30)
    plt.tight_layout()

    fig.savefig(str(save_path), facecolor=_DARK_BG, bbox_inches="tight", dpi=dpi)
    plt.close(fig)
    log.info("Saved chart: %s", save_path)
    return save_path


# ═══════════════════════════════════════════════════════════════════════
#  Batch generation
# ═══════════════════════════════════════════════════════════════════════

def _trading_days_from_data(df: pd.DataFrame, n: int) -> list[datetime]:
    """Get the last N trading days that actually have data (min 100 rows)."""
    if df.index.tz is None:
        df.index = pd.DatetimeIndex(df.index).tz_localize("UTC").tz_convert("US/Eastern")
    else:
        df.index = df.index.tz_convert("US/Eastern")
    dates = df.index.date
    unique_dates = sorted(set(dates), reverse=True)
    result = []
    for d in unique_dates:
        count = (df.index.date == d).sum()
        if count > 100:  # at least 100 bars = substantial session
            result.append(datetime.combine(d, time(12, 0)))
        if len(result) >= n:
            break
    return list(reversed(result))


def generate_charts(
    tickers: list[str],
    dates: list[datetime] | None = None,
    last_n: int | None = None,
    dpi: int = 150,
) -> list[Path]:
    """Generate chart images for the given tickers and dates.

    Args:
        tickers: list of ticker symbols (e.g. ["ES1", "NQ1"])
        dates: specific dates to render (if None, uses last_n)
        last_n: render last N trading days (used if dates is None)
        dpi: output DPI (higher = better for vision model reading)

    Returns:
        list of saved file paths
    """
    if dates is None:
        if last_n is None:
            last_n = 1
        # Find dates with actual data
        df_check = load_fused_data(tickers[0], timeframe="1m", require_historical=False)
        if df_check is not None and not df_check.empty:
            dates = _trading_days_from_data(df_check, last_n)
        else:
            dates = []

    saved = []
    for ticker in tickers:
        log.info("Loading 1m data for %s...", ticker)
        df_1m = load_fused_data(ticker, timeframe="1m", require_historical=False)
        if df_1m is None or df_1m.empty:
            log.warning("No data for %s — skipping", ticker)
            continue

        if df_1m.index.tz is None:
            df_1m.index = pd.DatetimeIndex(df_1m.index).tz_localize("UTC").tz_convert("US/Eastern")
        else:
            df_1m.index = df_1m.index.tz_convert("US/Eastern")

        for target_date in dates:
            target_d = target_date.date() if hasattr(target_date, "date") else target_date

            ict_ctx = load_ict_context(ticker, current_price=0)
            save_path = _OUTPUT_DIR / f"{ticker}_{target_d}_daily_context.png"

            try:
                result = render_daily_context_chart(ticker, target_date, df_1m, ict_ctx, save_path, dpi=dpi)
                if result:
                    saved.append(result)
            except Exception as e:
                log.error("Failed to render %s %s: %s", ticker, target_d, e)

    return saved


# ═══════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ap = argparse.ArgumentParser(description="Generate ICT chart images for the chart agent")
    ap.add_argument("--ticker", nargs="+", default=["ES1"], help="Ticker(s): ES1 NQ1 ...")
    ap.add_argument("--date", type=str, default=None, help="Specific date YYYY-MM-DD")
    ap.add_argument("--last-n", type=int, default=None, help="Last N trading days")
    ap.add_argument("--dpi", type=int, default=150, help="Output DPI (higher = better for vision)")
    args = ap.parse_args()

    dates = None
    if args.date:
        dates = [datetime.strptime(args.date, "%Y-%m-%d")]
    elif args.last_n:
        # Will be resolved from data inside generate_charts
        pass
    else:
        args.last_n = 1

    saved = generate_charts(args.ticker, dates=dates, last_n=args.last_n, dpi=args.dpi)
    print(f"\nGenerated {len(saved)} chart(s):")
    for p in saved:
        print(f"  {p}")


if __name__ == "__main__":
    main()