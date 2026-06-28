"""
Three-layer options data backfill.
Priority waterfall per field: unified_levels > daily_levels > gex_profiles (derived)
"""
import os
import glob
import json
import sqlite3
import uuid
import numpy as np
from datetime import datetime
from zoneinfo import ZoneInfo

TZ_NY = ZoneInfo("America/New_York")

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def dt_to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)

def generate_cuid() -> str:
    return "cmk" + uuid.uuid4().hex[:22]

def _first_file_for_date(pattern: str) -> str | None:
    files = sorted(glob.glob(pattern))
    return files[0] if files else None

# ---------------------------------------------------------------------------
# Layer 1 -- daily_levels parser
# ---------------------------------------------------------------------------

def parse_daily_levels(date_str: str, data_dir: str = "data/options") -> dict:
    path = _first_file_for_date(os.path.join(data_dir, f"daily_levels_{date_str}_*.json"))
    if not path:
        return {}

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"  [DL] Error reading {path}: {e}")
        return {}

    gen_at_str = data.get("generated_at")
    gen_at = datetime.fromisoformat(gen_at_str.replace("Z", "+00:00")).astimezone(TZ_NY) if gen_at_str else None

    results = {}
    for m in data.get("market_structure", []):
        asset = m.get("asset", "")
        cash  = m.get("cash_ticker") or asset
        if asset == "ES":   ticker = "SPX"
        elif asset == "NQ": ticker = "QQQ"
        elif asset in ("SPY",) or cash == "SPY": ticker = "SPY"
        else: continue
        if ticker not in ("SPY", "SPX", "QQQ"): continue

        sa     = m.get("scored_analysis", {})
        tagged = {x.get("field"): x.get("strike") for x in sa.get("all_tagged", []) if x.get("field")}

        em_list  = m.get("expected_moves", [])
        em       = em_list[0] if em_list else {}
        em_hi, em_lo = em.get("em_upper"), em.get("em_lower")
        spot     = (em_hi + em_lo) / 2.0 if (em_hi and em_lo) else None
        straddle = (em_hi - em_lo) if (em_hi and em_lo) else None

        results[ticker] = {
            "gen_at":                  gen_at,
            "spot":                    spot,
            "gamma_magnet":            m.get("gamma_magnet"),
            "pin_strike":              m.get("pin_strike"),
            "total_gex":               m.get("total_gex"),
            "total_gex_delta_adj":     m.get("total_gex_delta_adj"),
            "call_gamma_total":        m.get("call_gamma_total"),
            "put_gamma_total":         m.get("put_gamma_total"),
            "net_vanna_exposure":      m.get("net_vanna_exposure"),
            "net_speed_exposure":      m.get("net_speed_exposure"),
            "put_25d_iv":              m.get("put_25d_iv"),
            "call_25d_iv":             m.get("call_25d_iv"),
            "volatility_skew_premium": m.get("volatility_skew_premium"),
            "gex_regime":              m.get("gex_regime"),
            "regime_label":            m.get("regime_label"),
            "zero_gamma":              tagged.get("zero_gamma"),
            "zero_gamma_delta_adj":    tagged.get("zero_gamma_delta_adj"),
            "call_wall":               tagged.get("call_wall"),
            "put_wall":                tagged.get("put_wall"),
            "em_straddle":             straddle,
            "open_price":              spot,
        }
    return results


# ---------------------------------------------------------------------------
# Layer 2 -- unified_levels parser
# ---------------------------------------------------------------------------

def _meta_val(meta_tags, prefix, default=None, as_type=float):
    for tag in meta_tags:
        t = tag.split(":")[-1]
        if t.startswith(prefix):
            try:
                return as_type(t[len(prefix):])
            except (ValueError, TypeError):
                pass
    return default

def _meta_str(meta_tags, prefix, default=None):
    for tag in meta_tags:
        t = tag.split(":")[-1]
        if t.startswith(prefix):
            return t[len(prefix):]
    return default

def _strike_by_label(tokens, labels):
    for t in tokens:
        if str(t.get("label", "")) in labels:
            try:
                return float(t.get("strike"))
            except (TypeError, ValueError):
                pass
    return None

def parse_unified_levels(date_str: str, data_dir: str = "data/options") -> dict:
    path = _first_file_for_date(os.path.join(data_dir, f"unified_levels_{date_str}_*.json"))
    if not path:
        return {}

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"  [UL] Error reading {path}: {e}")
        return {}

    gen_at_str = data.get("generated_at")
    gen_at = datetime.fromisoformat(gen_at_str.replace("Z", "+00:00")).astimezone(TZ_NY) if gen_at_str else None

    results = {}
    for t in data.get("tickers", []):
        ticker = t.get("ticker")
        if ticker not in ("SPY", "SPX", "QQQ"):
            continue

        line   = t.get("line", "")
        tokens = t.get("tokens", [])
        meta_tags = [p.strip() for p in line.split(",") if "META" in p]

        em_hi, em_lo = None, None
        for tok in tokens:
            lbl = str(tok.get("label", ""))
            if lbl.startswith("EM HI"):
                try: em_hi = float(tok.get("strike"))
                except: pass
            if lbl.startswith("EM LO"):
                try: em_lo = float(tok.get("strike"))
                except: pass

        spot     = (em_hi + em_lo) / 2.0 if (em_hi and em_lo) else _meta_val(meta_tags, "META_S_TRIG_")
        straddle = (em_hi - em_lo) if (em_hi and em_lo) else None
        bias     = _meta_str(meta_tags, "META_BIAS_", "")

        record = {
            "gen_at":                  gen_at,
            "spot":                    spot,
            "total_gex":               _meta_val(meta_tags, "META_GEX_TOTAL_"),
            "total_gex_delta_adj":     _meta_val(meta_tags, "META_GEX_DA_"),
            "net_vanna_exposure":      _meta_val(meta_tags, "META_VANNA_"),
            "net_speed_exposure":      _meta_val(meta_tags, "META_SPEED_"),
            "volatility_skew_premium": _meta_val(meta_tags, "META_SKEW_"),
            "gex_regime":              "POSITIVE" if bias == "BULLISH" else "NEGATIVE",
            "regime_label":            _meta_str(meta_tags, "META_REGIME_", "NORMAL"),
            "zero_gamma":              _strike_by_label(tokens, ["ZERO GEX"]),
            "zero_gamma_delta_adj":    _strike_by_label(tokens, ["ZERO GEX DA"]),
            "call_wall":               _strike_by_label(tokens, ["CW", "0D CW", "CW 0%BK", "CW 1%BK", "CW 2%BK"]),
            "put_wall":                _strike_by_label(tokens, ["PW", "0D PW", "PW 1%BK"]),
            "gamma_magnet":            _strike_by_label(tokens, ["MAGNET"]),
            "pin_strike":              _strike_by_label(tokens, ["PIN"]),
            "em_straddle":             straddle,
            "open_price":              spot,
        }
        # Only keep non-None so waterfall preserves DL values where UL is absent
        results[ticker] = {k: v for k, v in record.items() if v is not None}

    return results


# ---------------------------------------------------------------------------
# Layer 3 -- gex_profiles derivation
# ---------------------------------------------------------------------------

def derive_from_gex_profiles(date_str: str, data_dir: str = "data/options") -> dict:
    path = _first_file_for_date(os.path.join(data_dir, f"gex_profiles_{date_str}_*.json"))
    if not path:
        return {}

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"  [GP] Error reading {path}: {e}")
        return {}

    gen_at_str = data.get("generated_at")
    gen_at = datetime.fromisoformat(gen_at_str.replace("Z", "+00:00")).astimezone(TZ_NY) if gen_at_str else None

    TICKER_MAP = {"ES": "SPX", "NQ": "QQQ", "SPY": "SPY", "SPX": "SPX", "QQQ": "QQQ"}
    results = {}

    for raw_ticker, surface in data.get("profiles", {}).items():
        ticker = TICKER_MAP.get(raw_ticker)
        if ticker not in ("SPY", "SPX", "QQQ"):
            continue
        if not isinstance(surface, list) or len(surface) < 5:
            continue

        surface_sorted = sorted(surface, key=lambda r: r.get("strike", 0))
        strikes  = np.array([r["strike"] for r in surface_sorted], dtype=float)
        net_gex  = np.array([r.get("net_gex", 0.0) for r in surface_sorted], dtype=float)
        net_dex  = np.array([r.get("net_dex", 0.0) for r in surface_sorted], dtype=float)
        call_gex = np.array([r.get("call_gex", 0.0) for r in surface_sorted], dtype=float)
        put_gex  = np.array([r.get("put_gex", 0.0) for r in surface_sorted], dtype=float)

        cum_gex = np.cumsum(net_gex)
        cum_dex = np.cumsum(net_dex)

        def _zero_cross(arr):
            for i in range(len(arr) - 1):
                if arr[i] * arr[i + 1] < 0:
                    frac = -arr[i] / (arr[i + 1] - arr[i])
                    return float(strikes[i] + frac * (strikes[i + 1] - strikes[i]))
            return None

        zero_gamma           = _zero_cross(cum_gex)
        zero_gamma_delta_adj = _zero_cross(cum_dex)

        peak_idx     = int(np.argmax(np.abs(net_gex)))
        gamma_magnet = float(strikes[peak_idx])

        mid_strike = float(np.median(strikes))

        upper_mask = strikes > mid_strike
        call_wall = None
        if upper_mask.any():
            cg_up = call_gex[upper_mask]
            call_wall = float(strikes[upper_mask][int(np.argmax(cg_up))]) if len(cg_up) else None

        lower_mask = strikes < mid_strike
        put_wall = None
        if lower_mask.any():
            pg_lo = np.abs(put_gex[lower_mask])
            put_wall = float(strikes[lower_mask][int(np.argmax(pg_lo))]) if len(pg_lo) else None

        results[ticker] = {
            "gen_at":               gen_at,
            "zero_gamma":           zero_gamma,
            "zero_gamma_delta_adj": zero_gamma_delta_adj,
            "gamma_magnet":         gamma_magnet,
            "total_gex":            float(np.sum(net_gex)),
            "total_gex_delta_adj":  float(np.sum(net_dex)),
            "call_wall":            call_wall,
            "put_wall":             put_wall,
        }

    return results


# ---------------------------------------------------------------------------
# Waterfall merge
# ---------------------------------------------------------------------------

def merge_records(dl: dict, ul: dict, gp: dict) -> dict:
    """UL overrides DL; GP only fills remaining None gaps."""
    merged = {k: v for k, v in dl.items() if v is not None}
    for k, v in ul.items():
        if v is not None:
            merged[k] = v
    for k, v in gp.items():
        if merged.get(k) is None and v is not None:
            merged[k] = v
    return merged


# ---------------------------------------------------------------------------
# Main backfill
# ---------------------------------------------------------------------------

def run_backfill(db_path: str = "web/prisma/dev.db", data_dir: str = "data/options"):
    print(f"Connecting to database at: {db_path}")
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()

    print("Clearing tables for fresh backfill...")
    cur.execute("DELETE FROM GexSnapshot")
    cur.execute("DELETE FROM MacroSnapshot")
    cur.execute("DELETE FROM RthExpectedMove")
    conn.commit()

    all_files = (
        glob.glob(os.path.join(data_dir, "unified_levels_2026*.json")) +
        glob.glob(os.path.join(data_dir, "daily_levels_2026*.json")) +
        glob.glob(os.path.join(data_dir, "gex_profiles_2026*.json"))
    )
    all_dates = set()
    for f in all_files:
        parts = os.path.basename(f).replace(".json", "").split("_")
        if len(parts) >= 3 and len(parts[2]) == 8:
            all_dates.add(parts[2])

    all_dates = sorted(all_dates)
    print(f"Found {len(all_dates)} unique trading days across all sources.")

    gex_count = macro_count = em_count = skipped = 0

    for date_str in all_dates:
        trading_date    = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=TZ_NY)
        trading_date_ms = dt_to_ms(trading_date)

        dl_data = parse_daily_levels(date_str, data_dir)
        ul_data = parse_unified_levels(date_str, data_dir)
        gp_data = derive_from_gex_profiles(date_str, data_dir)

        all_tickers = (set(dl_data) | set(ul_data) | set(gp_data)) & {"SPY", "SPX", "QQQ"}
        if not all_tickers:
            print(f"  [{date_str}] No data for target tickers — skipping.")
            skipped += 1
            continue

        for ticker in sorted(all_tickers):
            rec = merge_records(
                dl_data.get(ticker, {}),
                ul_data.get(ticker, {}),
                gp_data.get(ticker, {}),
            )

            gen_at = rec.get("gen_at") or trading_date.replace(hour=9, minute=30)
            timestamp_ms = dt_to_ms(gen_at)
            spot = rec.get("spot")
            if spot is None:
                continue  # can't insert without price anchor

            # --- GexSnapshot ---
            cur.execute(
                "SELECT COUNT(*) FROM GexSnapshot WHERE ticker = ? AND timestamp = ?",
                (ticker, timestamp_ms)
            )
            if cur.fetchone()[0] == 0:
                cur.execute("""
                    INSERT INTO GexSnapshot (
                        ticker, timestamp, tradingDate, totalGex, totalGexDeltaAdj,
                        callGammaTotal, putGammaTotal, gexRegime, regimeLabel, spotPrice,
                        gammaMagnet, pinStrike, callVolumeCentroid, putVolumeCentroid,
                        netSpeedExposure, netVannaExposure, put25dIv, call25dIv,
                        volatilitySkewPremium, createdAt, futuresBasisRatio,
                        futuresBasisSpread, futuresSymbol, futuresTranslationMode
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    ticker, timestamp_ms, trading_date_ms,
                    rec.get("total_gex", 0.0),
                    rec.get("total_gex_delta_adj", 0.0),
                    rec.get("call_gamma_total", 0.0),
                    rec.get("put_gamma_total", 0.0),
                    rec.get("gex_regime", "POSITIVE"),
                    rec.get("regime_label", "NORMAL"),
                    spot,
                    rec.get("gamma_magnet"),
                    rec.get("pin_strike"),
                    None, None,
                    rec.get("net_speed_exposure", 0.0),
                    rec.get("net_vanna_exposure", 0.0),
                    rec.get("put_25d_iv"),
                    rec.get("call_25d_iv"),
                    rec.get("volatility_skew_premium"),
                    timestamp_ms,
                    None, None, None, None,
                ))
                gex_count += 1

            # --- MacroSnapshot ---
            cur.execute(
                "SELECT COUNT(*) FROM MacroSnapshot WHERE ticker = ? AND tradingDate = ?",
                (ticker, trading_date_ms)
            )
            if cur.fetchone()[0] == 0:
                cur.execute("""
                    INSERT INTO MacroSnapshot (
                        id, ticker, timestamp, tradingDate, spotPrice,
                        macroCallWall, macroPutWall, zeroGamma, put25dIv,
                        call25dIv, volatilitySkewPremium, anomalies, dominantNodes,
                        zero_gamma_delta_adj
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    generate_cuid(), ticker, timestamp_ms, trading_date_ms,
                    spot,
                    rec.get("call_wall"),
                    rec.get("put_wall"),
                    rec.get("zero_gamma"),
                    rec.get("put_25d_iv"),
                    rec.get("call_25d_iv"),
                    rec.get("volatility_skew_premium"),
                    "{}", "[]",
                    rec.get("zero_gamma_delta_adj"),
                ))
                macro_count += 1

            # --- RthExpectedMove ---
            em_straddle = rec.get("em_straddle")
            if em_straddle:
                cur.execute(
                    "SELECT COUNT(*) FROM RthExpectedMove WHERE ticker = ? AND date = ?",
                    (ticker, trading_date_ms)
                )
                if cur.fetchone()[0] == 0:
                    cur.execute("""
                        INSERT INTO RthExpectedMove (
                            ticker, date, openPrice, vixValue, straddlePrice,
                            emStraddle, ivAtOpen, emIv, emVix, createdAt, updatedAt
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        ticker, trading_date_ms,
                        rec.get("open_price") or spot,
                        15.0,
                        em_straddle,
                        em_straddle / 2.0,
                        rec.get("volatility_skew_premium", 0.0),
                        rec.get("volatility_skew_premium", 0.0),
                        15.0,
                        timestamp_ms, timestamp_ms,
                    ))
                    em_count += 1

    conn.commit()
    conn.close()

    print()
    print("=" * 52)
    print("Backfill Complete!")
    print(f"  Unique dates processed: {len(all_dates) - skipped}/{len(all_dates)}")
    print(f"  Inserted GexSnapshot records:     {gex_count}")
    print(f"  Inserted MacroSnapshot records:   {macro_count}")
    print(f"  Inserted RthExpectedMove records: {em_count}")
    print(f"  Skipped (no target ticker data):  {skipped}")


if __name__ == "__main__":
    run_backfill()
