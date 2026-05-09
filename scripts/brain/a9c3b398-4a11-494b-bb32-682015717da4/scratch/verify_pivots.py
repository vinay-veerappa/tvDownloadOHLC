
import sys
import os
from dataclasses import dataclass, field
from typing import List, Optional, Any

# Mock the HasLevels protocol
@dataclass
class MockLevels:
    ticker: str = "SPX"
    spot: float = 5150.0
    em_upper: float = 5200.0
    em_lower: float = 5100.0
    em_value: float = 50.0
    call_wall: float = 5250.0
    put_wall: float = 5050.0
    local_call_node: float = 5180.0
    local_put_node: float = 5120.0
    call_wall_0dte: float = 5190.0
    put_wall_0dte: float = 5110.0
    dex_call_node: float = 5175.0
    dex_put_node: float = 5125.0
    gamma_flip_upper: float = 5160.0
    gamma_flip_lower: float = 5140.0
    gamma_cliff_up: float = 5210.0
    gamma_cliff_down: float = 5090.0
    zero_gamma: float = 5145.0
    max_pain: float = 5130.0
    hedge_wall: float = 5000.0
    total_gex: float = 1000000000.0
    gex_regime: str = "POSITIVE"
    secondary_call_wall: float = 5260.0
    secondary_put_wall: float = 5040.0
    vol_trigger_upper_05: float = 5185.0
    vol_trigger_lower_05: float = 5115.0
    vol_trigger_upper_10: float = 5205.0
    vol_trigger_lower_10: float = 5095.0
    vol_trigger_upper_15: float = 5225.0
    vol_trigger_lower_15: float = 5075.0
    vanna_call_node: float = 5170.0
    vanna_put_node: float = 5130.0
    charm_call_node: float = 10.0
    charm_put_node: float = 2.0
    volume_imbalance_call_node: float = 5180.0
    volume_imbalance_put_node: float = 5120.0
    liquidity_vacuum_lower: float = 5135.0
    liquidity_vacuum_upper: float = 5165.0
    skew_pivot_put_25d: float = 5100.0
    skew_pivot_call_25d: float = 5200.0
    gamma_magnet: float = 5155.0
    pin_strike: float = 5150.0
    pin_odds: float = 0.25
    wall_separation: float = 200.0
    regime_label: str = "PINNED"
    directional_bias: str = "BULLISH"
    call_gamma_total: float = 600000000.0
    put_gamma_total: float = -400000000.0
    net_vanna_exposure: float = 2.5
    net_speed_exposure: float = 15.0
    total_gex_delta_adj: float = 800000000.0
    expected_moves: list = field(default_factory=list)
    call_gex_0dte: float = 600000000.0
    put_gex_0dte: float = 100000000.0
    atm_iv: float = 0.12
    iv_change: float = -0.015
    volatility_skew_premium: float = 0.02

# Import the formatting functions
# We need to make sure the imports in formatting.py don't break
sys.path.append(os.path.abspath(r"c:\Users\vinay\tvDownloadOHLC\scripts"))
from streaming.options import formatting

def verify():
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    levels = MockLevels()
    
    print("\n--- Testing build_pine_note ---")
    note = formatting.build_pine_note(levels)
    print(f"Note: {note}")
    
    print("\n--- Testing copy_ready_line ---")
    copy_line = formatting.copy_ready_line("SPX_TEST", levels)
    print(f"Copy Line: {copy_line[:200]}...") # Truncated for readability
    
    print("\n--- Testing build_coaches_note (Pivot Priority) ---")
    coaches_note = formatting.build_coaches_note("SPX_TEST", levels)
    for part in coaches_note:
        print(f"\n{part}")

if __name__ == "__main__":
    verify()
