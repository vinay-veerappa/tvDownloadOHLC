import os
import sys
import json
import math
from datetime import date, datetime
from zoneinfo import ZoneInfo

# Add project root to sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

from scripts.streaming.options.options_fetcher import OptionChainData, OptionContract, fetch_option_chain_data
from scripts.streaming.options.gex_calculator import _expected_move

def get_dolt_30d_iv(ticker):
    try:
        from scripts.libs_py.strategy_engine.services.iv_service import IvService
        iv_svc = IvService(db=None, dolt_dir=os.path.join(ROOT_DIR, "data", "options", "options"))
        if iv_svc._dolt_available():
            row = iv_svc._query_dolt_vol_row(ticker)
            if row and row.get("iv_current"):
                val = float(row.get("iv_current"))
                if val > 1.0:
                    val = val / 100.0
                return val
    except Exception:
        pass
    return None

def get_contract_val(c, price_type="mid"):
    if not c:
        return 0.0
    bid = c.bid
    ask = c.ask
    mid = (bid + ask) / 2.0 if (bid > 0 and ask > 0) else 0.0
    if price_type == "mid":
        return mid
    else:
        return getattr(c, "mark", mid)

def interpolate_premium(contracts, target_strike, is_call, price_type="mid"):
    subset = [c for c in contracts if c.contract_type == ("CALL" if is_call else "PUT")]
    if not subset:
        return 0.0
    subset = sorted(subset, key=lambda c: c.strike)
    strikes = [c.strike for c in subset]
    
    # Exact match check
    for c in subset:
        if abs(c.strike - target_strike) < 1e-6:
            return get_contract_val(c, price_type)
            
    # Boundary check
    if target_strike <= strikes[0]:
        return get_contract_val(subset[0], price_type)
    if target_strike >= strikes[-1]:
        return get_contract_val(subset[-1], price_type)
        
    # Linear interpolation
    for i in range(len(strikes) - 1):
        s1, s2 = strikes[i], strikes[i+1]
        if s1 <= target_strike <= s2:
            c1, c2 = subset[i], subset[i+1]
            p1 = get_contract_val(c1, price_type)
            p2 = get_contract_val(c2, price_type)
            if s2 - s1 > 0:
                return p1 + (target_strike - s1) / (s2 - s1) * (p2 - p1)
            else:
                return p1
    return 0.0

def format_contract_row(strike, calls, puts):
    c = next((x for x in calls if x.strike == strike), None)
    p = next((x for x in puts if x.strike == strike), None)
    
    def extract_fields(contract):
        if not contract:
            return 0.0, 0.0, 0.0, 0.0, 0.0, 0, "NO_CONTRACT"
        bid = contract.bid
        ask = contract.ask
        mid = (bid + ask) / 2.0 if (bid > 0 and ask > 0) else 0.0
        mark = getattr(contract, "mark", mid)
        iv = contract.iv
        oi = contract.open_interest
        
        flags = []
        if bid <= 0:
            flags.append("NO_BID")
        if ask <= 0:
            flags.append("NO_ASK")
        if bid >= ask and bid > 0 and ask > 0:
            flags.append("CROSSED")
            
        return bid, ask, mid, mark, iv, oi, ",".join(flags)
        
    c_bid, c_ask, c_mid, c_mark, c_iv, c_oi, c_flags = extract_fields(c)
    p_bid, p_ask, p_mid, p_mark, p_iv, p_oi, p_flags = extract_fields(p)
    
    all_flags = []
    if c_flags:
        all_flags.append(f"C:{c_flags}")
    if p_flags:
        all_flags.append(f"P:{p_flags}")
    flag_str = "|".join(all_flags)
    
    return {
        "strike": strike,
        "call": {"bid": c_bid, "ask": c_ask, "mid": c_mid, "mark": c_mark, "iv": c_iv, "oi": c_oi},
        "put": {"bid": p_bid, "ask": p_ask, "mid": p_mid, "mark": p_mark, "iv": p_iv, "oi": p_oi},
        "flags": flag_str
    }

def run_calibration():
    tickers = ["SPX", "SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "TSLA"]
    
    now_et = datetime.now(ZoneInfo("America/New_York"))
    print(f"CALIBRATION SNAPSHOT TIMESTAMP (New York): {now_et.strftime('%Y-%m-%dT%H:%M:%S %Z')}")
    print("========================================================================================\n")
    
    json_output = {}
    
    for ticker in tickers:
        print(f"Fetching options chain live for {ticker}...")
        try:
            # Fetch options chain live targeting nearest DTEs (next 7 days)
            chain = fetch_option_chain_data(None, ticker, [0, 1, 2, 3, 4, 5, 6, 7])
        except Exception as e:
            print(f"Error fetching live chain for {ticker}: {e}")
            continue
            
        if not chain or not chain.contracts:
            print(f"No contracts found for {ticker}")
            continue
            
        spot = chain.spot_price
        
        # Determine unique expiries from contracts
        all_expiries = sorted(list(set(c.expiry for c in chain.contracts)))
        if not all_expiries:
            print(f"No expiries found in contracts for {ticker}")
            continue
            
        # Select target expiries (nearest 3 for indexes/ETFs, nearest 2 for stocks)
        if ticker in ["SPX", "SPY", "QQQ", "IWM"]:
            target_expiries = all_expiries[:3]
        else:
            target_expiries = all_expiries[:2]
            
        # Resolve Dolt 30-day IV
        ticker_clean = ticker.upper().replace("$", "").replace("/", "")
        dolt_iv_30d = get_dolt_30d_iv(ticker_clean)
        if dolt_iv_30d is None and ticker_clean == "SPX":
            dolt_iv_30d = get_dolt_30d_iv("SPY")
            
        json_output[ticker] = {}
        
        for exp_date in target_expiries:
            exp_str = exp_date.isoformat()
            dte = (exp_date - now_et.date()).days
            
            calls = [c for c in chain.calls if c.expiry == exp_date]
            puts = [p for p in chain.puts if p.expiry == exp_date]
            
            if not calls or not puts:
                print(f"Skipping {ticker} {exp_str}: no contracts found.")
                continue
                
            # Production ATM Strike Selection Logic
            strikes = sorted(list(set([c.strike for c in calls] + [p.strike for p in puts])))
            atm_strike = min(strikes, key=lambda s: abs(s - spot))
            dist = atm_strike - spot
            
            # Find ATM contract average IV
            atm_call = min(calls, key=lambda c: abs(c.strike - spot))
            atm_put = min(puts, key=lambda p: abs(p.strike - spot))
            atm_iv_front = (atm_call.iv + atm_put.iv) / 2.0 if (atm_call.iv > 0 and atm_put.iv > 0) else 0.0
            
            # Center strike ladder: ATM strike + 3 strikes above/below
            try:
                idx = strikes.index(atm_strike)
                start_idx = max(0, idx - 3)
                end_idx = min(len(strikes), idx + 4)
                ladder_strikes = strikes[start_idx:end_idx]
                if len(ladder_strikes) < 7:
                    # Pad if needed
                    pass
            except ValueError:
                ladder_strikes = sorted(strikes)[:7]
                
            # Build strike ladder rows
            ladder_rows = []
            for s in ladder_strikes:
                row_data = format_contract_row(s, calls, puts)
                ladder_rows.append(row_data)
                
            # Extract specific contracts for derived measures
            try:
                atm_idx = ladder_strikes.index(atm_strike)
            except ValueError:
                atm_idx = len(ladder_strikes) // 2
                
            # Helper to get row by relative offset from ATM
            def get_row_offset(offset):
                target_idx = atm_idx + offset
                if 0 <= target_idx < len(ladder_rows):
                    return ladder_rows[target_idx]
                if target_idx < 0:
                    return ladder_rows[0]
                return ladder_rows[-1]
                
            r_atm = get_row_offset(0)
            r_plus1 = get_row_offset(1)
            r_minus1 = get_row_offset(-1)
            r_plus2 = get_row_offset(2)
            r_minus2 = get_row_offset(-2)
            r_plus3 = get_row_offset(3)
            r_minus3 = get_row_offset(-3)
            
            atm_straddle_mid = r_atm["call"]["mid"] + r_atm["put"]["mid"]
            atm_straddle_mark = r_atm["call"]["mark"] + r_atm["put"]["mark"]
            
            otm1_strangle_mid = r_plus1["call"]["mid"] + r_minus1["put"]["mid"]
            otm1_strangle_mark = r_plus1["call"]["mark"] + r_minus1["put"]["mark"]
            
            otm2_strangle_mid = r_plus2["call"]["mid"] + r_minus2["put"]["mid"]
            otm2_strangle_mark = r_plus2["call"]["mark"] + r_minus2["put"]["mark"]
            
            otm3_strangle_mid = r_plus3["call"]["mid"] + r_minus3["put"]["mid"]
            otm3_strangle_mark = r_plus3["call"]["mark"] + r_minus3["put"]["mark"]
            
            # --- Percentage Distance-Normalized Strangles ---
            # Strangle at ±0.5%
            strangle_05pct_mid = (
                interpolate_premium(calls, spot * 1.005, is_call=True, price_type="mid") +
                interpolate_premium(puts, spot * 0.995, is_call=False, price_type="mid")
            )
            strangle_05pct_mark = (
                interpolate_premium(calls, spot * 1.005, is_call=True, price_type="mark") +
                interpolate_premium(puts, spot * 0.995, is_call=False, price_type="mark")
            )
            
            # Strangle at ±1.0%
            strangle_10pct_mid = (
                interpolate_premium(calls, spot * 1.010, is_call=True, price_type="mid") +
                interpolate_premium(puts, spot * 0.990, is_call=False, price_type="mid")
            )
            strangle_10pct_mark = (
                interpolate_premium(calls, spot * 1.010, is_call=True, price_type="mark") +
                interpolate_premium(puts, spot * 0.990, is_call=False, price_type="mark")
            )
            
            # Strangle at ±1.5%
            strangle_15pct_mid = (
                interpolate_premium(calls, spot * 1.015, is_call=True, price_type="mid") +
                interpolate_premium(puts, spot * 0.985, is_call=False, price_type="mid")
            )
            strangle_15pct_mark = (
                interpolate_premium(calls, spot * 1.015, is_call=True, price_type="mark") +
                interpolate_premium(puts, spot * 0.985, is_call=False, price_type="mark")
            )
            
            # Real _expected_move logic
            is_futures = any(ticker.startswith(f) for f in ["/ES", "/NQ", "/CL", "/GC", "ES", "NQ"])
            em_val, _ = _expected_move(calls, puts, spot, dte=dte, is_futures=is_futures)
            
            # Print Text Block
            print(f"== Ticker: {ticker:5} | Expiry: {exp_str} | DTE: {dte} | Spot: {spot:.2f} ==")
            print(f"ATM Strike: {atm_strike:.2f} (Dist: {dist:+.2f})")
            print(f"Front ATM IV ({dte}DTE): {atm_iv_front*100:.2f}% | Dolt IV (30D): {f'{dolt_iv_30d*100:.2f}%' if dolt_iv_30d else 'N/A'}")
            print(f"Chain Timestamp: {chain.timestamp}")
            print("-" * 115)
            # Table Header
            print(f"{'Strike':<9} | {'C_Bid':<6} {'C_Ask':<6} {'C_Mid':<6} {'C_Mark':<6} {'C_IV':<6} {'C_OI':<6} | {'P_Bid':<6} {'P_Ask':<6} {'P_Mid':<6} {'P_Mark':<6} {'P_IV':<6} {'P_OI':<6} | {'Flags':<12}")
            print("-" * 115)
            for row in ladder_rows:
                s = row["strike"]
                c = row["call"]
                p = row["put"]
                f_str = row["flags"]
                print(f"{s:<9.2f} | {c['bid']:<6.2f} {c['ask']:<6.2f} {c['mid']:<6.2f} {c['mark']:<6.2f} {c['iv']:<6.4f} {c['oi']:<6d} | {p['bid']:<6.2f} {p['ask']:<6.2f} {p['mid']:<6.2f} {p['mark']:<6.2f} {p['iv']:<6.4f} {p['oi']:<6d} | {f_str:<12}")
            print("-" * 115)
            
            # Derived measures output
            def safe_ratio(num, den):
                return num / den if den > 0 else 0.0
                
            ratios_mid = {
                "straddle": 1.0,
                "strangle_1st": safe_ratio(otm1_strangle_mid, atm_straddle_mid),
                "strangle_2nd": safe_ratio(otm2_strangle_mid, atm_straddle_mid),
                "strangle_3rd": safe_ratio(otm3_strangle_mid, atm_straddle_mid),
                "strangle_05pct": safe_ratio(strangle_05pct_mid, atm_straddle_mid),
                "strangle_10pct": safe_ratio(strangle_10pct_mid, atm_straddle_mid),
                "strangle_15pct": safe_ratio(strangle_15pct_mid, atm_straddle_mid),
                "model_em": safe_ratio(em_val, atm_straddle_mid)
            }
            ratios_mark = {
                "straddle": 1.0,
                "strangle_1st": safe_ratio(otm1_strangle_mark, atm_straddle_mark),
                "strangle_2nd": safe_ratio(otm2_strangle_mark, atm_straddle_mark),
                "strangle_3rd": safe_ratio(otm3_strangle_mark, atm_straddle_mark),
                "strangle_05pct": safe_ratio(strangle_05pct_mark, atm_straddle_mark),
                "strangle_10pct": safe_ratio(strangle_10pct_mark, atm_straddle_mark),
                "strangle_15pct": safe_ratio(strangle_15pct_mark, atm_straddle_mark),
                "model_em": safe_ratio(em_val, atm_straddle_mark)
            }
            
            print(f"DERIVED MEASURES (Mid-priced vs Mark-priced):")
            print(f"  ATM Straddle (mid)       : {atm_straddle_mid:7.2f}  (Ratio: {ratios_mid['straddle']:.4f})")
            print(f"  ATM Straddle (mark)      : {atm_straddle_mark:7.2f}  (Ratio: {ratios_mark['straddle']:.4f})")
            print(f"  1st OTM Strangle (mid)   : {otm1_strangle_mid:7.2f}  (Ratio: {ratios_mid['strangle_1st']:.4f})")
            print(f"  1st OTM Strangle (mark)  : {otm1_strangle_mark:7.2f}  (Ratio: {ratios_mark['strangle_1st']:.4f})")
            print(f"  2nd OTM Strangle (mid)   : {otm2_strangle_mid:7.2f}  (Ratio: {ratios_mid['strangle_2nd']:.4f})")
            print(f"  2nd OTM Strangle (mark)  : {otm2_strangle_mark:7.2f}  (Ratio: {ratios_mark['strangle_2nd']:.4f})")
            print(f"  3rd OTM Strangle (mid)   : {otm3_strangle_mid:7.2f}  (Ratio: {ratios_mid['strangle_3rd']:.4f})")
            print(f"  3rd OTM Strangle (mark)  : {otm3_strangle_mark:7.2f}  (Ratio: {ratios_mark['strangle_3rd']:.4f})")
            
            print(f"  Strangle @ ±0.5% (mid)   : {strangle_05pct_mid:7.2f}  (Ratio: {ratios_mid['strangle_05pct']:.4f}, Target Strikes: {spot*1.005:.1f} / {spot*0.995:.1f})")
            print(f"  Strangle @ ±0.5% (mark)  : {strangle_05pct_mark:7.2f}  (Ratio: {ratios_mark['strangle_05pct']:.4f})")
            print(f"  Strangle @ ±1.0% (mid)   : {strangle_10pct_mid:7.2f}  (Ratio: {ratios_mid['strangle_10pct']:.4f}, Target Strikes: {spot*1.010:.1f} / {spot*0.990:.1f})")
            print(f"  Strangle @ ±1.0% (mark)  : {strangle_10pct_mark:7.2f}  (Ratio: {ratios_mark['strangle_10pct']:.4f})")
            print(f"  Strangle @ ±1.5% (mid)   : {strangle_15pct_mid:7.2f}  (Ratio: {ratios_mid['strangle_15pct']:.4f}, Target Strikes: {spot*1.015:.1f} / {spot*0.985:.1f})")
            print(f"  Strangle @ ±1.5% (mark)  : {strangle_15pct_mark:7.2f}  (Ratio: {ratios_mark['strangle_15pct']:.4f})")
            
            print(f"  Our model EM (reference) : {em_val:7.2f}  (Ratio: {ratios_mid['model_em']:.4f} mid / {ratios_mark['model_em']:.4f} mark)")
            print("-" * 115)
            print("\n")
            
            # Store in JSON format
            json_output[ticker][exp_str] = {
                "spot": spot,
                "dte": dte,
                "atm_strike": atm_strike,
                "distance": dist,
                "headline_iv_30d": dolt_iv_30d,
                "atm_iv_front": atm_iv_front,
                "atm_straddle_mid": atm_straddle_mid,
                "atm_straddle_mark": atm_straddle_mark,
                "otm1_strangle_mid": otm1_strangle_mid,
                "otm1_strangle_mark": otm1_strangle_mark,
                "otm2_strangle_mid": otm2_strangle_mid,
                "otm2_strangle_mark": otm2_strangle_mark,
                "otm3_strangle_mid": otm3_strangle_mid,
                "otm3_strangle_mark": otm3_strangle_mark,
                "strangle_05pct_mid": strangle_05pct_mid,
                "strangle_05pct_mark": strangle_05pct_mark,
                "strangle_10pct_mid": strangle_10pct_mid,
                "strangle_10pct_mark": strangle_10pct_mark,
                "strangle_15pct_mid": strangle_15pct_mid,
                "strangle_15pct_mark": strangle_15pct_mark,
                "our_model_em": em_val,
                "ratios": {
                    "mid": ratios_mid,
                    "mark": ratios_mark
                },
                "tos_displayed_em": None,  # For manual fill
                "timestamp": chain.timestamp.isoformat(),
                "strikes_ladder": ladder_rows
            }
            
    # Write JSON output
    out_path = os.path.join(ROOT_DIR, "scratch", "tos_em_calibration.json")
    with open(out_path, "w") as f:
        json.dump(json_output, f, indent=2)
    print(f"Successfully wrote calibration data to {out_path}")

if __name__ == "__main__":
    run_calibration()
