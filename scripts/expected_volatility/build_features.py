"""Build sessions.parquet (+ bars.parquet) for the EV zone research.

Implements DATA_PLAN.md §3 (corrected rev 2026-08-30):
- trading_day = CME futures day 18:00 T-1 -> 17:00 T, filed under RTH date T
- sessions tile the day: Asia 18:00-03:00 (540), London 03:00-09:30 (390),
  NY_AM 09:30-12:00 (150), NY_PM 12:00-16:00 (240), Settlement 16:00-17:00 (60),
  plus rollups RTH (09:30-16:00) and Overnight (18:00-09:30)
- 5m primary buckets (0..275) + 15m rollup (0..91) on both trading-day and
  session clocks, DST-aware via America/New_York wall-clock (§3.3)
- as-of T-1 for VIX pack and settlement (no lookahead, §3.4)
- continuous c sweep: all 12 levels are S*(1 ± c*a) with c in
  {0.2077,0.2289,0.25,0.4155,0.4577,0.5,0.8309,0.9155,1.0,1.2464,1.3732,1.5}
  emitted as parallel arith/log columns; scale_mode includes 1380
- VX1/VX2 (CFE, fetch_cboe_vx_futures.py) joined as-of T-1 for futures basis

Usage:
  python scripts/expected_volatility/build_features.py --ticker ES1 --from 2022-05-13 --vol-source VIX
  python scripts/expected_volatility/build_features.py --ticker ES1 --from 2022-05-13 --vol-source all
  python scripts/expected_volatility/build_features.py --ticker ES1 --from 2022-05-13 --bars   # also build bars.parquet
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import math
# ensure repo root is on sys.path for `import scripts.libs_py...` when run as `python scripts/...`
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import numpy as np

ET_TZ = ZoneInfo("America/New_York")
DATA_DIR = Path("data")
OUT_DIR = DATA_DIR / "expected_volatility"

# Continuous c sweep constants (§1.3) — all 12 levels collapsed to S*(1 ± c*a)
# Derived: c = m * b/a for bottom, c = m * mid/a for mid, c = m for top
# Ordered for readability: 0.25 ladder, 0.5 ladder, 1.0 ladder, 1.5 ladder
C_VALUES = {
    # 0.25 ladder: bottom(c=0.2077), mid(0.2289), top(0.25)
    # 0.5 ladder: 0.4155, 0.4577, 0.5
    # 1.0 ladder: 0.8309, 0.9155, 1.0
    # 1.5 ladder: 1.2464, 1.3732, 1.5
}
C_LIST = [0.2077274, 0.2288647, 0.25, 0.4154549, 0.4577295, 0.5, 0.8309097, 0.9154549, 1.0, 1.2463646, 1.3731823, 1.5]

# Session catalog (tiled, §3.1)
SESSIONS = [
    ("Asia",       time(18,0), time(3,0),  540, "prior close T-1"),
    ("London",     time(3,0),  time(9,30), 390, "prior close T-1"),
    ("NY_AM",      time(9,30), time(12,0), 150, "prior close T-1"),
    ("NY_PM",      time(12,0), time(16,0), 240, "prior close T-1"),
    ("Settlement", time(16,0), time(17,0), 60,  "prior close T-1"),
    ("RTH",        time(9,30), time(16,0), 390, "rollup NY_AM+NY_PM"),
    ("Overnight",  time(18,0), time(9,30), 930, "rollup Asia+London"),
]
SESSION_MINUTES = {s: m for s,_,_,m,_ in SESSIONS}
TRADING_DAY_MINUTES = 1380  # 18:00->17:00 = 23h

SQRT252 = math.sqrt(252)
SQRT365 = math.sqrt(365)

def load_fused_intraday(ticker: str, start: date | None = None, end: date | None = None) -> pd.DataFrame:
    """Load 1m bars for ticker, tz-naive UTC parquet -> tz-aware UTC."""
    # Try live storage first for recent, fallback to historical
    # For this v1 we load the historical 1m parquet (2006->2024) directly;
    # live_storage is tiny (1 year) and will be fused if present.
    hist_path = DATA_DIR / f"{ticker}_1m.parquet"
    live_path = DATA_DIR / f"live/live_storage_-{ticker.replace('1','')}.parquet"
    # ticker is like ES1, live file is live_storage_-ES.parquet
    dfs = []
    if hist_path.exists():
        df = pd.read_parquet(hist_path)
        df.index = df.index.tz_localize("UTC")
        dfs.append(df)
    if live_path.exists():
        try:
            ldf = pd.read_parquet(live_path)
            # live storage is tz-naive UTC per repo
            if ldf.index.tz is None:
                ldf.index = ldf.index.tz_localize("UTC")
            dfs.append(ldf)
        except Exception:
            pass
    if not dfs:
        raise FileNotFoundError(f"No data for {ticker}: tried {hist_path} and {live_path}")
    df = pd.concat(dfs).sort_index()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    if start:
        df = df[df.index.tz_convert(ET_TZ).date >= start]
    if end:
        df = df[df.index.tz_convert(ET_TZ).date <= end]
    return df

def load_daily_settlement_series(symbol: str) -> pd.Series:
    """Load daily settlement series indexed by ET-normalized date (anchor at 16:00 ET).
    symbol like VIX, VIX1D, VOLI, VX1 etc. Handles both _1d.parquet daily and _1m intraday fallback.
    """
    # Try daily first
    daily_path = DATA_DIR / f"{symbol}_1d.parquet"
    if daily_path.exists():
        df = pd.read_parquet(daily_path)
        # Index is 20:00 UTC = 16:00 ET
        idx = df.index.tz_convert(ET_TZ).normalize()
        s = pd.Series(df["close"].values, index=idx).sort_index()
        s = s[~s.index.duplicated(keep="last")]
        return s
    # Fallback to 1m -> daily settlement via 16:00 cutoff (like settlements.py)
    m_path = DATA_DIR / f"{symbol}_1m.parquet"
    if m_path.exists():
        from scripts.libs_py.expected_volatility.settlements import build_daily_settlements
        intraday = pd.read_parquet(m_path)
        intraday.index = intraday.index.tz_localize("UTC")
        # build_daily_settlements handles 16:00 cutoff internally
        s = build_daily_settlements(intraday, None, toggle=False)
        return s
    return pd.Series(dtype=float)

def trading_day_for_ts(ts: pd.Timestamp) -> date:
    """CME trading day: 18:00 T-1 -> 17:00 T belongs to T."""
    et = ts.tz_convert(ET_TZ)
    # If time >= 18:00, belongs to next calendar day
    if et.hour >= 18:
        return (et.date() + timedelta(days=1))
    else:
        return et.date()

def minutes_since_trading_day_open(ts: pd.Timestamp) -> int:
    """0 at 18:00 T-1, DST-aware via ET wall-clock."""
    et = ts.tz_convert(ET_TZ)
    td = trading_day_for_ts(ts)
    # Trading day open is 18:00 ET on T-1
    open_et = datetime.combine(td - timedelta(days=1), time(18,0), tzinfo=ET_TZ)
    # Handle DST: open_et is wall-clock 18:00, which is unambiguous
    delta = et - open_et
    return int(delta.total_seconds() // 60)

def session_window_for_trading_day(trading_day: date, session_id: str):
    """Return (start_ts, end_ts) as tz-aware UTC for a given trading_day and session_id."""
    # trading_day is RTH date T, session windows per catalog
    for sid, start_t, end_t, mins, _ in SESSIONS:
        if sid == session_id:
            # Start
            if sid == "Asia":
                # 18:00 T-1
                start_et = datetime.combine(trading_day - timedelta(days=1), time(18,0), tzinfo=ET_TZ)
                end_et = datetime.combine(trading_day, time(3,0), tzinfo=ET_TZ)
            elif sid == "Overnight":
                start_et = datetime.combine(trading_day - timedelta(days=1), time(18,0), tzinfo=ET_TZ)
                end_et = datetime.combine(trading_day, time(9,30), tzinfo=ET_TZ)
            elif sid in ("RTH",):
                start_et = datetime.combine(trading_day, time(9,30), tzinfo=ET_TZ)
                end_et = datetime.combine(trading_day, time(16,0), tzinfo=ET_TZ)
            else:
                start_et = datetime.combine(trading_day, start_t, tzinfo=ET_TZ)
                end_et = datetime.combine(trading_day, end_t, tzinfo=ET_TZ)
                # Handle wrap past midnight for Asia already done; others same day
            return start_et.astimezone(timezone.utc), end_et.astimezone(timezone.utc)
    raise ValueError(f"Unknown session {session_id}")

def bucket_ids(minutes: int | None) -> tuple[int | None, int | None]:
    if minutes is None or pd.isna(minutes):
        return None, None
    return minutes // 5, minutes // 15

def compute_ev_levels(S: float, vix: float, scale_factor: float = 1.0) -> dict:
    """Compute all c levels for given S, VIX (as-of T-1), and scale_factor.
    Returns dict with keys like R_1.0_arith, R_0.8309_arith, etc., plus log variants.
    For v1 we emit the 4 Pine m markers plus the continuous c values.
    """
    if pd.isna(S) or pd.isna(vix):
        return {}
    a = vix / SQRT252 / 100.0 * scale_factor
    out = {}
    for c in C_LIST:
        label = f"{c:.4f}".rstrip("0").rstrip(".")
        # Arith: S*(1 ± c*a)
        out[f"R_arith_{label}"] = S * (1 + c * a)
        out[f"S_arith_{label}"] = S * (1 - c * a)
        # Log: S*exp(±c*a)
        out[f"R_log_{label}"] = S * math.exp(c * a)
        out[f"S_log_{label}"] = S * math.exp(-c * a)
    # Also emit Pine m markers for convenience (top = c= m, bottom = c= m*0.8309)
    for m in [0.25, 0.5, 1.0, 1.5]:
        ms = f"{m:g}"
        out[f"R_top_arith_{ms}"] = S * (1 + m * vix / SQRT252 / 100 * scale_factor)
        out[f"R_bot_arith_{ms}"] = S * (1 + m * vix / SQRT365 / 100 * scale_factor)
        out[f"S_top_arith_{ms}"] = S * (1 - m * vix / SQRT365 / 100 * scale_factor)
        out[f"S_bot_arith_{ms}"] = S * (1 - m * vix / SQRT252 / 100 * scale_factor)
    return out

def main():
    parser = argparse.ArgumentParser(description="Build sessions.parquet with VX1/VX2 join and 5m buckets")
    parser.add_argument("--ticker", default="ES1", help="Ticker like ES1")
    parser.add_argument("--from", dest="from_date", default="2022-05-13", help="Start trading_day (YYYY-MM-DD)")
    parser.add_argument("--to", dest="to_date", default=None, help="End trading_day")
    parser.add_argument("--vol-source", default="VIX", help="Vol source or 'all' (VIX,VIX1D,VOLI,VIX9D,VIX3M,VX1)")
    parser.add_argument("--bars", action="store_true", help="Also build bars.parquet")
    parser.add_argument("--out", default=None, help="Output dir (default data/expected_volatility)")
    args = parser.parse_args()

    from_date = date.fromisoformat(args.from_date) if args.from_date else date(2022,5,13)
    to_date = date.fromisoformat(args.to_date) if args.to_date else date.today()
    out_dir = Path(args.out) if args.out else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    vol_sources = ["VIX","VIX1D","VOLI","VIX9D","VIX3M","VX1"] if args.vol_source == "all" else [args.vol_source]
    print(f"Building for {args.ticker} {from_date}->{to_date} vol_sources={vol_sources}")

    # Load intraday and daily settlement series (as-of)
    intraday = load_fused_intraday(args.ticker, start=from_date - timedelta(days=2), end=to_date + timedelta(days=1))
    print(f"Intraday rows {len(intraday)} {intraday.index[0]} -> {intraday.index[-1]}")

    # Daily settlement series (as-of T-1)
    daily_S = load_daily_settlement_series(args.ticker.replace("1",""))  # ES1 -> ES -> try ES_1d? Actually settlement is prior close <16:00, we need intraday-derived
    # For ES settlement we use intraday 16:00 cutoff, not daily parquet
    from scripts.libs_py.expected_volatility.settlements import build_daily_settlements
    # Build settlement series from intraday (16:00 cutoff) — this is S_T
    S_series = build_daily_settlements(intraday, None, toggle=False)
    # S_series indexed by ET-normalized date T (value is prior close? Actually build_daily_settlements returns shifted series where index T holds S_T = close_{T-1})
    # For our trading_day T, we need S_T = settlement as-of T (prior close), which is S_series.loc[T]
    print(f"S_series {len(S_series)} {S_series.index[0].date()}->{S_series.index[-1].date()} sample {S_series.tail(2).to_dict()}")

    # Load vol daily series (as-of)
    vol_daily = {}
    for vs in vol_sources:
        s = load_daily_settlement_series(vs)
        vol_daily[vs] = s
        print(f"{vs:6s} daily {len(s)} {s.index[0].date() if len(s) else 'empty'}->{s.index[-1].date() if len(s) else ''}")

    # Ecosystem pack — always load for as-of joins regardless of vol_sources filter
    # These are used for the VIX pack columns (§2 Q20-28) on every row
    ecosystem_symbols = ["VIX","VIX1D","VIX9D","VIX3M","VVIX","VX1","VX2"]
    eco_daily = {}
    for sym in ecosystem_symbols:
        if sym not in vol_daily:
            s = load_daily_settlement_series(sym)
            eco_daily[sym] = s
            print(f"{sym:6s} eco   {len(s)} {s.index[0].date() if len(s) else 'empty'}->{s.index[-1].date() if len(s) else ''}")
        else:
            eco_daily[sym] = vol_daily[sym]
    # Also ensure VVIX daily is in eco
    vvix_daily = eco_daily.get("VVIX", load_daily_settlement_series("VVIX"))
    # as-of shifts for leakage-safe joins (§3.4): S_series is already as-of T, vol series hold close_T at T so need shift(1) to get T-1
    vol_asof = {k: v.shift(1) for k, v in eco_daily.items()}
    vol_daily_asof = {k: v.shift(1) for k, v in vol_daily.items()}
    vvix_daily_asof = vol_asof.get("VVIX", vvix_daily.shift(1) if hasattr(vvix_daily, 'shift') else vvix_daily)
    # Load ES realized vol proxy (20d) from intraday daily closes
    # Build daily closes for RV20
    # Use S_series closes? Actually need close-to-close log returns
    # Derive daily close series from intraday settlement (prior close series shifted back)
    # S_series index T holds close_{T-1}, so close_T = S_series.shift(-1) index? Simpler: build daily close from intraday via same cutoff but without shift
    # For RV20 we can compute from S_series values
    close_series = S_series.shift(-1)  # so close_series.loc[T] = close_T
    log_ret = np.log(close_series / close_series.shift(1))
    rv20 = log_ret.rolling(20).std() * math.sqrt(252) * 100  # annualized % at T
    rv20_asof = rv20.shift(1)  # as-of T-1 for leakage-safe

    # Build sessions rows
    scale_modes = {
        "unscaled": 1.0,
        "sqrt_sess_over_1380": None,  # per session
        "sqrt_sess_over_390": None,
        "sqrt_sess_over_1440": None,
    }

    rows = []
    # Iterate trading days
    trading_days = pd.date_range(from_date, to_date, freq="D").date
    for td in trading_days:
        # Skip weekends whereno RTH? Still emit but will be empty
        for session_id in ["Asia","London","NY_AM","NY_PM","Settlement","RTH","Overnight"]:
            # Session window
            try:
                start_utc, end_utc = session_window_for_trading_day(td, session_id)
            except Exception:
                continue
            # Filter intraday bars for this session
            sess_bars = intraday[(intraday.index >= start_utc) & (intraday.index < end_utc)]
            if sess_bars.empty:
                continue
            sess_high = sess_bars["high"].max()
            sess_low = sess_bars["low"].min()
            sess_close = sess_bars["close"].iloc[-1]
            sess_open = sess_bars["open"].iloc[0]
            sess_range = sess_high - sess_low

            # As-of settlement and vol (T-1 close) — leakage-safe per §3.4
            # session decision time: Asia 18:00 T-1, London 03:00 T, NY/RTH 09:30 T, NY_PM midday 12:00 T
            # For v1, all sessions except NY_PM midday use T-1
            et_td = pd.Timestamp(td, tz=ET_TZ)
            S = S_series.get(et_td, np.nan)
            # For Asia/London, S_T-1 is correct as-of (prior RTH close)
            # For NY_PM midday variant, would use 12:00 price — not emitted in v1 base rows
            for vs in vol_sources:
                vix_series_asof = vol_daily_asof.get(vs, pd.Series(dtype=float))
                vix = vix_series_asof.get(et_td, np.nan)
                if pd.isna(S) or pd.isna(vix):
                    continue
                # VIX ecosystem pack as-of T-1 (leakage-safe)
                trailing = vix_series_asof.loc[:et_td].dropna()
                pctl_63 = trailing.tail(63).rank(pct=True).iloc[-1] * 100 if len(trailing) >= 63 else np.nan
                pctl_252 = trailing.tail(252).rank(pct=True).iloc[-1] * 100 if len(trailing) >= 252 else np.nan
                # Term slopes as-of T-1 (from eco pack, not vol_daily filter)
                vix9d = vol_asof.get("VIX9D", pd.Series(dtype=float)).get(et_td, np.nan)
                vix3m = vol_asof.get("VIX3M", pd.Series(dtype=float)).get(et_td, np.nan)
                vix1d = vol_asof.get("VIX1D", pd.Series(dtype=float)).get(et_td, np.nan)
                term_1d_30d = vix - vix1d if not pd.isna(vix1d) else np.nan
                term_9d_30d = vix - vix9d if not pd.isna(vix9d) else np.nan
                term_30d_90d = vix - vix3m if not pd.isna(vix3m) else np.nan
                vvix = vvix_daily_asof.get(et_td, np.nan)
                rv = rv20_asof.get(et_td, np.nan)
                vrp = vix - rv if not pd.isna(rv) else np.nan
                vx1 = vol_asof.get("VX1", pd.Series(dtype=float)).get(et_td, np.nan)
                vx2 = vol_asof.get("VX2", pd.Series(dtype=float)).get(et_td, np.nan)
                vx_basis = vx1 - vix if not pd.isna(vx1) else np.nan
                vx_curve = vx2 - vx1 if not pd.isna(vx2) and not pd.isna(vx1) else np.nan

                for scale_id, scale_val in [("unscaled",1.0),("sqrt_sess_over_1380", math.sqrt(SESSION_MINUTES[session_id]/1380)),("sqrt_sess_over_390", math.sqrt(SESSION_MINUTES[session_id]/390))]:
                    ev_levels = compute_ev_levels(S, vix, scale_factor=scale_val)
                    # Hit stats per c level (continuous sweep)
                    # For each of the 12 c values, compute touched etc.
                    # Also compute Pine m markers for convenience
                    for c in C_LIST:
                        label = f"{c:.4f}".rstrip("0").rstrip(".")
                        for mode in ["arith","log"]:
                            lvl_key = f"R_{mode}_{label}"
                            lvl = ev_levels.get(lvl_key)
                            if lvl is None or pd.isna(lvl):
                                continue
                            # Touch detection
                            touched = (sess_high >= lvl >= sess_low) if "R_" in lvl_key else (sess_low <= lvl <= sess_high)
                            # Actually R levels are above S, so high crosses; S levels low crosses — same logic
                            # First touch time
                            first_touch_min_session = None
                            first_touch_min_trading_day = None
                            max_pierce = 0
                            pierce_bars = 0
                            close_beyond = False
                            if touched:
                                # Find first bar where high >= lvl (R) or low <= lvl (S)
                                if lvl > S:  # R
                                    mask = sess_bars["high"] >= lvl
                                    pierce = (sess_bars["high"] - lvl).clip(lower=0).max()
                                else:
                                    mask = sess_bars["low"] <= lvl
                                    pierce = (lvl - sess_bars["low"]).clip(lower=0).max()
                                first_idx = mask[mask].index[0] if mask.any() else None
                                if first_idx is not None:
                                    # minutes since session open
                                    first_touch_min_session = int((first_idx - start_utc).total_seconds()//60)
                                    first_touch_min_trading_day = minutes_since_trading_day_open(first_idx)
                                    max_pierce = float(pierce)
                                    pierce_bars = int(mask.sum())
                                    close_beyond = bool(sess_close >= lvl) if lvl > S else bool(sess_close <= lvl)
                            b5_sess, b15_sess = bucket_ids(first_touch_min_session)
                            b5_td, b15_td = bucket_ids(first_touch_min_trading_day)
                            # Reversal placeholder: max favorable move after touch within session
                            reversal_hit = None
                            if touched and first_touch_min_session is not None:
                                # Bars after touch
                                after = sess_bars[sess_bars.index > first_idx] if first_idx is not None else pd.DataFrame()
                                if not after.empty:
                                    if lvl > S:
                                        # R touch: reversal is down move from lvl
                                        rev = (lvl - after["low"].min())
                                        reversal_hit = bool(rev >= 4)  # 4 pts ES threshold per plan §6.1; will be param
                                    else:
                                        rev = (after["high"].max() - lvl)
                                        reversal_hit = bool(rev >= 4)

                            rows.append({
                                "trading_day": td,
                                "session_id": session_id,
                                "ticker": args.ticker,
                                "vol_source": vs,
                                "scale_mode": scale_id,
                                "anchor_mode": "close",  # v1 only close; open/midday gated per §3.2
                                "settlement_close": S,
                                "vix_close": vix,
                                "session_open": sess_open,
                                "session_high": sess_high,
                                "session_low": sess_low,
                                "session_close": sess_close,
                                "session_range": sess_range,
                                "c": c,
                                "level_mode": mode,
                                "level_price": lvl,
                                "touched": bool(touched),
                                "first_touch_min_session": first_touch_min_session,
                                "first_touch_min_trading_day": first_touch_min_trading_day,
                                "bucket_5m_session": b5_sess,
                                "bucket_15m_session": b15_sess,
                                "bucket_5m_trading_day": b5_td,
                                "bucket_15m_trading_day": b15_td,
                                "max_pierce_pts": max_pierce if touched else 0,
                                "pierce_bars": pierce_bars,
                                "close_beyond": close_beyond,
                                "reversal_hit": reversal_hit,
                                "vix_pctl_63d": pctl_63,
                                "vix_pctl_252d": pctl_252,
                                "vix_term_slope_1d_30d": term_1d_30d,
                                "vix_term_slope_9d_30d": term_9d_30d,
                                "vix_term_slope_30d_90d": term_30d_90d,
                                "vvix": vvix,
                                "vrp_20d": vrp,
                                "vx1_close": vx1,
                                "vx2_close": vx2,
                                "vx_basis_spot": vx_basis,
                                "vx_curve_1_2": vx_curve,
                            })
                    # Also emit Pine m markers as separate rows for convenience (optional)
                    # For brevity, v1 keeps only continuous c; Pine markers are just c=0.25 etc.
    df = pd.DataFrame(rows)
    if df.empty:
        print("No rows built — check date range and vol_source")
        return
    # De-duplicate by key (trading_day, session_id, ticker, vol_source, scale_mode, c, level_mode)
    df = df.sort_values(["trading_day","session_id","c","level_mode"])
    out_path = out_dir / "sessions.parquet"
    # Upsert: read existing, concat, deduplicate keep last
    if out_path.exists():
        existing = pd.read_parquet(out_path)
        combined = pd.concat([existing, df], ignore_index=True).drop_duplicates(subset=["trading_day","session_id","ticker","vol_source","scale_mode","c","level_mode"], keep="last").sort_values(["trading_day","session_id","c"])
        df = combined
    df.to_parquet(out_path)
    print(f"Wrote {out_path} rows {len(df)} trading_days {df['trading_day'].nunique()} sessions {df['session_id'].nunique()}")

    if args.bars:
        # Build bars.parquet: one row per 1m bar with both clocks and distances
        print("Building bars.parquet...")
        # For each bar, compute trading_day, session_id, and distances to each c level (using as-of S_T)
        # For v1, use S_T-1 and vix_T-1 per bar's trading_day
        bars = intraday.copy()
        bars["trading_day"] = [trading_day_for_ts(ts) for ts in bars.index]
        bars["minutes_since_trading_day_open"] = [minutes_since_trading_day_open(ts) for ts in bars.index]
        bars["bucket_5m_trading_day"] = bars["minutes_since_trading_day_open"] // 5
        bars["bucket_15m_trading_day"] = bars["minutes_since_trading_day_open"] // 15
        # Session id per bar (tiled)
        def bar_session(ts):
            td = trading_day_for_ts(ts)
            for sid in ["Asia","London","NY_AM","NY_PM","Settlement"]:
                s,e = session_window_for_trading_day(td, sid)
                if s <= ts < e:
                    return sid
            return "Unknown"
        bars["session_id"] = [bar_session(ts) for ts in bars.index]
        bars["minutes_since_session_open"] = bars.apply(lambda r: int((r.name - session_window_for_trading_day(r["trading_day"], r["session_id"])[0]).total_seconds()//60) if r["session_id"] != "Unknown" else None, axis=1)
        bars["bucket_5m_session"] = bars["minutes_since_session_open"] // 5
        bars["bucket_15m_session"] = bars["minutes_since_session_open"] // 15
        # For each bar, compute distance to nearest R/S at that trading_day's as-of S (using unscaled c=1.0 arith)
        # Keep lightweight: just nearest distance, not all 12 c
        # Use S_T per bar's trading_day
        def dist_for_bar(row):
            td = row["trading_day"]
            et_td = pd.Timestamp(td, tz=ET_TZ)
            S = S_series.get(et_td, np.nan)
            if pd.isna(S):
                return np.nan
            # Use VIX as-of T-1 for the bar's trading_day, unscaled c=1.0
            vix = vol_daily.get("VIX", pd.Series(dtype=float)).get(et_td, np.nan)
            if pd.isna(vix):
                vix = vol_daily.get(vol_sources[0], pd.Series(dtype=float)).get(et_td, np.nan)
            if pd.isna(vix):
                return np.nan
            a = vix / SQRT252 / 100
            R1 = S*(1 + a)
            S1 = S*(1 - a)
            # distance to nearest of the two
            return min(abs(row["close"]-R1), abs(row["close"]-S1))
        bars["dist_to_nearest_R1"] = bars.apply(dist_for_bar, axis=1)
        bars.to_parquet(out_dir / "bars.parquet")
        print(f"Wrote bars.parquet rows {len(bars)}")

if __name__ == "__main__":
    main()
