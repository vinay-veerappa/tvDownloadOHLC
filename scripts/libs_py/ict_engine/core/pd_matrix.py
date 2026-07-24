"""PD Array Priority Matrix (canonical ICT array ranking).

Ranks active Premium/Discount arrays by priority:
- Premium (Sell): Bearish OB -> Breaker Block -> FVG -> Mitigation Block -> Old High
- Discount (Buy): Bullish OB -> Breaker Block -> FVG -> Mitigation Block -> Old Low
"""

import numpy as np
import pandas as pd
from .validation import validate_ohlc


@validate_ohlc(input_type="ohlc")
def rank_pd_arrays(
    ohlc: pd.DataFrame,
    ob_df: pd.DataFrame,
    breaker_df: pd.DataFrame,
    fvg_df: pd.DataFrame,
    mitigation_df: pd.DataFrame,
    swings: pd.DataFrame,
    dealing_range: pd.DataFrame,
) -> pd.DataFrame:
    """
    Ranks active PD Arrays according to ICT Priority Matrix.

    Returns
    -------
    pd.DataFrame with:
        primary_premium_array  - Name of highest priority active premium array
        primary_discount_array - Name of highest priority active discount array
        highest_priority_rank  - Rank integer (1=OB, 2=Breaker, 3=FVG, 4=Mitigation, 5=Old Peak)
    """
    is_premium = dealing_range["is_premium"].values
    is_discount = dealing_range["is_discount"].values
    n = len(ohlc)

    has_bear_ob = (ob_df["ob"] == -1).values
    has_bear_breaker = (breaker_df["breaker"] == -1).values
    has_bear_fvg = (fvg_df["fvg_type"] == -1).values
    has_bear_mit = (mitigation_df["mitigation_block"] == -1).values
    has_old_high = (swings["shl"] == 1).values

    has_bull_ob = (ob_df["ob"] == 1).values
    has_bull_breaker = (breaker_df["breaker"] == 1).values
    has_bull_fvg = (fvg_df["fvg_type"] == 1).values
    has_bull_mit = (mitigation_df["mitigation_block"] == 1).values
    has_old_low = (swings["shl"] == -1).values

    prem_conds = [
        is_premium & has_bear_ob,
        is_premium & has_bear_breaker,
        is_premium & has_bear_fvg,
        is_premium & has_bear_mit,
        is_premium & has_old_high,
    ]
    prem_names = ["BEARISH_OB", "BEARISH_BREAKER", "BEARISH_FVG", "BEARISH_MITIGATION", "OLD_HIGH"]
    prem_ranks = [1, 2, 3, 4, 5]

    disc_conds = [
        is_discount & has_bull_ob,
        is_discount & has_bull_breaker,
        is_discount & has_bull_fvg,
        is_discount & has_bull_mit,
        is_discount & has_old_low,
    ]
    disc_names = ["BULLISH_OB", "BULLISH_BREAKER", "BULLISH_FVG", "BULLISH_MITIGATION", "OLD_LOW"]
    disc_ranks = [1, 2, 3, 4, 5]

    prem_name = np.select(prem_conds, prem_names, default="NONE")
    prem_rank = np.select(prem_conds, prem_ranks, default=99)

    disc_name = np.select(disc_conds, disc_names, default="NONE")
    disc_rank = np.select(disc_conds, disc_ranks, default=99)

    # If both are active, prioritize the one with a lower (better) rank
    rank = np.minimum(prem_rank, disc_rank)

    return pd.DataFrame({
        "primary_premium_array": prem_name,
        "primary_discount_array": disc_name,
        "highest_priority_rank": rank,
    }, index=ohlc.index)
