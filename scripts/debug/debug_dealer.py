

import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.streaming.options.gex_calculator import DealerLevels
import inspect

print("Checking DealerLevels definition...")
sig = inspect.signature(DealerLevels)
print(f"Signature: {sig}")

try:
    # Try creating with minimal fields
    d = DealerLevels(
        ticker="TEST",
        spot=100.0,
        total_gex=1000.0,
        gex_regime="POSITIVE",
        zero_gamma=None,
        gamma_flip_lower=None,
        gamma_flip_upper=None,
        call_wall=None,
        put_wall=None,
        secondary_call_wall=None,
        secondary_put_wall=None,
        local_call_node=None,
        local_put_node=None,
        call_wall_0dte=None,
        put_wall_0dte=None,
        hedge_wall=None,
        max_pain=None,
        em_upper=110.0,
        em_lower=90.0,
        em_value=10.0,
        atm_straddle=10.0,
        vol_trigger_upper_05=None,
        vol_trigger_lower_05=None,
        vol_trigger_upper_10=None,
        vol_trigger_lower_10=None,
        vol_trigger_upper_15=None,
        vol_trigger_lower_15=None,
        gamma_cliff_up=None,
        gamma_cliff_down=None,
        vanna_call_node=None,
        vanna_put_node=None,
        charm_call_node=None,
        charm_put_node=None,
        volume_imbalance_call_node=None,
        volume_imbalance_put_node=None,
        dex_call_node=None,
        dex_put_node=None,
        liquidity_vacuum_lower=None,
        liquidity_vacuum_upper=None,
        skew_pivot_put_25d=None,
        skew_pivot_call_25d=None,
        # Now the Tier 2 fields (required)
        gamma_magnet=None,
        pin_strike=None,
        pin_odds=0.5,
        wall_separation=None,
        regime_label="TEST",
        directional_bias="NEUTRAL",
        call_gamma_total=0,
        put_gamma_total=0,
        net_vanna_exposure=0,
        wall_scope="FRONT_WEEK_WEIGHTED",
        wall_dte_min=0,
        wall_dte_max=14,
        concentration_score=0.0,
        # Enhanced analytics (required)
        call_volume_centroid=None,
        put_volume_centroid=None,
        total_gex_delta_adj=0,
        net_speed_exposure=0,
        max_gex_strike=None
    )
    print("SUCCESS: Instantiated DealerLevels without skew fields (defaults worked).")
except TypeError as e:
    print(f"FAILURE: {e}")
