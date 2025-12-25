"""
Measure API response sizes before and after gzip configuration
Run this while the dev server is running on localhost:3000
"""
import requests
import time
import gzip

def measure_response(url, accept_gzip=True):
    """Measure response size and time"""
    headers = {}
    if accept_gzip:
        headers['Accept-Encoding'] = 'gzip, deflate'
    
    start = time.perf_counter()
    response = requests.get(url, headers=headers)
    elapsed = (time.perf_counter() - start) * 1000
    
    # Check if response was gzipped
    content_encoding = response.headers.get('Content-Encoding', 'none')
    content_length = response.headers.get('Content-Length', len(response.content))
    actual_size = len(response.content)
    
    return {
        'status': response.status_code,
        'encoding': content_encoding,
        'content_length': int(content_length) if content_length else actual_size,
        'actual_size': actual_size,
        'time_ms': elapsed
    }

def main():
    # Test URLs - adjust these based on your data
    base_url = "http://localhost:3000"
    
    # Static JSON chunk (served from public folder)
    test_urls = [
        f"{base_url}/data/ES1_1m/chunk_0.json",
        f"{base_url}/data/ES1_1m/meta.json",
        f"{base_url}/data/NQ1_1m/chunk_0.json",
    ]
    
    print("=" * 80)
    print("API Response Size Measurement")
    print("=" * 80)
    print()
    
    for url in test_urls:
        print(f"URL: {url}")
        print("-" * 60)
        
        try:
            # Without gzip request
            result_no_gzip = measure_response(url, accept_gzip=False)
            print(f"  Without Accept-Encoding:")
            print(f"    Encoding: {result_no_gzip['encoding']}")
            print(f"    Size: {result_no_gzip['actual_size'] / 1024:.2f} KB")
            print(f"    Time: {result_no_gzip['time_ms']:.2f} ms")
            
            # With gzip request
            result_gzip = measure_response(url, accept_gzip=True)
            print(f"  With Accept-Encoding: gzip:")
            print(f"    Encoding: {result_gzip['encoding']}")
            print(f"    Size: {result_gzip['actual_size'] / 1024:.2f} KB")
            print(f"    Time: {result_gzip['time_ms']:.2f} ms")
            
            # Calculate savings if gzipped
            if result_gzip['encoding'] == 'gzip':
                savings = (1 - result_gzip['actual_size'] / result_no_gzip['actual_size']) * 100
                print(f"  GZIP enabled! Savings: {savings:.1f}%")
            else:
                print(f"  GZIP NOT ENABLED - server compression needed")
                
        except requests.exceptions.ConnectionError:
            print(f"  ERROR: Could not connect. Is the dev server running?")
        except Exception as e:
            print(f"  ERROR: {e}")
        
        print()
    
    print("=" * 80)

if __name__ == "__main__":
    main()
