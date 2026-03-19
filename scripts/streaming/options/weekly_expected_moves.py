import logging
import math
from datetime import datetime, time, timedelta, date
from zoneinfo import ZoneInfo

from scripts.streaming.options.config import (
    SECRETS_PATH, 
    TOKEN_PATH,
    PRIMARY_INDEX_TICKERS,
    INDEX_TO_FUTURES
)
from scripts.streaming.options.options_fetcher import (
    create_client, 
    _schwab_symbol, 
    _today_ny, 
    fetch_futures_quote
)

# Set up basic logging to console
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

def calculate_exact_atm_em(cash_spot: float, exp_date: date, strikes_dict: dict) -> tuple[float, float]:
    """Finds the exact ATM contract for the given expiration date, extracts its IV, and calculates Expected Move."""
    try:
        available_strikes = [float(k) for k in strikes_dict.keys()]
        atm_strike = min(available_strikes, key=lambda x: abs(x - cash_spot))
        
        atm_contract_data = strikes_dict[str(atm_strike)][0]
        atm_vol_pct = float(atm_contract_data.get("volatility", 0.0))
        
        if atm_vol_pct <= 0:
            return 0.0, 0.0
            
        iv_decimal = atm_vol_pct / 100.0 if atm_vol_pct > 1.0 else atm_vol_pct
        
    except (ValueError, KeyError, IndexError):
        return 0.0, 0.0

    tz = ZoneInfo("America/New_York")
    now = datetime.now(tz)
    exp_dt = datetime.combine(exp_date, time(16, 0), tzinfo=tz)
    
    minutes_remaining = (exp_dt - now).total_seconds() / 60.0
    
    if minutes_remaining <= 0:
        return 0.0, atm_vol_pct
        
    fractional_dte = minutes_remaining / (24.0 * 60.0)
    years_to_expiry = fractional_dte / 365.0
    
    em_value = cash_spot * iv_decimal * math.sqrt(years_to_expiry)
    return em_value, atm_vol_pct

def fetch_weekly_expected_moves():
    client = create_client(SECRETS_PATH, TOKEN_PATH)
    logical_today = _today_ny()
    
    days_to_friday = (4 - logical_today.weekday()) % 7
    target_friday = logical_today + timedelta(days=days_to_friday)
    
    log.info(f"==================================================")
    log.info(f"WEEKLY EXPECTED MOVES")
    log.info(f"Logical Today:   {logical_today.strftime('%A, %b %d')}")
    log.info(f"Target Friday:   {target_friday.strftime('%A, %b %d')}")
    log.info(f"==================================================\n")

    for cash_sym in PRIMARY_INDEX_TICKERS:
        # Safety check: Ignore futures tickers if accidentally added to PRIMARY_INDEX_TICKERS
        if cash_sym.startswith("/"):
            log.warning(f"Skipping '{cash_sym}' -> Options chains must be fetched using the cash/ETF ticker.")
            continue
            
        api_sym = _schwab_symbol(cash_sym)
        
        response = client.get_option_chain(
            api_sym,
            from_date=logical_today,
            to_date=target_friday,
            include_underlying_quote=True,
        )
        
        if response.status_code != 200:
            log.error(f"Failed to fetch {cash_sym}. HTTP {response.status_code}")
            continue
            
        payload = response.json()
        underlying = payload.get("underlying", {})
        cash_spot = underlying.get("mark") or underlying.get("last") or payload.get("underlyingPrice", 0.0)
        
        if cash_spot == 0.0:
            continue
            
        # Check if we need to translate this index to a futures contract
        fut_sym = INDEX_TO_FUTURES.get(cash_sym)
        do_futures = False
        ratio = 1.0
        use_scale = False
        fut_price = 0.0
        
        if fut_sym:
            fut = fetch_futures_quote(fut_sym)
            if fut is not None:
                fut_price = fut.price
                ratio = fut_price / cash_spot if cash_spot > 0 else 1.0
                use_scale = abs(ratio - 1.0) > 0.02
                do_futures = True
            
        call_map = payload.get("callExpDateMap", {})
        
        cash_results, cash_pine = [], []
        fut_results, fut_pine = [], []
        
        for exp_key, strikes_dict in call_map.items():
            date_str = exp_key.split(":")[0]
            exp_date = date.fromisoformat(date_str)
            
            if logical_today <= exp_date <= target_friday:
                cash_em, atm_vol_pct = calculate_exact_atm_em(cash_spot, exp_date, strikes_dict)
                
                if cash_em <= 0:
                    continue
                
                day_name = exp_date.strftime('%A')[:3]
                
                # Store Cash Data
                cash_results.append((exp_date, day_name, atm_vol_pct, cash_em))
                cash_pine.append(f"{cash_em:.2f}:{day_name}")
                
                # Store Futures Data if mapped
                if do_futures:
                    fut_em = cash_em * ratio if use_scale else cash_em
                    fut_results.append((exp_date, day_name, atm_vol_pct, fut_em))
                    fut_pine.append(f"{fut_em:.2f}:{day_name}")

        # --- Print Base Ticker (ETF/Cash) ---
        cash_results.sort(key=lambda x: x[0])
        log.info(f"[{cash_sym}] Base Expected Moves  |  Spot: ${cash_spot:,.2f}")
        for res in cash_results:
            exp_date, day_name, vol, em = res
            upper = cash_spot + em
            lower = cash_spot - em
            log.info(f"  ↳ {day_name} ({exp_date.strftime('%m/%d')}): ATM IV {vol:>5.2f}% | EM ±${em:<5.2f} | Range: {lower:,.2f} ↔ {upper:,.2f}")
            
        clean_cash_sym = cash_sym.replace("$", "")
        log.info(f"  Pine Script Copy: {clean_cash_sym}_EM=" + ", ".join(cash_pine))
        
        # --- Print Translated Futures Ticker (if applicable) ---
        if do_futures:
            fut_results.sort(key=lambda x: x[0])
            trans_mode = "Multiplicative" if use_scale else "Additive"
            log.info(f"\n[{fut_sym}] Translated Futures |  Spot: {fut_price:,.2f} ({trans_mode} scaling from {cash_sym})")
            for res in fut_results:
                exp_date, day_name, vol, em = res
                upper = fut_price + em
                lower = fut_price - em
                log.info(f"  ↳ {day_name} ({exp_date.strftime('%m/%d')}): ATM IV {vol:>5.2f}% | EM ±{em:<5.2f} | Range: {lower:,.2f} ↔ {upper:,.2f}")
                
            clean_fut_sym = fut_sym.replace("/", "")
            log.info(f"  Pine Script Copy: {clean_fut_sym}_EM=" + ", ".join(fut_pine))
            
        log.info("-" * 60 + "\n")

if __name__ == "__main__":
    fetch_weekly_expected_moves()