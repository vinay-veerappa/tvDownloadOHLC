"""
Performance Benchmark Suite for tvDownloadOHLC API

This module provides comprehensive benchmarks for all major backend services
to identify performance bottlenecks and measure optimization impact.

Run with: python -m api.benchmarks.run_benchmarks
Or:       cd api && python -m benchmarks.run_benchmarks
"""
import time
import statistics
import sys
from pathlib import Path
from typing import Callable, List, Optional, Dict, Any
import json
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd


class BenchmarkResult:
    """Holds benchmark results for a single test."""
    def __init__(self, name: str, times: List[float], rows: int = 0):
        self.name = name
        self.times = times  # in milliseconds
        self.rows = rows
        
    @property
    def avg(self) -> float:
        return statistics.mean(self.times)
    
    @property
    def std(self) -> float:
        return statistics.stdev(self.times) if len(self.times) > 1 else 0
    
    @property
    def min(self) -> float:
        return min(self.times)
    
    @property
    def max(self) -> float:
        return max(self.times)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "avg_ms": round(self.avg, 2),
            "std_ms": round(self.std, 2),
            "min_ms": round(self.min, 2),
            "max_ms": round(self.max, 2),
            "iterations": len(self.times),
            "rows": self.rows
        }
    
    def __str__(self) -> str:
        return (f"{self.name}:\n"
                f"  Average: {self.avg:.2f}ms (±{self.std:.2f}ms)\n"
                f"  Min: {self.min:.2f}ms, Max: {self.max:.2f}ms\n"
                f"  Rows: {self.rows:,}")


def benchmark(name: str, fn: Callable, iterations: int = 10, 
              warmup: int = 2, rows: int = 0) -> BenchmarkResult:
    """
    Run a function multiple times and collect timing statistics.
    
    Args:
        name: Descriptive name for the benchmark
        fn: Function to benchmark (should take no arguments)
        iterations: Number of timed iterations
        warmup: Number of warmup iterations (not timed)
        rows: Number of data rows being processed (for context)
    
    Returns:
        BenchmarkResult with timing statistics
    """
    # Warmup runs
    for _ in range(warmup):
        fn()
    
    # Timed runs
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
        times.append(elapsed)
    
    result = BenchmarkResult(name, times, rows)
    print(result)
    print()
    return result


def run_data_loader_benchmarks() -> List[BenchmarkResult]:
    """Benchmark data loading operations."""
    print("\n" + "=" * 60)
    print("DATA LOADER BENCHMARKS")
    print("=" * 60 + "\n")
    
    from api.services.data_loader import load_parquet, get_available_data
    
    results = []
    
    # Cold load (first time)
    start = time.perf_counter()
    df = load_parquet("ES1", "1m")
    cold_time = (time.perf_counter() - start) * 1000
    print(f"Cold Load (first call): {cold_time:.2f}ms ({len(df):,} rows)")
    
    # Warm load (subsequent calls - no caching currently)
    result = benchmark(
        "Data Load (ES1 1m)",
        lambda: load_parquet("ES1", "1m"),
        iterations=5,
        warmup=0,
        rows=len(df) if df is not None else 0
    )
    results.append(result)
    
    # Load different timeframes
    for tf in ["5m", "1h", "1D"]:
        try:
            df_tf = load_parquet("ES1", tf)
            if df_tf is not None:
                result = benchmark(
                    f"Data Load (ES1 {tf})",
                    lambda tf=tf: load_parquet("ES1", tf),
                    iterations=5,
                    rows=len(df_tf)
                )
                results.append(result)
        except Exception as e:
            print(f"Skipping ES1 {tf}: {e}")
    
    # get_available_data
    result = benchmark(
        "get_available_data()",
        get_available_data,
        iterations=10
    )
    results.append(result)
    
    return results


def run_session_benchmarks() -> List[BenchmarkResult]:
    """Benchmark session calculation operations."""
    print("\n" + "=" * 60)
    print("SESSION SERVICE BENCHMARKS")
    print("=" * 60 + "\n")
    
    from api.services.data_loader import load_parquet
    from api.services.session_service import SessionService
    
    results = []
    
    # Load and prepare data
    df = load_parquet("ES1", "1m")
    if df is None:
        print("ERROR: Could not load ES1 1m data")
        return results
    
    df_indexed = df.copy()
    df_indexed['datetime'] = pd.to_datetime(df_indexed['time'], unit='s', utc=True)
    df_indexed = df_indexed.set_index('datetime')
    df_indexed.index = df_indexed.index.tz_convert('US/Eastern')
    
    print(f"Data prepared: {len(df_indexed):,} rows")
    print(f"Date range: {df_indexed.index.min()} to {df_indexed.index.max()}")
    print()
    
    # Full dataset benchmarks
    result = benchmark(
        "calculate_sessions (full dataset)",
        lambda: SessionService.calculate_sessions(df_indexed, "ES1"),
        iterations=5,
        warmup=1,
        rows=len(df_indexed)
    )
    results.append(result)
    
    result = benchmark(
        "calculate_hourly (full dataset)",
        lambda: SessionService.calculate_hourly(df_indexed),
        iterations=5,
        warmup=1,
        rows=len(df_indexed)
    )
    results.append(result)
    
    # Subset benchmarks (simulate typical visible range)
    # Last 30 days
    recent = df_indexed.last('30D')
    print(f"Recent subset: {len(recent):,} rows (last 30 days)")
    
    result = benchmark(
        "calculate_sessions (30 days)",
        lambda: SessionService.calculate_sessions(recent, "ES1"),
        iterations=5,
        rows=len(recent)
    )
    results.append(result)
    
    result = benchmark(
        "calculate_hourly (30 days)",
        lambda: SessionService.calculate_hourly(recent),
        iterations=5,
        rows=len(recent)
    )
    results.append(result)
    
    # Opening range only
    result = benchmark(
        "calculate_opening_range",
        lambda: SessionService.calculate_opening_range(df_indexed, "09:30", 1),
        iterations=5,
        rows=len(df_indexed)
    )
    results.append(result)
    
    return results


def run_vwap_benchmarks() -> List[BenchmarkResult]:
    """Benchmark VWAP calculation operations."""
    print("\n" + "=" * 60)
    print("VWAP BENCHMARKS")
    print("=" * 60 + "\n")
    
    from api.services.data_loader import load_parquet
    from api.services.vwap import calculate_vwap_with_settings
    
    results = []
    
    # Load data
    df = load_parquet("ES1", "1m")
    if df is None:
        print("ERROR: Could not load ES1 1m data")
        return results
    
    print(f"Data loaded: {len(df):,} rows")
    print()
    
    # Session anchor (most common)
    result = benchmark(
        "VWAP (session anchor, no bands)",
        lambda: calculate_vwap_with_settings(df, anchor="session"),
        iterations=5,
        rows=len(df)
    )
    results.append(result)
    
    # With bands
    result = benchmark(
        "VWAP (session anchor, 2 bands)",
        lambda: calculate_vwap_with_settings(df, anchor="session", bands=[1.0, 2.0]),
        iterations=5,
        rows=len(df)
    )
    results.append(result)
    
    result = benchmark(
        "VWAP (session anchor, 3 bands)",
        lambda: calculate_vwap_with_settings(df, anchor="session", bands=[1.0, 2.0, 3.0]),
        iterations=5,
        rows=len(df)
    )
    results.append(result)
    
    # Week anchor
    result = benchmark(
        "VWAP (week anchor)",
        lambda: calculate_vwap_with_settings(df, anchor="week"),
        iterations=5,
        rows=len(df)
    )
    results.append(result)
    
    # Subset (last 5 days - typical chart view)
    recent = df.tail(5 * 390)  # ~5 days of RTH bars
    print(f"Recent subset: {len(recent):,} rows")
    
    result = benchmark(
        "VWAP (5 days subset, 2 bands)",
        lambda: calculate_vwap_with_settings(recent, anchor="session", bands=[1.0, 2.0]),
        iterations=10,
        rows=len(recent)
    )
    results.append(result)
    
    return results


def run_indicator_benchmarks() -> List[BenchmarkResult]:
    """Benchmark indicator calculation operations."""
    print("\n" + "=" * 60)
    print("INDICATOR BENCHMARKS")
    print("=" * 60 + "\n")
    
    from api.services.data_loader import load_parquet
    from api.services.indicators import calculate_indicator, calculate_indicators
    
    results = []
    
    # Load data
    df = load_parquet("ES1", "1m")
    if df is None:
        print("ERROR: Could not load ES1 1m data")
        return results
    
    print(f"Data loaded: {len(df):,} rows")
    print()
    
    # Individual indicators
    for indicator in ["sma_20", "ema_9", "rsi_14", "macd"]:
        result = benchmark(
            f"calculate_indicator ({indicator})",
            lambda ind=indicator: calculate_indicator(df, ind),
            iterations=5,
            rows=len(df)
        )
        results.append(result)
    
    # Multiple indicators at once
    result = benchmark(
        "calculate_indicators (sma_20, ema_9, rsi_14)",
        lambda: calculate_indicators(df, ["sma_20", "ema_9", "rsi_14"]),
        iterations=5,
        rows=len(df)
    )
    results.append(result)
    
    return results


def run_resampling_benchmarks() -> List[BenchmarkResult]:
    """Benchmark resampling operations."""
    print("\n" + "=" * 60)
    print("RESAMPLING BENCHMARKS")
    print("=" * 60 + "\n")
    
    from api.services.data_loader import load_parquet
    from api.services.resampling import resample_ohlc, can_resample
    
    results = []
    
    # Load 1m data
    df = load_parquet("ES1", "1m")
    if df is None:
        print("ERROR: Could not load ES1 1m data")
        return results
    
    print(f"Data loaded: {len(df):,} rows (1m)")
    print()
    
    # Resample to various timeframes
    for to_tf in ["5m", "15m", "30m", "1h", "4h"]:
        if can_resample("1m", to_tf):
            result = benchmark(
                f"resample_ohlc (1m -> {to_tf})",
                lambda tf=to_tf: resample_ohlc(df, "1m", tf),
                iterations=5,
                rows=len(df)
            )
            results.append(result)
    
    return results


def save_results(all_results: List[BenchmarkResult], output_file: Optional[str] = None):
    """Save benchmark results to JSON file."""
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"benchmark_results_{timestamp}.json"
    
    output_path = Path(__file__).parent / output_file
    
    data = {
        "timestamp": datetime.now().isoformat(),
        "results": [r.to_dict() for r in all_results]
    }
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\nResults saved to: {output_path}")


def main():
    """Run all benchmarks and report results."""
    print("=" * 60)
    print("tvDownloadOHLC Performance Benchmark Suite")
    print("=" * 60)
    print(f"Started: {datetime.now().isoformat()}")
    
    all_results: List[BenchmarkResult] = []
    
    try:
        # Run all benchmark suites
        all_results.extend(run_data_loader_benchmarks())
        all_results.extend(run_session_benchmarks())
        all_results.extend(run_vwap_benchmarks())
        all_results.extend(run_indicator_benchmarks())
        all_results.extend(run_resampling_benchmarks())
        
    except Exception as e:
        print(f"\nERROR during benchmarks: {e}")
        import traceback
        traceback.print_exc()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    # Sort by average time (slowest first)
    sorted_results = sorted(all_results, key=lambda x: x.avg, reverse=True)
    
    print("\nTop 10 Slowest Operations:")
    print("-" * 60)
    for i, r in enumerate(sorted_results[:10], 1):
        print(f"{i:2}. {r.name}: {r.avg:.2f}ms avg")
    
    # Save results
    save_results(all_results)
    
    print("\n" + "=" * 60)
    print(f"Completed: {datetime.now().isoformat()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
