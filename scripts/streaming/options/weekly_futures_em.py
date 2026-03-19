import logging
import math
from datetime import datetime, time, timedelta, date
from zoneinfo import ZoneInfo

from scripts.streaming.options.config import SECRETS_PATH, TOKEN_PATH
from scripts.streaming.options.options_fetcher import (
    create_client, 
    _today_ny, 
    fetch_futures_quote
)

# Set up basic logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# We are testing direct futures chains now
TARGET_FUTURES = ["ESM26", "NQM26"]

def calculate_exact_atm_em(spot_price: float, exp_date: date, strikes_dict: dict) -> tuple[float, float]:
    """Finds the exact ATM contract, extracts its IV, and calculates Expected Move."""
    try:
        available_strikes = [float(k) for k in strikes_dict.keys()]
        atm_strike = min(available_strikes, key=lambda x: abs(x - spot_price))
        
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
    
    em_value = spot_price * iv_decimal * math.sqrt(years_to_expiry)
    return em_value, atm_vol_pct

def test_direct_futures_chain():
    client = create_client(SECRETS_PATH, TOKEN_PATH)
    logical_today = _today_ny()
    
    days_to_friday = (4 - logical_today.weekday()) % 7
    target_friday = logical_today + timedelta(days=days_to_friday)
    
    log.info(f"==================================================")
    log.info(f"DIRECT FUTURES OPTIONS CHAIN TEST")
    log.info(f"Logical Today:   {logical_today.strftime('%A, %b %d')}")
    log.info(f"Target Friday:   {target_friday.strftime('%A, %b %d')}")
    log.info(f"==================================================\n")

    for fut_sym in TARGET_FUTURES:
        log.info(f"Attempting to fetch raw options chain for {fut_sym}...")
        
        # We still use our reliable futures quoter to get the exact spot price
        # because the options chain payload sometimes omits it for futures.
        fut_quote = fetch_futures_quote(fut_sym)
        if not fut_quote:
            log.error(f"  [X] Failed to get live spot price for {fut_sym}. Skipping.")
            continue
            
        spot_price = fut_quote.price
        
        # The Moment of Truth: Asking Schwab for the futures chain
        response = client.get_option_chain(
            fut_sym,
            from_date=logical_today,
            to_date=target_friday,
        )
        
        if response.status_code != 200:
            log.error(f"  [X] API rejected the request. HTTP {response.status_code}")
            log.error(f"  Response: {response.text}\n")
            continue
            
        payload = response.json()
        status = payload.get("status")
        
        if status != "SUCCESS":
            log.error(f"  [X] API returned status: {status}\n")
            continue
            
        call_map = payload.get("callExpDateMap", {})
        if not call_map:
            log.error(f"  [X] API returned SUCCESS, but the options chain is empty. Schwab may require a specific contract month.\n")
            continue
            
        # If we reach here, Schwab gave us the holy grail: a native futures options chain!
        log.info(f"  [✓] SUCCESS! Schwab returned {len(call_map)} expirations.")
        
        results = []
        pine_script_outputs = []
        
        for exp_key, strikes_dict in call_map.items():
            date_str = exp_key.split(":")[0]
            exp_date = date.fromisoformat(date_str)
            
            if logical_today <= exp_date <= target_friday:
                em_value, atm_vol_pct = calculate_exact_atm_em(spot_price, exp_date, strikes_dict)
                
                if em_value <= 0:
                    continue
                
                day_name = exp_date.strftime('%A')[:3]
                results.append((exp_date, day_name, atm_vol_pct, em_value))
                pine_script_outputs.append(f"{em_value:.2f}:{day_name}")

        results.sort(key=lambda x: x[0])
        
        # Print the clean results
        log.info(f"\n[{fut_sym}] NATIVE OPTIONS CHAIN | Spot: {spot_price:,.2f}")
        for res in results:
            exp_date, day_name, vol, em = res
            upper = spot_price + em
            lower = spot_price - em
            log.info(f"  ↳ {day_name} ({exp_date.strftime('%m/%d')}): ATM IV {vol:>5.2f}% | EM ±{em:<5.2f} | Range: {lower:,.2f} ↔ {upper:,.2f}")
            
        clean_fut_sym = fut_sym.replace("/", "")
        log.info(f"  Pine Script Copy: {clean_fut_sym}_EM=" + ", ".join(pine_script_outputs) + "\n")

if __name__ == "__main__":
    test_direct_futures_chain()