"""
OptionSymbolBuilder — futures option symbol construction for TOS RTD.

Ported from: 2187Nick/tos-streamlit-dashboard (futures branch)
Source: src/utils/option_symbol_builder.py

Builds TOS RTD-compatible option symbols for futures:
  /ES, /NQ, /ZN, /CL, /GC, /SI, /ZC, /ZS, /ZW, /RTY, /YM, /ZB

Also provides parse_rtd_option_symbol() to reverse-parse RTD symbols
back into structured OptionContract dataclasses.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class OptionContract:
    """Parsed futures option contract from an RTD symbol."""

    rtd_symbol: str           # Full RTD symbol, e.g. "./NQH25C21000:XCME"
    product_code: str          # e.g. "NQH25"
    option_type: str           # "C" or "P"
    strike: float              # e.g. 21000.0
    exchange: str              # e.g. "XCME"
    base_symbol: str           # e.g. "/NQ" (inferred from product code)
    expiry: Optional[date] = None  # Expiration date (set by build_chain_snapshot)


class OptionSymbolBuilder:
    """Builds TOS RTD option symbols for futures and equities."""

    # Futures → exchange mapping
    FUTURES_EXCHANGES = {
        "/ZN": "XCBT",  # 10-Year T-Note
        "/ZB": "XCBT",  # 30-Year T-Bond
        "/ES": "XCME",  # E-mini S&P 500
        "/NQ": "XCME",  # E-mini NASDAQ
        "/RTY": "XCME", # E-mini Russell 2000
        "/YM": "XCBT",  # E-mini Dow
        "/CL": "XNYM",  # Crude Oil
        "/GC": "XCEC",  # Gold
        "/SI": "XCEC",  # Silver
        "/ZC": "XCBT",  # Corn
        "/ZS": "XCBT",  # Soybeans
        "/ZW": "XCBT",  # Wheat
    }

    # Futures month codes
    FUTURES_MONTHS = {
        "F": "01",  # January
        "G": "02",  # February
        "H": "03",  # March
        "J": "04",  # April
        "K": "05",  # May
        "M": "06",  # June
        "N": "07",  # July
        "Q": "08",  # August
        "U": "09",  # September
        "V": "10",  # October
        "X": "11",  # November
        "Z": "12",  # December
    }

    MONTH_TO_CODE = {v: k for k, v in FUTURES_MONTHS.items()}

    # Weekday codes for /ES options
    WEEKDAY_CODES = {
        0: "A",  # Monday
        1: "B",  # Tuesday
        2: "C",  # Wednesday
        3: "D",  # Thursday
        4: "W",  # Friday
    }

    # ------------------------------------------------------------------
    # Date helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _round_to_nearest_strike(price: float, spacing: float) -> float:
        """Round price to nearest valid strike price."""
        return round(price / spacing) * spacing

    @staticmethod
    def _is_third_friday(d: date) -> bool:
        """Check if date is the third Friday of its month."""
        first = date(d.year, d.month, 1)
        friday = first + timedelta(days=((4 - first.weekday()) % 7))
        third_friday = friday + timedelta(days=14)
        return d == third_friday

    @staticmethod
    def _is_third_week(d: date) -> bool:
        """Check if date is in the third week of its month."""
        return 15 <= d.day <= 21

    @staticmethod
    def _get_weekday_code(d: date) -> str:
        """Get the weekday code for /ES options."""
        return OptionSymbolBuilder.WEEKDAY_CODES.get(d.weekday(), "W")

    @staticmethod
    def _get_week_indicator(d: date) -> str:
        """Get the week indicator number (1-5) based on business week."""
        first_day = date(d.year, d.month, 1)
        target_day = d

        if first_day.weekday() > 4:
            days_to_monday = 7 - first_day.weekday()
            first_day = first_day + timedelta(days=days_to_monday)

        days_difference = (target_day - first_day).days
        weeks = (days_difference + first_day.weekday()) // 7 + 1

        if target_day < first_day:
            return "1"

        return str(min(max(weeks, 1), 5))

    @staticmethod
    def _get_futures_month_code(expiry: date) -> str:
        """Convert a date to a futures month code."""
        for code, month in OptionSymbolBuilder.FUTURES_MONTHS.items():
            if int(month) == expiry.month:
                return code
        return ""

    @staticmethod
    def _is_end_of_month(d: date) -> bool:
        """Check if date is the last weekday of the month."""
        if d.month == 12:
            last_day = date(d.year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(d.year, d.month + 1, 1) - timedelta(days=1)
        while last_day.weekday() > 4:
            last_day -= timedelta(days=1)
        return d == last_day

    @staticmethod
    def _is_quarterly_expiration(d: date) -> bool:
        """Check if date is a quarterly expiration (3rd Friday of Mar/Jun/Sep/Dec)."""
        quarterly_months = {3, 6, 9, 12}
        return d.month in quarterly_months and OptionSymbolBuilder._is_third_friday(d)

    # ------------------------------------------------------------------
    # Product code builders
    # ------------------------------------------------------------------

    @staticmethod
    def _get_zn_product_code(expiry: date) -> list[str]:
        """
        Get product code(s) for /ZN options.

        Quarterly: OZN[month_code][year]
        Weekly Mon: VY[week][month_code][year]
        Weekly Wed: WY[week][month_code][year]
        Weekly Fri: ZN[week][month_code][year]
        """
        month_code = OptionSymbolBuilder.MONTH_TO_CODE.get(f"{expiry.month:02d}")
        year = str(expiry.year)[-2:]

        week_indicator = OptionSymbolBuilder._get_week_indicator(expiry)

        if OptionSymbolBuilder._is_quarterly_expiration(expiry):
            log.debug("Quarterly expiration for /ZN: %s", expiry)
            return [f"OZN{month_code}{year}"]

        if expiry.weekday() == 0:  # Monday
            return [f"VY{week_indicator}{month_code}{year}"]
        elif expiry.weekday() == 2:  # Wednesday
            return [f"WY{week_indicator}{month_code}{year}"]
        elif expiry.weekday() == 4:  # Friday
            return [f"ZN{week_indicator}{month_code}{year}"]
        return []

    @staticmethod
    def _get_nq_product_code(expiry: date) -> list[str]:
        """
        Get product code(s) for /NQ options.

        Quarterly: NQ[month_code][year] (AM) + QN[week][month_code][year] (PM)
        Weekly Mon-Thu: Q[week][weekday_code][month_code][year]
        Weekly Fri: QN[week][month_code][year]
        EOM: QNE[month_code][year]
        """
        month_code = OptionSymbolBuilder.MONTH_TO_CODE.get(f"{expiry.month:02d}")
        year = str(expiry.year)[-2:]

        if OptionSymbolBuilder._is_end_of_month(expiry):
            return [f"QNE{month_code}{year}"]

        week_indicator = OptionSymbolBuilder._get_week_indicator(expiry)

        if OptionSymbolBuilder._is_quarterly_expiration(expiry):
            log.debug("Quarterly expiration for /NQ: %s", expiry)
            return [
                f"NQ{month_code}{year}",
                f"QN{week_indicator}{month_code}{year}",
            ]

        if expiry.weekday() == 4:  # Friday
            return [f"QN{week_indicator}{month_code}{year}"]
        else:
            weekday_code = OptionSymbolBuilder._get_weekday_code(expiry)
            return [f"Q{week_indicator}{weekday_code}{month_code}{year}"]

    @staticmethod
    def _get_es_product_code(expiry: date) -> list[str]:
        """
        Get product code(s) for /ES options.

        Quarterly: ES[month_code][year] (AM) + EW[month_code][year] (PM)
        Weekly Mon-Thu: E[week][weekday_code][month_code][year]
        Weekly Fri: E[weekday_code][week][month_code][year]
        EOM: EW[month_code][year]
        """
        month_code = OptionSymbolBuilder.MONTH_TO_CODE.get(f"{expiry.month:02d}")
        year = str(expiry.year)[-2:]

        if OptionSymbolBuilder._is_quarterly_expiration(expiry):
            log.debug("Quarterly expiration for /ES: %s", expiry)
            return [
                f"ES{month_code}{year}",
                f"EW{month_code}{year}",
            ]

        weekday_code = OptionSymbolBuilder._get_weekday_code(expiry)

        if OptionSymbolBuilder._is_end_of_month(expiry):
            return [f"EW{month_code}{year}"]

        week_indicator = OptionSymbolBuilder._get_week_indicator(expiry)

        if expiry.weekday() == 4:  # Friday
            return [f"E{weekday_code}{week_indicator}{month_code}{year}"]
        else:
            return [f"E{week_indicator}{weekday_code}{month_code}{year}"]

    # ------------------------------------------------------------------
    # Strike formatting
    # ------------------------------------------------------------------

    @staticmethod
    def _format_strike(
        strike: float, is_futures: bool = False, strike_spacing: Optional[float] = None
    ) -> str:
        """
        Format strike price string for options.

        Examples:
            109.25 -> "109.25" (quarter points)
            109.50 -> "109.5"  (half points)
            100.00 -> "100"    (whole numbers)
        """
        if strike_spacing == 0.25:
            if abs(strike % 0.25) < 0.001:
                if strike % 1 == 0:
                    return f"{int(strike)}"
                if abs((strike % 1) - 0.5) < 0.001:
                    return f"{strike:.1f}"
                return f"{strike:.2f}"

        if strike_spacing in (0.5, 2.5):
            if abs(strike % 1 - 0.5) < 0.001:
                return f"{strike:.1f}"

        return f"{int(round(strike))}"

    # ------------------------------------------------------------------
    # Main symbol builder
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_tiered_strikes(
        current_price: float,
        strike_tiers: list[tuple[float, float]],
    ) -> list[float]:
        """
        Generate strikes using tiered spacing (CME standard).

        Args:
            current_price: ATM price
            strike_tiers: list of (max_distance_from_atm, spacing) tuples.
                         e.g. [(200, 5.0), (500, 10.0), (1000, 25.0)]
                         Tiers are applied cumulatively from ATM outward.

        Returns:
            Sorted list of unique strike prices.
        """
        strikes: set[float] = set()
        atm = OptionSymbolBuilder._round_to_nearest_strike(current_price, strike_tiers[0][1])

        for max_dist, spacing in strike_tiers:
            # Generate strikes from ATM to max_dist at this spacing
            n = int(max_dist / spacing)
            for i in range(-n, n + 1):
                strike = atm + i * spacing
                # Only include if within this tier's range
                if abs(strike - atm) <= max_dist:
                    strikes.add(strike)

        return sorted(strikes)

    @staticmethod
    def build_symbols(
        base_symbol: str,
        expiry: date,
        current_price: float,
        strike_range: int,
        strike_spacing: float,
        strike_tiers: list[tuple[float, float]] | None = None,
    ) -> list[str]:
        """
        Build a list of option symbols for both calls and puts.

        Args:
            base_symbol: Underlying symbol (e.g. "/ES", "/NQ", "SPY")
            expiry: Contract expiration date
            current_price: Current price of the underlying
            strike_range: ± strike range to monitor (fallback if no tiers)
            strike_spacing: Spacing between strikes (fallback if no tiers)
            strike_tiers: Optional tiered spacing [(max_dist, spacing), ...].
                         If provided, overrides strike_range/strike_spacing.

        Returns:
            List of RTD option symbols (e.g. "./NQH25C21000:XCME")
        """
        if not current_price or current_price <= 0:
            log.warning("Invalid current price: %s", current_price)
            return []

        exchange = OptionSymbolBuilder.FUTURES_EXCHANGES.get(base_symbol, "XCBT")

        # Generate strikes — tiered if available, flat otherwise
        if strike_tiers:
            strikes = OptionSymbolBuilder._generate_tiered_strikes(current_price, strike_tiers)
            log.debug(
                "Tiered strikes for %s: %d strikes from %.0f to %.0f (tiers=%s)",
                base_symbol, len(strikes), strikes[0], strikes[-1], strike_tiers,
            )
        else:
            if not strike_range or strike_range <= 0:
                log.warning("Invalid strike range: %s", strike_range)
                return []
            if not strike_spacing or strike_spacing <= 0:
                log.warning("Invalid strike spacing: %s", strike_spacing)
                return []

            rounded_price = OptionSymbolBuilder._round_to_nearest_strike(current_price, strike_spacing)
            num_strikes = int(2 * strike_range / strike_spacing) + 1
            strikes = list(np.linspace(
                rounded_price - strike_range,
                rounded_price + strike_range,
                num_strikes,
            ))
            log.debug(
                "Flat strikes for %s: %d strikes from %.0f to %.0f (range=±%d, spacing=%.1f)",
                base_symbol, len(strikes), strikes[0], strikes[-1], strike_range, strike_spacing,
            )

        if len(strikes) == 0:
            log.warning("No strikes generated")
            return []

        symbols: list[str] = []

        # /ES futures options
        if base_symbol == "/ES":
            product_codes = OptionSymbolBuilder._get_es_product_code(expiry)
            for product_code in product_codes:
                for strike in strikes:
                    strike_str = OptionSymbolBuilder._format_strike(strike, is_futures=True)
                    symbols.append(f"./{product_code}C{strike_str}:{exchange}")
                    symbols.append(f"./{product_code}P{strike_str}:{exchange}")

        # /NQ futures options
        elif base_symbol == "/NQ":
            product_codes = OptionSymbolBuilder._get_nq_product_code(expiry)
            for product_code in product_codes:
                for strike in strikes:
                    strike_str = OptionSymbolBuilder._format_strike(strike, is_futures=True)
                    symbols.append(f"./{product_code}C{strike_str}:{exchange}")
                    symbols.append(f"./{product_code}P{strike_str}:{exchange}")

        # /ZN futures options
        elif base_symbol == "/ZN":
            product_codes = OptionSymbolBuilder._get_zn_product_code(expiry)
            for product_code in product_codes:
                for strike in strikes:
                    strike_str = OptionSymbolBuilder._format_strike(
                        strike, is_futures=True, strike_spacing=strike_spacing
                    )
                    symbols.append(f"./{product_code}C{strike_str}:{exchange}")
                    symbols.append(f"./{product_code}P{strike_str}:{exchange}")

        # Other futures options (CL, GC, SI, etc.)
        elif base_symbol.startswith("/"):
            month_code = OptionSymbolBuilder._get_futures_month_code(expiry)
            futures_base = f"{base_symbol[1:]}1{month_code}{str(expiry.year)[-2:]}"
            for strike in strikes:
                strike_str = OptionSymbolBuilder._format_strike(strike, is_futures=True)
                symbols.append(f"./{futures_base}C{strike_str}:{exchange}")
                symbols.append(f"./{futures_base}P{strike_str}:{exchange}")

        # Equity/index options
        else:
            if not OptionSymbolBuilder._is_third_friday(expiry):
                if base_symbol == "SPX":
                    base_symbol = "SPXW"
                elif base_symbol == "NDX":
                    base_symbol = "NDXP"
                elif base_symbol == "RUT":
                    base_symbol = "RUTW"

            date_str = expiry.strftime("%y%m%d")
            for strike in strikes:
                strike_str = OptionSymbolBuilder._format_strike(strike)
                symbols.append(f".{base_symbol}{date_str}C{strike_str}")
                symbols.append(f".{base_symbol}{date_str}P{strike_str}")

        if not symbols:
            log.warning("No symbols generated")
            return []

        log.debug("Generated %d total symbols. First few: %s", len(symbols), symbols[:4])
        return symbols


# ----------------------------------------------------------------------
# Reverse parser — RTD symbol → OptionContract
# ----------------------------------------------------------------------

# Map product code prefixes to base futures symbols
_PRODUCT_PREFIX_MAP = {
    "NQ": "/NQ",
    "QN": "/NQ",
    "QNE": "/NQ",
    "ES": "/ES",
    "EW": "/ES",
    "E": "/ES",
    "OZN": "/ZN",
    "ZN": "/ZN",
    "VY": "/ZN",
    "WY": "/ZN",
    "CL": "/CL",
    "GC": "/GC",
    "SI": "/SI",
    "RTY": "/RTY",
    "YM": "/YM",
    "ZC": "/ZC",
    "ZS": "/ZS",
    "ZW": "/ZW",
    "ZB": "/ZB",
}


def parse_rtd_option_symbol(rtd_symbol: str) -> Optional[OptionContract]:
    """
    Parse a TOS RTD option symbol into structured data.

    Args:
        rtd_symbol: RTD symbol like "./NQH25C21000:XCME" or "./CL1G25C7500:XNYM"

    Returns:
        OptionContract dataclass, or None if parsing fails.

    Examples:
        >>> parse_rtd_option_symbol("./NQH25C21000:XCME")
        OptionContract(rtd_symbol="./NQH25C21000:XCME", product_code="NQH25",
                        option_type="C", strike=21000.0, exchange="XCME",
                        base_symbol="/NQ")
    """
    # Pattern: ./PRODUCT_CODE[CP]STRIKE:EXCHANGE
    pattern = r"^\./(.+?)([CP])([\d.]+):(\w+)$"
    match = re.match(pattern, rtd_symbol)
    if not match:
        log.debug("Failed to parse RTD symbol: %s", rtd_symbol)
        return None

    product_code, option_type, strike_str, exchange = match.groups()

    # Parse strike — could be int or float string
    try:
        if "." in strike_str:
            strike = float(strike_str)
        else:
            strike = float(int(strike_str))
    except ValueError:
        log.debug("Failed to parse strike: %s", strike_str)
        return None

    # Infer base symbol from product code prefix
    base_symbol = "/UNKNOWN"
    for prefix_len in (3, 2, 1):
        prefix = product_code[:prefix_len].upper()
        if prefix in _PRODUCT_PREFIX_MAP:
            base_symbol = _PRODUCT_PREFIX_MAP[prefix]
            break

    return OptionContract(
        rtd_symbol=rtd_symbol,
        product_code=product_code,
        option_type=option_type,
        strike=strike,
        exchange=exchange,
        base_symbol=base_symbol,
    )