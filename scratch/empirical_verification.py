import sys
import os
import math
import json
import datetime as dt_module
from datetime import date, datetime
from zoneinfo import ZoneInfo

# Add project root to sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

# Monkeypatch datetime in gex_calculator to anchor calculations to 2026-05-09
class MockDatetime(dt_module.datetime):
    @classmethod
    def now(cls, tz=None):
        return dt_module.datetime(2026, 5, 9, 10, 0, 0, tzinfo=tz)

import scripts.streaming.options.gex_calculator as gex_calc
gex_calc.datetime = MockDatetime

from scripts.streaming.options.options_fetcher import OptionChainData, OptionContract, FuturesQuote
from scripts.streaming.options.macro_pipeline import _deserialize_chain
from scripts.streaming.options.gex_calculator import (
    calculate_dealer_levels, 
    _expected_move, 
    _atm_straddle_cost, 
    _atm_contract,
    _calculate_all_ems
)
from scripts.streaming.options.futures_translator import translate_to_futures
from scripts.streaming.options.level_scorer import score_levels, InflectionPoint
from scripts.streaming.options.config import INTRADAY_VIEW, MACRO_VIEW, get_ticker_profile

def run_verification():
    # Expiries we have ToS targets for on 2026-05-09:
    # May 11 (DTE=2)
    tos_targets = {
        "SPX": {"expiry": "2026-05-11", "dte": 2, "target": 45.679},
        "SPY": {"expiry": "2026-05-11", "dte": 2, "target": 4.736},
        "AAPL": {"expiry": "2026-05-11", "dte": 2, "target": 4.160}
    }

    print("======================================================================")
    # ==========================================
    # Verification Task 1: EM / DTE parameter & ToS Reconciliation
    # ==========================================
    print("--- Task 1: EM / DTE parameter ---")
    
    reconciliation_table = []
    
    for ticker, info in tos_targets.items():
        cache_path = os.path.join(ROOT_DIR, "data", "options", f"macro_cache_{ticker}_2026-05-09.json")
        if not os.path.exists(cache_path):
            print(f"Cache file not found: {cache_path}")
            continue
            
        with open(cache_path, "r") as f:
            cache_data = json.load(f)
            
        chain = _deserialize_chain(cache_data)
        spot = chain.spot_price
        vol = chain.chain_volatility
        
        # 1. Our old buggy footer EM (we bypass warning logic by passing float, but it logs warning)
        em_val_footer_old, _ = _expected_move(chain.calls, chain.puts, spot, vol)
        
        # 2. Our header EM for the target expiry (May 11)
        target_expiry = date.fromisoformat(info["expiry"])
        calls_exp = [c for c in chain.calls if c.expiry == target_expiry]
        puts_exp = [p for p in chain.puts if p.expiry == target_expiry]
        
        em_val_header, straddle_header = _expected_move(calls_exp, puts_exp, spot, dte=info["dte"])

        # 3. Our NEW pipeline footer EM
        new_metrics = gex_calc.calculate_price_metrics(chain)
        em_val_footer_new = new_metrics["em_value"]
        
        reconciliation_table.append({
            "ticker": ticker,
            "tos_em": info["target"],
            "straddle": straddle_header,
            "footer_em_old": em_val_footer_old,
            "footer_em_new": em_val_footer_new,
            "header_em": em_val_header,
            "spot": spot,
            "vol": vol
        })
        
        if ticker == "SPX":
            print(f"SPX chain.chain_volatility = {vol:.6f}")
            print(f"SPX OLD Footer Path call: _expected_move(chain.calls, chain.puts, spot, chain.chain_volatility)")
            t_eff_yr_footer = (0.637 * vol + 0.24) / 365.0
            print(f"  Receiving function binds 'dte' parameter to: {vol:.6f}")
            print(f"  t_eff_yr computed: {t_eff_yr_footer:.8f}")
            print(f"  Final returned em_value: {em_val_footer_old:.4f}")
            print(f"SPX NEW Footer Path call (via calculate_price_metrics):")
            print(f"  Final returned em_value: {em_val_footer_new:.4f}")
            print(f"SPX Header Path call: _expected_move(calls, puts, spot, dte={info['dte']})")
            t_eff_yr_header = (0.637 * info["dte"] + 0.24) / 365.0
            print(f"  Receiving function binds 'dte' parameter to: {info['dte']}")
            print(f"  t_eff_yr computed: {t_eff_yr_header:.8f}")
            print(f"  Final returned em_value: {em_val_header:.4f}")

    print("\nToS Reconciliation Table (May 11 Expiry, DTE=2):")
    print("| Ticker | ToS EM | our straddle | our old footer EM | our new footer EM | our header EM |")
    print("|--------|--------|--------------|-------------------|-------------------|---------------|")
    for r in reconciliation_table:
        print(f"| {r['ticker']:6} | {r['tos_em']:6.3f} | {r['straddle']:12.3f} | {r['footer_em_old']:17.3f} | {r['footer_em_new']:17.3f} | {r['header_em']:13.3f} |")

    # ==========================================
    # Verification Task 2: Zero Gamma translation
    # ==========================================
    print("\n--- Task 2: Zero Gamma translation ---")
    # Load SPX chain to test zero gamma
    cache_path = os.path.join(ROOT_DIR, "data", "options", "macro_cache_SPX_2026-05-09.json")
    with open(cache_path, "r") as f:
        chain = _deserialize_chain(json.load(f))
    spot = chain.spot_price
    
    print(f"SPX contracts in chain: {len(chain.contracts)} | calls: {len(chain.calls)} | puts: {len(chain.puts)}")
    gamma_sum = sum(abs(c.gamma) for c in chain.contracts)
    print(f"Sum of absolute Gamma in chain: {gamma_sum:.8f}")
    
    profile = get_ticker_profile("SPX")
    # Call calculate_dealer_levels with min_oi_floor=0 to bypass open interest filtering
    levels = calculate_dealer_levels(chain, "SPX", min_oi_floor=0)
    
    mock_fut = FuturesQuote(symbol="/ES", price=spot + 5.5, open_price=chain.spot_open + 5.5)
    translated = translate_to_futures(levels, mock_fut)
    
    scored_macro = score_levels(levels, chain, "SPX", profile, MACRO_VIEW)
    scored_intra = score_levels(levels, chain, "SPX", profile, INTRADAY_VIEW)

    from scripts.streaming.options.futures_translator import translate_scored_levels
    use_scale = (translated.translation_mode == "multiplicative")
    scored_macro_trans = translate_scored_levels(scored_macro, translated.basis_spread, translated.basis_ratio, use_scale)
    scored_intra_trans = translate_scored_levels(scored_intra, translated.basis_spread, translated.basis_ratio, use_scale)
    
    inflection_zg_macro = None
    for l in scored_macro.tagged_levels:
        if isinstance(l, InflectionPoint) and l.label == "Zero Gamma Level":
            inflection_zg_macro = l
            break
            
    inflection_zg_intra = None
    for l in scored_intra.tagged_levels:
        if isinstance(l, InflectionPoint) and l.label == "Zero Gamma Level":
            inflection_zg_intra = l
            break

    inflection_zg_intra_trans = None
    for l in scored_intra_trans.tagged_levels:
        if isinstance(l, InflectionPoint) and l.label == "Zero Gamma Level":
            inflection_zg_intra_trans = l
            break
            
    print(f"Raw Cash levels.zero_gamma: {levels.zero_gamma}")
    print(f"TranslatedLevels.zero_gamma: {translated.zero_gamma}")
    print(f"InflectionPoint strike in MACRO ScoredLevels (Cash): {inflection_zg_macro.strike if inflection_zg_macro else 'NOT FOUND'}")
    print(f"InflectionPoint strike in INTRADAY ScoredLevels (Cash): {inflection_zg_intra.strike if inflection_zg_intra else 'NOT FOUND'}")
    print(f"InflectionPoint strike in Translated INTRADAY ScoredLevels (Futures): {inflection_zg_intra_trans.strike if inflection_zg_intra_trans else 'NOT FOUND'}")
    
    # Basis direction check
    basis_spread = mock_fut.price - spot
    print(f"Basis Spread (Futures - Cash): {basis_spread:.2f}")
    print(f"Futures Price: {mock_fut.price:.2f}")
    print(f"Cash Spot (levels.spot): {levels.spot:.2f}")
    print(f"Is Cash Spot + Basis Spread equal to Futures Price? {spot + basis_spread == mock_fut.price} (Value: {spot + basis_spread:.2f})")

    # ==========================================
    # Verification Task 3: Straddle vs EM
    # ==========================================
    print("\n--- Task 3: Straddle vs EM ---")
    atm_call_chain = _atm_contract(chain.calls, spot)
    atm_put_chain = _atm_contract(chain.puts, spot)
    print(f"Whole Chain ATM Call contract selected:")
    print(f"  Symbol: {atm_call_chain.symbol} | Strike: {atm_call_chain.strike} | Expiry: {atm_call_chain.expiry} | DTE: {atm_call_chain.dte} | Mark: {atm_call_chain.mark:.2f} | IV: {atm_call_chain.iv:.4%}")
    print(f"Whole Chain ATM Put contract selected:")
    print(f"  Symbol: {atm_put_chain.symbol} | Strike: {atm_put_chain.strike} | Expiry: {atm_put_chain.expiry} | DTE: {atm_put_chain.dte} | Mark: {atm_put_chain.mark:.2f} | IV: {atm_put_chain.iv:.4%}")
    print(f"Whole Chain Straddle Cost: {atm_call_chain.mark + atm_put_chain.mark:.2f}")
    
    target_expiry = date(2026, 5, 11)
    calls_exp = [c for c in chain.calls if c.expiry == target_expiry]
    puts_exp = [p for p in chain.puts if p.expiry == target_expiry]
    atm_call_exp = _atm_contract(calls_exp, spot)
    atm_put_exp = _atm_contract(puts_exp, spot)
    print(f"May 11 Expiry ATM Call contract selected:")
    print(f"  Symbol: {atm_call_exp.symbol} | Strike: {atm_call_exp.strike} | Expiry: {atm_call_exp.expiry} | DTE: {atm_call_exp.dte} | Mark: {atm_call_exp.mark:.2f} | IV: {atm_call_exp.iv:.4%}")
    print(f"May 11 Expiry ATM Put contract selected:")
    print(f"  Symbol: {atm_put_exp.symbol} | Strike: {atm_put_exp.strike} | Expiry: {atm_put_exp.expiry} | DTE: {atm_put_exp.dte} | Mark: {atm_put_exp.mark:.2f} | IV: {atm_put_exp.iv:.4%}")
    print(f"May 11 Expiry Straddle Cost: {atm_call_exp.mark + atm_put_exp.mark:.2f}")

    # ==========================================
    # Verification Task 4: IV 9.4% vs 18%
    # ==========================================
    print("\n--- Task 4: IV 9.4% vs 18% ---")
    print(f"ATM Contract IV (selected from front contract May 11): {atm_call_exp.iv:.4%} (DTE: {atm_call_exp.dte})")
    
    try:
        from scripts.libs_py.strategy_engine.services.iv_service import IvService
        iv_svc = IvService(db=None, dolt_dir=os.path.join(ROOT_DIR, "data", "options", "options"))
        if iv_svc._dolt_available():
            row = iv_svc._query_dolt_vol_row("SPY")
            print(f"Dolt latest volatility_history row: {row}")
            if row.get("iv_current"):
                iv_decimal = float(row.get("iv_current")) / 100.0 if float(row.get("iv_current")) > 1.0 else float(row.get("iv_current"))
                print(f"  iv_current from Dolt: {iv_decimal:.4%} (Tenor/Source: 30-day index IV history from Dolt database)")
        else:
            print("Dolt GEX database not available at data/options/options")
    except Exception as e:
        print(f"Error querying Dolt: {e}")

    # ==========================================
    # Verification Task 5: Single-source-of-truth audit
    # ==========================================
    print("\n--- Task 5: Single-source-of-truth audit ---")
    print(f"Audit table for the SPX run on 2026-05-09:")
    print("| Metric | Source Module | Value | Timestamp |")
    print("|--------|---------------|-------|-----------|")
    print(f"| Spot | OptionChainData.spot_price | {spot:.2f} | {chain.timestamp} |")
    print(f"| Chain Volatility | OptionChainData.chain_volatility | {vol:.4%} | {chain.timestamp} |")
    print(f"| ATM Call IV | Selected ATM contract (May 11) | {atm_call_exp.iv:.4%} | {chain.timestamp} |")
    print(f"| ATM Put IV | Selected ATM contract (May 11) | {atm_put_exp.iv:.4%} | {chain.timestamp} |")

if __name__ == "__main__":
    run_verification()

