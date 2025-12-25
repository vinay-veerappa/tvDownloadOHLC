"""
Experiment: Measure gzip compression effectiveness on JSON chart data
"""
import gzip
import json
from pathlib import Path
import time

def measure_compression():
    data_dir = Path("web/public/data")
    
    if not data_dir.exists():
        print(f"Data directory not found: {data_dir}")
        return
    
    results = []
    total_original = 0
    total_compressed = 0
    
    # Find all chunk files
    chunk_files = list(data_dir.rglob("chunk_*.json"))
    
    print(f"Found {len(chunk_files)} chunk files\n")
    print(f"{'Ticker':<20} {'Original':>12} {'Gzipped':>12} {'Ratio':>8} {'Savings':>10}")
    print("-" * 65)
    
    # Group by ticker for summary
    ticker_stats = {}
    
    for chunk_path in chunk_files:
        # Read original file
        original_size = chunk_path.stat().st_size
        
        # Compress with gzip
        with open(chunk_path, 'rb') as f:
            original_data = f.read()
        
        compressed_data = gzip.compress(original_data, compresslevel=6)
        compressed_size = len(compressed_data)
        
        # Aggregate by ticker folder
        ticker = chunk_path.parent.name
        if ticker not in ticker_stats:
            ticker_stats[ticker] = {'original': 0, 'compressed': 0, 'chunks': 0}
        
        ticker_stats[ticker]['original'] += original_size
        ticker_stats[ticker]['compressed'] += compressed_size
        ticker_stats[ticker]['chunks'] += 1
        
        total_original += original_size
        total_compressed += compressed_size
    
    # Print per-ticker summary (top 10 by size)
    sorted_tickers = sorted(ticker_stats.items(), key=lambda x: x[1]['original'], reverse=True)
    
    for ticker, stats in sorted_tickers[:15]:
        ratio = stats['compressed'] / stats['original'] if stats['original'] > 0 else 1
        savings = (1 - ratio) * 100
        print(f"{ticker:<20} {stats['original']/1024/1024:>10.2f}MB {stats['compressed']/1024/1024:>10.2f}MB {ratio:>7.2%} {savings:>9.1f}%")
    
    print("-" * 65)
    
    # Total summary
    total_ratio = total_compressed / total_original if total_original > 0 else 1
    total_savings = (1 - total_ratio) * 100
    
    print(f"\n{'TOTAL':<20} {total_original/1024/1024:>10.2f}MB {total_compressed/1024/1024:>10.2f}MB {total_ratio:>7.2%} {total_savings:>9.1f}%")
    print(f"\nPotential savings: {(total_original - total_compressed)/1024/1024:.2f} MB")
    
    # Also measure decompression time for a large file
    largest = max(chunk_files, key=lambda f: f.stat().st_size)
    with open(largest, 'rb') as f:
        data = f.read()
    
    compressed = gzip.compress(data, compresslevel=6)
    
    # Time decompression
    start = time.perf_counter()
    for _ in range(10):
        gzip.decompress(compressed)
    decompress_time = (time.perf_counter() - start) / 10 * 1000
    
    print(f"\nDecompression benchmark ({largest.name}, {len(data)/1024:.1f}KB):")
    print(f"  Average decompression time: {decompress_time:.2f}ms")

if __name__ == "__main__":
    measure_compression()
