"""
Render August 25, 2026 Exact User Master Short Trade
=====================================================
Matches user's TradingView charts (media_1788413921355.png and media_1788414220242.png):
1. R-EQH Sweep @ 29,414.75
2. WOPEN Rejection @ 29,392.25
3. 1m CISD Shift @ 29,378.00
4. 2nd Stage -OB Entry @ 29,380.00 - 29,387.00
5. Target: London Low @ 29,212.25 (+165 pts WIN!) & DOPEN Purge @ 29,138.00
6. Post-10:30 ET: Structural Chop Warning
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import mplfinance as mpf

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

OUTPUT_DIR = Path("C:/Users/vinay/.gemini/antigravity/brain/4c21dcc0-89c9-42df-8e6a-fc48ef5552a9")

def render_aug25_user_trade():
    df_nq = pd.read_parquet("data/NQ_recent_week.parquet").sort_index()
    target_date = "2026-08-25"
    target_d = pd.to_datetime(target_date).date()
    nq_day = df_nq[df_nq.index.date == target_d].copy()

    mc = mpf.make_marketcolors(up='#089981', down='#f23645', edge='inherit', wick='inherit')
    s = mpf.make_mpf_style(marketcolors=mc, gridcolor='#f1f5f9', gridstyle='--', y_on_right=True, figcolor='#ffffff')

    # Zoom window: 09:20 ET to 10:45 ET
    df_trade = nq_day.loc[f"{target_date} 09:25:00":f"{target_date} 10:45:00"].copy()

    fig, ax = mpf.plot(
        df_trade,
        type='candle',
        style=s,
        figsize=(16, 9),
        returnfig=True,
        title="NQ 1-Min — August 25, 2026 | User's Master Short: WOPEN Rejection to London Low Target",
        ylabel="Price (Points)"
    )

    time_list = [t.strftime("%H:%M") for t in df_trade.index]
    idx_top = time_list.index("09:50") if "09:50" in time_list else 25
    idx_cisd = time_list.index("09:51") if "09:51" in time_list else 26
    idx_entry = time_list.index("09:53") if "09:53" in time_list else 28
    idx_lndn = time_list.index("10:30") if "10:30" in time_list else 65
    idx_purge = time_list.index("10:31") if "10:31" in time_list else 66

    # 1. R-EQH Line: 29414.75
    ax[0].axhline(29414.75, color='#3b82f6', linestyle='-', linewidth=1.5)
    ax[0].text(1, 29416.50, "R-EQH (Relative Equal Highs) @ 29414.75", color='#1d4ed8', fontsize=9.5, fontweight='bold')

    # 2. WOPEN Line: 29392.25
    ax[0].axhline(29392.25, color='#2563eb', linestyle='--', linewidth=1.5)
    ax[0].text(1, 29394.00, "WOPEN rejection @ 29392.25 (Weekly Open)", color='#1e40af', fontsize=9.5, fontweight='bold')

    # 3. 1m CISD Line: 29378.00
    ax[0].axhline(29378.00, color='#6366f1', linestyle=':', linewidth=1.5)
    ax[0].text(1, 29379.50, "1m CISD (29378.00)", color='#4338ca', fontsize=9, fontweight='bold')

    # 4. -OB / iFVG Box: 29378 - 29388
    rect_ob = Rectangle((idx_entry - 2, 29375.0), 5.0, 13.0,
                        facecolor='#a855f7', alpha=0.3, edgecolor='#9333ea', linestyle='--')
    ax[0].add_patch(rect_ob)
    ax[0].text(idx_entry - 2, 29390.0, "-OB / iFVG / BPR", color='#7e22ce', fontsize=8.5, fontweight='bold')

    # 5. London Low Line: 29212.25
    ax[0].axhline(29212.25, color='#ec4899', linestyle='--', linewidth=1.8)
    ax[0].text(1, 29214.00, "Target London Low (29212.25)", color='#db2777', fontsize=9.5, fontweight='bold')

    # 6. DOPEN Purge Level: 29138.00
    ax[0].axhline(29138.00, color='#ef4444', linestyle=':', linewidth=1.5)
    ax[0].text(1, 29141.00, "DOPEN purge (29138.00)", color='#b91c1c', fontsize=9.5, fontweight='bold')

    # Annotations
    ax[0].annotate(
        "2nd stage OB entry\nLimit Fill @ 29380 - 29385\nStop Loss: 29420.00 (above R-EQH)",
        xy=(idx_entry, 29385.00),
        xytext=(idx_entry - 12, 29350.00),
        arrowprops=dict(facecolor='#a855f7', edgecolor='#7e22ce', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#faf5ff", edgecolor="#a855f7", alpha=0.95),
        fontsize=9, fontweight='bold', color='#6b21a8'
    )

    ax[0].annotate(
        "TARGET HIT: London Low (29212.25)\n+168.0 Points Profit (+57 bps)!\nInstitutional delivery target fulfilled",
        xy=(idx_lndn, 29212.25),
        xytext=(idx_lndn - 18, 29240.00),
        arrowprops=dict(facecolor='#16a34a', edgecolor='#15803d', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#f0fdf4", edgecolor="#16a34a", alpha=0.95),
        fontsize=9, fontweight='bold', color='#14532d'
    )

    ax[0].annotate(
        "DOPEN PURGE (29138.00)\nPanic sell stop flush\nPost-target: Market enters chop",
        xy=(idx_purge, 29138.00),
        xytext=(idx_purge - 15, 29165.00),
        arrowprops=dict(facecolor='#ef4444', edgecolor='#b91c1c', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fef2f2", edgecolor="#ef4444", alpha=0.95),
        fontsize=9, fontweight='bold', color='#991b1b'
    )

    out_file = OUTPUT_DIR / "aug25_user_master_short.png"
    fig.savefig(out_file, dpi=160, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved: {out_file}")

if __name__ == "__main__":
    render_aug25_user_trade()
