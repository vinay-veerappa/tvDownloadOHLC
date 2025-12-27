"""
Fibonacci Calculator for Pullback Entry Analysis

Calculates Fibonacci retracement and extension levels for identifying
optimal pullback entry zones.
"""

from typing import Dict, List, Tuple
import pandas as pd


class FibonacciCalculator:
    """Calculate Fibonacci retracement and extension levels"""
    
    # Standard Fibonacci ratios (FIXED: Removed 23.6% - too shallow for pullbacks)
    RETRACEMENT_LEVELS = {
        '38.2%': 0.382,
        '50.0%': 0.500,
        '61.8%': 0.618,
        '78.6%': 0.786
    }
    
    EXTENSION_LEVELS = {
        '127.2%': 1.272,
        '161.8%': 1.618,
        '200.0%': 2.000,
        '261.8%': 2.618
    }
    
    @staticmethod
    def calculate_retracements(
        swing_low: float,
        swing_high: float,
        direction: str = 'LONG'
    ) -> Dict[str, float]:
        """
        Calculate Fibonacci retracement levels
        
        Args:
            swing_low: Low point of the swing
            swing_high: High point of the swing
            direction: 'LONG' or 'SHORT'
            
        Returns:
            Dictionary of retracement levels with prices
        """
        range_size = swing_high - swing_low
        
        if direction == 'LONG':
            # For longs, retracements are below swing high
            levels = {
                name: swing_high - (range_size * ratio)
                for name, ratio in FibonacciCalculator.RETRACEMENT_LEVELS.items()
            }
        else:
            # For shorts, retracements are above swing low
            levels = {
                name: swing_low + (range_size * ratio)
                for name, ratio in FibonacciCalculator.RETRACEMENT_LEVELS.items()
            }
        
        return levels
    
    @staticmethod
    def calculate_extensions(
        swing_low: float,
        swing_high: float,
        direction: str = 'LONG'
    ) -> Dict[str, float]:
        """
        Calculate Fibonacci extension levels for take profit targets
        
        Args:
            swing_low: Low point of the swing
            swing_high: High point of the swing
            direction: 'LONG' or 'SHORT'
            
        Returns:
            Dictionary of extension levels with prices
        """
        range_size = swing_high - swing_low
        
        if direction == 'LONG':
            # For longs, extensions are above swing high
            levels = {
                name: swing_high + (range_size * (ratio - 1.0))
                for name, ratio in FibonacciCalculator.EXTENSION_LEVELS.items()
            }
        else:
            # For shorts, extensions are below swing low
            levels = {
                name: swing_low - (range_size * (ratio - 1.0))
                for name, ratio in FibonacciCalculator.EXTENSION_LEVELS.items()
            }
        
        return levels
    
    @staticmethod
    def is_price_at_fib_level(
        price: float,
        fib_levels: Dict[str, float],
        tolerance_pct: float = 0.1
    ) -> Tuple[bool, str]:
        """
        Check if price is at a Fibonacci level
        
        Args:
            price: Current price to check
            fib_levels: Dictionary of Fibonacci levels
            tolerance_pct: Tolerance as % (0.1 = 0.1%)
            
        Returns:
            (is_at_level, level_name)
        """
        for name, level_price in fib_levels.items():
            tolerance = level_price * (tolerance_pct / 100)
            if abs(price - level_price) <= tolerance:
                return True, name
        
        return False, ''
    
    @staticmethod
    def get_nearest_fib_level(
        price: float,
        fib_levels: Dict[str, float]
    ) -> Tuple[str, float, float]:
        """
        Get nearest Fibonacci level to current price
        
        Args:
            price: Current price
            fib_levels: Dictionary of Fibonacci levels
            
        Returns:
            (level_name, level_price, distance_pct)
        """
        nearest_name = ''
        nearest_price = 0.0
        min_distance = float('inf')
        
        for name, level_price in fib_levels.items():
            distance = abs(price - level_price)
            if distance < min_distance:
                min_distance = distance
                nearest_name = name
                nearest_price = level_price
        
        distance_pct = (min_distance / price) * 100
        
        return nearest_name, nearest_price, distance_pct
    
    @staticmethod
    def calculate_internal_ib_fibonacci(
        ib_data: Dict
    ) -> Dict:
        """
        Calculate Fibonacci levels strictly within the IB High/Low range
        
        Args:
            ib_data: IB data dictionary with 'ib_high' and 'ib_low'
            
        Returns:
            Dictionary with retracement levels
        """
        swing_high = ib_data['ib_high']
        swing_low = ib_data['ib_low']
        
        # Calculate retracements for both directions
        # For Internal Fibs, we measure from Boundary 0 to Boundary 1
        # Direction depends on the bias (who came first)
        
        long_retracements = FibonacciCalculator.calculate_retracements(
            swing_low, swing_high, 'LONG'
        )
        short_retracements = FibonacciCalculator.calculate_retracements(
            swing_low, swing_high, 'SHORT'
        )
        
        return {
            'swing_low': swing_low,
            'swing_high': swing_high,
            'range': swing_high - swing_low,
            'retracements': {
                'LONG': long_retracements,
                'SHORT': short_retracements
            }
        }
    
    @staticmethod
    def calculate_ib_fibonacci(
        ib_data: Dict,
        breakout_extreme: float,
        direction: str
    ) -> Dict:
        """
        Calculate Fibonacci levels for IB break pullback
        
        Args:
            ib_data: IB data dictionary
            breakout_extreme: Highest/lowest point after IB break
            direction: 'LONG' or 'SHORT'
            
        Returns:
            Dictionary with retracement and extension levels
        """
        if direction == 'LONG':
            swing_low = ib_data['ib_high']  # Entry point (IB high)
            swing_high = breakout_extreme    # First push high
        else:
            swing_low = breakout_extreme     # First push low
            swing_high = ib_data['ib_low']   # Entry point (IB low)
        
        retracements = FibonacciCalculator.calculate_retracements(
            swing_low, swing_high, direction
        )
        
        extensions = FibonacciCalculator.calculate_extensions(
            swing_low, swing_high, direction
        )
        
        return {
            'swing_low': swing_low,
            'swing_high': swing_high,
            'range': swing_high - swing_low,
            'retracements': retracements,
            'extensions': extensions,
            'direction': direction
        }
    
    @staticmethod
    def get_entry_zone(
        fib_data: Dict,
        entry_type: str = 'standard'
    ) -> Tuple[float, float]:
        """
        Get entry zone based on Fibonacci levels
        
        Args:
            fib_data: Fibonacci data from calculate_ib_fibonacci
            entry_type: 'aggressive' (38.2%), 'standard' (50%), 'conservative' (61.8%)
            
        Returns:
            (zone_low, zone_high) for entry
        """
        retracements = fib_data['retracements']
        
        if entry_type == 'aggressive':
            # 38.2% level with small buffer
            center = retracements['38.2%']
            buffer = fib_data['range'] * 0.05  # 5% buffer
        elif entry_type == 'conservative':
            # 61.8% level with small buffer
            center = retracements['61.8%']
            buffer = fib_data['range'] * 0.05
        else:  # standard
            # 50% level with buffer
            center = retracements['50.0%']
            buffer = fib_data['range'] * 0.05
        
        if fib_data['direction'] == 'LONG':
            return (center - buffer, center + buffer)
        else:
            return (center - buffer, center + buffer)
