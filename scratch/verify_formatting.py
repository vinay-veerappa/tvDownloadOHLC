
import sys
import os

# Add the root directory to sys.path to import our libs
sys.path.append(r"c:\Users\vinay\tvDownloadOHLC")

from scripts.streaming.options.formatting import copy_ready_line

class MockLevels:
    def __init__(self):
        self.spot = 18000.0
        self.em_upper = 18100.0
        self.em_lower = 17900.0
        self.em_value = 100.0
        self.call_wall = 18200.0
        self.put_wall = 17800.0
        self.local_call_node = 18150.0
        self.local_put_node = 17850.0
        self.call_wall_0dte = 18100.0
        self.put_wall_0dte = 17900.0
        self.dex_call_node = 18050.0
        self.dex_put_node = 17950.0
        self.gamma_flip_upper = 18020.0
        self.gamma_flip_lower = 17980.0
        self.gamma_cliff_up = 18050.0
        self.gamma_cliff_down = 17950.0
        self.zero_gamma = 18000.0
        self.max_pain = 18000.0
        self.hedge_wall = 17700.0
        self.total_gex = 1000000.0
        self.gex_regime = "POSITIVE"
        self.secondary_call_wall = 18300.0
        self.secondary_put_wall = 17700.0
        self.vol_trigger_upper_05 = 18250.0
        self.vol_trigger_lower_05 = 17750.0
        self.vol_trigger_upper_10 = 18350.0
        self.vol_trigger_lower_10 = 17650.0
        self.vol_trigger_upper_15 = 18450.0
        self.vol_trigger_lower_15 = 17550.0
        self.vanna_call_node = 18100.0
        self.vanna_put_node = 17900.0
        self.charm_call_node = 18050.0
        self.charm_put_node = 17950.0
        self.volume_imbalance_call_node = 18100.0
        self.volume_imbalance_put_node = 17900.0
        self.liquidity_vacuum_lower = 17900.0
        self.liquidity_vacuum_upper = 18100.0
        self.skew_pivot_put_25d = 17800.0
        self.skew_pivot_call_25d = 18200.0
        self.gamma_magnet = 18000.0
        self.pin_strike = 18000.0
        self.pin_odds = 0.20
        self.wall_separation = 400.0
        self.regime_label = "PINNED"
        self.directional_bias = "NEUTRAL"
        self.call_gamma_total = 500000.0
        self.put_gamma_total = -500000.0
        self.net_vanna_exposure = 2.0
        self.net_speed_exposure = 15.0
        self.total_gex_delta_adj = 800000.0
        self.expected_moves = []
        self.call_gex_0dte = 300000.0
        self.put_gex_0dte = -100000.0
        self.atm_iv = 0.15
        self.iv_change = -0.01
        self.volatility_skew_premium = 0.02

levels = MockLevels()
line = copy_ready_line("NQ", levels)
print(line)
